"""
Scheduler API Router

REST API endpoints for managing scheduled runbook executions.
"""

from typing import List, Optional
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_async_db
from ..models import User
from ..models_scheduler import ScheduledJob, ScheduleExecutionHistory
from ..models_remediation import Runbook
from ..schemas_scheduler import (
    ScheduledJobCreate,
    ScheduledJobUpdate,
    ScheduledJobResponse,
    ScheduleExecutionHistoryResponse,
    SchedulerStatsResponse
)
from ..services.auth_service import get_current_user, require_permission, require_role
from ..services.scheduler_service import get_scheduler

router = APIRouter(prefix="/api/schedules", tags=["Scheduler"])


@router.post("", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: ScheduledJobCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Create a new scheduled job for a runbook."""
    # Verify runbook exists
    runbook_result = await db.execute(
        select(Runbook).where(Runbook.id == schedule_data.runbook_id)
    )
    runbook = runbook_result.scalar_one_or_none()
    
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {schedule_data.runbook_id} not found"
        )
    
    # Check for duplicate name
    existing = await db.execute(
        select(ScheduledJob).where(ScheduledJob.name == schedule_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule with name '{schedule_data.name}' already exists"
        )
    
    # Create scheduled job
    scheduled_job = ScheduledJob(
        runbook_id=schedule_data.runbook_id,
        name=schedule_data.name,
        description=schedule_data.description,
        schedule_type=schedule_data.schedule_type,
        cron_expression=schedule_data.cron_expression,
        interval_seconds=schedule_data.interval_seconds,
        start_date=schedule_data.start_date,
        end_date=schedule_data.end_date,
        timezone=schedule_data.timezone,
        target_server_id=schedule_data.target_server_id,
        execution_params=schedule_data.execution_params,
        max_instances=schedule_data.max_instances,
        misfire_grace_time=schedule_data.misfire_grace_time,
        enabled=schedule_data.enabled,
        created_by=current_user.id
    )
    
    db.add(scheduled_job)
    await db.commit()
    await db.refresh(scheduled_job)
    
    # Add to scheduler if enabled
    if scheduled_job.enabled:
        try:
            scheduler = get_scheduler()
            await scheduler.add_schedule(scheduled_job)
        except Exception as e:
            # Rollback if scheduler fails
            await db.delete(scheduled_job)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add schedule to scheduler: {str(e)}"
            )
    
    # Build response with related data
    return await _build_schedule_response(db, scheduled_job)


@router.get("", response_model=List[ScheduledJobResponse])
async def list_schedules(
    runbook_id: Optional[UUID] = None,
    enabled: Optional[bool] = None,
    schedule_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """List all scheduled jobs with optional filtering."""
    query = select(ScheduledJob)
    
    # Apply filters
    conditions = []
    if runbook_id:
        conditions.append(ScheduledJob.runbook_id == runbook_id)
    if enabled is not None:
        conditions.append(ScheduledJob.enabled == enabled)
    if schedule_type:
        conditions.append(ScheduledJob.schedule_type == schedule_type)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(ScheduledJob.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    schedules = result.scalars().all()
    
    # Build responses with related data
    responses = []
    for schedule in schedules:
        responses.append(await _build_schedule_response(db, schedule))
    
    return responses


@router.get("/{schedule_id}", response_model=ScheduledJobResponse)
async def get_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get details of a specific scheduled job."""
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    return await _build_schedule_response(db, schedule)


@router.put("/{schedule_id}", response_model=ScheduledJobResponse)
async def update_schedule(
    schedule_id: UUID,
    schedule_data: ScheduledJobUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Update an existing scheduled job."""
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    # Update fields
    update_data = schedule_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)
    
    schedule.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(schedule)
    
    # Update in scheduler
    try:
        scheduler = get_scheduler()
        await scheduler.update_schedule(schedule)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update schedule in scheduler: {str(e)}"
        )
    
    return await _build_schedule_response(db, schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Delete a scheduled job."""
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    # Remove from scheduler first
    try:
        scheduler = get_scheduler()
        await scheduler.remove_schedule(schedule_id)
    except Exception:
        pass  # Continue even if removal fails (schedule might not be in scheduler)
    
    # Delete from database
    await db.delete(schedule)
    await db.commit()


@router.post("/{schedule_id}/pause", response_model=ScheduledJobResponse)
async def pause_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer", "operator"]))
):
    """Pause a scheduled job."""
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    schedule.enabled = False
    schedule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Pause in scheduler
    try:
        scheduler = get_scheduler()
        await scheduler.pause_schedule(schedule_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause schedule: {str(e)}"
        )
    
    return await _build_schedule_response(db, schedule)


@router.post("/{schedule_id}/resume", response_model=ScheduledJobResponse)
async def resume_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer", "operator"]))
):
    """Resume a paused scheduled job."""
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    schedule.enabled = True
    schedule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Resume in scheduler
    try:
        scheduler = get_scheduler()
        await scheduler.resume_schedule(schedule_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume schedule: {str(e)}"
        )
    
    return await _build_schedule_response(db, schedule)


