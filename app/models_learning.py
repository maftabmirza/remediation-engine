"""
Learning System Models
Tracks user feedback and execution outcomes for continuous improvement
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class AnalysisFeedback(Base):
    """
    User feedback on AI-generated alert analysis.
    Tracks the quality and usefulness of AI recommendations.
    """
    __tablename__ = "analysis_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Feedback flags
    helpful = Column(Boolean, nullable=True)  # Was the analysis helpful?
    rating = Column(Integer, nullable=True)  # 1-5 star rating
    accuracy = Column(String(30), nullable=True)  # accurate, partially_accurate, inaccurate

    # Qualitative feedback
    what_was_missing = Column(Text, nullable=True)  # What information was missing?
    what_actually_worked = Column(Text, nullable=True)  # What actually resolved the issue?

    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    alert = relationship("Alert", back_populates="feedback")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            'rating IS NULL OR (rating >= 1 AND rating <= 5)',
            name='ck_analysis_feedback_rating'
        ),
        CheckConstraint(
            "accuracy IS NULL OR accuracy IN ('accurate', 'partially_accurate', 'inaccurate')",
            name='ck_analysis_feedback_accuracy'
        ),
        Index('idx_analysis_feedback_alert_id', 'alert_id'),
        Index('idx_analysis_feedback_user_id', 'user_id'),
        Index('idx_analysis_feedback_created_at', 'created_at'),
    )


class ExecutionOutcome(Base):
    """
    Tracks the actual outcome of runbook executions.
    Used to calculate runbook effectiveness and improve recommendations.
    """
    __tablename__ = "execution_outcomes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("runbook_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Outcome
    resolved_issue = Column(Boolean, nullable=True)  # Did this execution resolve the issue?
    resolution_type = Column(String(30), nullable=True)  # full, partial, no_effect, made_worse

    # Timing
    time_to_resolution_minutes = Column(Integer, nullable=True)  # How long did it take?

    # Learning
    recommendation_followed = Column(Boolean, nullable=True)  # Did they follow the AI recommendation?
    manual_steps_taken = Column(Text, nullable=True)  # What manual steps were needed?
    improvement_suggestion = Column(Text, nullable=True)  # How can we improve this runbook?

    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    execution = relationship("RunbookExecution")
    alert = relationship("Alert")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "resolution_type IS NULL OR resolution_type IN ('full', 'partial', 'no_effect', 'made_worse')",
            name='ck_execution_outcomes_resolution_type'
        ),
        CheckConstraint(
            'time_to_resolution_minutes IS NULL OR time_to_resolution_minutes >= 0',
            name='ck_execution_outcomes_time_positive'
        ),
        Index('idx_execution_outcomes_execution_id', 'execution_id'),
        Index('idx_execution_outcomes_alert_id', 'alert_id'),
        Index('idx_execution_outcomes_user_id', 'user_id'),
        Index('idx_execution_outcomes_created_at', 'created_at'),
    )
