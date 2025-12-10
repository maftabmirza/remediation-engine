"""
Auto-Remediation API Router

Provides CRUD operations for runbooks, triggers, executions, and safety controls.
Supports IaC import/export via YAML format.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import yaml

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_async_db
from ..models import User, ServerCredential
from ..models_remediation import (
    Runbook, RunbookStep, RunbookTrigger,
    RunbookExecution, StepExecution, CircuitBreaker, BlackoutWindow
)
from ..schemas_remediation import (
    RunbookCreate, RunbookUpdate, RunbookResponse, RunbookListResponse,
    RunbookStepCreate, RunbookStepResponse,
    RunbookTriggerCreate, RunbookTriggerResponse,
    ExecuteRunbookRequest, RunbookExecutionResponse, ExecutionListResponse,
    ApprovalRequest, StepExecutionResponse,
    BlackoutWindowCreate, BlackoutWindowUpdate, BlackoutWindowResponse,
    CircuitBreakerResponse, CircuitBreakerOverride,
    ImportRunbookRequest, ImportRunbookResponse,
    RunbookYAML
)
from ..services.auth_service import get_current_user, require_role

router = APIRouter(prefix="/api/remediation", tags=["Auto-Remediation"])


def utc_now():
    """Return current UTC time."""
    return datetime.now(timezone.utc)


# ============================================================================
# RUNBOOKS CRUD
# ============================================================================

@router.get("/runbooks", response_model=List[RunbookListResponse])
async def list_runbooks(
    enabled: Optional[bool] = None,
    auto_execute: Optional[bool] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """List all runbooks with optional filtering."""
    query = select(Runbook).options(
        selectinload(Runbook.steps),
        selectinload(Runbook.triggers),
        selectinload(Runbook.executions)
    )
    
    # Apply filters
    conditions = []
    if enabled is not None:
        conditions.append(Runbook.enabled == enabled)
    if auto_execute is not None:
        conditions.append(Runbook.auto_execute == auto_execute)
    if category:
        conditions.append(Runbook.category == category)
    if search:
        conditions.append(
            or_(
                Runbook.name.ilike(f"%{search}%"),
                Runbook.description.ilike(f"%{search}%")
            )
        )
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(Runbook.name).offset(skip).limit(limit)
    result = await db.execute(query)
    runbooks = result.scalars().all()
    
    # Build response with counts
    response = []
    for rb in runbooks:
        response.append(RunbookListResponse(
            id=rb.id,
            name=rb.name,
            description=rb.description,
            category=rb.category,
            tags=rb.tags or [],
            enabled=rb.enabled,
            auto_execute=rb.auto_execute,
            approval_required=rb.approval_required,
            version=rb.version,
            created_at=rb.created_at,
            updated_at=rb.updated_at,
            steps_count=len(rb.steps) if rb.steps else 0,
            triggers_count=len(rb.triggers) if rb.triggers else 0,
            executions_count=len(rb.executions) if rb.executions else 0
        ))
    
    return response


@router.post("/runbooks", response_model=RunbookResponse, status_code=status.HTTP_201_CREATED)
async def create_runbook(
    runbook_data: RunbookCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Create a new runbook with steps and triggers."""
    # Check for duplicate name
    existing = await db.execute(
        select(Runbook).where(Runbook.name == runbook_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Runbook with name '{runbook_data.name}' already exists"
        )
    
    # Create runbook
    runbook = Runbook(
        name=runbook_data.name,
        description=runbook_data.description,
        category=runbook_data.category,
        tags=runbook_data.tags,
        enabled=runbook_data.enabled,
        auto_execute=runbook_data.auto_execute,
        approval_required=runbook_data.approval_required,
        approval_roles=runbook_data.approval_roles,
        approval_timeout_minutes=runbook_data.approval_timeout_minutes,
        max_executions_per_hour=runbook_data.max_executions_per_hour,
        cooldown_minutes=runbook_data.cooldown_minutes,
        default_server_id=runbook_data.default_server_id,
        target_os_filter=runbook_data.target_os_filter,
        target_from_alert=runbook_data.target_from_alert,
        target_alert_label=runbook_data.target_alert_label,
        notifications_json=runbook_data.notifications_json,
        documentation_url=runbook_data.documentation_url,
        created_by=current_user.id,
        source="ui"
    )
    db.add(runbook)
    await db.flush()  # Get runbook.id
    
    # Create steps
    for step_data in runbook_data.steps:
        step = RunbookStep(
            runbook_id=runbook.id,
            step_order=step_data.step_order,
            name=step_data.name,
            description=step_data.description,
            command_linux=step_data.command_linux,
            command_windows=step_data.command_windows,
            target_os=step_data.target_os,
            timeout_seconds=step_data.timeout_seconds,
            requires_elevation=step_data.requires_elevation,
            working_directory=step_data.working_directory,
            environment_json=step_data.environment_json,
            continue_on_fail=step_data.continue_on_fail,
            retry_count=step_data.retry_count,
            retry_delay_seconds=step_data.retry_delay_seconds,
            expected_exit_code=step_data.expected_exit_code,
            expected_output_pattern=step_data.expected_output_pattern,
            rollback_command_linux=step_data.rollback_command_linux,
            rollback_command_windows=step_data.rollback_command_windows
        )
        db.add(step)
    
    # Create triggers
    for trigger_data in runbook_data.triggers:
        trigger = RunbookTrigger(
            runbook_id=runbook.id,
            alert_name_pattern=trigger_data.alert_name_pattern,
            severity_pattern=trigger_data.severity_pattern,
            instance_pattern=trigger_data.instance_pattern,
            job_pattern=trigger_data.job_pattern,
            label_matchers_json=trigger_data.label_matchers_json,
            annotation_matchers_json=trigger_data.annotation_matchers_json,
            min_duration_seconds=trigger_data.min_duration_seconds,
            min_occurrences=trigger_data.min_occurrences,
            priority=trigger_data.priority,
            enabled=trigger_data.enabled
        )
        db.add(trigger)
    
    # Create initial circuit breaker (closed state)
    circuit_breaker = CircuitBreaker(
        scope="runbook",
        scope_id=runbook.id,
        state="closed"
    )
    db.add(circuit_breaker)
    
    await db.commit()
    
    # Reload with relationships
    result = await db.execute(
        select(Runbook)
        .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
        .where(Runbook.id == runbook.id)
    )
    return result.scalar_one()


@router.get("/runbooks/{runbook_id}", response_model=RunbookResponse)
async def get_runbook(
    runbook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get a runbook by ID with steps and triggers."""
    result = await db.execute(
        select(Runbook)
        .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
        .where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one_or_none()
    
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )
    
    return runbook


@router.put("/runbooks/{runbook_id}", response_model=RunbookResponse)
async def update_runbook(
    runbook_id: UUID,
    runbook_data: RunbookCreate,  # Changed to RunbookCreate to allow steps/triggers update
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Update a runbook with steps and triggers. Increments version number."""
    try:
        result = await db.execute(
            select(Runbook)
            .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
            .where(Runbook.id == runbook_id)
        )
        runbook = result.scalar_one_or_none()

        if not runbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Runbook {runbook_id} not found"
            )

        # Check name uniqueness if changing
        if runbook_data.name and runbook_data.name != runbook.name:
            existing = await db.execute(
                select(Runbook).where(
                    and_(Runbook.name == runbook_data.name, Runbook.id != runbook_id)
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Runbook with name '{runbook_data.name}' already exists"
                )

        # Update runbook fields
        runbook.name = runbook_data.name
        runbook.description = runbook_data.description
        runbook.category = runbook_data.category
        runbook.tags = runbook_data.tags
        runbook.enabled = runbook_data.enabled
        runbook.auto_execute = runbook_data.auto_execute
        runbook.approval_required = runbook_data.approval_required
        runbook.approval_roles = runbook_data.approval_roles
        runbook.approval_timeout_minutes = runbook_data.approval_timeout_minutes
        runbook.max_executions_per_hour = runbook_data.max_executions_per_hour
        runbook.cooldown_minutes = runbook_data.cooldown_minutes
        runbook.default_server_id = runbook_data.default_server_id
        runbook.target_os_filter = runbook_data.target_os_filter
        runbook.target_from_alert = runbook_data.target_from_alert
        runbook.target_alert_label = runbook_data.target_alert_label
        runbook.notifications_json = runbook_data.notifications_json
        runbook.documentation_url = runbook_data.documentation_url

        # Delete existing steps and triggers
        # First, delete step_executions that reference these steps to avoid FK violation
        for step in list(runbook.steps):
            # Delete step executions that reference this step
            await db.execute(
                select(StepExecution).where(StepExecution.step_id == step.id)
            )
            step_execs_result = await db.execute(
                select(StepExecution).where(StepExecution.step_id == step.id)
            )
            step_execs = step_execs_result.scalars().all()
            for step_exec in step_execs:
                await db.delete(step_exec)
            
            # Now safe to delete the step
            await db.delete(step)
            
        for trigger in list(runbook.triggers):
            # Detach executions from this trigger before deletion to avoid FK violation
            await db.execute(
                update(RunbookExecution)
                .where(RunbookExecution.trigger_id == trigger.id)
                .values(trigger_id=None)
            )
            await db.delete(trigger)

        await db.flush()

        # Create new steps
        for step_data in runbook_data.steps:
            step = RunbookStep(
                runbook_id=runbook.id,
                step_order=step_data.step_order,
                name=step_data.name,
                description=step_data.description,
                command_linux=step_data.command_linux,
                command_windows=step_data.command_windows,
                target_os=step_data.target_os,
                timeout_seconds=step_data.timeout_seconds,
                requires_elevation=step_data.requires_elevation,
                working_directory=step_data.working_directory,
                environment_json=step_data.environment_json,
                continue_on_fail=step_data.continue_on_fail,
                retry_count=step_data.retry_count,
                retry_delay_seconds=step_data.retry_delay_seconds,
                expected_exit_code=step_data.expected_exit_code,
                expected_output_pattern=step_data.expected_output_pattern,
                rollback_command_linux=step_data.rollback_command_linux,
                rollback_command_windows=step_data.rollback_command_windows
            )
            db.add(step)

        # Create new triggers
        for trigger_data in runbook_data.triggers:
            trigger = RunbookTrigger(
                runbook_id=runbook.id,
                alert_name_pattern=trigger_data.alert_name_pattern,
                severity_pattern=trigger_data.severity_pattern,
                instance_pattern=trigger_data.instance_pattern,
                job_pattern=trigger_data.job_pattern,
                label_matchers_json=trigger_data.label_matchers_json,
                annotation_matchers_json=trigger_data.annotation_matchers_json,
                min_duration_seconds=trigger_data.min_duration_seconds,
                min_occurrences=trigger_data.min_occurrences,
                priority=trigger_data.priority,
                enabled=trigger_data.enabled
            )
            db.add(trigger)

        # Increment version
        runbook.version += 1

        await db.commit()

        # Reload with relationships
        result = await db.execute(
            select(Runbook)
            .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
            .where(Runbook.id == runbook_id)
        )
        return result.scalar_one()
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        await db.rollback()
        raise
    except Exception as e:
        # Catch all other exceptions and return proper JSON error
        await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Unexpected error updating runbook {runbook_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error updating runbook: {str(e)}"
        )


@router.delete("/runbooks/{runbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_runbook(
    runbook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Delete a runbook. Only admins can delete."""
    result = await db.execute(
        select(Runbook).where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one_or_none()

    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )

    await db.delete(runbook)
    await db.commit()


@router.post("/runbooks/{runbook_id}/clone", response_model=RunbookResponse, status_code=status.HTTP_201_CREATED)
async def clone_runbook(
    runbook_id: UUID,
    new_name: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Clone/duplicate an existing runbook with all its steps and triggers."""
    # Load original runbook
    result = await db.execute(
        select(Runbook)
        .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
        .where(Runbook.id == runbook_id)
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )

    # Generate unique name
    clone_name = new_name if new_name else f"{original.name} (Copy)"
    counter = 1
    while True:
        existing = await db.execute(
            select(Runbook).where(Runbook.name == clone_name)
        )
        if not existing.scalar_one_or_none():
            break
        clone_name = f"{original.name} (Copy {counter})"
        counter += 1

    # Create cloned runbook
    cloned_runbook = Runbook(
        name=clone_name,
        description=original.description,
        category=original.category,
        tags=original.tags,
        enabled=False,  # Start as disabled for safety
        auto_execute=False,  # Disable auto-execute for clones
        approval_required=original.approval_required,
        approval_roles=original.approval_roles,
        approval_timeout_minutes=original.approval_timeout_minutes,
        max_executions_per_hour=original.max_executions_per_hour,
        cooldown_minutes=original.cooldown_minutes,
        default_server_id=original.default_server_id,
        target_os_filter=original.target_os_filter,
        target_from_alert=original.target_from_alert,
        target_alert_label=original.target_alert_label,
        notifications_json=original.notifications_json,
        documentation_url=original.documentation_url,
        created_by=current_user.id,
        source="ui"
    )
    db.add(cloned_runbook)
    await db.flush()

    # Clone steps
    for step in original.steps:
        cloned_step = RunbookStep(
            runbook_id=cloned_runbook.id,
            step_order=step.step_order,
            name=step.name,
            description=step.description,
            command_linux=step.command_linux,
            command_windows=step.command_windows,
            target_os=step.target_os,
            timeout_seconds=step.timeout_seconds,
            requires_elevation=step.requires_elevation,
            working_directory=step.working_directory,
            environment_json=step.environment_json,
            continue_on_fail=step.continue_on_fail,
            retry_count=step.retry_count,
            retry_delay_seconds=step.retry_delay_seconds,
            expected_exit_code=step.expected_exit_code,
            expected_output_pattern=step.expected_output_pattern,
            rollback_command_linux=step.rollback_command_linux,
            rollback_command_windows=step.rollback_command_windows
        )
        db.add(cloned_step)

    # Clone triggers
    for trigger in original.triggers:
        cloned_trigger = RunbookTrigger(
            runbook_id=cloned_runbook.id,
            alert_name_pattern=trigger.alert_name_pattern,
            severity_pattern=trigger.severity_pattern,
            instance_pattern=trigger.instance_pattern,
            job_pattern=trigger.job_pattern,
            label_matchers_json=trigger.label_matchers_json,
            annotation_matchers_json=trigger.annotation_matchers_json,
            min_duration_seconds=trigger.min_duration_seconds,
            min_occurrences=trigger.min_occurrences,
            priority=trigger.priority,
            enabled=trigger.enabled
        )
        db.add(cloned_trigger)

    # Create circuit breaker
    circuit_breaker = CircuitBreaker(
        scope="runbook",
        scope_id=cloned_runbook.id,
        state="closed"
    )
    db.add(circuit_breaker)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Runbook)
        .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
        .where(Runbook.id == cloned_runbook.id)
    )
    return result.scalar_one()


@router.get("/runbooks/{runbook_id}/executions", response_model=List[ExecutionListResponse])
async def get_runbook_executions(
    runbook_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent execution history for a specific runbook."""
    # Verify runbook exists
    result = await db.execute(
        select(Runbook).where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one_or_none()

    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )

    # Get executions
    query = select(RunbookExecution).options(
        selectinload(RunbookExecution.runbook),
        selectinload(RunbookExecution.server)
    ).where(
        RunbookExecution.runbook_id == runbook_id
    ).order_by(
        RunbookExecution.queued_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    executions = result.scalars().all()

    # Build response
    response = []
    for ex in executions:
        response.append(ExecutionListResponse(
            id=ex.id,
            runbook_id=ex.runbook_id,
            runbook_name=ex.runbook.name if ex.runbook else "Unknown",
            alert_id=ex.alert_id,
            server_hostname=ex.server.hostname if ex.server else None,
            execution_mode=ex.execution_mode,
            status=ex.status,
            dry_run=ex.dry_run,
            queued_at=ex.queued_at,
            started_at=ex.started_at,
            completed_at=ex.completed_at,
            steps_total=ex.steps_total,
            steps_completed=ex.steps_completed,
            steps_failed=ex.steps_failed
        ))

    return response


@router.post("/runbooks/bulk-action")
async def bulk_runbook_action(
    runbook_ids: List[UUID],
    action: str = Query(..., regex="^(enable|disable|delete)$"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Perform bulk actions on multiple runbooks.
    Actions: enable, disable, delete
    """
    if not runbook_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No runbook IDs provided"
        )

    # Fetch runbooks
    result = await db.execute(
        select(Runbook).where(Runbook.id.in_(runbook_ids))
    )
    runbooks = result.scalars().all()

    if len(runbooks) != len(runbook_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more runbooks not found"
        )

    # Perform action
    affected_count = 0
    if action == "enable":
        for runbook in runbooks:
            runbook.enabled = True
            affected_count += 1
    elif action == "disable":
        for runbook in runbooks:
            runbook.enabled = False
            runbook.auto_execute = False  # Also disable auto-execute for safety
            affected_count += 1
    elif action == "delete":
        # Only admins can delete
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can delete runbooks"
            )
        for runbook in runbooks:
            await db.delete(runbook)
            affected_count += 1

    await db.commit()

    return {
        "success": True,
        "action": action,
        "affected_count": affected_count,
        "message": f"Successfully {action}d {affected_count} runbook(s)"
    }


