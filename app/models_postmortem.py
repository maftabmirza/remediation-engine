"""
Post-Incident Postmortem Models

SQLAlchemy model for auto-generated and manually edited postmortem reports.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base

# Ensure the Incident mapper is registered before PostmortemReport so that the
# back-reference relationship can be resolved at mapper configuration time.
import app.models_incident  # noqa: F401


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class PostmortemReport(Base):
    """
    Auto-generated (or manually created) post-incident review document.

    AI generates the initial draft from alert + execution + feedback data.
    Engineers can edit and add out-of-band context before publishing.
    """

    __tablename__ = "postmortem_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core metadata
    title = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft, in_review, published
    severity = Column(String(20), nullable=True)
    generated_by = Column(String(20), nullable=False, default="ai")  # ai, manual

    # Incident time window
    incident_start = Column(DateTime(timezone=True), nullable=True)
    incident_end = Column(DateTime(timezone=True), nullable=True)

    # Links to source data
    # Primary anchor: incident_id (new incident-first model)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Legacy anchor: alert_id kept for backward compatibility and lineage
    alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    app_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # AI-generated narrative sections
    impact_summary = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    lessons_learned = Column(Text, nullable=True)

    # Structured data stored as JSONB arrays/objects
    # [{timestamp, event, source, manual: bool}]
    timeline = Column(JSONB, nullable=False, default=list)
    # [string]
    contributing_factors = Column(JSONB, nullable=False, default=list)
    # [{action, runbook_id, outcome, duration_minutes}]
    remediation_actions = Column(JSONB, nullable=False, default=list)
    # [{description, owner, due_date, status}]
    action_items = Column(JSONB, nullable=False, default=list)
    # {mttd_minutes, mtta_minutes, mtte_minutes, mttr_minutes}
    metrics = Column(JSONB, nullable=False, default=dict)
    # [{source, content, timestamp}]
    out_of_band_context = Column(JSONB, nullable=False, default=list)

    # Review workflow
    reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    # Relationships
    incident = relationship("Incident", back_populates="postmortems", foreign_keys=[incident_id])
    alert = relationship("Alert", foreign_keys=[alert_id])
    application = relationship("Application", foreign_keys=[app_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_postmortem_reports_incident_id", "incident_id"),
        Index("ix_postmortem_reports_alert_id", "alert_id"),
        Index("ix_postmortem_reports_app_id", "app_id"),
        Index("ix_postmortem_reports_status", "status"),
        Index("ix_postmortem_reports_created_at", "created_at"),
    )
