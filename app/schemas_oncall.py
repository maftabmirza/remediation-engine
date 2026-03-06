"""
Pydantic schemas for the On-Call Scheduling & Escalation feature (A1).
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# OnCallSchedule
# ---------------------------------------------------------------------------


class OnCallScheduleCreate(BaseModel):
    """Input schema for creating a new on-call schedule."""

    name: str
    group_id: UUID
    rotation_type: str  # "daily", "weekly", "custom"
    participants: List[dict]  # [{"user_id": "uuid", "order": 1, "role": "primary"}]
    timezone: str = "UTC"
    handoff_time: str = "09:00"  # "HH:MM"
    handoff_day: Optional[str] = None  # "monday" for weekly
    effective_from: datetime
    effective_until: Optional[datetime] = None

    @field_validator("rotation_type")
    @classmethod
    def validate_rotation_type(cls, v: str) -> str:
        if v not in ("daily", "weekly", "custom"):
            raise ValueError("rotation_type must be 'daily', 'weekly', or 'custom'")
        return v


class OnCallScheduleUpdate(BaseModel):
    """Input schema for updating an on-call schedule (all fields optional)."""

    name: Optional[str] = None
    rotation_type: Optional[str] = None
    participants: Optional[List[dict]] = None
    timezone: Optional[str] = None
    handoff_time: Optional[str] = None
    handoff_day: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    is_active: Optional[bool] = None


class OnCallScheduleResponse(BaseModel):
    """Output schema for an on-call schedule."""

    id: UUID
    name: str
    group_id: UUID
    rotation_type: str
    participants: List[dict]
    timezone: str
    handoff_time: Any  # time object serialised as string
    handoff_day: Optional[str]
    effective_from: datetime
    effective_until: Optional[datetime]
    is_active: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnCallScheduleListResponse(BaseModel):
    """Paginated list of on-call schedules."""

    items: List[OnCallScheduleResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# EscalationPolicy
# ---------------------------------------------------------------------------


class EscalationPolicyCreate(BaseModel):
    """Input schema for creating an escalation policy."""

    name: str
    app_id: Optional[UUID] = None
    description: Optional[str] = None
    repeat_count: int = 0
    resolve_timeout_minutes: int = 60
    is_default: bool = False


class EscalationPolicyUpdate(BaseModel):
    """Input schema for updating an escalation policy (all fields optional)."""

    name: Optional[str] = None
    app_id: Optional[UUID] = None
    description: Optional[str] = None
    repeat_count: Optional[int] = None
    resolve_timeout_minutes: Optional[int] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class EscalationPolicyResponse(BaseModel):
    """Output schema for an escalation policy."""

    id: UUID
    name: str
    app_id: Optional[UUID]
    description: Optional[str]
    repeat_count: int
    resolve_timeout_minutes: int
    is_default: bool
    is_active: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    levels: List["EscalationLevelResponse"] = []

    model_config = {"from_attributes": True}


class EscalationPolicyListResponse(BaseModel):
    """Paginated list of escalation policies."""

    items: List[EscalationPolicyResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# EscalationLevel
# ---------------------------------------------------------------------------


class EscalationLevelCreate(BaseModel):
    """Input schema for adding a level to an escalation policy."""

    policy_id: UUID
    level_number: int
    schedule_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    channel_id: Optional[UUID] = None
    timeout_minutes: int = 30
    urgency: str = "high"
    notification_steps: List[dict] = []

    @model_validator(mode="after")
    def validate_target(self) -> "EscalationLevelCreate":
        has_schedule = self.schedule_id is not None
        has_user = self.user_id is not None
        if has_schedule == has_user:
            raise ValueError(
                "Exactly one of schedule_id or user_id must be set (not both, not neither)"
            )
        return self

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        if v not in ("high", "low"):
            raise ValueError("urgency must be 'high' or 'low'")
        return v


class EscalationLevelResponse(BaseModel):
    """Output schema for an escalation level."""

    id: UUID
    policy_id: UUID
    level_number: int
    schedule_id: Optional[UUID]
    user_id: Optional[UUID]
    channel_id: Optional[UUID]
    timeout_minutes: int
    urgency: str
    notification_steps: List[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# OnCallOverride
# ---------------------------------------------------------------------------


class OnCallOverrideCreate(BaseModel):
    """Input schema for creating a schedule override."""

    schedule_id: UUID
    override_user_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "OnCallOverrideCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class OnCallOverrideResponse(BaseModel):
    """Output schema for an on-call override."""

    id: UUID
    schedule_id: UUID
    override_user_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# On-Call Info (query outputs)
# ---------------------------------------------------------------------------


class OnCallInfo(BaseModel):
    """Information about who is currently on-call."""

    user_id: UUID
    user_name: str
    user_email: str
    role: str  # "primary", "secondary", "shadow"
    schedule_id: UUID
    schedule_name: str
    is_override: bool
    escalation_level: int  # 1 = first responder
    escalates_in_minutes: Optional[int]  # Time until next escalation level


class EscalationContact(BaseModel):
    """A single contact in an escalation chain."""

    level: int
    user: OnCallInfo
    channel_preference: str
    timeout_minutes: int
    policy_id: UUID


class OnCallTimelineEntry(BaseModel):
    """A single slot in the upcoming rotation timeline."""

    starts_at: datetime
    ends_at: datetime
    user_id: UUID
    user_name: str
    is_override: bool


class OnCallCurrentResponse(BaseModel):
    """Response for 'who is on-call right now?' queries."""

    oncall: List[OnCallInfo]


class EscalationChainResponse(BaseModel):
    """Full escalation chain for an application."""

    app_id: UUID
    policy_id: Optional[UUID]
    policy_name: Optional[str]
    contacts: List[EscalationContact]


# Allow forward refs to resolve
EscalationPolicyResponse.model_rebuild()
