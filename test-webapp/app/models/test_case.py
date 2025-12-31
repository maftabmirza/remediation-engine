"""
Test Case Model
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class TestPriority(str, enum.Enum):
    """Test case priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestCase(Base):
    """
    Test Case - Individual test definition
    """
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(String(50), nullable=False, unique=True, index=True)  # e.g., "L01", "S01"
    suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    test_file_path = Column(String(500), nullable=False)  # Path to the pytest file
    test_function = Column(String(255), nullable=False)  # Pytest function name
    priority = Column(Enum(TestPriority), default=TestPriority.MEDIUM, nullable=False)
    timeout_seconds = Column(Integer, default=300, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    tags = Column(JSON, nullable=True)  # Array of tags
    requirements = Column(JSON, nullable=True)  # Required conditions to run
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    test_suite = relationship("TestSuite", back_populates="test_cases")
    test_results = relationship("TestResult", back_populates="test_case", cascade="all, delete-orphan")
    alert_links = relationship("TestAlertLink", back_populates="test_case", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TestCase(id={self.id}, test_id='{self.test_id}', name='{self.name}')>"
