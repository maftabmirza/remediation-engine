"""
Alert Trigger Matcher Service

Matches incoming alerts to runbook triggers for auto-remediation.
Handles trigger conditions, execution mode selection, and runbook invocation.
"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from ..models import ServerCredential

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
                
                # Determine execution mode from runbook settings
                if trigger.runbook.auto_execute:
                    execution_mode = "auto"
                elif trigger.runbook.approval_required:
                    execution_mode = "semi_auto"
                else:
                    execution_mode = "manual"
                
                match = TriggerMatch(
                    trigger=trigger,
                    runbook=trigger.runbook,
                    match_details=match_details,
                    execution_mode=execution_mode,
                    can_execute=can_execute,
                    block_reason=block_reason
                )
                matches.append(match)
        
        # Deduplicate matches by runbook_id, picking highest priority (lowest number)
        unique_matches = {}
        for m in matches:
            rb_id = m.runbook.id
            if rb_id not in unique_matches:
                unique_matches[rb_id] = m
            else:
                # Compare priority (lower is better)
                curr_p = getattr(m.trigger, 'priority', 100)
                best_p = getattr(unique_matches[rb_id].trigger, 'priority', 100)
                if curr_p < best_p:
                    unique_matches[rb_id] = m
        
        matches = list(unique_matches.values())

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
        result = {
            "matched": False,
            "matched_conditions": [],
            "extracted_variables": {}
        }
        
        # Get alert fields
        alert_name = getattr(alert, 'alert_name', alert.name if hasattr(alert, 'name') else '')
        alert_severity = getattr(alert, 'severity', '')
        alert_instance = getattr(alert, 'instance', '')
        alert_job = getattr(alert, 'job', '')
        alert_labels = getattr(alert, 'labels_json', {}) or {}
        
        # Check alert name pattern
        if trigger.alert_name_pattern and trigger.alert_name_pattern != '*':
            pattern = trigger.alert_name_pattern.replace('*', '.*')
            try:
                if not re.match(pattern, alert_name, re.IGNORECASE):
                    return result
                result["matched_conditions"].append(f"alert_name: {alert_name}")
            except re.error as e:
                logger.error(f"Invalid alert_name pattern in trigger {trigger.id}: {e}")
                return result
        
        # Check severity pattern
        if trigger.severity_pattern and trigger.severity_pattern != '*':
            pattern = trigger.severity_pattern.replace('*', '.*')
            try:
                if not re.match(pattern, alert_severity, re.IGNORECASE):
                    return result
                result["matched_conditions"].append(f"severity: {alert_severity}")
            except re.error as e:
                logger.error(f"Invalid severity pattern in trigger {trigger.id}: {e}")
                return result
        
        # Check instance pattern
        if trigger.instance_pattern and trigger.instance_pattern != '*':
            pattern = trigger.instance_pattern.replace('*', '.*')
            try:
                if not re.match(pattern, alert_instance, re.IGNORECASE):
                    return result
                result["matched_conditions"].append(f"instance: {alert_instance}")
            except re.error as e:
                logger.error(f"Invalid instance pattern in trigger {trigger.id}: {e}")
                return result
        
        # Check job pattern
        if trigger.job_pattern and trigger.job_pattern != '*':
            pattern = trigger.job_pattern.replace('*', '.*')
            try:
                if not re.match(pattern, alert_job, re.IGNORECASE):
                    return result
                result["matched_conditions"].append(f"job: {alert_job}")
            except re.error as e:
                logger.error(f"Invalid job pattern in trigger {trigger.id}: {e}")
                return result
        
        # Check label matchers
        if trigger.label_matchers_json:
            for key, value in trigger.label_matchers_json.items():
                if key not in alert_labels:
                    return result
                if value != '*' and alert_labels.get(key) != value:
                    return result
            result["matched_conditions"].append(f"labels matched")
        
        # If we got here, all patterns matched
        result["matched"] = True
        
        # Extract variables from alert
        result["extracted_variables"] = {
            "alert_id": str(alert.id),
            "alert_name": alert_name,
            "alert_severity": alert_severity,
            "alert_instance": alert_instance,
            "alert_job": alert_job,
            "alert_source": getattr(alert, 'source', ''),
            "alert_timestamp": alert.timestamp.isoformat() if hasattr(alert, 'timestamp') and alert.timestamp else "",
        }
        
        # Add alert labels as variables with prefix
        for key, value in alert_labels.items():
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
        now = datetime.now(timezone.utc)
        
        # Check circuit breaker
        circuit_result = await self.db.execute(
            select(CircuitBreaker).where(
                and_(
                    CircuitBreaker.scope == "runbook",
                    CircuitBreaker.scope_id == runbook.id
                )
            )
        )
        circuit = circuit_result.scalar_one_or_none()
        
        if circuit and circuit.state == "open":
            return False, f"Circuit breaker is open until {circuit.closes_at}"
        
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
        
        # Check rate limiting using runbook's own settings
        if hasattr(runbook, 'max_executions_per_hour') and runbook.max_executions_per_hour:
            # Calculate window start (1 hour ago)
            window_start = now - timedelta(hours=1)
            
            # Count recent executions
            exec_count_result = await self.db.execute(
                select(RunbookExecution).where(
                    and_(
                        RunbookExecution.runbook_id == runbook.id,
                        RunbookExecution.queued_at >= window_start
                    )
                )
            )
            recent_executions = len(exec_count_result.scalars().all())
            
            if recent_executions >= runbook.max_executions_per_hour:
                return False, f"Rate limit exceeded: {recent_executions}/{runbook.max_executions_per_hour} executions in the last hour"
        
        # Check cooldown period
        if hasattr(runbook, 'cooldown_minutes') and runbook.cooldown_minutes:
            # Get the most recent execution
            last_exec_result = await self.db.execute(
                select(RunbookExecution)
                .where(RunbookExecution.runbook_id == runbook.id)
                .order_by(RunbookExecution.queued_at.desc())
                .limit(1)
            )
            last_execution = last_exec_result.scalar_one_or_none()
            
            if last_execution and last_execution.queued_at:
                cooldown_end = last_execution.queued_at + timedelta(minutes=runbook.cooldown_minutes)
                if now < cooldown_end:
                    remaining = int((cooldown_end - now).total_seconds() / 60)
                    return False, f"Cooldown period active: {remaining} minutes remaining"
        
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
    
    async def _resolve_target_server(
        self,
        runbook: Runbook,
        alert: Alert
    ) -> Optional[str]:
        """
        Resolve target server from alert labels or runbook default.
        
        Returns:
            Server ID if found, None otherwise.
        """
        server_id = None
        
        # Try to get from alert if configured
        if runbook.target_from_alert and runbook.target_alert_label:
            alert_labels = getattr(alert, 'labels_json', {}) or {}
            target_identifier = alert_labels.get(runbook.target_alert_label)
            
            if target_identifier:
                # Look up server by name or hostname
                result = await self.db.execute(
                    select(ServerCredential).where(
                        (ServerCredential.name == target_identifier) |
                        (ServerCredential.hostname == target_identifier)
                    )
                )
                server = result.scalar_one_or_none()
                if server:
                    server_id = server.id
                    logger.info(f"Resolved server {server.name} from alert label {runbook.target_alert_label}={target_identifier}")
        
        # Fall back to runbook default
        if not server_id and runbook.default_server_id:
            server_id = runbook.default_server_id
            logger.info(f"Using runbook default server {runbook.default_server_id}")
        
        return server_id
    
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
        # Resolve target server
        server_id = await self._resolve_target_server(match.runbook, alert)
        
        # Create execution record
        execution = RunbookExecution(
            runbook_id=match.runbook.id,
            runbook_version=match.runbook.version,
            trigger_id=match.trigger.id,
            alert_id=alert.id,
            server_id=server_id,
            status="queued",
            execution_mode="auto",
            variables_json=match.match_details.get("extracted_variables", {})
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
        
        # Resolve target server
        server_id = await self._resolve_target_server(match.runbook, alert)
        
        # Create execution with pending_approval status
        execution = RunbookExecution(
            runbook_id=match.runbook.id,
            runbook_version=match.runbook.version,
            trigger_id=match.trigger.id,
            alert_id=alert.id,
            server_id=server_id,
            status="pending_approval",
            execution_mode="semi_auto",
            variables_json=match.match_details.get("extracted_variables", {}),
            approval_token=secrets.token_urlsafe(32),
            approval_expires_at=datetime.now(timezone.utc) + timedelta(hours=4)  # 4 hour expiry
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
        
        if execution.approval_expires_at and execution.approval_expires_at < datetime.now(timezone.utc):
            execution.status = "expired"
            await self.db.commit()
            return False, "Approval token has expired"
        
        # Check if approver has permission
        # TODO: Add RBAC check here
        
        # Approve the execution
        execution.status = "pending"  # Ready for execution
        execution.approved_by_id = approver.id
        execution.approved_at = datetime.now(timezone.utc)
        
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
        execution.approved_at = datetime.now(timezone.utc)
        
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
        now = datetime.now(timezone.utc)
        
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