# ============================================================================
# RUNBOOK STEPS
# ============================================================================

@router.post("/runbooks/{runbook_id}/steps", response_model=RunbookStepResponse)
async def add_step(
    runbook_id: UUID,
    step_data: RunbookStepCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Add a step to a runbook."""
    result = await db.execute(
        select(Runbook).where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one_or_none()
    
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )
    
    step = RunbookStep(
        runbook_id=runbook_id,
        step_order=step_data.step_order,
        name=step_data.name,
        description=step_data.description,
        command_linux=step_data.command_linux,
        command_windows=step_data.command_windows,
        target_os=step_data.target_os,
        timeout_seconds=step_data.timeout_seconds,
        requires_elevation=step_data.requires_elevation,
        working_directory=step_data.working_directory,
        environment_json=step_data.environment_json,
        continue_on_fail=step_data.continue_on_fail,
        retry_count=step_data.retry_count,
        retry_delay_seconds=step_data.retry_delay_seconds,
        expected_exit_code=step_data.expected_exit_code,
        expected_output_pattern=step_data.expected_output_pattern,
        rollback_command_linux=step_data.rollback_command_linux,
        rollback_command_windows=step_data.rollback_command_windows
    )
    db.add(step)
    
    # Increment runbook version
    runbook.version += 1
    
    await db.commit()
    await db.refresh(step)
    
    return step


@router.delete("/runbooks/{runbook_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    runbook_id: UUID,
    step_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Remove a step from a runbook."""
    result = await db.execute(
        select(RunbookStep).where(
            and_(RunbookStep.id == step_id, RunbookStep.runbook_id == runbook_id)
        )
    )
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step {step_id} not found"
        )
    
    # Increment runbook version
    result = await db.execute(
        select(Runbook).where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one()
    runbook.version += 1
    
    await db.delete(step)
    await db.commit()


# ============================================================================
# TRIGGERS
# ============================================================================

@router.post("/runbooks/{runbook_id}/triggers", response_model=RunbookTriggerResponse)
async def add_trigger(
    runbook_id: UUID,
    trigger_data: RunbookTriggerCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Add a trigger to a runbook."""
    result = await db.execute(
        select(Runbook).where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one_or_none()
    
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )
    
    trigger = RunbookTrigger(
        runbook_id=runbook_id,
        alert_name_pattern=trigger_data.alert_name_pattern,
        severity_pattern=trigger_data.severity_pattern,
        instance_pattern=trigger_data.instance_pattern,
        job_pattern=trigger_data.job_pattern,
        label_matchers_json=trigger_data.label_matchers_json,
        annotation_matchers_json=trigger_data.annotation_matchers_json,
        min_duration_seconds=trigger_data.min_duration_seconds,
        min_occurrences=trigger_data.min_occurrences,
        priority=trigger_data.priority,
        enabled=trigger_data.enabled
    )
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    
    return trigger


@router.delete("/runbooks/{runbook_id}/triggers/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    runbook_id: UUID,
    trigger_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Remove a trigger from a runbook."""
    result = await db.execute(
        select(RunbookTrigger).where(
            and_(RunbookTrigger.id == trigger_id, RunbookTrigger.runbook_id == runbook_id)
        )
    )
    trigger = result.scalar_one_or_none()
    
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found"
        )
    
    await db.delete(trigger)
    await db.commit()


# ============================================================================
# IaC IMPORT/EXPORT
# ============================================================================

@router.get("/runbooks/{runbook_id}/export", response_class=Response)
async def export_runbook_yaml(
    runbook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Export a runbook as YAML for version control."""
    result = await db.execute(
        select(Runbook)
        .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
        .where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one_or_none()
    
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )
    
    # Build YAML structure
    yaml_data = {
        "apiVersion": "aiops.io/v1",
        "kind": "Runbook",
        "metadata": {
            "name": runbook.name,
            "description": runbook.description,
            "category": runbook.category,
            "tags": runbook.tags or [],
            "documentation_url": runbook.documentation_url
        },
        "spec": {
            "execution": {
                "auto_execute": runbook.auto_execute,
                "approval_required": runbook.approval_required,
                "approval_roles": runbook.approval_roles or ["admin", "engineer"],
                "approval_timeout_minutes": runbook.approval_timeout_minutes
            },
            "safety": {
                "max_executions_per_hour": runbook.max_executions_per_hour,
                "cooldown_minutes": runbook.cooldown_minutes
            },
            "target": {
                "os_filter": runbook.target_os_filter or ["linux", "windows"],
                "from_alert": runbook.target_from_alert,
                "alert_label": runbook.target_alert_label
            },
            "notifications": runbook.notifications_json or {}
        },
        "triggers": [],
        "steps": []
    }
    
    # Add triggers
    for trigger in runbook.triggers:
        yaml_data["triggers"].append({
            "alert_name_pattern": trigger.alert_name_pattern,
            "severity_pattern": trigger.severity_pattern,
            "instance_pattern": trigger.instance_pattern,
            "job_pattern": trigger.job_pattern,
            "label_matchers": trigger.label_matchers_json or {},
            "min_duration_seconds": trigger.min_duration_seconds,
            "min_occurrences": trigger.min_occurrences,
            "priority": trigger.priority,
            "enabled": trigger.enabled
        })
    
    # Add steps
    for step in sorted(runbook.steps, key=lambda s: s.step_order):
        step_data = {
            "name": step.name,
            "description": step.description,
            "target_os": step.target_os
        }
        if step.command_linux:
            step_data["command_linux"] = step.command_linux
        if step.command_windows:
            step_data["command_windows"] = step.command_windows
        step_data.update({
            "timeout_seconds": step.timeout_seconds,
            "requires_elevation": step.requires_elevation,
            "continue_on_fail": step.continue_on_fail,
            "retry_count": step.retry_count,
            "expected_exit_code": step.expected_exit_code
        })
        if step.expected_output_pattern:
            step_data["expected_output_pattern"] = step.expected_output_pattern
        if step.rollback_command_linux:
            step_data["rollback_command_linux"] = step.rollback_command_linux
        if step.rollback_command_windows:
            step_data["rollback_command_windows"] = step.rollback_command_windows
        
        yaml_data["steps"].append(step_data)
    
    yaml_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
    
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f"attachment; filename={runbook.name}.yaml"
        }
    )


@router.post("/runbooks/import", response_model=ImportRunbookResponse, status_code=status.HTTP_201_CREATED)
async def import_runbook_yaml(
    import_data: ImportRunbookRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Import a runbook from YAML content."""
    try:
        if import_data.format == "yaml":
            data = yaml.safe_load(import_data.content)
        else:
            import json
            data = json.loads(import_data.content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format: {str(e)}"
        )
    
    # Validate structure
    if data.get("kind") != "Runbook":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid kind - expected 'Runbook'"
        )
    
    metadata = data.get("metadata", {})
    spec = data.get("spec", {})
    name = metadata.get("name")
    
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing metadata.name"
        )
    
    # Check for existing
    existing = await db.execute(
        select(Runbook).where(Runbook.name == name)
    )
    existing_runbook = existing.scalar_one_or_none()
    
    if existing_runbook and not import_data.overwrite:
        return ImportRunbookResponse(
            success=False,
            runbook_name=name,
            action="skipped",
            errors=[f"Runbook '{name}' already exists. Use overwrite=true to update."]
        )
    
    action = "updated" if existing_runbook else "created"
    
    # Build runbook
    execution_spec = spec.get("execution", {})
    safety_spec = spec.get("safety", {})
    target_spec = spec.get("target", {})
    
    if existing_runbook:
        runbook = existing_runbook
        runbook.version += 1
        # Delete existing steps and triggers
        for step in list(runbook.steps):
            await db.delete(step)
        for trigger in list(runbook.triggers):
            await db.delete(trigger)
    else:
        runbook = Runbook(created_by=current_user.id)
        db.add(runbook)
    
    runbook.name = name
    runbook.description = metadata.get("description")
    runbook.category = metadata.get("category")
    runbook.tags = metadata.get("tags", [])
    runbook.documentation_url = metadata.get("documentation_url")
    runbook.auto_execute = execution_spec.get("auto_execute", False)
    runbook.approval_required = execution_spec.get("approval_required", True)
    runbook.approval_roles = execution_spec.get("approval_roles", ["admin", "engineer"])
    runbook.approval_timeout_minutes = execution_spec.get("approval_timeout_minutes", 30)
    runbook.max_executions_per_hour = safety_spec.get("max_executions_per_hour", 5)
    runbook.cooldown_minutes = safety_spec.get("cooldown_minutes", 10)
    runbook.target_os_filter = target_spec.get("os_filter", ["linux", "windows"])
    runbook.target_from_alert = target_spec.get("from_alert", True)
    runbook.target_alert_label = target_spec.get("alert_label", "instance")
    runbook.notifications_json = spec.get("notifications", {})
    runbook.source = "yaml"
    
    await db.flush()
    
    # Add steps
    for idx, step_data in enumerate(data.get("steps", [])):
        step = RunbookStep(
            runbook_id=runbook.id,
            step_order=idx + 1,
            name=step_data.get("name", f"Step {idx + 1}"),
            description=step_data.get("description"),
            command_linux=step_data.get("command_linux"),
            command_windows=step_data.get("command_windows"),
            target_os=step_data.get("target_os", "any"),
            timeout_seconds=step_data.get("timeout_seconds", 60),
            requires_elevation=step_data.get("requires_elevation", False),
            working_directory=step_data.get("working_directory"),
            environment_json=step_data.get("environment"),
            continue_on_fail=step_data.get("continue_on_fail", False),
            retry_count=step_data.get("retry_count", 0),
            retry_delay_seconds=step_data.get("retry_delay_seconds", 5),
            expected_exit_code=step_data.get("expected_exit_code", 0),
            expected_output_pattern=step_data.get("expected_output_pattern"),
            rollback_command_linux=step_data.get("rollback_command_linux"),
            rollback_command_windows=step_data.get("rollback_command_windows")
        )
        db.add(step)
    
    # Add triggers
    for trigger_data in data.get("triggers", []):
        trigger = RunbookTrigger(
            runbook_id=runbook.id,
            alert_name_pattern=trigger_data.get("alert_name_pattern", "*"),
            severity_pattern=trigger_data.get("severity_pattern", "*"),
            instance_pattern=trigger_data.get("instance_pattern", "*"),
            job_pattern=trigger_data.get("job_pattern", "*"),
            label_matchers_json=trigger_data.get("label_matchers"),
            min_duration_seconds=trigger_data.get("min_duration_seconds", 0),
            min_occurrences=trigger_data.get("min_occurrences", 1),
            priority=trigger_data.get("priority", 100),
            enabled=trigger_data.get("enabled", True)
        )
        db.add(trigger)
    
    # Create circuit breaker if new
    if not existing_runbook:
        circuit_breaker = CircuitBreaker(
            scope="runbook",
            scope_id=runbook.id,
            state="closed"
        )
        db.add(circuit_breaker)
    
    await db.commit()
    
    return ImportRunbookResponse(
        success=True,
        runbook_id=runbook.id,
        runbook_name=name,
        action=action,
        errors=[],
        warnings=[]
    )


