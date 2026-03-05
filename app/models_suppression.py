"""
SQLAlchemy model for Alert Suppression Rules.

Allows operators to suppress alert noise during maintenance windows.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class AlertSuppressionRule(Base):
    """
    Defines a rule that suppresses matching alerts.

    Alerts matched by an active suppression rule are stored with
    status='suppressed' and bypassed from clustering, analysis, and
    auto-remediation pipelines.
    """

    __tablename__ = "alert_suppression_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Human-readable name for the rule
    name = Column(String(200), nullable=False)

    # Rule type: "time_based" | "label_based" | "service_based" | "maintenance"
    rule_type = Column(String(20), nullable=False)

    # JSON dict of label matchers, e.g. {"alertname": ".*CPU.*", "severity": "warning"}
    # Values are treated as regex patterns matched against alert label values.
    matchers = Column(JSONB, nullable=True)

    # Optional: restrict rule to a specific application
    app_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Active window
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)  # NULL = permanent

    # Minutes to continue suppression after window ends (prevents flapping storms)
    grace_period_minutes = Column(Integer, default=5, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Audit
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    application = relationship("Application", foreign_keys=[app_id])
    creator = relationship("User", foreign_keys=[created_by])
