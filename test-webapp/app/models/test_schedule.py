"""
Test Schedule Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class TestSchedule(Base):
    """
    Test Schedule - Scheduled test execution configuration
    """
    __tablename__ = "test_schedules"

    id = Column(Integer, primary_key=True, index=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    cron_expression = Column(String(100), nullable=False)  # e.g., "0 2 * * *"
    enabled = Column(Boolean, default=True, nullable=False)
    environment = Column(String(100), nullable=True)
    config = Column(JSON, nullable=True)  # Additional configuration
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    test_suite = relationship("TestSuite")

    def __repr__(self):
        return f"<TestSchedule(id={self.id}, name='{self.name}', cron='{self.cron_expression}')>"
