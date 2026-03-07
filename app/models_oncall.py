"""
On-Call Scheduling & Escalation Models (Feature A1).

Extends the existing NotificationChannel/NotificationPolicy/NotificationDispatcher
architecture with on-call rotations and escalation policies.
"""

import uuid
from datetime import datetime, timezone, time as _time
from typing import List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base
import app.models_group  # noqa: F401 — ensure Group mapper is registered before OnCallSchedule


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class OnCallSchedule(Base):
    """
    An on-call rotation schedule for a group.

    Defines who is on-call at any given time by rotating through a list of
    participants (group members) based on rotation_type (daily/weekly/custom).
    Overrides take priority over the computed rotation.
    """

    __tablename__ = "oncall_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id"),
        nullable=False,
        index=True,
    )
    rotation_type = Column(String(20), nullable=False)
    # [{"user_id": "uuid", "order": 1, "role": "primary"}, ...]
    participants = Column(JSONB, nullable=False, default=list)
    timezone = Column(String(50), nullable=False, default="UTC")
    handoff_time = Column(Time, nullable=False, default=_time(9, 0))
    handoff_day = Column(String(10), nullable=True)  # "monday" (weekly only)
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    group = relationship("Group", foreign_keys=[group_id], lazy="noload")
    created_by_user = relationship("User", foreign_keys=[created_by], lazy="noload")
    overrides = relationship(
        "OnCallOverride", back_populates="schedule", cascade="all, delete-orphan"
    )
    escalation_levels = relationship(
        "EscalationLevel", back_populates="schedule", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint(
            "rotation_type IN ('daily', 'weekly', 'custom')",
            name="oncall_schedules_rotation_type_check",
        ),
        Index("ix_oncall_schedules_group_id", "group_id"),
        Index("ix_oncall_schedules_is_active", "is_active"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OnCallSchedule id={self.id} name={self.name!r} type={self.rotation_type}>"


class EscalationPolicy(Base):
    """
    An ordered escalation policy for an application (or a global default).

    When an alert fires for an application, the matching policy determines which
    on-call person is contacted first and how long to wait before escalating.
    """

    __tablename__ = "escalation_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    app_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id"),
        nullable=True,
        index=True,
    )
    description = Column(Text, nullable=True)
    repeat_count = Column(Integer, nullable=False, default=0)
    resolve_timeout_minutes = Column(Integer, nullable=False, default=60)
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    levels = relationship(
        "EscalationLevel",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="EscalationLevel.level_number",
        lazy="selectin",
    )
    created_by_user = relationship("User", foreign_keys=[created_by], lazy="noload")

    __table_args__ = (
        Index("ix_escalation_policies_app_id", "app_id"),
        Index("ix_escalation_policies_is_default", "is_default"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EscalationPolicy id={self.id} name={self.name!r} default={self.is_default}>"


class EscalationLevel(Base):
    """
    A single level within an EscalationPolicy.

    Each level references either a schedule (on-call rotation) or a specific
    user, plus an optional delivery channel override.
    """

    __tablename__ = "escalation_levels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("escalation_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level_number = Column(Integer, nullable=False)
    schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("oncall_schedules.id"),
        nullable=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    channel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id"),
        nullable=True,
    )
    timeout_minutes = Column(Integer, nullable=False, default=30)
    urgency = Column(String(20), nullable=False, default="high")
    # [{channel_id, delay_minutes}] ordered notification steps within the level
    notification_steps = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    policy = relationship("EscalationPolicy", back_populates="levels")
    schedule = relationship("OnCallSchedule", back_populates="escalation_levels", lazy="noload")
    user = relationship("User", foreign_keys=[user_id], lazy="noload")
    channel = relationship("NotificationChannel", foreign_keys=[channel_id], lazy="noload")

    __table_args__ = (
        CheckConstraint(
            "urgency IN ('high', 'low')",
            name="escalation_levels_urgency_check",
        ),
        CheckConstraint(
            "(schedule_id IS NOT NULL AND user_id IS NULL) OR (schedule_id IS NULL AND user_id IS NOT NULL)",
            name="escalation_levels_target_check",
        ),
        Index("ix_escalation_levels_policy_id", "policy_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<EscalationLevel id={self.id} policy={self.policy_id}"
            f" level={self.level_number}>"
        )


class OnCallOverride(Base):
    """
    A temporary override for an on-call schedule.

    Takes priority over the computed rotation for the duration of the override.
    Used for holiday swaps, PTO coverage, etc.
    """

    __tablename__ = "oncall_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("oncall_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    override_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String(500), nullable=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    schedule = relationship("OnCallSchedule", back_populates="overrides")
    override_user = relationship("User", foreign_keys=[override_user_id], lazy="noload")
    created_by_user = relationship("User", foreign_keys=[created_by], lazy="noload")

    __table_args__ = (Index("ix_oncall_overrides_schedule_id", "schedule_id"),)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<OnCallOverride id={self.id} schedule={self.schedule_id}"
            f" user={self.override_user_id}>"
        )
