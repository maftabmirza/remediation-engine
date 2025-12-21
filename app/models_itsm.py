"""
ITSM Integration Models

Models for ITSM system integrations and change event tracking.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


class ITSMIntegration(Base):
    """ITSM system integration configuration"""
    __tablename__ = "itsm_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    connector_type = Column(String(50), default='generic_api', nullable=False)
    config_encrypted = Column(Text, nullable=False)  # Encrypted JSON config
    is_enabled = Column(Boolean, default=True, nullable=False, index=True)
    last_sync = Column(DateTime(timezone=True), index=True)
    last_sync_status = Column(String(50))  # success, failed, partial
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ChangeEvent(Base):
    """Change/deployment event from ITSM system"""
    __tablename__ = "change_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_id = Column(String(255), unique=True, nullable=False, index=True)
    change_type = Column(String(50), nullable=False)  # deployment, config, scaling, maintenance
    service_name = Column(String(255), index=True)
    description = Column(Text)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True))  # When the change started
    end_time = Column(DateTime(timezone=True))    # When the change completed
    source = Column(String(100), index=True)  # integration ID or 'webhook'
    change_metadata = Column(JSONB, default={})  # Renamed from 'metadata' which is reserved
    correlation_score = Column(Float, index=True)
    impact_level = Column(String(20))  # high, medium, low, none
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    impact_analysis = relationship("ChangeImpactAnalysis", back_populates="change_event", uselist=False, cascade="all, delete-orphan")


class ChangeImpactAnalysis(Base):
    """Analysis of change impact on incidents"""
    __tablename__ = "change_impact_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_event_id = Column(UUID(as_uuid=True), ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False)
    incidents_after = Column(Integer, default=0)
    critical_incidents = Column(Integer, default=0)
    correlation_score = Column(Float, nullable=False, index=True)
    impact_level = Column(String(20), nullable=False)  # high, medium, low, none
    recommendation = Column(Text)
    analyzed_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    change_event = relationship("ChangeEvent", back_populates="impact_analysis")