@router.post("/{schedule_id}/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_schedule_now(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer", "operator"]))
):
    """Trigger immediate execution of a scheduled job (outside its normal schedule)."""
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    # Import the callback function
    from ..services.scheduler_service import _execute_scheduled_runbook
    
    # Manually invoke the execution
    try:
        # Execute immediately
        await _execute_scheduled_runbook(
            scheduled_job_id=str(schedule.id),
            runbook_id=str(schedule.runbook_id),
            server_id=str(schedule.target_server_id) if schedule.target_server_id else None,
            params=schedule.execution_params
        )
        
        return {"message": "Schedule triggered successfully", "schedule_id": schedule_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger schedule: {str(e)}"
        )


@router.get("/{schedule_id}/history", response_model=List[ScheduleExecutionHistoryResponse])
async def get_schedule_history(
    schedule_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get execution history for a scheduled job."""
    # Verify schedule exists
    schedule_result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == schedule_id)
    )
    if not schedule_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    # Get history
    query = select(ScheduleExecutionHistory).where(
        ScheduleExecutionHistory.scheduled_job_id == schedule_id
    ).order_by(ScheduleExecutionHistory.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    history = result.scalars().all()
    
    return history


@router.get("/stats/summary", response_model=SchedulerStatsResponse)
async def get_scheduler_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get scheduler statistics and health information."""
    # Count schedules
    total_count = await db.scalar(select(func.count()).select_from(ScheduledJob))
    enabled_count = await db.scalar(
        select(func.count()).select_from(ScheduledJob).where(ScheduledJob.enabled == True)
    )
    
    # Get today's execution counts
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_total = await db.scalar(
        select(func.count()).select_from(ScheduleExecutionHistory)
        .where(ScheduleExecutionHistory.created_at >= today_start)
    )
    
    today_success = await db.scalar(
        select(func.count()).select_from(ScheduleExecutionHistory)
        .where(
            and_(
                ScheduleExecutionHistory.created_at >= today_start,
                ScheduleExecutionHistory.status == "success"
            )
        )
    )
    
    today_failed = await db.scalar(
        select(func.count()).select_from(ScheduleExecutionHistory)
        .where(
            and_(
                ScheduleExecutionHistory.created_at >= today_start,
                ScheduleExecutionHistory.status == "failed"
            )
        )
    )
    
    # Get next scheduled run
    next_run_result = await db.execute(
        select(ScheduledJob.next_run_at)
        .where(and_(ScheduledJob.enabled == True, ScheduledJob.next_run_at.isnot(None)))
        .order_by(ScheduledJob.next_run_at.asc())
        .limit(1)
    )
    next_run = next_run_result.scalar_one_or_none()
    
    # Check scheduler status
    scheduler = get_scheduler()
    scheduler_running = scheduler._scheduler.running if scheduler._scheduler else False
    
    return SchedulerStatsResponse(
        total_schedules=total_count or 0,
        enabled_schedules=enabled_count or 0,
        disabled_schedules=(total_count or 0) - (enabled_count or 0),
        total_executions_today=today_total or 0,
        successful_executions_today=today_success or 0,
        failed_executions_today=today_failed or 0,
        next_scheduled_run=next_run,
        scheduler_running=scheduler_running
    )


async def _build_schedule_response(db: AsyncSession, schedule: ScheduledJob) -> ScheduledJobResponse:
    """Build a complete schedule response with related data."""
    # Get runbook name
    runbook_result = await db.execute(
        select(Runbook.name).where(Runbook.id == schedule.runbook_id)
    )
    runbook_name = runbook_result.scalar_one_or_none()
    
    # Get server hostname if applicable
    server_hostname = None
    if schedule.target_server_id:
        from ..models import ServerCredential
        server_result = await db.execute(
            select(ServerCredential.hostname).where(ServerCredential.id == schedule.target_server_id)
        )
        server_hostname = server_result.scalar_one_or_none()
    
    return ScheduledJobResponse(
        id=schedule.id,
        runbook_id=schedule.runbook_id,
        runbook_name=runbook_name,
        name=schedule.name,
        description=schedule.description,
        schedule_type=schedule.schedule_type,
        cron_expression=schedule.cron_expression,
        interval_seconds=schedule.interval_seconds,
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        timezone=schedule.timezone,
        target_server_id=schedule.target_server_id,
        server_hostname=server_hostname,
        execution_params=schedule.execution_params,
        max_instances=schedule.max_instances,
        misfire_grace_time=schedule.misfire_grace_time,
        enabled=schedule.enabled,
        last_run_at=schedule.last_run_at,
        last_run_status=schedule.last_run_status,
        next_run_at=schedule.next_run_at,
        run_count=schedule.run_count,
        failure_count=schedule.failure_count,
        created_by=schedule.created_by,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at
    )