# ============================================================================
# EXECUTIONS
# ============================================================================

@router.get("/executions", response_model=List[ExecutionListResponse])
async def list_executions(
    runbook_id: Optional[UUID] = None,
    server_id: Optional[UUID] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """List runbook executions with filtering."""
    query = select(RunbookExecution).options(
        selectinload(RunbookExecution.runbook),
        selectinload(RunbookExecution.server)
    )
    
    conditions = []
    if runbook_id:
        conditions.append(RunbookExecution.runbook_id == runbook_id)
    if server_id:
        conditions.append(RunbookExecution.server_id == server_id)
    if status:
        conditions.append(RunbookExecution.status == status)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(RunbookExecution.queued_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    executions = result.scalars().all()
    
    # Build response
    response = []
    for ex in executions:
        response.append(ExecutionListResponse(
            id=ex.id,
            runbook_id=ex.runbook_id,
            runbook_name=ex.runbook.name if ex.runbook else "Unknown",
            alert_id=ex.alert_id,
            server_hostname=ex.server.hostname if ex.server else None,
            execution_mode=ex.execution_mode,
            status=ex.status,
            dry_run=ex.dry_run,
            queued_at=ex.queued_at,
            started_at=ex.started_at,
            completed_at=ex.completed_at,
            steps_total=ex.steps_total,
            steps_completed=ex.steps_completed,
            steps_failed=ex.steps_failed
        ))
    
    return response


@router.post("/executions", response_model=RunbookExecutionResponse, status_code=status.HTTP_201_CREATED)
async def execute_runbook(
    exec_request: ExecuteRunbookRequest,
    runbook_id: UUID = Query(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer", "operator"]))
):
    """
    Manually trigger a runbook execution.
    
    For runbooks with approval_required=True, creates a pending execution awaiting approval.
    For auto_execute runbooks, starts execution immediately.
    """
    # Validate runbook
    result = await db.execute(
        select(Runbook)
        .options(selectinload(Runbook.steps))
        .where(Runbook.id == runbook_id)
    )
    runbook = result.scalar_one_or_none()
    
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found"
        )
    
    if not runbook.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Runbook is disabled"
        )
    
    # Determine target server
    server_id = exec_request.server_id or runbook.default_server_id
    server = None
    
    if server_id:
        result = await db.execute(
            select(ServerCredential).where(ServerCredential.id == server_id)
        )
        server = result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server {server_id} not found"
            )
    
    # Check circuit breaker
    result = await db.execute(
        select(CircuitBreaker).where(
            and_(CircuitBreaker.scope == "runbook", CircuitBreaker.scope_id == runbook.id)
        )
    )
    circuit_breaker = result.scalar_one_or_none()
    
    if circuit_breaker and circuit_breaker.state == "open" and not exec_request.bypass_cooldown:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Circuit breaker is open - runbook execution temporarily disabled"
        )
    
    # Check blackout windows
    if not exec_request.bypass_blackout:
        now = utc_now()
        result = await db.execute(
            select(BlackoutWindow).where(
                and_(
                    BlackoutWindow.enabled == True,
                    BlackoutWindow.recurrence == "once",
                    BlackoutWindow.start_time <= now,
                    BlackoutWindow.end_time >= now
                )
            )
        )
        blackout = result.scalar_one_or_none()
        
        if blackout:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Execution blocked by blackout window: {blackout.name}"
            )
    
    # Determine initial status
    if runbook.approval_required and not exec_request.dry_run:
        initial_status = "pending"
        approval_expires = utc_now() + timedelta(minutes=runbook.approval_timeout_minutes)
    else:
        initial_status = "running"
        approval_expires = None
    
    execution = RunbookExecution(
        runbook_id=runbook.id,
        runbook_version=runbook.version,
        server_id=server_id,
        alert_id=exec_request.alert_id,
        status=initial_status,
        execution_mode="manual",
        dry_run=exec_request.dry_run,
        triggered_by=current_user.id,
        triggered_by_system=False,
        approval_required=runbook.approval_required,
        approval_token=str(uuid4()) if runbook.approval_required else None,
        approval_requested_at=utc_now() if runbook.approval_required else None,
        approval_expires_at=approval_expires,
        queued_at=utc_now(),
        started_at=utc_now() if initial_status == "running" else None,
        steps_total=len(runbook.steps),
        variables_json=exec_request.variables
    )
    db.add(execution)
    await db.commit()
    
    result = await db.execute(
        select(RunbookExecution)
        .options(selectinload(RunbookExecution.step_executions))
        .where(RunbookExecution.id == execution.id)
    )
    execution_with_steps = result.scalar_one()
    
    # The background ExecutionWorker will pick up and process executions
    # with status "running" or "approved" automatically
    
    return execution_with_steps


