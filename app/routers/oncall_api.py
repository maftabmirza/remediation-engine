"""
On-Call Scheduling & Escalation API Router (Feature A1).

CRUD endpoints for schedules, escalation policies, escalation levels,
overrides, and "who is on-call?" queries.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import User
from app.models_oncall import (
    EscalationLevel,
    EscalationPolicy,
    OnCallOverride,
    OnCallSchedule,
)
from app.schemas_oncall import (
    EscalationChainResponse,
    EscalationContact,
    EscalationLevelCreate,
    EscalationLevelResponse,
    EscalationPolicyCreate,
    EscalationPolicyListResponse,
    EscalationPolicyResponse,
    EscalationPolicyUpdate,
    OnCallCurrentResponse,
    OnCallOverrideCreate,
    OnCallOverrideResponse,
    OnCallScheduleCreate,
    OnCallScheduleListResponse,
    OnCallScheduleResponse,
    OnCallScheduleUpdate,
    OnCallTimelineEntry,
)
from app.services.auth_service import get_current_user, require_admin
from app.services.oncall_service import OnCallService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oncall", tags=["On-Call Scheduling"])


# ===========================================================================
# Schedule Management
# ===========================================================================


@router.get(
    "/schedules",
    response_model=OnCallScheduleListResponse,
    summary="List on-call schedules",
)
async def list_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    group_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> OnCallScheduleListResponse:
    """List on-call schedules (paginated, optionally filtered by group_id)."""
    stmt = select(OnCallSchedule)
    count_stmt = select(func.count()).select_from(OnCallSchedule)

    if group_id is not None:
        stmt = stmt.where(OnCallSchedule.group_id == group_id)
        count_stmt = count_stmt.where(OnCallSchedule.group_id == group_id)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    result = await db.execute(
        stmt.order_by(OnCallSchedule.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    schedules = result.scalars().all()

    return OnCallScheduleListResponse(
        items=[OnCallScheduleResponse.model_validate(s) for s in schedules],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/schedules",
    response_model=OnCallScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an on-call schedule",
)
async def create_schedule(
    body: OnCallScheduleCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> OnCallScheduleResponse:
    """Create a new on-call rotation schedule.  **Admin only.**"""
    from datetime import time as _time  # noqa: PLC0415

    # Parse handoff_time from "HH:MM" string
    try:
        parts = body.handoff_time.split(":")
        handoff_time = _time(int(parts[0]), int(parts[1]))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="handoff_time must be in 'HH:MM' format",
        )

    schedule = OnCallSchedule(
        name=body.name,
        group_id=body.group_id,
        rotation_type=body.rotation_type,
        participants=body.participants,
        timezone=body.timezone,
        handoff_time=handoff_time,
        handoff_day=body.handoff_day,
        effective_from=body.effective_from,
        effective_until=body.effective_until,
        created_by=current_user.id,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return OnCallScheduleResponse.model_validate(schedule)


@router.get(
    "/schedules/{schedule_id}",
    response_model=OnCallScheduleResponse,
    summary="Get an on-call schedule",
)
async def get_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> OnCallScheduleResponse:
    """Get details of an on-call schedule."""
    schedule = await db.get(OnCallSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return OnCallScheduleResponse.model_validate(schedule)


@router.put(
    "/schedules/{schedule_id}",
    response_model=OnCallScheduleResponse,
    summary="Update an on-call schedule",
)
async def update_schedule(
    schedule_id: UUID,
    body: OnCallScheduleUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> OnCallScheduleResponse:
    """Update an on-call schedule.  **Admin only.**"""
    schedule = await db.get(OnCallSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    update_data = body.model_dump(exclude_unset=True)
    if "handoff_time" in update_data and update_data["handoff_time"] is not None:
        from datetime import time as _time  # noqa: PLC0415

        try:
            parts = update_data["handoff_time"].split(":")
            update_data["handoff_time"] = _time(int(parts[0]), int(parts[1]))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="handoff_time must be in 'HH:MM' format",
            )

    for field, value in update_data.items():
        setattr(schedule, field, value)

    await db.commit()
    await db.refresh(schedule)
    return OnCallScheduleResponse.model_validate(schedule)


@router.delete(
    "/schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an on-call schedule",
)
async def delete_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Deactivate an on-call schedule (soft delete).  **Admin only.**"""
    schedule = await db.get(OnCallSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    schedule.is_active = False
    await db.commit()


@router.get(
    "/schedules/{schedule_id}/timeline",
    response_model=List[OnCallTimelineEntry],
    summary="Get upcoming rotation timeline",
)
async def get_schedule_timeline(
    schedule_id: UUID,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> List[OnCallTimelineEntry]:
    """Get the upcoming rotation view for the next N days (default 30)."""
    schedule = await db.get(OnCallSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    svc = OnCallService(db)
    timeline = await svc.get_schedule_timeline(schedule_id, days=days)
    return timeline


# ===========================================================================
# Escalation Policy Management
# ===========================================================================


@router.get(
    "/escalation-policies",
    response_model=EscalationPolicyListResponse,
    summary="List escalation policies",
)
async def list_escalation_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> EscalationPolicyListResponse:
    """List all escalation policies (paginated)."""
    total_result = await db.execute(
        select(func.count()).select_from(EscalationPolicy)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(EscalationPolicy)
        .order_by(EscalationPolicy.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    policies = result.scalars().all()

    return EscalationPolicyListResponse(
        items=[EscalationPolicyResponse.model_validate(p) for p in policies],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/escalation-policies",
    response_model=EscalationPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an escalation policy",
)
async def create_escalation_policy(
    body: EscalationPolicyCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> EscalationPolicyResponse:
    """Create a new escalation policy.  **Admin only.**"""
    policy = EscalationPolicy(
        name=body.name,
        app_id=body.app_id,
        description=body.description,
        repeat_count=body.repeat_count,
        resolve_timeout_minutes=body.resolve_timeout_minutes,
        is_default=body.is_default,
        created_by=current_user.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return EscalationPolicyResponse.model_validate(policy)


@router.get(
    "/escalation-policies/{policy_id}",
    response_model=EscalationPolicyResponse,
    summary="Get an escalation policy with its levels",
)
async def get_escalation_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> EscalationPolicyResponse:
    """Get an escalation policy including all its levels."""
    policy = await db.get(EscalationPolicy, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )
    return EscalationPolicyResponse.model_validate(policy)


@router.put(
    "/escalation-policies/{policy_id}",
    response_model=EscalationPolicyResponse,
    summary="Update an escalation policy",
)
async def update_escalation_policy(
    policy_id: UUID,
    body: EscalationPolicyUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> EscalationPolicyResponse:
    """Update an escalation policy.  **Admin only.**"""
    policy = await db.get(EscalationPolicy, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)

    await db.commit()
    await db.refresh(policy)
    return EscalationPolicyResponse.model_validate(policy)


@router.delete(
    "/escalation-policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an escalation policy",
)
async def delete_escalation_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Deactivate an escalation policy (soft delete).  **Admin only.**"""
    policy = await db.get(EscalationPolicy, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )
    policy.is_active = False
    await db.commit()


@router.post(
    "/escalation-policies/{policy_id}/levels",
    response_model=EscalationLevelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an escalation level",
)
async def add_escalation_level(
    policy_id: UUID,
    body: EscalationLevelCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> EscalationLevelResponse:
    """Add a new escalation level to a policy.  **Admin only.**"""
    policy = await db.get(EscalationPolicy, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    level = EscalationLevel(
        policy_id=policy_id,
        level_number=body.level_number,
        schedule_id=body.schedule_id,
        user_id=body.user_id,
        channel_id=body.channel_id,
        timeout_minutes=body.timeout_minutes,
        urgency=body.urgency,
        notification_steps=body.notification_steps,
    )
    db.add(level)
    await db.commit()
    await db.refresh(level)
    return EscalationLevelResponse.model_validate(level)


@router.delete(
    "/escalation-policies/{policy_id}/levels/{level_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an escalation level",
)
async def delete_escalation_level(
    policy_id: UUID,
    level_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Remove an escalation level from a policy.  **Admin only.**"""
    level = await db.get(EscalationLevel, level_id)
    if level is None or level.policy_id != policy_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Level not found"
        )
    await db.delete(level)
    await db.commit()


# ===========================================================================
# Override Management
# ===========================================================================


@router.post(
    "/overrides",
    response_model=OnCallOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a schedule override",
)
async def create_override(
    body: OnCallOverrideCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> OnCallOverrideResponse:
    """
    Create an on-call override (swap).

    Regular users can only create overrides for themselves.
    Admins can create overrides for any user.
    """
    is_admin = getattr(current_user, "role", "") == "admin"
    is_own = body.override_user_id == current_user.id

    if not is_own and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create overrides for yourself",
        )

    schedule = await db.get(OnCallSchedule, body.schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )

    override = OnCallOverride(
        schedule_id=body.schedule_id,
        override_user_id=body.override_user_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
        created_by=current_user.id,
    )
    db.add(override)
    await db.commit()
    await db.refresh(override)
    return OnCallOverrideResponse.model_validate(override)


@router.delete(
    "/overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a schedule override",
)
async def delete_override(
    override_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Cancel an on-call override."""
    override = await db.get(OnCallOverride, override_id)
    if override is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Override not found"
        )

    is_admin = getattr(current_user, "role", "") == "admin"
    is_own = override.override_user_id == current_user.id or override.created_by == current_user.id

    if not is_own and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot cancel this override",
        )

    await db.delete(override)
    await db.commit()


# ===========================================================================
# Current On-Call Queries
# ===========================================================================


@router.get(
    "/current",
    response_model=OnCallCurrentResponse,
    summary="Who is on-call right now?",
)
async def get_current_oncall(
    app_id: Optional[UUID] = Query(None),
    group_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> OnCallCurrentResponse:
    """
    Return who is on-call right now.

    Optional filters:
    - **app_id**: Return the escalation chain for a specific application.
    - **group_id**: Return on-call info for all schedules of a specific group.
    """
    svc = OnCallService(db)
    oncall = await svc.get_current_oncall(group_id=group_id, app_id=app_id)
    return OnCallCurrentResponse(oncall=oncall)


@router.get(
    "/current/app/{app_id}",
    response_model=EscalationChainResponse,
    summary="Full escalation chain for an application",
)
async def get_app_escalation_chain(
    app_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> EscalationChainResponse:
    """Return the full escalation chain (all levels) for an application."""
    svc = OnCallService(db)
    contacts = await svc.resolve_for_app(app_id)

    policy_id: Optional[UUID] = None
    policy_name: Optional[str] = None
    if contacts:
        policy_id = contacts[0].policy_id
        policy = await db.get(EscalationPolicy, policy_id)
        if policy:
            policy_name = policy.name

    return EscalationChainResponse(
        app_id=app_id,
        policy_id=policy_id,
        policy_name=policy_name,
        contacts=contacts,
    )
