"""
Test Alert Link Model - Links test cases to alert types in the remediation engine
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class TestAlertLink(Base):
    """
    Test Alert Link - Maps test cases to alert types in the remediation engine
    This allows automatic test execution when specific alerts are triggered
    """
    __tablename__ = "test_alert_links"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_name = Column(String(255), nullable=False, index=True)  # e.g., "HighCPUUsage"
    alert_labels = Column(JSON, nullable=True)  # Label matchers for alerts
    auto_execute = Column(Boolean, default=False, nullable=False)  # Auto-run on alert
    notify_on_failure = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    test_case = relationship("TestCase", back_populates="alert_links")

    def __repr__(self):
        return f"<TestAlertLink(id={self.id}, alert='{self.alert_name}', case_id={self.case_id})>"
