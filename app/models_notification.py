"""
Notification System Models

Handles notification channels (Slack, MS Teams, Email, Webhook),
routing policies, and delivery audit logs.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Index,
    Integer, String, Text, ForeignKey,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class NotificationChannel(Base):
    """
    A configured notification destination.

    Stores the connection config for a delivery channel such as a
    Slack workspace, SMTP server, or generic webhook endpoint.
    Secrets inside ``config_json`` are encrypted with the app's
    ``encryption_key`` before persistence.
    """

    __tablename__ = "notification_channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    channel_type = Column(String(20), nullable=False, index=True)
    config_json = Column(JSONB, nullable=False, default=dict)
    is_enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], lazy="noload")
    log_entries = relationship(
        "NotificationLog", back_populates="channel", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "channel_type IN ('slack', 'msteams', 'email', 'webhook')",
            name="notification_channels_type_check",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificationChannel id={self.id} name={self.name!r} type={self.channel_type}>"


class NotificationPolicy(Base):
    """
    A routing rule that maps an event type (and optional severity) to one or
    more destination channels.
    """

    __tablename__ = "notification_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False, index=True)
    severity_filter = Column(ARRAY(String), nullable=True)  # None = all severities
    channel_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    is_enabled = Column(Boolean, nullable=False, default=True, index=True)
    template_key = Column(String(50), nullable=True)  # Override default template
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], lazy="noload")
    log_entries = relationship("NotificationLog", back_populates="policy")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<NotificationPolicy id={self.id} name={self.name!r}"
            f" event={self.event_type}>"
        )


class NotificationLog(Base):
    """
    An immutable delivery audit record for every notification attempt.

    A single ``notify()`` call may generate multiple log rows — one per
    channel that matches the policy.
    """

    __tablename__ = "notification_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(50), nullable=False)
    event_id = Column(UUID(as_uuid=True), nullable=True)
    recipient = Column(String(255), nullable=True)  # e.g. "#ops-alerts" or email address
    status = Column(String(20), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    payload_json = Column(JSONB, nullable=True)  # Snapshot of what was actually sent
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    policy = relationship("NotificationPolicy", back_populates="log_entries")
    channel = relationship("NotificationChannel", back_populates="log_entries")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'retrying')",
            name="notification_log_status_check",
        ),
        Index("idx_notification_log_status", "status"),
        Index("idx_notification_log_event", "event_type", "event_id"),
        Index("idx_notification_log_created", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<NotificationLog id={self.id} event={self.event_type}"
            f" status={self.status}>"
        )
