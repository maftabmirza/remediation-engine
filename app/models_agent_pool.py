import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .database import Base

class AgentPool(Base):
    __tablename__ = "agent_pools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id"), nullable=False)
    name = Column(String(255), nullable=False)
    max_concurrent_agents = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agent_tasks = relationship("AgentTask", back_populates="pool")

class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id = Column(UUID(as_uuid=True), ForeignKey("agent_pools.id"), nullable=False)
    agent_session_id = Column(UUID(as_uuid=True), ForeignKey("agent_sessions.id"), nullable=True) # Can be null if queued but not started
    
    agent_type = Column(String(50), default="background") # 'local', 'background'
    goal = Column(Text, nullable=False)
    priority = Column(Integer, default=10)
    status = Column(String(50), default="queued") # 'queued', 'running', 'completed', 'failed', 'paused'
    
    worktree_path = Column(String(1024), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Auto-Iteration Config for this task
    auto_iterate = Column(Boolean, default=False)
    max_iterations = Column(Integer, default=5)

    # Relationships
    pool = relationship("AgentPool", back_populates="agent_tasks")
    agent_session = relationship("AgentSession", backref="task")
    iterations = relationship("IterationLoop", back_populates="task", cascade="all, delete-orphan")

    @property
    def iteration_count(self):
        return len(self.iterations)


class ActionProposal(Base):
    """
    Proposed actions from background agents that require user approval.
    
    Background agents cannot execute commands directly.
    They propose actions which appear in the Agent HQ UI for user review.
    """
    __tablename__ = "action_proposals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False)
    
    action_type = Column(String(50), nullable=False)  # 'execute_command', 'restart_service', 'modify_file'
    description = Column(Text, nullable=False)  # Human-readable explanation
    command = Column(Text, nullable=True)  # Actual command or action details
    safety_level = Column(String(20), default='warning')  # 'safe', 'warning', 'dangerous'
    
    status = Column(String(20), default='pending')  # 'pending', 'approved', 'rejected', 'executed'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    result = Column(Text, nullable=True)  # Execution result if approved and executed
    rejection_reason = Column(Text, nullable=True)  # Why it was rejected (optional)
    
    # Relationships
    task = relationship("AgentTask", backref="action_proposals")
