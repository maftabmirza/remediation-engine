"""
SQLAlchemy models for PII detection system.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, ForeignKey
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


class PIIFalsePositiveFeedback(Base):
    """User feedback for false positive PII/secret detections."""
    
    __tablename__ = "pii_false_positive_feedback"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # What was flagged
    detected_text = Column(String(500), nullable=False, index=True, comment='The text incorrectly flagged as PII')
    detected_entity_type = Column(String(100), nullable=False, index=True, comment='Entity type that was detected')
    detection_engine = Column(String(50), nullable=False, comment='presidio or detect_secrets')
    original_confidence = Column(Float, nullable=True, comment='Original confidence score')
    
    # Context
    user_id = Column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True, comment='Agent session ID')
    agent_mode = Column(String(50), nullable=True, index=True, comment='alert/revive/troubleshoot')
    detection_log_id = Column(PGUUID(as_uuid=True), ForeignKey('pii_detection_logs.id', ondelete='SET NULL'), nullable=True)
    
    # Feedback details
    reported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    user_comment = Column(Text, nullable=True, comment='Optional reason from user')
    
    # Whitelist status
    whitelisted = Column(Boolean, nullable=False, default=True, index=True, comment='Active in whitelist')
    whitelisted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    whitelist_scope = Column(String(50), nullable=False, default='organization', comment='organization/user/global')
    
    # Admin review workflow (optional)
    review_status = Column(String(50), nullable=False, default='auto_approved', index=True, comment='approved/rejected/pending')
    reviewed_by = Column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Audit
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PIIFalsePositiveFeedback(text='{self.detected_text[:30]}...', type={self.detected_entity_type}, whitelisted={self.whitelisted})>"