@router.get("/executions/{execution_id}", response_model=RunbookExecutionResponse)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get execution details with step results."""
    result = await db.execute(
        select(RunbookExecution)
        .options(selectinload(RunbookExecution.step_executions))
        .where(RunbookExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )
    
    return execution


@router.post("/executions/{execution_id}/approve", response_model=RunbookExecutionResponse)
async def approve_execution(
    execution_id: UUID,
    approval: ApprovalRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Approve or reject a pending execution."""
    result = await db.execute(
        select(RunbookExecution)
        .options(
            selectinload(RunbookExecution.runbook),
            selectinload(RunbookExecution.step_executions)
        )
        .where(RunbookExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )
    
    if execution.status not in ["pending", "queued", "pending_approval"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution is not pending (status: {execution.status})"
        )
    
    # Check expiry
    if execution.approval_expires_at and execution.approval_expires_at < utc_now():
        execution.status = "timeout"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval window has expired"
        )
    
    # Check user role against runbook approval_roles
    runbook = execution.runbook
    if runbook and runbook.approval_roles:
        if current_user.role not in runbook.approval_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ({current_user.role}) cannot approve this runbook"
            )
    
    if approval.approved:
        execution.status = "approved"
        execution.approved_by = current_user.id
        execution.approved_at = utc_now()
        # The background ExecutionWorker will pick up and execute approved runbooks
    else:
        execution.status = "cancelled"
        execution.rejection_reason = approval.reason
    
    await db.commit()
    await db.refresh(execution)
    
    return execution


