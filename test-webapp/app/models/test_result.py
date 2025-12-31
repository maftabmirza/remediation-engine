"""
Test Result Models
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class TestResultStatus(str, enum.Enum):
    """Individual test result status"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestResult(Base):
    """
    Test Result - Result of a single test case execution
    """
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(TestResultStatus), nullable=False, index=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    screenshots = Column(JSON, nullable=True)  # Array of screenshot paths
    logs = Column(JSON, nullable=True)  # Structured logs
    metadata = Column(JSON, nullable=True)  # Additional data
    executed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    test_run = relationship("TestRun", back_populates="test_results")
    test_case = relationship("TestCase", back_populates="test_results")
    test_steps = relationship("TestStepResult", back_populates="test_result", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TestResult(id={self.id}, status='{self.status}', case_id={self.case_id})>"


class TestStepResult(Base):
    """
    Test Step Result - Individual step within a test case
    """
    __tablename__ = "test_step_results"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    step_name = Column(String(255), nullable=False)
    status = Column(Enum(TestResultStatus), nullable=False)
    duration_seconds = Column(Float, nullable=True)
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    executed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    test_result = relationship("TestResult", back_populates="test_steps")

    def __repr__(self):
        return f"<TestStepResult(id={self.id}, step={self.step_number}, status='{self.status}')>"
