"""
Troubleshooting Models
Models for alert correlation, root cause analysis, and failure patterns.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Text, Float, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class AlertCorrelation(Base):
    """
    Groups related alerts (an "incident" or "storm") covering a specific problem.
    """
    __tablename__ = "alert_correlations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    summary = Column(String(255), nullable=False)
    root_cause_analysis = Column(Text, nullable=True)
    status = Column(String(50), default='active', nullable=False)  # active, resolved, false_positive
    confidence_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    alerts = relationship("Alert", back_populates="correlation")


class FailurePattern(Base):
    """
    Stores learned failure signatures for faster future diagnosis.
    Matches alert patterns to known root causes.
    """
    __tablename__ = "failure_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_signature = Column(Text, nullable=False)  # JSON or text representation of the pattern
    root_cause_type = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    occurrence_count = Column(Integer, default=1)
    last_seen_at = Column(DateTime(timezone=True), default=utc_now)
    created_at = Column(DateTime(timezone=True), default=utc_now)