@router.post("/executions/{execution_id}/cancel", response_model=RunbookExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer", "operator"]))
):
    """Cancel a pending or running execution."""
    result = await db.execute(
        select(RunbookExecution)
        .options(selectinload(RunbookExecution.step_executions))
        .where(RunbookExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )
    
    if execution.status not in ["pending", "approved", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel execution with status: {execution.status}"
        )
    
    execution.status = "cancelled"
    execution.completed_at = utc_now()
    
    await db.commit()
    await db.refresh(execution)
    
    return execution


@router.post("/executions/{execution_id}/retry", response_model=RunbookExecutionResponse, status_code=status.HTTP_201_CREATED)
async def retry_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer", "operator"]))
):
    """Retry a failed or cancelled execution."""
    # Fetch original execution
    result = await db.execute(
        select(RunbookExecution)
        .options(selectinload(RunbookExecution.runbook).selectinload(Runbook.steps))
        .where(RunbookExecution.id == execution_id)
    )
    original_execution = result.scalar_one_or_none()

    if not original_execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )

    runbook = original_execution.runbook
    if not runbook:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runbook for this execution not found"
        )

    # Check if runbook is enabled
    if not runbook.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Runbook is disabled"
        )

    # Determine initial status
    if runbook.approval_required and not original_execution.dry_run:
        initial_status = "pending"
        approval_expires = utc_now() + timedelta(minutes=runbook.approval_timeout_minutes)
    else:
        initial_status = "running"
        approval_expires = None

    # Create new execution
    new_execution = RunbookExecution(
        runbook_id=original_execution.runbook_id,
        runbook_version=runbook.version,
        server_id=original_execution.server_id,
        alert_id=original_execution.alert_id,
        status=initial_status,
        execution_mode="manual", # Retry is manual
        dry_run=original_execution.dry_run,
        triggered_by=current_user.id,
        triggered_by_system=False,
        approval_required=runbook.approval_required,
        approval_token=str(uuid4()) if runbook.approval_required else None,
        approval_requested_at=utc_now() if runbook.approval_required else None,
        approval_expires_at=approval_expires,
        queued_at=utc_now(),
        started_at=utc_now() if initial_status == "running" else None,
        steps_total=len(runbook.steps),
        variables_json=original_execution.variables_json
    )

    db.add(new_execution)
    await db.commit()

    # Reload with steps for response
    result = await db.execute(
        select(RunbookExecution)
        .options(selectinload(RunbookExecution.step_executions))
        .where(RunbookExecution.id == new_execution.id)
    )
    execution_with_steps = result.scalar_one()

    return execution_with_steps


