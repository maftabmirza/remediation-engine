"""
Execution Worker Service

Background worker that processes pending and approved runbook executions.
Runs as an asyncio background task within the FastAPI application.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import async_session_factory
from ..models_remediation import RunbookExecution, Runbook
from ..config import get_settings
from .runbook_executor import RunbookExecutor

logger = logging.getLogger(__name__)
settings = get_settings()


class ExecutionWorker:
    """
    Background worker that polls for and executes pending/approved runbook executions.
    
    Features:
    - Polls database for ready-to-execute jobs
    - Handles approval timeouts
    - Processes one execution at a time (can be extended for parallel)
    - Graceful shutdown support
    """
    
    def __init__(self, poll_interval: int = 5):
        """
        Initialize the execution worker.
        
        Args:
            poll_interval: Seconds between database polls
        """
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.fernet_key = settings.encryption_key if settings.encryption_key else None
    
    async def start(self):
        """Start the background worker."""
        if self._running:
            logger.warning("Execution worker is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Execution worker started")
    
    async def stop(self):
        """Stop the background worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Execution worker stopped")
    
    async def _worker_loop(self):
        """Main worker loop - polls for and processes executions."""
        while self._running:
            try:
                await self._process_pending_executions()
                await self._check_approval_timeouts()
            except Exception as e:
                logger.exception(f"Error in execution worker loop: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    async def _process_pending_executions(self):
        """Find and process executions that are ready to run."""
        async with async_session_factory() as db:
            try:
                # Find executions that are:
                # 1. Status = 'approved' (approved and ready to run)
                # 2. Status = 'running' but not yet started (initial state for non-approval runbooks)
                result = await db.execute(
                    select(RunbookExecution)
                    .options(
                        selectinload(RunbookExecution.runbook).selectinload(Runbook.steps),
                        selectinload(RunbookExecution.server)
                    )
                    .where(
                        RunbookExecution.status.in_(["approved", "running"])
                    )
                    .where(
                        # Only pick up executions that haven't actually started
                        # (started_at is None or very recent for 'running' initial state)
                        RunbookExecution.completed_at.is_(None)
                    )
                    .order_by(RunbookExecution.queued_at)
                    .limit(5)  # Process up to 5 at a time
                )
                executions = result.scalars().all()
                
                for execution in executions:
                    if not self._running:
                        break
                    
                    await self._execute_runbook(db, execution)
                    
            except Exception as e:
                logger.exception(f"Error processing pending executions: {e}")
    
    async def _execute_runbook(self, db: AsyncSession, execution: RunbookExecution):
        """Execute a single runbook."""
        logger.info(f"Starting execution {execution.id} for runbook {execution.runbook.name if execution.runbook else 'Unknown'}")
        
        try:
            # Update status to running
            execution.status = "running"
            execution.started_at = datetime.now(timezone.utc)
            await db.commit()
            
            # Check if we have required data
            if not execution.runbook:
                execution.status = "failed"
                execution.error_message = "Runbook not found"
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return
            
            if not execution.server_id:
                execution.status = "failed"
                execution.error_message = "No target server specified"
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return
            
            # Create executor and run
            executor = RunbookExecutor(db=db, fernet_key=self.fernet_key)
            
            # Define callbacks for logging
            def on_step_start(step_order: int, step_name: str):
                logger.info(f"  Step {step_order}: {step_name} - Starting")
            
            def on_step_complete(step_order: int, step_name: str, success: bool):
                status = "Success" if success else "Failed"
                logger.info(f"  Step {step_order}: {step_name} - {status}")
            
            def on_output(line: str):
                logger.debug(f"    Output: {line[:200]}")  # Truncate long lines
            
            # Execute the runbook
            result = await executor.execute_runbook(
                execution=execution,
                on_step_start=on_step_start,
                on_step_complete=on_step_complete,
                on_output=on_output
            )
            
            logger.info(f"Execution {execution.id} completed with status: {result.status}")
            
        except Exception as e:
            logger.exception(f"Error executing runbook {execution.id}: {e}")
            execution.status = "failed"
            execution.error_message = f"Execution error: {str(e)}"
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()
    
    async def _check_approval_timeouts(self):
        """Check for and timeout expired pending approvals."""
        async with async_session_factory() as db:
            try:
                now = datetime.now(timezone.utc)
                
                # Find pending executions that have expired
                result = await db.execute(
                    select(RunbookExecution)
                    .where(
                        and_(
                            RunbookExecution.status == "pending",
                            RunbookExecution.approval_expires_at.isnot(None),
                            RunbookExecution.approval_expires_at < now
                        )
                    )
                )
                expired_executions = result.scalars().all()
                
                for execution in expired_executions:
                    logger.info(f"Timing out execution {execution.id} - approval expired")
                    execution.status = "timeout"
                    execution.completed_at = now
                    execution.error_message = "Approval timeout - no response within allowed window"
                
                if expired_executions:
                    await db.commit()
                    logger.info(f"Timed out {len(expired_executions)} pending executions")
                    
            except Exception as e:
                logger.exception(f"Error checking approval timeouts: {e}")


# Global worker instance
_worker: Optional[ExecutionWorker] = None


def get_execution_worker() -> ExecutionWorker:
    """Get or create the global execution worker instance."""
    global _worker
    if _worker is None:
        _worker = ExecutionWorker()
    return _worker


async def start_execution_worker():
    """Start the global execution worker."""
    worker = get_execution_worker()
    await worker.start()


async def stop_execution_worker():
    """Stop the global execution worker."""
    global _worker
    if _worker:
        await _worker.stop()
        _worker = None
