"""
Scheduler Models

Database models for scheduled runbook execution.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, CheckConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone

from .database import Base


class ScheduledJob(Base):
    """
    Scheduled job configuration for automated runbook execution.
    Supports cron, interval, and one-time date-based schedules.
    """
    __tablename__ = "scheduled_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Schedule Configuration
    schedule_type = Column(String(50), nullable=False)  # 'cron', 'interval', 'date'
    cron_expression = Column(String(100))  # e.g., '0 2 * * *' (daily at 2 AM)
    interval_seconds = Column(Integer)  # For interval-based schedules
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    timezone = Column(String(50), default="UTC")
    
    # Execution Configuration  
    target_server_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"))
    execution_params = Column(JSON)  # Override runbook parameters
    max_instances = Column(Integer, default=1)  # Prevent overlapping executions
    misfire_grace_time = Column(Integer, default=300)  # Seconds to allow late execution
    
    # Status and Statistics
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True))
    last_run_status = Column(String(50))  # 'success', 'failed', 'skipped'
    next_run_at = Column(DateTime(timezone=True))
    run_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    runbook = relationship("Runbook", back_populates="schedules")
    server = relationship("ServerCredential")
    creator = relationship("User")
    execution_history = relationship("ScheduleExecutionHistory", back_populates="scheduled_job", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("schedule_type IN ('cron', 'interval', 'date')", name="valid_schedule_type"),
    )


class ScheduleExecutionHistory(Base):
    """
    Execution history for scheduled jobs.
    Tracks when a schedule was supposed to run and whether it succeeded.
    """
    __tablename__ = "schedule_execution_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheduled_job_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_jobs.id", ondelete="CASCADE"), nullable=False)
    runbook_execution_id = Column(UUID(as_uuid=True), ForeignKey("runbook_executions.id"))
    
    scheduled_at = Column(DateTime(timezone=True), nullable=False)  # When it was supposed to run
    executed_at = Column(DateTime(timezone=True))  # When it actually ran
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(50), nullable=False)  # 'success', 'failed', 'missed', 'skipped'
    error_message = Column(Text)
    duration_ms = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    scheduled_job = relationship("ScheduledJob", back_populates="execution_history")
    runbook_execution = relationship("RunbookExecution")