@router.post("/runbooks/{runbook_id}/steps/{step_id}/test", response_model=StepExecutionResponse)
async def test_single_step(
    runbook_id: UUID,
    step_id: UUID,
    exec_request: ExecuteRunbookRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Test a single step from a runbook without executing the entire runbook.
    Always runs in dry_run mode unless explicitly disabled.
    """
    # Validate runbook and step
    result = await db.execute(
        select(RunbookStep)
        .join(Runbook)
        .where(
            and_(
                RunbookStep.id == step_id,
                RunbookStep.runbook_id == runbook_id,
                Runbook.id == runbook_id
            )
        )
        .options(selectinload(RunbookStep.runbook))
    )
    step = result.scalar_one_or_none()

    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step {step_id} not found in runbook {runbook_id}"
        )

    runbook = step.runbook
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runbook not found"
        )

    # Determine target server
    server_id = exec_request.server_id or runbook.default_server_id
    if not server_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server ID is required for step testing"
        )

    result = await db.execute(
        select(ServerCredential).where(ServerCredential.id == server_id)
    )
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server {server_id} not found"
        )

    # Create a temporary execution for this step test
    execution = RunbookExecution(
        runbook_id=runbook.id,
        runbook_version=runbook.version,
        server_id=server_id,
        status="running",
        execution_mode="manual",
        dry_run=True,  # Always dry run for testing
        triggered_by=current_user.id,
        triggered_by_system=False,
        approval_required=False,
        queued_at=utc_now(),
        started_at=utc_now(),
        steps_total=1,
        variables_json=exec_request.variables
    )
    db.add(execution)
    await db.flush()

    # Create step execution record
    from ..services.runbook_executor import RunbookExecutor

    step_execution = StepExecution(
        execution_id=execution.id,
        step_id=step.id,
        step_order=step.step_order,
        step_name=step.name,
        command_executed=step.command_linux or step.command_windows,
        status="pending",
        retry_attempt=0,
        started_at=utc_now()
    )
    db.add(step_execution)
    await db.flush()

    # Execute the step using RunbookExecutor
    executor = RunbookExecutor(db)
    await executor.execute_single_step(
        execution=execution,
        step=step,
        step_execution=step_execution,
        server=server,
        variables=exec_request.variables or {}
    )

    await db.commit()
    await db.refresh(step_execution)

    return step_execution


# ============================================================================
# CIRCUIT BREAKERS
# ============================================================================

@router.get("/circuit-breakers", response_model=List[CircuitBreakerResponse])
async def list_circuit_breakers(
    scope: Optional[str] = None,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """List all circuit breakers."""
    query = select(CircuitBreaker)
    
    conditions = []
    if scope:
        conditions.append(CircuitBreaker.scope == scope)
    if state:
        conditions.append(CircuitBreaker.state == state)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/runbooks/{runbook_id}/circuit-breaker", response_model=CircuitBreakerResponse)
async def get_circuit_breaker(
    runbook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get circuit breaker status for a runbook."""
    result = await db.execute(
        select(CircuitBreaker).where(
            and_(CircuitBreaker.scope == "runbook", CircuitBreaker.scope_id == runbook_id)
        )
    )
    cb = result.scalar_one_or_none()
    
    if not cb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker for runbook {runbook_id} not found"
        )
    
    return cb


@router.post("/runbooks/{runbook_id}/circuit-breaker", response_model=CircuitBreakerResponse)
async def override_circuit_breaker(
    runbook_id: UUID,
    override: CircuitBreakerOverride,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Manually open, close, or reset a circuit breaker."""
    result = await db.execute(
        select(CircuitBreaker).where(
            and_(CircuitBreaker.scope == "runbook", CircuitBreaker.scope_id == runbook_id)
        )
    )
    cb = result.scalar_one_or_none()
    
    if not cb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker for runbook {runbook_id} not found"
        )
    
    if override.action == "open":
        cb.state = "open"
        cb.manually_opened = True
        cb.manually_opened_by = current_user.id
        cb.manually_opened_reason = override.reason
        cb.opened_at = utc_now()
    elif override.action == "close":
        cb.state = "closed"
        cb.manually_opened = False
        cb.failure_count = 0
        cb.success_count = 0
        cb.opened_at = None
        cb.closes_at = None
    elif override.action == "reset":
        cb.state = "closed"
        cb.manually_opened = False
        cb.failure_count = 0
        cb.success_count = 0
        cb.opened_at = None
        cb.closes_at = None
        cb.last_failure_at = None
        cb.last_success_at = None
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {override.action}. Use 'open', 'close', or 'reset'"
        )
    
    await db.commit()
    await db.refresh(cb)
    
    return cb


# ============================================================================
# BLACKOUT WINDOWS
# ============================================================================

@router.get("/blackout-windows", response_model=List[BlackoutWindowResponse])
async def list_blackout_windows(
    active_only: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """List blackout windows."""
    query = select(BlackoutWindow)
    
    if active_only:
        now = utc_now()
        query = query.where(
            and_(
                BlackoutWindow.enabled == True,
                BlackoutWindow.recurrence == "once",
                BlackoutWindow.start_time <= now,
                BlackoutWindow.end_time >= now
            )
        )
    
    query = query.order_by(BlackoutWindow.start_time)
    result = await db.execute(query)
    windows = result.scalars().all()
    
    # Add is_active_now computation
    now = utc_now()
    response = []
    for w in windows:
        is_active = False
        if w.enabled and w.recurrence == "once" and w.start_time and w.end_time:
            is_active = w.start_time <= now <= w.end_time
        
        response.append(BlackoutWindowResponse(
            id=w.id,
            name=w.name,
            description=w.description,
            recurrence=w.recurrence,
            start_time=w.start_time,
            end_time=w.end_time,
            daily_start_time=w.daily_start_time,
            daily_end_time=w.daily_end_time,
            days_of_week=w.days_of_week,
            days_of_month=w.days_of_month,
            timezone=w.timezone,
            applies_to=w.applies_to,
            applies_to_runbook_ids=w.applies_to_runbook_ids or [],
            enabled=w.enabled,
            created_by=w.created_by,
            created_at=w.created_at,
            updated_at=w.updated_at,
            is_active_now=is_active
        ))
    
    return response


@router.post("/blackout-windows", response_model=BlackoutWindowResponse, status_code=status.HTTP_201_CREATED)
async def create_blackout_window(
    window_data: BlackoutWindowCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Create a blackout window."""
    # Validate time range for one-time windows
    if window_data.recurrence == "once":
        if not window_data.start_time or not window_data.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time and end_time are required for one-time blackout windows"
            )
        if window_data.end_time <= window_data.start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be after start_time"
            )
    
    window = BlackoutWindow(
        name=window_data.name,
        description=window_data.description,
        recurrence=window_data.recurrence,
        start_time=window_data.start_time,
        end_time=window_data.end_time,
        daily_start_time=window_data.daily_start_time,
        daily_end_time=window_data.daily_end_time,
        days_of_week=window_data.days_of_week,
        days_of_month=window_data.days_of_month,
        timezone=window_data.timezone,
        applies_to=window_data.applies_to,
        applies_to_runbook_ids=window_data.applies_to_runbook_ids,
        created_by=current_user.id,
        enabled=window_data.enabled
    )
    db.add(window)
    await db.commit()
    await db.refresh(window)
    
    return window


