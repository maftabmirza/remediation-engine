"""
SQLAlchemy models for PII detection system.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.sql import func

from app.database import Base


class PIIDetectionConfig(Base):
    """Configuration for PII and secret detection."""
    
    __tablename__ = "pii_detection_config"
    __table_args__ = (
        UniqueConstraint('config_type', 'entity_type', name='uq_config_type_entity'),
    )
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    config_type = Column(String(50), nullable=False, index=True, comment='presidio or detect_secrets')
    entity_type = Column(String(100), nullable=False, index=True, comment='Entity/plugin name')
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    threshold = Column(Float, nullable=False, default=0.7, comment='Confidence threshold (0.0-1.0)')
    redaction_type = Column(String(50), nullable=False, default='mask', comment='mask, hash, remove, or tag')
    custom_pattern = Column(Text, nullable=True, comment='Optional custom regex')
    settings_json = Column(JSONB, nullable=True, comment='Additional settings')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PIIDetectionConfig(type={self.config_type}, entity={self.entity_type}, enabled={self.enabled})>"


class PIIDetectionLog(Base):
    """Audit log of PII/secret detections."""
    
    __tablename__ = "pii_detection_logs"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    detection_engine = Column(String(50), nullable=False, index=True, comment='presidio or detect_secrets')
    confidence_score = Column(Float, nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True, comment='runbook_output, llm_response, alert, etc.')
    source_id = Column(PGUUID(as_uuid=True), nullable=True, index=True, comment='FK to source record')
    context_snippet = Column(Text, nullable=True, comment='Surrounding text (redacted)')
    position_start = Column(Integer, nullable=False)
    position_end = Column(Integer, nullable=False)
    was_redacted = Column(Boolean, nullable=False, default=True)
    redaction_type = Column(String(50), nullable=True)
    original_hash = Column(String(64), nullable=False, index=True, comment='SHA-256 hash of original value')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    def __repr__(self):
        return f"<PIIDetectionLog(type={self.entity_type}, engine={self.detection_engine}, score={self.confidence_score})>"


class SecretBaseline(Base):
    """Baseline tracking for known/acknowledged secrets."""
    
    __tablename__ = "secret_baselines"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    secret_hash = Column(String(64), nullable=False, unique=True, index=True, comment='SHA-256 hash of secret')
    secret_type = Column(String(100), nullable=False, index=True)
    first_detected = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_detected = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    detection_count = Column(Integer, nullable=False, default=1)
    is_acknowledged = Column(Boolean, nullable=False, default=False, index=True)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<SecretBaseline(type={self.secret_type}, acknowledged={self.is_acknowledged}, count={self.detection_count})>"
