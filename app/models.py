"""SQLAlchemy ORM Models"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from typing import TYPE_CHECKING

from app.database import Base
if TYPE_CHECKING:
    from app.models_chat import ChatSession, ChatMessage
else:
    # Avoid runtime circular import but allow SQLAlchemy to find models if needed
    pass


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


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
    created_at = Column(DateTime(timezone=True), default=utc_now)
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
    provider_type = Column(String(50), nullable=False, index=True)  # anthropic, openai, google, ollama
    model_id = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)
    api_base_url = Column(String(255), nullable=True)
    is_default = Column(Boolean, default=False, index=True)
    is_enabled = Column(Boolean, default=True, index=True)
    config_json = Column(JSON, default={"temperature": 0.3, "max_tokens": 2000})
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AutoAnalyzeRule(Base):
    __tablename__ = "auto_analyze_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=100, index=True)  # Lower = higher priority
    alert_name_pattern = Column(String(255), default="*")
    severity_pattern = Column(String(50), default="*")
    instance_pattern = Column(String(255), default="*")
    job_pattern = Column(String(255), default="*")
    action = Column(String(20), default="manual")  # auto_analyze, ignore, manual
    enabled = Column(Boolean, default=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

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
    status = Column(String(20), default="firing", index=True)  # firing, resolved
    labels_json = Column(JSON)
    annotations_json = Column(JSON)
    raw_alert_json = Column(JSON)
    matched_rule_id = Column(UUID(as_uuid=True), ForeignKey("auto_analyze_rules.id"), nullable=True)
    action_taken = Column(String(20), index=True)  # auto_analyze, ignore, manual, pending
    analyzed = Column(Boolean, default=False, index=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    analyzed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    llm_provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id"), nullable=True)
    ai_analysis = Column(Text, nullable=True)
    recommendations_json = Column(JSON, nullable=True)
    analysis_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    matched_rule = relationship("AutoAnalyzeRule", back_populates="matched_alerts")
    analyzed_by_user = relationship("User", back_populates="alerts_analyzed")
    llm_provider = relationship("LLMProvider")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    user = relationship("User")


class ServerCredential(Base):
    __tablename__ = "server_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    hostname = Column(String(255), nullable=False, index=True)
    port = Column(Integer, default=22)
    username = Column(String(100), nullable=False)
    auth_type = Column(String(20), default="key")  # key, password
    ssh_key_encrypted = Column(Text, nullable=True)
    password_encrypted = Column(Text, nullable=True)
    environment = Column(String(50), default="production", index=True)  # production, staging, dev
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    created_by_user = relationship("User")


class TerminalSession(Base):
    __tablename__ = "terminal_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    server_credential_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=False)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, index=True)
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
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
