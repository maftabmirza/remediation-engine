"""
Notification System Pydantic Schemas

Request/response models for the notifications API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VALID_CHANNEL_TYPES = {"slack", "msteams", "email", "webhook"}
VALID_STATUSES = {"pending", "sent", "failed", "retrying"}


# ===========================================================================
# NotificationChannel
# ===========================================================================


class NotificationChannelBase(BaseModel):
    name: str = Field(..., max_length=100, description="Human-readable label, e.g. 'Engineering Slack'")
    channel_type: str = Field(..., description="One of: slack, msteams, email, webhook")
    config_json: Dict[str, Any] = Field(default_factory=dict, description="Channel-specific config (webhook_url, smtp_host, etc.)")
    is_enabled: bool = Field(default=True)

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        if v not in VALID_CHANNEL_TYPES:
            raise ValueError(f"channel_type must be one of {sorted(VALID_CHANNEL_TYPES)}")
        return v


class NotificationChannelCreate(NotificationChannelBase):
    pass


class NotificationChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    channel_type: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CHANNEL_TYPES:
            raise ValueError(f"channel_type must be one of {sorted(VALID_CHANNEL_TYPES)}")
        return v


class NotificationChannelResponse(NotificationChannelBase):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationChannelListResponse(BaseModel):
    items: List[NotificationChannelResponse]
    total: int
    page: int
    page_size: int


# ===========================================================================
# NotificationPolicy
# ===========================================================================


class NotificationPolicyBase(BaseModel):
    name: str = Field(..., max_length=100)
    event_type: str = Field(..., max_length=50, description="e.g. 'alert.firing', 'execution.completed'")
    severity_filter: Optional[List[str]] = Field(
        None, description="Restrict to these severities; None = all"
    )
    channel_ids: List[UUID] = Field(default_factory=list, description="Channels to deliver to")
    is_enabled: bool = Field(default=True)
    template_key: Optional[str] = Field(None, max_length=50, description="Override template key")


class NotificationPolicyCreate(NotificationPolicyBase):
    pass


class NotificationPolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    event_type: Optional[str] = Field(None, max_length=50)
    severity_filter: Optional[List[str]] = None
    channel_ids: Optional[List[UUID]] = None
    is_enabled: Optional[bool] = None
    template_key: Optional[str] = Field(None, max_length=50)


class NotificationPolicyResponse(NotificationPolicyBase):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationPolicyListResponse(BaseModel):
    items: List[NotificationPolicyResponse]
    total: int
    page: int
    page_size: int


# ===========================================================================
# NotificationLog
# ===========================================================================


class NotificationLogResponse(BaseModel):
    id: UUID
    policy_id: Optional[UUID] = None
    channel_id: UUID
    event_type: str
    event_id: Optional[UUID] = None
    recipient: Optional[str] = None
    status: str
    attempt_count: int
    error_message: Optional[str] = None
    payload_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationLogListResponse(BaseModel):
    items: List[NotificationLogResponse]
    total: int
    page: int
    page_size: int


class NotificationLogStats(BaseModel):
    """Aggregated delivery statistics."""

    total: int
    sent: int
    failed: int
    pending: int
    retrying: int
    success_rate: float  # 0.0 – 1.0


# ===========================================================================
# Test channel
# ===========================================================================


class ChannelTestResult(BaseModel):
    success: bool
    message: str
    provider_response: Optional[Any] = None


# ===========================================================================
# Internal message / result types (used by service layer)
# ===========================================================================


class NotificationMessage(BaseModel):
    """A rendered, ready-to-send notification payload."""

    event_type: str
    event_id: Optional[UUID] = None
    title: str
    body: str
    severity: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    template_key: Optional[str] = None


class ProviderResult(BaseModel):
    """Result returned by a notification provider after a send attempt."""

    success: bool
    recipient: Optional[str] = None
    provider_response: Optional[Any] = None
    error: Optional[str] = None
