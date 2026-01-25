"""
Safety Mechanisms Services

Implements circuit breaker, rate limiting, and blackout window logic
to ensure safe execution of auto-remediation runbooks.
"""

import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from ..models_remediation import (
    Runbook,
    RunbookExecution,
    CircuitBreaker,
    BlackoutWindow,
    ExecutionRateLimit
)

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation, executions allowed
    OPEN = "open"           # Failures detected, executions blocked
    HALF_OPEN = "half_open" # Testing if service has recovered


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""
    allowed: bool
    reason: Optional[str] = None
    retry_after: Optional[datetime] = None


class CircuitBreakerService:
    """
    Implements circuit breaker pattern for runbook executions.
    
    When a runbook fails repeatedly, the circuit opens to prevent
    further damage. After a cooldown period, it moves to half-open
    to test if the issue is resolved.
    """
    
    DEFAULT_FAILURE_THRESHOLD = 5
    DEFAULT_SUCCESS_THRESHOLD = 3
    DEFAULT_RESET_TIMEOUT_SECONDS = 300  # 5 minutes
    
    def __init__(self, db: AsyncSession):
        """Initialize the circuit breaker service."""
        self.db = db
    
    async def check_circuit(self, runbook_id: int) -> SafetyCheckResult:
        """
        Check if circuit allows execution.
        
        Args:
            runbook_id: The runbook to check.
        
        Returns:
            SafetyCheckResult indicating if execution is allowed.
        """
        circuit = await self._get_or_create_circuit(runbook_id)
        
        # Check for state transitions
        await self._maybe_transition_state(circuit)
        
        if circuit.state == CircuitState.OPEN:
            return SafetyCheckResult(
                allowed=False,
                reason=f"Circuit breaker is open due to {circuit.failure_count} failures",
                retry_after=circuit.closes_at
            )
        
        return SafetyCheckResult(allowed=True)
    
    async def record_success(self, runbook_id: int):
        """
        Record a successful execution.
        
        Args:
            runbook_id: The runbook that succeeded.
        """
        circuit = await self._get_or_create_circuit(runbook_id)
        circuit.last_success_at = datetime.utcnow()
        circuit.success_count += 1
        
        if circuit.state == CircuitState.HALF_OPEN:
            
            if circuit.success_count >= (circuit.success_threshold or self.DEFAULT_SUCCESS_THRESHOLD):
                # Close the circuit - service has recovered
                circuit.state = CircuitState.CLOSED
                circuit.failure_count = 0
                circuit.success_count = 0  # Reset consecutive successes counter
                circuit.closes_at = None
                circuit.opened_at = None
                logger.info(f"Circuit breaker for runbook {runbook_id} closed after recovery")
        
        elif circuit.state == CircuitState.CLOSED:
            # Reset failure count on success
            circuit.failure_count = 0
        
        await self.db.commit()
    
    async def record_failure(self, runbook_id: int, error: Optional[str] = None):
        """
        Record a failed execution.
        
        Args:
            runbook_id: The runbook that failed.
            error: Optional error message.
        """
        circuit = await self._get_or_create_circuit(runbook_id)
        circuit.last_failure_at = datetime.utcnow()
        circuit.failure_count += 1
        circuit.success_count = 0  # Reset consecutive successes
        
        if circuit.state == CircuitState.HALF_OPEN:
            # Failure during half-open, reopen the circuit
            circuit.state = CircuitState.OPEN
            open_duration = circuit.open_duration_minutes or (self.DEFAULT_RESET_TIMEOUT_SECONDS // 60)
            # Double the duration for half-open failure
            circuit.closes_at = datetime.utcnow() + timedelta(minutes=open_duration * 2)
            circuit.opened_at = datetime.utcnow()
            logger.warning(
                f"Circuit breaker for runbook {runbook_id} reopened after half-open failure"
            )
        
        elif circuit.state == CircuitState.CLOSED:
            threshold = circuit.failure_threshold or self.DEFAULT_FAILURE_THRESHOLD
            
            if circuit.failure_count >= threshold:
                # Open the circuit
                circuit.state = CircuitState.OPEN
                open_duration = circuit.open_duration_minutes or (self.DEFAULT_RESET_TIMEOUT_SECONDS // 60)
                circuit.closes_at = datetime.utcnow() + timedelta(minutes=open_duration)
                circuit.opened_at = datetime.utcnow()
                logger.warning(
                    f"Circuit breaker for runbook {runbook_id} opened after {circuit.failure_count} failures"
                )
        
        await self.db.commit()
    
    async def force_open(
        self,
        runbook_id: int,
        duration_minutes: int = 60,
        reason: Optional[str] = None
    ):
        """
        Manually open the circuit breaker.
        
        Args:
            runbook_id: The runbook to block.
            duration_minutes: How long to keep open.
            reason: Reason for manual override.
        """
        circuit = await self._get_or_create_circuit(runbook_id)
        circuit.state = CircuitState.OPEN
        circuit.closes_at = datetime.utcnow() + timedelta(minutes=duration_minutes)
        circuit.manually_opened = True
        circuit.manually_opened_reason = reason
        circuit.manually_opened_by = None  # TODO: Add user context
        circuit.opened_at = datetime.utcnow()
        
        await self.db.commit()
        logger.info(f"Circuit breaker for runbook {runbook_id} manually opened: {reason}")
    
    async def force_close(self, runbook_id: int, reason: Optional[str] = None):
        """
        Manually close the circuit breaker.
        
        Args:
            runbook_id: The runbook to unblock.
            reason: Reason for manual override.
        """
        circuit = await self._get_or_create_circuit(runbook_id)
        circuit.state = CircuitState.CLOSED
        circuit.failure_count = 0
        circuit.success_count = 0
        circuit.manually_opened = False
        circuit.manually_opened_reason = reason
        circuit.closes_at = None
        circuit.opened_at = None
        
        await self.db.commit()
        logger.info(f"Circuit breaker for runbook {runbook_id} manually closed: {reason}")
    
    async def get_status(self, runbook_id: int) -> dict:
        """
        Get current circuit breaker status.
        
        Args:
            runbook_id: The runbook to check.
        
        Returns:
            Dict with circuit breaker status.
        """
        circuit = await self._get_or_create_circuit(runbook_id)
        
        return {
            "runbook_id": runbook_id,
            "state": circuit.state,
            "failure_count": circuit.failure_count,
            "failure_threshold": circuit.failure_threshold or self.DEFAULT_FAILURE_THRESHOLD,
            "consecutive_successes": circuit.success_count,
            "success_threshold": circuit.success_threshold or self.DEFAULT_SUCCESS_THRESHOLD,
            "reset_at": circuit.closes_at.isoformat() if circuit.closes_at else None,  # Mapped for API compatibility
            "last_failure_at": circuit.last_failure_at.isoformat() if circuit.last_failure_at else None,
            "manual_override": circuit.manually_opened,  # Mapped for API compatibility
            "override_reason": circuit.manually_opened_reason
        }
    
    async def _get_or_create_circuit(self, runbook_id: int) -> CircuitBreaker:
        """Get or create circuit breaker for runbook."""
        result = await self.db.execute(
            select(CircuitBreaker)
            .where(
                and_(
                    CircuitBreaker.scope == "runbook",
                    CircuitBreaker.scope_id == runbook_id
                )
            )
        )
        circuit = result.scalar_one_or_none()
        
        if not circuit:
            circuit = CircuitBreaker(
                scope="runbook",
                scope_id=runbook_id,
                state=CircuitState.CLOSED,
                failure_count=0,
                success_count=0
            )
            self.db.add(circuit)
            await self.db.commit()
            await self.db.refresh(circuit)
        
        return circuit
    
    async def _maybe_transition_state(self, circuit: CircuitBreaker):
        """Check if circuit should transition states."""
        if circuit.state == CircuitState.OPEN:
            # Check if reset timeout has passed
            if circuit.closes_at and circuit.closes_at <= datetime.utcnow():
                circuit.state = CircuitState.HALF_OPEN
                circuit.success_count = 0
                await self.db.commit()
                logger.info(
                    f"Circuit breaker for runbook {circuit.scope_id} "
                    f"transitioned to half-open"
                )
                return

            # Check if configuration changed (failure count below current threshold)
            # This allows auto-recovery if the threshold is increased
            current_threshold = circuit.failure_threshold or self.DEFAULT_FAILURE_THRESHOLD
            if not circuit.manually_opened and circuit.failure_count < current_threshold:
                circuit.state = CircuitState.CLOSED
                circuit.closes_at = None
                circuit.opened_at = None
                await self.db.commit()
                logger.info(
                    f"Circuit breaker for runbook {circuit.scope_id} "
                    f"auto-closed due to threshold adjustment ({circuit.failure_count} < {current_threshold})"
                )


class RateLimitService:
    """
    Implements rate limiting for runbook executions.
    
    Prevents too many executions of the same runbook
    within a given time window.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize the rate limit service."""
        self.db = db
    
    async def check_rate_limit(self, runbook_id: int) -> SafetyCheckResult:
        """
        Check if runbook execution is within rate limits.
        
        Args:
            runbook_id: The runbook to check.
        
        Returns:
            SafetyCheckResult indicating if execution is allowed.
        """
        result = await self.db.execute(
            select(ExecutionRateLimit)
            .where(ExecutionRateLimit.runbook_id == runbook_id)
        )
        rate_limit = result.scalar_one_or_none()
        
        if not rate_limit:
            return SafetyCheckResult(allowed=True)
        
        # Count recent executions
        window_start = datetime.utcnow() - timedelta(seconds=rate_limit.window_seconds)
        
        count_result = await self.db.execute(
            select(func.count(RunbookExecution.id))
            .where(
                and_(
                    RunbookExecution.runbook_id == runbook_id,
                    RunbookExecution.started_at >= window_start
                )
            )
        )
        execution_count = count_result.scalar() or 0
        
        if execution_count >= rate_limit.max_executions:
            # Calculate when rate limit resets
            oldest_in_window_result = await self.db.execute(
                select(RunbookExecution.started_at)
                .where(
                    and_(
                        RunbookExecution.runbook_id == runbook_id,
                        RunbookExecution.started_at >= window_start
                    )
                )
                .order_by(RunbookExecution.started_at)
                .limit(1)
            )
            oldest = oldest_in_window_result.scalar()
            
            retry_after = oldest + timedelta(seconds=rate_limit.window_seconds) if oldest else None
            
            return SafetyCheckResult(
                allowed=False,
                reason=f"Rate limit exceeded: {execution_count}/{rate_limit.max_executions} "
                       f"executions in {rate_limit.window_seconds}s window",
                retry_after=retry_after
            )
        
        return SafetyCheckResult(allowed=True)
    
    async def set_rate_limit(
        self,
        runbook_id: int,
        max_executions: int,
        window_seconds: int
    ):
        """
        Set or update rate limit for a runbook.
        
        Args:
            runbook_id: The runbook to limit.
            max_executions: Maximum executions allowed.
            window_seconds: Time window in seconds.
        """
        result = await self.db.execute(
            select(ExecutionRateLimit)
            .where(ExecutionRateLimit.runbook_id == runbook_id)
        )
        rate_limit = result.scalar_one_or_none()
        
        if rate_limit:
            rate_limit.max_executions = max_executions
            rate_limit.window_seconds = window_seconds
        else:
            rate_limit = ExecutionRateLimit(
                runbook_id=runbook_id,
                max_executions=max_executions,
                window_seconds=window_seconds
            )
            self.db.add(rate_limit)
        
        await self.db.commit()
    
    async def remove_rate_limit(self, runbook_id: int):
        """Remove rate limit for a runbook."""
        result = await self.db.execute(
            select(ExecutionRateLimit)
            .where(ExecutionRateLimit.runbook_id == runbook_id)
        )
        rate_limit = result.scalar_one_or_none()
        
        if rate_limit:
            await self.db.delete(rate_limit)
            await self.db.commit()
    
    async def get_usage(self, runbook_id: int) -> dict:
        """
        Get current rate limit usage for a runbook.
        
        Args:
            runbook_id: The runbook to check.
        
        Returns:
            Dict with rate limit status.
        """
        result = await self.db.execute(
            select(ExecutionRateLimit)
            .where(ExecutionRateLimit.runbook_id == runbook_id)
        )
        rate_limit = result.scalar_one_or_none()
        
        if not rate_limit:
            return {
                "runbook_id": runbook_id,
                "rate_limited": False,
                "message": "No rate limit configured"
            }
        
        window_start = datetime.utcnow() - timedelta(seconds=rate_limit.window_seconds)
        
        count_result = await self.db.execute(
            select(func.count(RunbookExecution.id))
            .where(
                and_(
                    RunbookExecution.runbook_id == runbook_id,
                    RunbookExecution.started_at >= window_start
                )
            )
        )
        execution_count = count_result.scalar() or 0
        
        return {
            "runbook_id": runbook_id,
            "rate_limited": True,
            "current_count": execution_count,
            "max_executions": rate_limit.max_executions,
            "window_seconds": rate_limit.window_seconds,
            "remaining": max(0, rate_limit.max_executions - execution_count),
            "window_start": window_start.isoformat()
        }


class BlackoutWindowService:
    """
    Manages blackout windows for preventing auto-remediation
    during maintenance or critical periods.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize the blackout window service."""
        self.db = db
    
    async def check_blackout(
        self,
        runbook: Optional[Runbook] = None,
        runbook_id: Optional[int] = None,
        category: Optional[str] = None
    ) -> SafetyCheckResult:
        """
        Check if execution is blocked by any blackout window.
        
        Args:
            runbook: The runbook to check (optional).
            runbook_id: The runbook ID (optional).
            category: The runbook category (optional).
        
        Returns:
            SafetyCheckResult indicating if execution is allowed.
        """
        now = datetime.utcnow()
        
        # Get active blackout windows
        result = await self.db.execute(
            select(BlackoutWindow)
            .where(
                and_(
                    BlackoutWindow.enabled == True,
                    BlackoutWindow.start_time <= now,
                    BlackoutWindow.end_time > now
                )
            )
        )
        blackouts = result.scalars().all()
        
        for blackout in blackouts:
            if self._affects_runbook(blackout, runbook, runbook_id, category):
                return SafetyCheckResult(
                    allowed=False,
                    reason=f"Blackout window active: {blackout.name}",
                    retry_after=blackout.end_time
                )
        
        return SafetyCheckResult(allowed=True)
    
    def _affects_runbook(
        self,
        blackout: BlackoutWindow,
        runbook: Optional[Runbook],
        runbook_id: Optional[int],
        category: Optional[str]
    ) -> bool:
        """Check if blackout affects the given runbook."""
        if blackout.scope == "all":
            return True
        
        if blackout.scope == "category":
            check_category = category or (runbook.category if runbook else None)
            if check_category and blackout.affected_categories:
                return check_category in blackout.affected_categories
        
        if blackout.scope == "runbook":
            check_id = runbook_id or (runbook.id if runbook else None)
            if check_id and blackout.affected_runbook_ids:
                return check_id in blackout.affected_runbook_ids
        
        return False
    
    async def create_blackout(
        self,
        name: str,
        start_time: datetime,
        end_time: datetime,
        scope: str = "all",
        reason: Optional[str] = None,
        affected_categories: Optional[List[str]] = None,
        affected_runbook_ids: Optional[List[int]] = None,
        created_by_id: Optional[int] = None
    ) -> BlackoutWindow:
        """
        Create a new blackout window.
        
        Args:
            name: Name of the blackout.
            start_time: When blackout starts.
            end_time: When blackout ends.
            scope: "all", "category", or "runbook".
            reason: Reason for blackout.
            affected_categories: Categories affected (if scope=category).
            affected_runbook_ids: Runbook IDs affected (if scope=runbook).
            created_by_id: User who created the blackout.
        
        Returns:
            Created BlackoutWindow.
        """
        blackout = BlackoutWindow(
            name=name,
            start_time=start_time,
            end_time=end_time,
            scope=scope,
            reason=reason,
            affected_categories=affected_categories,
            affected_runbook_ids=affected_runbook_ids,
            created_by_id=created_by_id,
            enabled=True
        )
        
        self.db.add(blackout)
        await self.db.commit()
        await self.db.refresh(blackout)
        
        logger.info(f"Created blackout window: {name} ({start_time} to {end_time})")
        return blackout
    
    async def get_active_blackouts(self) -> List[BlackoutWindow]:
        """Get all currently active blackout windows."""
        now = datetime.utcnow()
        
        result = await self.db.execute(
            select(BlackoutWindow)
            .where(
                and_(
                    BlackoutWindow.enabled == True,
                    BlackoutWindow.start_time <= now,
                    BlackoutWindow.end_time > now
                )
            )
            .order_by(BlackoutWindow.end_time)
        )
        
        return result.scalars().all()
    
    async def get_upcoming_blackouts(
        self,
        hours_ahead: int = 24
    ) -> List[BlackoutWindow]:
        """Get blackout windows starting within specified hours."""
        now = datetime.utcnow()
        future = now + timedelta(hours=hours_ahead)
        
        result = await self.db.execute(
            select(BlackoutWindow)
            .where(
                and_(
                    BlackoutWindow.enabled == True,
                    BlackoutWindow.start_time > now,
                    BlackoutWindow.start_time <= future
                )
            )
            .order_by(BlackoutWindow.start_time)
        )
        
        return result.scalars().all()
    
    async def disable_blackout(self, blackout_id: int) -> bool:
        """Disable a blackout window early."""
        result = await self.db.execute(
            select(BlackoutWindow)
            .where(BlackoutWindow.id == blackout_id)
        )
        blackout = result.scalar_one_or_none()
        
        if blackout:
            blackout.enabled = False
            await self.db.commit()
            logger.info(f"Disabled blackout window: {blackout.name}")
            return True
        
        return False
    
    async def extend_blackout(
        self,
        blackout_id: int,
        new_end_time: datetime
    ) -> Optional[BlackoutWindow]:
        """Extend a blackout window's end time."""
        result = await self.db.execute(
            select(BlackoutWindow)
            .where(BlackoutWindow.id == blackout_id)
        )
        blackout = result.scalar_one_or_none()
        
        if blackout:
            old_end = blackout.end_time
            blackout.end_time = new_end_time
            await self.db.commit()
            logger.info(
                f"Extended blackout window {blackout.name}: "
                f"{old_end} -> {new_end_time}"
            )
            return blackout
        
        return None


class SafetyGate:
    """
    Unified safety gate that checks all safety mechanisms.
    
    Combines circuit breaker, rate limiting, and blackout checks
    into a single check point.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize the safety gate."""
        self.db = db
        self.circuit_breaker = CircuitBreakerService(db)
        self.rate_limiter = RateLimitService(db)
        self.blackout_service = BlackoutWindowService(db)
    
    async def check_can_execute(
        self,
        runbook: Runbook
    ) -> Tuple[bool, List[str]]:
        """
        Check all safety mechanisms for a runbook.
        
        Args:
            runbook: The runbook to check.
        
        Returns:
            Tuple of (allowed, list of reasons if blocked).
        """
        reasons = []
        
        # Check circuit breaker
        circuit_check = await self.circuit_breaker.check_circuit(runbook.id)
        if not circuit_check.allowed:
            reasons.append(circuit_check.reason)
        
        # Check rate limit
        rate_check = await self.rate_limiter.check_rate_limit(runbook.id)
        if not rate_check.allowed:
            reasons.append(rate_check.reason)
        
        # Check blackout windows
        blackout_check = await self.blackout_service.check_blackout(runbook=runbook)
        if not blackout_check.allowed:
            reasons.append(blackout_check.reason)
        
        return len(reasons) == 0, reasons
    
    async def on_execution_complete(
        self,
        runbook_id: int,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Update safety mechanisms after execution.
        
        Args:
            runbook_id: The runbook that executed.
            success: Whether execution was successful.
            error: Error message if failed.
        """
        if success:
            await self.circuit_breaker.record_success(runbook_id)
        else:
            await self.circuit_breaker.record_failure(runbook_id, error)
    
    async def get_safety_status(self, runbook_id: int) -> dict:
        """
        Get comprehensive safety status for a runbook.
        
        Args:
            runbook_id: The runbook to check.
        
        Returns:
            Dict with all safety mechanism statuses.
        """
        return {
            "circuit_breaker": await self.circuit_breaker.get_status(runbook_id),
            "rate_limit": await self.rate_limiter.get_usage(runbook_id),
            "active_blackouts": [
                {
                    "id": b.id,
                    "name": b.name,
                    "ends_at": b.end_time.isoformat()
                }
                for b in await self.blackout_service.get_active_blackouts()
            ]
        }