@router.put("/blackout-windows/{window_id}", response_model=BlackoutWindowResponse)
async def update_blackout_window(
    window_id: UUID,
    window_data: BlackoutWindowUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Update a blackout window."""
    result = await db.execute(
        select(BlackoutWindow).where(BlackoutWindow.id == window_id)
    )
    window = result.scalar_one_or_none()
    
    if not window:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blackout window {window_id} not found"
        )
    
    update_data = window_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(window, field, value)
    
    await db.commit()
    await db.refresh(window)
    
    return window


@router.delete("/blackout-windows/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blackout_window(
    window_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Delete a blackout window."""
    result = await db.execute(
        select(BlackoutWindow).where(BlackoutWindow.id == window_id)
    )
    window = result.scalar_one_or_none()
    
    if not window:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blackout window {window_id} not found"
        )
    
    await db.delete(window)
    await db.commit()


# ============================================================================
# STATISTICS
# ============================================================================

@router.get("/stats")
async def get_remediation_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get auto-remediation statistics."""
    # Count runbooks
    result = await db.execute(select(func.count(Runbook.id)))
    total_runbooks = result.scalar()
    
    result = await db.execute(
        select(func.count(Runbook.id)).where(Runbook.enabled == True)
    )
    enabled_runbooks = result.scalar()
    
    result = await db.execute(
        select(func.count(Runbook.id)).where(Runbook.auto_execute == True)
    )
    auto_execute_runbooks = result.scalar()
    
    # Count executions
    result = await db.execute(select(func.count(RunbookExecution.id)))
    total_executions = result.scalar()
    
    result = await db.execute(
        select(func.count(RunbookExecution.id)).where(RunbookExecution.status == "success")
    )
    successful_executions = result.scalar()
    
    result = await db.execute(
        select(func.count(RunbookExecution.id)).where(RunbookExecution.status == "failed")
    )
    failed_executions = result.scalar()
    
    result = await db.execute(
        select(func.count(RunbookExecution.id)).where(RunbookExecution.status == "pending")
    )
    pending_approvals = result.scalar()
    
    # Count open circuit breakers
    result = await db.execute(
        select(func.count(CircuitBreaker.id)).where(CircuitBreaker.state == "open")
    )
    open_circuit_breakers = result.scalar()
    
    # Count active blackout windows
    now = utc_now()
    result = await db.execute(
        select(func.count(BlackoutWindow.id)).where(
            and_(
                BlackoutWindow.enabled == True,
                BlackoutWindow.recurrence == "once",
                BlackoutWindow.start_time <= now,
                BlackoutWindow.end_time >= now
            )
        )
    )
    active_blackouts = result.scalar()
    
    return {
        "runbooks": {
            "total": total_runbooks,
            "enabled": enabled_runbooks,
            "auto_execute": auto_execute_runbooks
        },
        "executions": {
            "total": total_executions,
            "successful": successful_executions,
            "failed": failed_executions,
            "pending_approval": pending_approvals
        },
        "safety": {
            "open_circuit_breakers": open_circuit_breakers,
            "active_blackout_windows": active_blackouts
        }
    }


# ============================================================================
# RUNBOOK TEMPLATES
# ============================================================================

@router.get("/templates")
async def get_runbook_templates(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get pre-built runbook templates for quick creation."""
    templates = [
        {
            "id": "restart-service",
            "name": "Restart Service",
            "category": "infrastructure",
            "description": "Restart a Linux systemd service",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Check service status",
                    "command_linux": "systemctl status {{service_name}}",
                    "target_os": "linux",
                    "timeout_seconds": 30,
                    "continue_on_fail": True
                },
                {
                    "step_order": 2,
                    "name": "Restart service",
                    "command_linux": "systemctl restart {{service_name}}",
                    "target_os": "linux",
                    "timeout_seconds": 60,
                    "requires_elevation": True
                },
                {
                    "step_order": 3,
                    "name": "Verify service is running",
                    "command_linux": "systemctl is-active {{service_name}}",
                    "target_os": "linux",
                    "timeout_seconds": 30
                }
            ],
            "triggers": [
                {
                    "alert_name_pattern": ".*ServiceDown.*",
                    "severity_pattern": "critical|warning"
                }
            ]
        },
        {
            "id": "clear-disk-space",
            "name": "Clear Disk Space",
            "category": "infrastructure",
            "description": "Clean up temporary files and logs to free disk space",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Check disk usage",
                    "command_linux": "df -h",
                    "target_os": "linux",
                    "timeout_seconds": 30
                },
                {
                    "step_order": 2,
                    "name": "Clear temp files",
                    "command_linux": "rm -rf /tmp/*",
                    "target_os": "linux",
                    "timeout_seconds": 60,
                    "requires_elevation": True
                },
                {
                    "step_order": 3,
                    "name": "Clear old logs",
                    "command_linux": "find /var/log -name '*.gz' -mtime +7 -delete",
                    "target_os": "linux",
                    "timeout_seconds": 120,
                    "requires_elevation": True
                },
                {
                    "step_order": 4,
                    "name": "Verify disk space freed",
                    "command_linux": "df -h",
                    "target_os": "linux",
                    "timeout_seconds": 30
                }
            ],
            "triggers": [
                {
                    "alert_name_pattern": ".*DiskFull.*|.*DiskSpace.*",
                    "severity_pattern": "warning|critical"
                }
            ]
        },
        {
            "id": "restart-nginx",
            "name": "Restart Nginx Web Server",
            "category": "application",
            "description": "Gracefully restart Nginx web server",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Test Nginx configuration",
                    "command_linux": "nginx -t",
                    "target_os": "linux",
                    "timeout_seconds": 30,
                    "requires_elevation": True
                },
                {
                    "step_order": 2,
                    "name": "Reload Nginx",
                    "command_linux": "systemctl reload nginx",
                    "target_os": "linux",
                    "timeout_seconds": 60,
                    "requires_elevation": True
                },
                {
                    "step_order": 3,
                    "name": "Check Nginx status",
                    "command_linux": "systemctl status nginx",
                    "target_os": "linux",
                    "timeout_seconds": 30
                }
            ],
            "triggers": [
                {
                    "alert_name_pattern": ".*Nginx.*Down.*",
                    "severity_pattern": "critical"
                }
            ]
        },
        {
            "id": "clear-redis-cache",
            "name": "Clear Redis Cache",
            "category": "database",
            "description": "Flush all keys from Redis cache",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Check Redis connection",
                    "command_linux": "redis-cli ping",
                    "target_os": "linux",
                    "timeout_seconds": 30
                },
                {
                    "step_order": 2,
                    "name": "Flush all keys",
                    "command_linux": "redis-cli FLUSHALL",
                    "target_os": "linux",
                    "timeout_seconds": 60
                },
                {
                    "step_order": 3,
                    "name": "Verify cache cleared",
                    "command_linux": "redis-cli DBSIZE",
                    "target_os": "linux",
                    "timeout_seconds": 30
                }
            ],
            "triggers": [
                {
                    "alert_name_pattern": ".*Redis.*Memory.*",
                    "severity_pattern": "warning"
                }
            ]
        },
        {
            "id": "kill-high-cpu-process",
            "name": "Kill High CPU Process",
            "category": "infrastructure",
            "description": "Identify and terminate processes consuming excessive CPU",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Identify high CPU processes",
                    "command_linux": "ps aux --sort=-%cpu | head -10",
                    "target_os": "linux",
                    "timeout_seconds": 30
                },
                {
                    "step_order": 2,
                    "name": "Kill process by PID",
                    "command_linux": "kill -9 {{pid}}",
                    "target_os": "linux",
                    "timeout_seconds": 30,
                    "requires_elevation": True
                },
                {
                    "step_order": 3,
                    "name": "Verify CPU usage normalized",
                    "command_linux": "top -bn1 | grep 'Cpu(s)'",
                    "target_os": "linux",
                    "timeout_seconds": 30
                }
            ],
            "triggers": [
                {
                    "alert_name_pattern": ".*HighCPU.*",
                    "severity_pattern": "critical"
                }
            ]
        },
        {
            "id": "restart-windows-service",
            "name": "Restart Windows Service",
            "category": "infrastructure",
            "description": "Restart a Windows service",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Check service status",
                    "command_windows": "Get-Service -Name {{service_name}} | Select-Object Status",
                    "target_os": "windows",
                    "timeout_seconds": 30
                },
                {
                    "step_order": 2,
                    "name": "Restart service",
                    "command_windows": "Restart-Service -Name {{service_name}} -Force",
                    "target_os": "windows",
                    "timeout_seconds": 60,
                    "requires_elevation": True
                },
                {
                    "step_order": 3,
                    "name": "Verify service is running",
                    "command_windows": "Get-Service -Name {{service_name}} | Where-Object {$_.Status -eq 'Running'}",
                    "target_os": "windows",
                    "timeout_seconds": 30
                }
            ],
            "triggers": [
                {
                    "alert_name_pattern": ".*WindowsService.*",
                    "severity_pattern": "critical"
                }
            ]
        }
    ]

    # Filter by category if specified
    if category:
        templates = [t for t in templates if t["category"] == category]

    return {
        "templates": templates,
        "count": len(templates)
    }


