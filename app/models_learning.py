"""
Learning System Models
Tracks user feedback and execution outcomes for continuous improvement
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, ForeignKey, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
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


class RunbookClick(Base):
    """
    Tracks all runbook link clicks from AI recommendations.
    Used for learning user preferences and boosting recommendation confidence.
    """
    __tablename__ = "runbook_clicks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Session tracking (can be chat session or AI helper session)
    session_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Source identification
    source = Column(String(50), nullable=False, default='unknown')  # 'chat_page', 'agent_widget', 'alert_detail'
    
    # Context at time of click
    query_text = Column(Text, nullable=True)  # What the user asked
    confidence_shown = Column(Float, nullable=True)  # Confidence score shown to user (0.0-1.0)
    rank_shown = Column(Integer, nullable=True)  # Position in list (1 = first)
    
    # Timestamp
    clicked_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    
    # Additional context (os_type, alert_id, etc.)
    context_json = Column(JSONB, nullable=True)

    # Relationships
    runbook = relationship("Runbook")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "source IN ('chat_page', 'agent_widget', 'alert_detail', 'runbook_list', 'unknown')",
            name='ck_runbook_clicks_source'
        ),
        CheckConstraint(
            'confidence_shown IS NULL OR (confidence_shown >= 0.0 AND confidence_shown <= 1.0)',
            name='ck_runbook_clicks_confidence_range'
        ),
        CheckConstraint(
            'rank_shown IS NULL OR rank_shown >= 1',
            name='ck_runbook_clicks_rank_positive'
        ),
        Index('idx_runbook_clicks_runbook_id', 'runbook_id'),
        Index('idx_runbook_clicks_user_id', 'user_id'),
        Index('idx_runbook_clicks_clicked_at', 'clicked_at'),
        Index('idx_runbook_clicks_source', 'source'),
    )


class AIFeedback(Base):
    """
    Tracks user thumbs up/down feedback on both:
    - Runbook suggestions (affects ranking)
    - LLM responses (for analytics/prompt tuning)
    """
    __tablename__ = "ai_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Feedback target (one of these is set based on target_type)
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id", ondelete="CASCADE"), nullable=True, index=True)
    message_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # For LLM response feedback
    
    # Feedback data
    feedback_type = Column(String(20), nullable=False)  # 'thumbs_up', 'thumbs_down'
    target_type = Column(String(20), nullable=False)    # 'runbook', 'llm_response'
    
    # Context
    query_text = Column(Text, nullable=True)     # What the user asked
    response_text = Column(Text, nullable=True)  # The AI response (for LLM feedback)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    runbook = relationship("Runbook")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "feedback_type IN ('thumbs_up', 'thumbs_down')",
            name='ck_ai_feedback_type'
        ),
        CheckConstraint(
            "target_type IN ('runbook', 'llm_response')",
            name='ck_ai_feedback_target_type'
        ),
        Index('idx_ai_feedback_runbook_id', 'runbook_id'),
        Index('idx_ai_feedback_user_id', 'user_id'),
        Index('idx_ai_feedback_created_at', 'created_at'),
        Index('idx_ai_feedback_feedback_type', 'feedback_type'),
        Index('idx_ai_feedback_target_type', 'target_type'),
    )
