"""
Test Run Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class TestRunStatus(str, enum.Enum):
    """Test run status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestRunTrigger(str, enum.Enum):
    """How the test run was triggered"""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    API = "api"


class TestRun(Base):
    """
    Test Run - An execution of one or more test cases
    """
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(Enum(TestRunStatus), default=TestRunStatus.PENDING, nullable=False, index=True)
    trigger = Column(Enum(TestRunTrigger), default=TestRunTrigger.MANUAL, nullable=False)
    triggered_by = Column(String(255), nullable=True)  # Username or system
    environment = Column(String(100), nullable=True)  # e.g., "staging", "production"
    branch = Column(String(255), nullable=True)  # Git branch if applicable
    commit_hash = Column(String(40), nullable=True)  # Git commit hash
    total_tests = Column(Integer, default=0, nullable=False)
    passed_tests = Column(Integer, default=0, nullable=False)
    failed_tests = Column(Integer, default=0, nullable=False)
    skipped_tests = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional metadata
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    test_suite = relationship("TestSuite", back_populates="test_runs")
    test_results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TestRun(id={self.id}, status='{self.status}', total={self.total_tests})>"