@router.post("/templates/{template_id}/create", response_model=RunbookResponse, status_code=status.HTTP_201_CREATED)
async def create_runbook_from_template(
    template_id: str,
    customizations: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """Create a new runbook from a template with optional customizations."""
    # Get template
    templates_response = await get_runbook_templates(current_user=current_user)
    templates = templates_response["templates"]

    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found"
        )

    # Apply customizations
    if customizations:
        template.update(customizations)

    # Check for duplicate name
    existing = await db.execute(
        select(Runbook).where(Runbook.name == template["name"])
    )
    if existing.scalar_one_or_none():
        # Append timestamp to make unique
        from datetime import datetime
        template["name"] = f"{template['name']} - {datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Create runbook from template
    runbook = Runbook(
        name=template["name"],
        description=template.get("description", ""),
        category=template.get("category", "infrastructure"),
        tags=template.get("tags", []),
        enabled=False,  # Start disabled
        auto_execute=False,
        approval_required=True,
        approval_roles=["operator", "engineer", "admin"],
        approval_timeout_minutes=30,
        max_executions_per_hour=5,
        cooldown_minutes=10,
        target_os_filter=["linux", "windows"],
        target_from_alert=True,
        target_alert_label="instance",
        created_by=current_user.id,
        source="template"
    )
    db.add(runbook)
    await db.flush()

    # Create steps from template
    for step_data in template.get("steps", []):
        step = RunbookStep(
            runbook_id=runbook.id,
            step_order=step_data.get("step_order", 1),
            name=step_data.get("name", "Step"),
            description=step_data.get("description"),
            command_linux=step_data.get("command_linux"),
            command_windows=step_data.get("command_windows"),
            target_os=step_data.get("target_os", "any"),
            timeout_seconds=step_data.get("timeout_seconds", 60),
            requires_elevation=step_data.get("requires_elevation", False),
            continue_on_fail=step_data.get("continue_on_fail", False),
            retry_count=step_data.get("retry_count", 0),
            retry_delay_seconds=step_data.get("retry_delay_seconds", 5),
            expected_exit_code=step_data.get("expected_exit_code", 0)
        )
        db.add(step)

    # Create triggers from template
    for trigger_data in template.get("triggers", []):
        trigger = RunbookTrigger(
            runbook_id=runbook.id,
            alert_name_pattern=trigger_data.get("alert_name_pattern", "*"),
            severity_pattern=trigger_data.get("severity_pattern", "*"),
            instance_pattern=trigger_data.get("instance_pattern", "*"),
            job_pattern=trigger_data.get("job_pattern", "*"),
            min_duration_seconds=trigger_data.get("min_duration_seconds", 0),
            min_occurrences=trigger_data.get("min_occurrences", 1),
            priority=trigger_data.get("priority", 100),
            enabled=trigger_data.get("enabled", True)
        )
        db.add(trigger)

    # Create circuit breaker
    circuit_breaker = CircuitBreaker(
        scope="runbook",
        scope_id=runbook.id,
        state="closed"
    )
    db.add(circuit_breaker)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Runbook)
        .options(selectinload(Runbook.steps), selectinload(Runbook.triggers))
        .where(Runbook.id == runbook.id)
    )
    return result.scalar_one()
