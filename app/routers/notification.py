"""
Notification API Router

Provides CRUD endpoints for notification channels and policies,
plus a delivery log query endpoint.

All write operations require admin or engineer role.
Read operations require authentication.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_async_db
from app.models import User
from app.models_notification import (
    NotificationChannel,
    NotificationLog,
    NotificationPolicy,
)
from app.schemas_notification import (
    ChannelTestResult,
    NotificationChannelCreate,
    NotificationChannelListResponse,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationLogListResponse,
    NotificationLogResponse,
    NotificationLogStats,
    NotificationPolicyCreate,
    NotificationPolicyListResponse,
    NotificationPolicyResponse,
    NotificationPolicyUpdate,
)
from app.services.auth_service import get_current_user, require_role
from app.services.notification.service import NotificationService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encrypt_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Encrypt any keys ending in ``_password``, ``_token``, or ``_secret``
    by renaming them with an ``_encrypted`` suffix.

    Args:
        config: Raw config dict from request body.

    Returns:
        Config dict with sensitive values encrypted.
    """
    enc_key = settings.encryption_key
    if not enc_key:
        return config
    try:
        fernet = Fernet(enc_key.encode() if isinstance(enc_key, str) else enc_key)
    except Exception:
        return config

    SENSITIVE_SUFFIXES = ("_password", "_token", "_secret", "_key")
    result = {}
    for k, v in config.items():
        if any(k.endswith(s) for s in SENSITIVE_SUFFIXES) and isinstance(v, str) and v:
            result[k + "_encrypted"] = fernet.encrypt(v.encode()).decode()
        else:
            result[k] = v
    return result


# ===========================================================================
# Channels
# ===========================================================================


