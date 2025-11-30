"""
SQLAlchemy ORM Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models_chat import ChatSession, ChatMessage


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    default_llm_provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    default_llm_provider = relationship("LLMProvider", foreign_keys=[default_llm_provider_id])
    rules_created = relationship("AutoAnalyzeRule", back_populates="created_by_user")
    alerts_analyzed = relationship("Alert", back_populates="analyzed_by_user")
    chat_sessions = relationship("ChatSession", back_populates="user")


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    provider_type = Column(String(50), nullable=False)  # anthropic, openai, google, ollama
    model_id = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)
    api_base_url = Column(String(255), nullable=True)
    is_default = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)
    config_json = Column(JSON, default={"temperature": 0.3, "max_tokens": 2000})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AutoAnalyzeRule(Base):
    __tablename__ = "auto_analyze_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=100)  # Lower = higher priority
    alert_name_pattern = Column(String(255), default="*")
    severity_pattern = Column(String(50), default="*")
    instance_pattern = Column(String(255), default="*")
    job_pattern = Column(String(255), default="*")
    action = Column(String(20), default="manual")  # auto_analyze, ignore, manual
    enabled = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by_user = relationship("User", back_populates="rules_created")
    matched_alerts = relationship("Alert", back_populates="matched_rule")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint = Column(String(100), index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    alert_name = Column(String(255), nullable=False, index=True)
    severity = Column(String(50), index=True)
    instance = Column(String(255))
    job = Column(String(100))
    status = Column(String(20), default="firing")  # firing, resolved
    labels_json = Column(JSON)
    annotations_json = Column(JSON)
    raw_alert_json = Column(JSON)
    matched_rule_id = Column(UUID(as_uuid=True), ForeignKey("auto_analyze_rules.id"), nullable=True)
    action_taken = Column(String(20))  # auto_analyze, ignore, manual, pending
    analyzed = Column(Boolean, default=False, index=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    analyzed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    llm_provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id"), nullable=True)
    ai_analysis = Column(Text, nullable=True)
    recommendations_json = Column(JSON, nullable=True)
    analysis_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    matched_rule = relationship("AutoAnalyzeRule", back_populates="matched_alerts")
    analyzed_by_user = relationship("User", back_populates="alerts_analyzed")
    llm_provider = relationship("LLMProvider")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    user = relationship("User")


class ServerCredential(Base):
    __tablename__ = "server_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    hostname = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(100), nullable=False)
    auth_type = Column(String(20), default="key")  # key, password
    ssh_key_encrypted = Column(Text, nullable=True)
    password_encrypted = Column(Text, nullable=True)
    environment = Column(String(50), default="production")  # production, staging, dev
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by_user = relationship("User")


class TerminalSession(Base):
    __tablename__ = "terminal_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    server_credential_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=False)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    recording_path = Column(String(255), nullable=True)

    # Relationships
    user = relationship("User")
    server = relationship("ServerCredential")
    alert = relationship("Alert")


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(50), primary_key=True)
    value_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
