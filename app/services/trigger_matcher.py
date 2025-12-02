"""
Alert Trigger Matcher Service

Matches incoming alerts to runbook triggers for auto-remediation.
Handles trigger conditions, execution mode selection, and runbook invocation.
"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from ..models import Alert, User
from ..models_remediation import (
    Runbook,
    RunbookTrigger,
    RunbookExecution,
    CircuitBreaker,
    BlackoutWindow,
    ExecutionRateLimit
)

logger = logging.getLogger(__name__)


@dataclass
class TriggerMatch:
    """Represents a matched trigger for an alert."""
    trigger: RunbookTrigger
    runbook: Runbook
    match_details: Dict[str, Any]
    execution_mode: str
    can_execute: bool
    block_reason: Optional[str] = None


@dataclass
class MatchResult:
    """Result of matching an alert to triggers."""
    alert_id: int
    matches: List[TriggerMatch]
    auto_execute: List[TriggerMatch]
    needs_approval: List[TriggerMatch]
    blocked: List[Tuple[TriggerMatch, str]]


class AlertTriggerMatcher:
    """
    Matches incoming alerts to configured runbook triggers.
    
    Handles:
    - Pattern matching (regex, exact, contains, severity-based)
    - Execution mode determination
    - Safety checks (blackout, circuit breaker, rate limiting)
    - Variable extraction from alerts
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize the matcher.
        
        Args:
            db: Database session.
        """
        self.db = db
    
    async def match_alert(self, alert: Alert) -> MatchResult:
        """
        Find all matching triggers for an alert.
        
        Args:
            alert: The alert to match.
        
        Returns:
            MatchResult with all matching triggers categorized.
        """
        matches: List[TriggerMatch] = []
        
        # Get all enabled triggers with their runbooks
        result = await self.db.execute(
            select(RunbookTrigger)
            .options(selectinload(RunbookTrigger.runbook))
            .where(
                and_(
                    RunbookTrigger.enabled == True,
                    RunbookTrigger.runbook.has(enabled=True)
                )
            )
        )
        triggers = result.scalars().all()
        
        for trigger in triggers:
            match_details = self._evaluate_conditions(trigger, alert)
            
            if match_details["matched"]:
                # Check if execution is allowed
                can_execute, block_reason = await self._check_execution_allowed(
                    trigger.runbook
                )
                
                match = TriggerMatch(
                    trigger=trigger,
                    runbook=trigger.runbook,
                    match_details=match_details,
                    execution_mode=trigger.execution_mode,
                    can_execute=can_execute,
                    block_reason=block_reason
                )
                matches.append(match)
        
        # Categorize matches
        auto_execute = [
            m for m in matches 
            if m.execution_mode == "auto" and m.can_execute
        ]
        
        needs_approval = [
            m for m in matches 
            if m.execution_mode == "semi_auto" and m.can_execute
        ]
        
        blocked = [
            (m, m.block_reason or "Unknown reason")
            for m in matches 
            if not m.can_execute
        ]
        
        return MatchResult(
            alert_id=alert.id,
            matches=matches,
            auto_execute=auto_execute,
            needs_approval=needs_approval,
            blocked=blocked
        )
    
    def _evaluate_conditions(
        self,
        trigger: RunbookTrigger,
        alert: Alert
    ) -> Dict[str, Any]:
        """
        Evaluate if trigger conditions match the alert.
        
        Args:
            trigger: The trigger to evaluate.
            alert: The alert to check against.
        
        Returns:
            Dict with matched status and extracted variables.
        """
        conditions = trigger.conditions
        match_type = trigger.match_type
        
        result = {
            "matched": False,
            "matched_conditions": [],
            "extracted_variables": {}
        }
        
        # Check severity condition
        if "severity" in conditions:
            severity_condition = conditions["severity"]
            
            if isinstance(severity_condition, list):
                if alert.severity not in severity_condition:
                    return result
            else:
                if alert.severity != severity_condition:
                    return result
            
            result["matched_conditions"].append(f"severity: {alert.severity}")
        
        # Check source condition
        if "source" in conditions:
            source_pattern = conditions["source"]
            
            if match_type == "regex":
                if not re.search(source_pattern, alert.source, re.IGNORECASE):
                    return result
            elif match_type == "contains":
                if source_pattern.lower() not in alert.source.lower():
                    return result
            else:  # exact
                if alert.source.lower() != source_pattern.lower():
                    return result
            
            result["matched_conditions"].append(f"source: {alert.source}")
        
        # Check message pattern
        if "message_pattern" in conditions:
            pattern = conditions["message_pattern"]
            
            try:
                if match_type == "regex":
                    match = re.search(pattern, alert.message, re.IGNORECASE)
                    if not match:
                        return result
                    
                    # Extract named groups as variables
                    if match.groupdict():
                        result["extracted_variables"].update(match.groupdict())
                elif match_type == "contains":
                    if pattern.lower() not in alert.message.lower():
                        return result
                else:  # exact
                    if alert.message != pattern:
                        return result
                
                result["matched_conditions"].append(f"message pattern matched")
            except re.error as e:
                logger.error(f"Invalid regex pattern in trigger {trigger.id}: {e}")
                return result
        
        # Check labels/tags condition
        if "labels" in conditions:
            required_labels = conditions["labels"]
            alert_labels = alert.labels or {}
            
            for key, value in required_labels.items():
                if key not in alert_labels:
                    return result
                if value is not None and alert_labels[key] != value:
                    return result
            
            result["matched_conditions"].append(f"labels: {required_labels}")
        
        # Check time-based conditions
        if "time_range" in conditions:
            time_range = conditions["time_range"]
            now = datetime.utcnow()
            
            if "start_hour" in time_range and "end_hour" in time_range:
                current_hour = now.hour
                start = time_range["start_hour"]
                end = time_range["end_hour"]
                
                if start <= end:
                    if not (start <= current_hour < end):
                        return result
                else:  # Spans midnight
                    if not (current_hour >= start or current_hour < end):
                        return result
                
                result["matched_conditions"].append(f"time range: {start}-{end}")
            
            if "days_of_week" in time_range:
                allowed_days = time_range["days_of_week"]
                current_day = now.weekday()  # 0=Monday
                
                if current_day not in allowed_days:
                    return result
                
                result["matched_conditions"].append(f"day of week: {current_day}")
        
        # If all conditions passed, it's a match
        if not conditions:
            # Empty conditions = match all
            result["matched"] = True
        elif result["matched_conditions"]:
            result["matched"] = True
        
        # Add alert info as variables
        result["extracted_variables"].update({
            "alert_id": str(alert.id),
            "alert_severity": alert.severity,
            "alert_source": alert.source,
            "alert_message": alert.message,
            "alert_timestamp": alert.timestamp.isoformat() if alert.timestamp else "",
        })
        
        # Add alert labels as variables with prefix
        if alert.labels:
            for key, value in alert.labels.items():
                result["extracted_variables"][f"alert_label_{key}"] = str(value)
        
        return result
    
    async def _check_execution_allowed(
        self,
        runbook: Runbook
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if runbook execution is currently allowed.
        
        Checks:
        - Circuit breaker status
        - Blackout windows
        - Rate limiting
        
        Args:
            runbook: The runbook to check.
        
        Returns:
            Tuple of (allowed, reason if blocked).
        """
        now = datetime.utcnow()
        
        # Check circuit breaker
        circuit_result = await self.db.execute(
            select(CircuitBreaker)
            .where(CircuitBreaker.runbook_id == runbook.id)
        )
        circuit = circuit_result.scalar_one_or_none()
        
        if circuit and circuit.state == "open":
            return False, f"Circuit breaker is open until {circuit.reset_at}"
        
        # Check blackout windows
        blackout_result = await self.db.execute(
            select(BlackoutWindow).where(
                and_(
                    BlackoutWindow.enabled == True,
                    BlackoutWindow.start_time <= now,
                    BlackoutWindow.end_time > now
                )
            )
        )
        blackouts = blackout_result.scalars().all()
        
        for blackout in blackouts:
            # Check if this runbook is affected
            affected = False
            
            if blackout.scope == "all":
                affected = True
            elif blackout.scope == "category" and blackout.affected_categories:
                if runbook.category in blackout.affected_categories:
                    affected = True
            elif blackout.scope == "runbook" and blackout.affected_runbook_ids:
                if runbook.id in blackout.affected_runbook_ids:
                    affected = True
            
            if affected:
                return False, f"Blackout window active: {blackout.name}"
        
        # Check rate limiting
        rate_limit_result = await self.db.execute(
            select(ExecutionRateLimit)
            .where(ExecutionRateLimit.runbook_id == runbook.id)
        )
        rate_limit = rate_limit_result.scalar_one_or_none()
        
        if rate_limit:
            window_start = now - timedelta(seconds=rate_limit.window_seconds)
            
            # Count recent executions
            exec_count_result = await self.db.execute(
                select(RunbookExecution).where(
                    and_(
                        RunbookExecution.runbook_id == runbook.id,
                        RunbookExecution.started_at >= window_start
                    )
                )
            )
            recent_executions = len(exec_count_result.scalars().all())
            
            if recent_executions >= rate_limit.max_executions:
                return False, f"Rate limit exceeded: {recent_executions}/{rate_limit.max_executions} in {rate_limit.window_seconds}s"
        
        return True, None
    
    async def process_alert_for_remediation(
        self,
        alert: Alert,
        executor_service: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Full processing of an alert for auto-remediation.
        
        Args:
            alert: The alert to process.
            executor_service: Optional RunbookExecutorService for auto execution.
        
        Returns:
            Dict with processing results.
        """
        result = {
            "alert_id": alert.id,
            "matches_found": 0,
            "auto_executed": [],
            "pending_approval": [],
            "blocked": [],
            "manual_only": []
        }
        
        try:
            match_result = await self.match_alert(alert)
            result["matches_found"] = len(match_result.matches)
            
            # Handle auto-execute matches
            for match in match_result.auto_execute:
                if executor_service:
                    try:
                        execution = await self._create_and_start_execution(
                            match,
                            alert,
                            executor_service
                        )
                        result["auto_executed"].append({
                            "runbook_id": match.runbook.id,
                            "runbook_name": match.runbook.name,
                            "execution_id": execution.id if execution else None,
                            "trigger_id": match.trigger.id
                        })
                    except Exception as e:
                        logger.error(f"Failed to auto-execute runbook {match.runbook.id}: {e}")
                        result["blocked"].append({
                            "runbook_id": match.runbook.id,
                            "runbook_name": match.runbook.name,
                            "reason": str(e)
                        })
                else:
                    result["auto_executed"].append({
                        "runbook_id": match.runbook.id,
                        "runbook_name": match.runbook.name,
                        "execution_id": None,
                        "trigger_id": match.trigger.id,
                        "note": "Executor service not provided"
                    })
            
            # Handle semi-auto matches (need approval)
            for match in match_result.needs_approval:
                approval = await self._create_pending_approval(match, alert)
                result["pending_approval"].append({
                    "runbook_id": match.runbook.id,
                    "runbook_name": match.runbook.name,
                    "execution_id": approval.id if approval else None,
                    "trigger_id": match.trigger.id,
                    "variables": match.match_details.get("extracted_variables", {})
                })
            
            # Report blocked matches
            for match, reason in match_result.blocked:
                result["blocked"].append({
                    "runbook_id": match.runbook.id,
                    "runbook_name": match.runbook.name,
                    "reason": reason
                })
            
            # Report manual-only matches
            manual_matches = [
                m for m in match_result.matches
                if m.execution_mode == "manual"
            ]
            for match in manual_matches:
                result["manual_only"].append({
                    "runbook_id": match.runbook.id,
                    "runbook_name": match.runbook.name,
                    "trigger_id": match.trigger.id
                })
            
            logger.info(
                f"Alert {alert.id} processing complete: "
                f"{len(result['auto_executed'])} auto-executed, "
                f"{len(result['pending_approval'])} pending approval, "
                f"{len(result['blocked'])} blocked"
            )
            
        except Exception as e:
            logger.error(f"Error processing alert {alert.id} for remediation: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _create_and_start_execution(
        self,
        match: TriggerMatch,
        alert: Alert,
        executor_service: Any
    ) -> Optional[RunbookExecution]:
        """
        Create and start an automatic execution.
        
        Args:
            match: The matched trigger.
            alert: The triggering alert.
            executor_service: The executor service.
        
        Returns:
            Created execution record.
        """
        # Create execution record
        execution = RunbookExecution(
            runbook_id=match.runbook.id,
            trigger_id=match.trigger.id,
            alert_id=alert.id,
            status="pending",
            execution_mode="auto",
            variables=match.match_details.get("extracted_variables", {})
        )
        
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        
        # Start execution (non-blocking)
        # In production, this would be queued to a background task
        logger.info(f"Starting auto-execution {execution.id} for runbook {match.runbook.name}")
        
        return execution
    
    async def _create_pending_approval(
        self,
        match: TriggerMatch,
        alert: Alert
    ) -> Optional[RunbookExecution]:
        """
        Create an execution pending approval.
        
        Args:
            match: The matched trigger.
            alert: The triggering alert.
        
        Returns:
            Created execution record.
        """
        import secrets
        
        # Create execution with pending_approval status
        execution = RunbookExecution(
            runbook_id=match.runbook.id,
            trigger_id=match.trigger.id,
            alert_id=alert.id,
            status="pending_approval",
            execution_mode="semi_auto",
            variables=match.match_details.get("extracted_variables", {}),
            approval_token=secrets.token_urlsafe(32),
            approval_expires_at=datetime.utcnow() + timedelta(hours=4)  # 4 hour expiry
        )
        
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        
        logger.info(
            f"Created pending approval execution {execution.id} "
            f"for runbook {match.runbook.name}"
        )
        
        # TODO: Send notification for approval
        # await notification_service.send_approval_request(execution)
        
        return execution


class ApprovalService:
    """
    Handles approval workflow for semi-automatic executions.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize the approval service."""
        self.db = db
    
    async def approve_execution(
        self,
        execution_id: int,
        token: str,
        approver: User
    ) -> Tuple[bool, str]:
        """
        Approve a pending execution.
        
        Args:
            execution_id: ID of the execution to approve.
            token: Approval token.
            approver: User approving the execution.
        
        Returns:
            Tuple of (success, message).
        """
        result = await self.db.execute(
            select(RunbookExecution)
            .options(selectinload(RunbookExecution.runbook))
            .where(RunbookExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        
        if not execution:
            return False, "Execution not found"
        
        if execution.status != "pending_approval":
            return False, f"Execution is not pending approval (status: {execution.status})"
        
        if execution.approval_token != token:
            return False, "Invalid approval token"
        
        if execution.approval_expires_at and execution.approval_expires_at < datetime.utcnow():
            execution.status = "expired"
            await self.db.commit()
            return False, "Approval token has expired"
        
        # Check if approver has permission
        # TODO: Add RBAC check here
        
        # Approve the execution
        execution.status = "pending"  # Ready for execution
        execution.approved_by_id = approver.id
        execution.approved_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(
            f"Execution {execution_id} approved by {approver.username}"
        )
        
        return True, "Execution approved successfully"
    
    async def reject_execution(
        self,
        execution_id: int,
        token: str,
        rejector: User,
        reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Reject a pending execution.
        
        Args:
            execution_id: ID of the execution to reject.
            token: Approval token.
            rejector: User rejecting the execution.
            reason: Reason for rejection.
        
        Returns:
            Tuple of (success, message).
        """
        result = await self.db.execute(
            select(RunbookExecution)
            .where(RunbookExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        
        if not execution:
            return False, "Execution not found"
        
        if execution.status != "pending_approval":
            return False, f"Execution is not pending approval (status: {execution.status})"
        
        if execution.approval_token != token:
            return False, "Invalid approval token"
        
        # Reject the execution
        execution.status = "rejected"
        execution.approved_by_id = rejector.id  # Track who rejected
        execution.approved_at = datetime.utcnow()
        
        # Store rejection reason in result_summary
        execution.result_summary = {"rejection_reason": reason} if reason else {}
        
        await self.db.commit()
        
        logger.info(
            f"Execution {execution_id} rejected by {rejector.username}: {reason}"
        )
        
        return True, "Execution rejected"
    
    async def get_pending_approvals(
        self,
        limit: int = 50
    ) -> List[RunbookExecution]:
        """
        Get all pending approval requests.
        
        Args:
            limit: Maximum number to return.
        
        Returns:
            List of pending executions.
        """
        result = await self.db.execute(
            select(RunbookExecution)
            .options(
                selectinload(RunbookExecution.runbook),
                selectinload(RunbookExecution.alert)
            )
            .where(RunbookExecution.status == "pending_approval")
            .order_by(RunbookExecution.created_at.desc())
            .limit(limit)
        )
        
        return result.scalars().all()
    
    async def cleanup_expired_approvals(self) -> int:
        """
        Mark expired approval requests.
        
        Returns:
            Number of expired executions.
        """
        now = datetime.utcnow()
        
        result = await self.db.execute(
            select(RunbookExecution)
            .where(
                and_(
                    RunbookExecution.status == "pending_approval",
                    RunbookExecution.approval_expires_at < now
                )
            )
        )
        expired = result.scalars().all()
        
        for execution in expired:
            execution.status = "expired"
        
        if expired:
            await self.db.commit()
            logger.info(f"Marked {len(expired)} approval requests as expired")
        
        return len(expired)
