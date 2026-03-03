"""
Scheduler Service

Core scheduling engine using APScheduler with PostgreSQL-backed job store.
Manages scheduled runbook executions with cron, interval, and date-based triggers.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from croniter import croniter
import pytz

from ..config import get_settings
from ..database import get_async_db
from ..models_scheduler import ScheduledJob, ScheduleExecutionHistory
from ..models_remediation import RunbookExecution
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Singleton service for managing scheduled runbook executions.
    Uses APScheduler with async executor and SQLAlchemy job store.
    """
    
    _instance: Optional['SchedulerService'] = None
    _scheduler: Optional[AsyncIOScheduler] = None
    
    @classmethod
    def get_instance(cls) -> 'SchedulerService':
        """Get or create the singleton scheduler instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize the scheduler with PostgreSQL job store and async executor."""
        if SchedulerService._instance is not None:
            raise RuntimeError("SchedulerService is a singleton. Use get_instance() instead.")
        
        settings = get_settings()
        
        # Configure job store (PostgreSQL-backed)
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.database_url, tablename='apscheduler_jobs')
        }
        
        # Configure async executor
        executors = {
            'default': AsyncIOExecutor()
        }
        
        # Job defaults
        job_defaults = {
            'coalesce': False,  # Run all missed jobs
            'max_instances': 3,  # Max concurrent instances per job
            'misfire_grace_time': 300  # 5 minutes grace period for misfires
        }
        
        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.UTC
        )
        
        logger.info("SchedulerService initialized")
    
    async def start(self):
        """Start the scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("✅ Scheduler started successfully")
            
            # Log current scheduled jobs
            jobs = self._scheduler.get_jobs()
            logger.info(f"📅 Loaded {len(jobs)} scheduled job(s)")
    
    async def shutdown(self):
        """Shutdown the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown completed")
    
    async def add_schedule(self, scheduled_job: ScheduledJob) -> str:
        """
        Add a new scheduled job to the scheduler.
        
        Args:
            scheduled_job: ScheduledJob model instance
            
        Returns:
            Job ID (str representation of schedule UUID)
        """
        try:
            trigger = self._create_trigger(scheduled_job)
            job_id = str(scheduled_job.id)
            
            self._scheduler.add_job(
                func=_execute_scheduled_runbook,
                trigger=trigger,
                id=job_id,
                name=scheduled_job.name,
                max_instances=scheduled_job.max_instances,
                misfire_grace_time=scheduled_job.misfire_grace_time,
                replace_existing=True,
                kwargs={
                    'scheduled_job_id': job_id,
                    'runbook_id': str(scheduled_job.runbook_id),
                    'server_id': str(scheduled_job.target_server_id) if scheduled_job.target_server_id else None,
                    'server_ids': list(scheduled_job.target_server_ids or []),
                    'group_ids': list(scheduled_job.target_server_group_ids or []),
                    'params': scheduled_job.execution_params
                }
            )
            
            logger.info(f"✅ Scheduled job added: '{scheduled_job.name}' (ID: {job_id}, Type: {scheduled_job.schedule_type})")
            
            # Update next_run_at in database
            next_run = self._scheduler.get_job(job_id).next_run_time
            if next_run:
                async for db in get_async_db():
                    await db.execute(
                        update(ScheduledJob)
                        .where(ScheduledJob.id == scheduled_job.id)
                        .values(next_run_at=next_run)
                    )
                    await db.commit()
                    break
            
            return job_id
            
        except Exception as e:
            logger.error(f"❌ Failed to add scheduled job '{scheduled_job.name}': {e}")
            raise
    
    async def remove_schedule(self, job_id: UUID):
        """Remove a scheduled job."""
        try:
            self._scheduler.remove_job(str(job_id))
            logger.info(f"🗑️  Scheduled job removed: {job_id}")
        except Exception as e:
            logger.error(f"Failed to remove scheduled job {job_id}: {e}")
            raise
    
    async def pause_schedule(self, job_id: UUID):
        """Pause a scheduled job."""
        try:
            self._scheduler.pause_job(str(job_id))
            logger.info(f"⏸️  Scheduled job paused: {job_id}")
        except Exception as e:
            logger.error(f"Failed to pause scheduled job {job_id}: {e}")
            raise
    
    async def resume_schedule(self, job_id: UUID):
        """Resume a paused job."""
        try:
            self._scheduler.resume_job(str(job_id))
            logger.info(f"▶️  Scheduled job resumed: {job_id}")
        except Exception as e:
            logger.error(f"Failed to resume scheduled job {job_id}: {e}")
            raise
    
    async def update_schedule(self, scheduled_job: ScheduledJob):
        """Update an existing scheduled job."""
        try:
            # Remove old job
            await self.remove_schedule(scheduled_job.id)
            
            # Add updated job if still enabled
            if scheduled_job.enabled:
                await self.add_schedule(scheduled_job)
            
            logger.info(f"🔄 Scheduled job updated: {scheduled_job.name}")
        except Exception as e:
            logger.error(f"Failed to update scheduled job {scheduled_job.id}: {e}")
            raise
    
    def _create_trigger(self, scheduled_job: ScheduledJob):
        """Create appropriate APScheduler trigger based on schedule type."""
        tz = pytz.timezone(scheduled_job.timezone)
        
        if scheduled_job.schedule_type == 'cron':
            # Validate cron expression
            if not croniter.is_valid(scheduled_job.cron_expression):
                raise ValueError(f"Invalid cron expression: {scheduled_job.cron_expression}")
            
            return CronTrigger.from_crontab(
                scheduled_job.cron_expression,
                timezone=tz
            )
        
        elif scheduled_job.schedule_type == 'interval':
            return IntervalTrigger(
                seconds=scheduled_job.interval_seconds,
                timezone=tz,
                start_date=scheduled_job.start_date,
                end_date=scheduled_job.end_date
            )
        
        elif scheduled_job.schedule_type == 'date':
            if not scheduled_job.start_date:
                raise ValueError("start_date is required for date-based schedules")
            
            return DateTrigger(
                run_date=scheduled_job.start_date,
                timezone=tz
            )
        
        else:
            raise ValueError(f"Unknown schedule type: {scheduled_job.schedule_type}")