@router.post(
    "/channels",
    response_model=NotificationChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a notification channel",
)
async def create_channel(
    body: NotificationChannelCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> NotificationChannelResponse:
    """Create a new notification channel (Slack, Teams, Email, or Webhook)."""
    svc = NotificationService(db)
    errors = await svc.validate_channel_config(body.channel_type, body.config_json)
    if errors:
        raise HTTPException(status_code=422, detail={"config_errors": errors})

    encrypted_config = _encrypt_config(body.config_json)

    channel = NotificationChannel(
        name=body.name,
        channel_type=body.channel_type,
        config_json=encrypted_config,
        is_enabled=body.is_enabled,
        created_by=current_user.id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return NotificationChannelResponse.model_validate(channel)


@router.get(
    "/channels",
    response_model=NotificationChannelListResponse,
    summary="List notification channels",
)
async def list_channels(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    channel_type: Optional[str] = Query(default=None),
    enabled_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> NotificationChannelListResponse:
    """List all configured notification channels."""
    q = select(NotificationChannel)
    if channel_type:
        q = q.where(NotificationChannel.channel_type == channel_type)
    if enabled_only:
        q = q.where(NotificationChannel.is_enabled.is_(True))

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(NotificationChannel.created_at.desc())
    result = await db.execute(q)
    channels = result.scalars().all()

    return NotificationChannelListResponse(
        items=[NotificationChannelResponse.model_validate(c) for c in channels],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/channels/{channel_id}",
    response_model=NotificationChannelResponse,
    summary="Get a notification channel",
)
async def get_channel(
    channel_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> NotificationChannelResponse:
    """Get details of a specific notification channel."""
    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return NotificationChannelResponse.model_validate(channel)


@router.put(
    "/channels/{channel_id}",
    response_model=NotificationChannelResponse,
    summary="Update a notification channel",
)
async def update_channel(
    channel_id: UUID,
    body: NotificationChannelUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> NotificationChannelResponse:
    """Update an existing notification channel."""
    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if body.name is not None:
        channel.name = body.name
    if body.channel_type is not None:
        channel.channel_type = body.channel_type
    if body.config_json is not None:
        svc = NotificationService(db)
        ch_type = body.channel_type or channel.channel_type
        errors = await svc.validate_channel_config(ch_type, body.config_json)
        if errors:
            raise HTTPException(status_code=422, detail={"config_errors": errors})
        channel.config_json = _encrypt_config(body.config_json)
    if body.is_enabled is not None:
        channel.is_enabled = body.is_enabled

    await db.commit()
    await db.refresh(channel)
    return NotificationChannelResponse.model_validate(channel)


@router.delete(
    "/channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a notification channel",
)
async def delete_channel(
    channel_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin"])),
) -> Response:
    """Delete a notification channel (admin only)."""
    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(channel)
    await db.commit()
    return Response(status_code=204)


@router.post(
    "/channels/{channel_id}/test",
    response_model=ChannelTestResult,
    summary="Send a test notification",
)
async def test_channel(
    channel_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> ChannelTestResult:
    """Send a test notification to verify channel configuration."""
    svc = NotificationService(db)
    result = await svc.test_channel(channel_id)
    return ChannelTestResult(
        success=result.success,
        message="Test notification sent successfully" if result.success else (result.error or "Send failed"),
        provider_response=result.provider_response,
    )


# ===========================================================================
# Policies
# ===========================================================================


@router.post(
    "/policies",
    response_model=NotificationPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a notification policy",
)
async def create_policy(
    body: NotificationPolicyCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> NotificationPolicyResponse:
    """Create a new notification routing policy."""
    policy = NotificationPolicy(
        name=body.name,
        event_type=body.event_type,
        severity_filter=body.severity_filter,
        channel_ids=[str(cid) for cid in body.channel_ids],
        is_enabled=body.is_enabled,
        template_key=body.template_key,
        created_by=current_user.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return NotificationPolicyResponse.model_validate(policy)


@router.get(
    "/policies",
    response_model=NotificationPolicyListResponse,
    summary="List notification policies",
)
async def list_policies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    event_type: Optional[str] = Query(default=None),
    enabled_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPolicyListResponse:
    """List all notification routing policies."""
    q = select(NotificationPolicy)
    if event_type:
        q = q.where(NotificationPolicy.event_type == event_type)
    if enabled_only:
        q = q.where(NotificationPolicy.is_enabled.is_(True))

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(NotificationPolicy.created_at.desc())
    result = await db.execute(q)
    policies = result.scalars().all()

    return NotificationPolicyListResponse(
        items=[NotificationPolicyResponse.model_validate(p) for p in policies],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/policies/{policy_id}",
    response_model=NotificationPolicyResponse,
    summary="Update a notification policy",
)
async def update_policy(
    policy_id: UUID,
    body: NotificationPolicyUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> NotificationPolicyResponse:
    """Update an existing notification policy."""
    policy = await db.get(NotificationPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    update_data = body.model_dump(exclude_unset=True)
    if "channel_ids" in update_data:
        update_data["channel_ids"] = [str(cid) for cid in update_data["channel_ids"]]

    for field, value in update_data.items():
        setattr(policy, field, value)

    await db.commit()
    await db.refresh(policy)
    return NotificationPolicyResponse.model_validate(policy)


@router.delete(
    "/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a notification policy",
)
async def delete_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin"])),
) -> Response:
    """Delete a notification policy (admin only)."""
    policy = await db.get(NotificationPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(policy)
    await db.commit()
    return Response(status_code=204)


# ===========================================================================
# Log
# ===========================================================================


@router.get(
    "/log",
    response_model=NotificationLogListResponse,
    summary="Query notification delivery log",
)
async def get_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    event_type: Optional[str] = Query(default=None),
    channel_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> NotificationLogListResponse:
    """Query the notification delivery audit log."""
    q = select(NotificationLog)
    if event_type:
        q = q.where(NotificationLog.event_type == event_type)
    if channel_id:
        q = q.where(NotificationLog.channel_id == channel_id)
    if status:
        q = q.where(NotificationLog.status == status)

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(NotificationLog.created_at.desc())
    result = await db.execute(q)
    entries = result.scalars().all()

    return NotificationLogListResponse(
        items=[NotificationLogResponse.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/log/stats",
    response_model=NotificationLogStats,
    summary="Notification delivery statistics",
)
async def get_log_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> NotificationLogStats:
    """Return aggregated delivery statistics for the notification log."""
    result = await db.execute(
        select(NotificationLog.status, func.count(NotificationLog.id).label("cnt"))
        .group_by(NotificationLog.status)
    )
    rows = result.all()

    counts: dict[str, int] = {row.status: row.cnt for row in rows}
    total = sum(counts.values())
    sent = counts.get("sent", 0)
    failed = counts.get("failed", 0)
    pending = counts.get("pending", 0)
    retrying = counts.get("retrying", 0)

    return NotificationLogStats(
        total=total,
        sent=sent,
        failed=failed,
        pending=pending,
        retrying=retrying,
        success_rate=round(sent / total, 4) if total > 0 else 0.0,
    )
