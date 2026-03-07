"""
Incident Aggregate Model

Native incident aggregate that groups related alerts into a first-class
incident entity, used as the primary anchor for postmortem generation.

An incident can be seeded from:
  1. AlertCorrelation  (primary grouping seed)
  2. AlertCluster      (fallback when no correlation exists)
  3. IncidentEvent     (optional ITSM linkage)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base

# Keep mapper registration order correct
import app.models_troubleshooting  # noqa: F401 — registers AlertCorrelation
import app.models_itsm  # noqa: F401 — registers IncidentEvent


def utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# Grace period (minutes) an incident must stay resolved before it becomes
# eligible for postmortem generation. Prevents premature reports for
# flapping incidents.
RESOLUTION_GRACE_PERIOD_MINUTES = 30


class Incident(Base):
    """
    Native incident aggregate.

    Materialised from one or more correlated/clustered alerts.  Once an
    incident reaches a stable *resolved* state (i.e. resolved_at is set
    AND the grace period has elapsed) it becomes eligible for postmortem
    generation.

    Status lifecycle:
        open  ──►  resolved  ──►  closed
               (grace period)
    """

    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Human-readable title derived from the root-cause alert / correlation
    title = Column(String(500), nullable=False)

    # Lifecycle status: open | resolved | closed
    status = Column(String(50), nullable=False, default="open", index=True)

    # Highest severity across all member alerts
    severity = Column(String(20), nullable=True, index=True)

    # ── Grouping seeds ────────────────────────────────────────────────────
    # Primary: AlertCorrelation  (preferred)
    correlation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_correlations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Fallback: AlertCluster
    cluster_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_clusters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Optional ITSM linkage
    itsm_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incident_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Time window ───────────────────────────────────────────────────────
    started_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # When the grace period ends (resolved_at + RESOLUTION_GRACE_PERIOD_MINUTES).
    # Set at the time the incident is resolved; postmortem eligibility is not
    # checked until this timestamp has passed.
    grace_period_ends_at = Column(DateTime(timezone=True), nullable=True)

    # ── Postmortem eligibility ────────────────────────────────────────────
    # Flipped to True once: status == resolved AND grace_period_ends_at has passed
    is_eligible_for_postmortem = Column(
        Boolean, nullable=False, default=False, index=True
    )

    # ── Affected services / components ────────────────────────────────────
    # JSONB array of service name strings derived from member alerts/correlation
    affected_services = Column(JSONB, nullable=False, default=list)

    # ── Audit ─────────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    correlation = relationship("AlertCorrelation", foreign_keys=[correlation_id])
    cluster = relationship("AlertCluster", foreign_keys=[cluster_id])
    itsm_event = relationship("IncidentEvent", foreign_keys=[itsm_event_id])
    postmortems = relationship("PostmortemReport", back_populates="incident")

    __table_args__ = (
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_severity", "severity"),
        Index("ix_incidents_correlation_id", "correlation_id"),
        Index("ix_incidents_cluster_id", "cluster_id"),
        Index("ix_incidents_resolved_at", "resolved_at"),
        Index("ix_incidents_eligible", "is_eligible_for_postmortem"),
        Index("ix_incidents_started_at", "started_at"),
    )
