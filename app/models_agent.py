"""
Agent Mode Models - For autonomous troubleshooting sessions
"""
import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AgentStatus(str, Enum):
    """Status of an agent session"""
    IDLE = "idle"
    THINKING = "thinking"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class StepType(str, Enum):
    """Type of agent step"""
    COMMAND = "command"
    ANALYSIS = "analysis"
    QUESTION = "question"
    COMPLETE = "complete"
    FAILED = "failed"


class StepStatus(str, Enum):
    """Status of an individual step"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"


class AgentSession(Base):
    """
    Represents an agent troubleshooting session.
    
    An agent session is created when the user starts "Agent Mode" with a goal.
    The agent then autonomously works through steps to achieve the goal.
    """
    __tablename__ = "agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id"), nullable=True)
    
    # The goal the agent is trying to achieve
    goal = Column(Text, nullable=False)
    
    # Current status
    status = Column(String(50), default=AgentStatus.IDLE.value)
    
    # Configuration
    auto_approve = Column(Boolean, default=False)
    max_steps = Column(Integer, default=20)
    
    # Progress tracking
    current_step_number = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error message if failed
    error_message = Column(Text, nullable=True)
    
    # Final summary when completed
    summary = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User")
    chat_session = relationship("ChatSession")
    server = relationship("Server")
    steps = relationship("AgentStep", back_populates="agent_session", cascade="all, delete-orphan", order_by="AgentStep.step_number")


class AgentStep(Base):
    """
    Represents a single step in an agent's troubleshooting process.
    
    Each step can be:
    - A command to execute
    - An analysis/observation
    - A question for the user
    - A completion message
    """
    __tablename__ = "agent_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_session_id = Column(UUID(as_uuid=True), ForeignKey("agent_sessions.id"), nullable=False)
    
    # Step ordering
    step_number = Column(Integer, nullable=False)
    
    # Step type and content
    step_type = Column(String(20), nullable=False)  # command, analysis, question, complete
    content = Column(Text, nullable=False)  # The command or message
    reasoning = Column(Text, nullable=True)  # Why the agent chose this step
    
    # Execution results
    output = Column(Text, nullable=True)  # Command output or user response
    exit_code = Column(Integer, nullable=True)  # Command exit code
    status = Column(String(20), default=StepStatus.PENDING.value)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    agent_session = relationship("AgentSession", back_populates="steps")
