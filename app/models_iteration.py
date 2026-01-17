from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base

class IterationLoop(Base):
    __tablename__ = "iteration_loops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False)
    iteration_number = Column(Integer, nullable=False)
    command = Column(Text, nullable=True)
    output = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    error_detected = Column(Boolean, default=False)
    error_type = Column(String(255), nullable=True)
    error_analysis = Column(Text, nullable=True)
    fix_proposed = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    task = relationship("AgentTask", back_populates="iterations")
