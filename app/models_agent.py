"""
Agent Mode Database Models

Provides SQLAlchemy models for agent sessions and steps.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer, Boolean, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class AgentSession(Base):
    """
    Agent session tracking.
    
    An agent session represents a goal-driven autonomous interaction
    where the AI agent executes commands on a remote server.
    """
    __tablename__ = "agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=True)
    
    goal = Column(Text, nullable=False)
    status = Column(String(50), default='idle')  # idle, thinking, awaiting_approval, executing, completed, failed, stopped
    auto_approve = Column(Boolean, default=False)
    max_steps = Column(Integer, default=20)
    current_step_number = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), default=utc_now)  # For session timeout
    
    error_message = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    
    # Multi-Agent columns
    agent_type = Column(String(50), default='local') # local, background, cloud
    pool_id = Column(UUID(as_uuid=True), ForeignKey("agent_pools.id"), nullable=True)
    worktree_path = Column(String(1024), nullable=True) # for file isolation
    
    # Auto-iteration columns
    auto_iterate = Column(Boolean, default=False)
    max_auto_iterations = Column(Integer, default=5)

    # Relationships
    steps = relationship("AgentStep", back_populates="session", cascade="all, delete-orphan", order_by="AgentStep.step_number")
    audit_logs = relationship("AgentAuditLog", back_populates="session", cascade="all, delete-orphan", order_by="AgentAuditLog.created_at")
    user = relationship("User")
    server = relationship("ServerCredential")
    # pool relationship defined in models_agent_pool.py to avoid circular import issues, or we use string reference if possible. 
    # For now, backref from AgentTask is often enough, but let's keep it simple.


class AgentStep(Base):
    """
    Individual step in an agent session.
    
    Each step represents either a command to execute, a completion message,
    or a failure message.
    """
    __tablename__ = "agent_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_session_id = Column(UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False)
    
    step_number = Column(Integer, nullable=False)
    step_type = Column(String(20), nullable=False)  # command, complete, failed, question
    content = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)
    
    output = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    status = Column(String(20), default='pending')  # pending, executed, rejected, failed, blocked
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Phase 3 Enhancements
    iteration_count = Column(Integer, default=0)
    change_set_id = Column(UUID(as_uuid=True), ForeignKey("change_sets.id"), nullable=True)
    
    # Command validation
    validation_result = Column(String(20), nullable=True)  # allowed, blocked, suspicious
    blocked_reason = Column(String(500), nullable=True)
    
    # User feedback and additional data (note: 'metadata' is reserved in SQLAlchemy)
    # Database schema has this as TEXT, not JSON
    step_metadata = Column(Text, nullable=True)

    
    # Relationships
    session = relationship("AgentSession", back_populates="steps")


class AgentAuditLog(Base):
    """
    Audit log for all agent actions.
    
    Records every command execution, approval, rejection, and system event
    for security auditing and compliance.
    """
    __tablename__ = "agent_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True)
    step_id = Column(UUID(as_uuid=True), ForeignKey("agent_steps.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    action = Column(String(50), nullable=False)  # session_start, command_proposed, command_approved, command_executed, command_blocked, command_rejected, session_complete, session_timeout
    command = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # Additional context - stored as TEXT in DB, serialize JSON manually
    
    ip_address = Column(String(45), nullable=True)  # Client IP
    user_agent = Column(String(500), nullable=True)
    
    # Command validation fields (matching database schema order)
    validation_result = Column(String(20), nullable=True)  # allowed, blocked, suspicious
    blocked_reason = Column(String(500), nullable=True)
    
    output_preview = Column(String(1000), nullable=True)  # First chars of output
    exit_code = Column(Integer, nullable=True)
    
    server_id = Column(UUID(as_uuid=True), nullable=True)
    server_name = Column(String(255), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    
    # Relationships
    session = relationship("AgentSession", back_populates="audit_logs")
    user = relationship("User")
    
    __table_args__ = (
        Index("idx_audit_user_created", "user_id", "created_at"),
        Index("idx_audit_session", "session_id"),
        Index("idx_audit_action", "action"),
    )


class AgentRateLimit(Base):
    """
    Rate limiting for agent operations.
    
    Tracks command/session counts per user for rate limiting.
    """
    __tablename__ = "agent_rate_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Counters
    commands_this_minute = Column(Integer, default=0)
    sessions_this_hour = Column(Integer, default=0)
    
    # Reset timestamps (match database column names)
    minute_window_start = Column(DateTime(timezone=True), default=utc_now)
    hour_window_start = Column(DateTime(timezone=True), default=utc_now)
    
    # Limits (can be customized per user)
    max_commands_per_minute = Column(Integer, default=10)
    max_sessions_per_hour = Column(Integer, default=30)
    
    # Rate limit status
    is_rate_limited = Column(Boolean, default=False)
    rate_limited_until = Column(DateTime(timezone=True), nullable=True)
    
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
