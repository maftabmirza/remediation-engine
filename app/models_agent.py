"""
Agent Mode Database Models

Provides SQLAlchemy models for agent sessions and steps.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer, Boolean
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
    status = Column(String(20), default='pending')  # pending, executed, rejected, failed
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Phase 3 Enhancements
    iteration_count = Column(Integer, default=0)
    change_set_id = Column(UUID(as_uuid=True), ForeignKey("change_sets.id"), nullable=True)

    
    # Relationships
    session = relationship("AgentSession", back_populates="steps")