# Module-level function for APScheduler callback (must be serializable)
async def _execute_scheduled_runbook(
    scheduled_job_id: str,
    runbook_id: str,
    server_id: Optional[str] = None,
    server_ids: Optional[list] = None,
    group_ids: Optional[list] = None,
    params: Optional[dict] = None
):
    """
    Execute a runbook as part of a scheduled job.
    This is the callback function invoked by APScheduler.
    Must be a module-level function to be serializable.
    Supports multi-server execution via server_ids / group_ids.
    """
    execution_start = datetime.utcnow()
    overall_status = "failed"
    error_message = None

    try:
        logger.info(f"🚀 Executing scheduled runbook: {runbook_id} (Schedule: {scheduled_job_id})")

        # Import here to avoid circular dependencies
        from ..models_remediation import Runbook
        from uuid import uuid4

        # Resolve target server list
        async for db in get_async_db():
            from sqlalchemy.orm import selectinload

            # Collect servers from multi-server fields
            resolved_ids: list = list(server_ids or [])

            # Expand group IDs into server IDs
            if group_ids:
                from ..models import ServerCredential
                for gid in group_ids:
                    try:
                        members_result = await db.execute(
                            select(ServerCredential.id).where(
                                ServerCredential.group_id == gid
                            )
                        )
                        resolved_ids.extend([str(r) for r in members_result.scalars().all()])
                    except Exception as ge:
                        logger.warning(f"Failed to resolve group {gid}: {ge}")

            # Deduplicate while preserving order
            seen: set = set()
            unique_ids: list = []
            for sid in resolved_ids:
                if sid not in seen:
                    seen.add(sid)
                    unique_ids.append(sid)

            # Fall back to legacy single server_id or None (runbook default)
            if not unique_ids:
                unique_ids = [server_id] if server_id else [None]

            runbook = await db.execute(
                select(Runbook)
                .options(selectinload(Runbook.steps))
                .where(Runbook.id == UUID(runbook_id))
            )
            runbook = runbook.scalar_one_or_none()

            if not runbook:
                raise ValueError(f"Runbook {runbook_id} not found")

            # Determine initial status based on approval requirements
            if runbook.approval_required:
                initial_status = "pending"
                from datetime import timezone
                now_utc = datetime.now(timezone.utc)
                approval_expires = now_utc + timedelta(minutes=runbook.approval_timeout_minutes or 30)
            else:
                initial_status = "running"
                approval_expires = None

            from datetime import timezone
            now_utc = datetime.now(timezone.utc)

            # Create one execution per target server
            execution_ids = []
            for target_sid in unique_ids:
                execution = RunbookExecution(
                    id=uuid4(),
                    runbook_id=UUID(runbook_id),
                    runbook_version=runbook.version,
                    execution_mode="auto",
                    status=initial_status,
                    triggered_by_system=True,
                    server_id=UUID(target_sid) if target_sid else runbook.default_server_id,
                    dry_run=False,
                    variables_json=params,
                    approval_required=runbook.approval_required,
                    approval_token=str(uuid4()) if runbook.approval_required else None,
                    approval_requested_at=now_utc if runbook.approval_required else None,
                    approval_expires_at=approval_expires,
                    started_at=now_utc if initial_status == "running" else None,
                    steps_total=len(runbook.steps) if runbook.steps else 0,
                    queued_at=now_utc
                )
                db.add(execution)
                await db.flush()
                execution_ids.append(execution.id)

            await db.commit()
            overall_status = "success"
            logger.info(f"✅ Scheduled runbook queued on {len(unique_ids)} target(s): {execution_ids}")

            # Update scheduled job statistics
            await db.execute(
                update(ScheduledJob)
                .where(ScheduledJob.id == UUID(scheduled_job_id))
                .values(
                    last_run_at=execution_start,
                    last_run_status=overall_status,
                    run_count=ScheduledJob.run_count + len(unique_ids)
                )
            )

            # Record execution in history (one entry per execution)
            for exec_id in execution_ids:
                history = ScheduleExecutionHistory(
                    scheduled_job_id=UUID(scheduled_job_id),
                    runbook_execution_id=exec_id,
                    scheduled_at=execution_start,
                    executed_at=execution_start,
                    completed_at=datetime.utcnow(),
                    status=overall_status,
                    error_message=error_message,
                    duration_ms=int((datetime.utcnow() - execution_start).total_seconds() * 1000)
                )
                db.add(history)

            await db.commit()
            break  # Exit the async for loop
            
    except Exception as e:
        logger.error(f"❌ Scheduled runbook execution failed: {e}", exc_info=True)
        error_message = str(e)
        overall_status = "failed"
        
        # Still record the failure in history
        async for db in get_async_db():
            history = ScheduleExecutionHistory(
                scheduled_job_id=UUID(scheduled_job_id),
                scheduled_at=execution_start,
                executed_at=execution_start,
                completed_at=datetime.utcnow(),
                status="failed",
                error_message=error_message,
                duration_ms=int((datetime.utcnow() - execution_start).total_seconds() * 1000)
            )
            db.add(history)
            
            # Update failure count
            await db.execute(
                update(ScheduledJob)
                .where(ScheduledJob.id == UUID(scheduled_job_id))
                .values(
                    last_run_at=execution_start,
                    last_run_status="failed",
                    failure_count=ScheduledJob.failure_count + 1
                )
            )
            
            await db.commit()
            break


# Global scheduler instance
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler() -> SchedulerService:
    """Get the global scheduler service instance."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService.get_instance()
    return _scheduler_service
