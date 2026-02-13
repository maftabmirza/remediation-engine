from datetime import datetime, timezone
import uuid
from typing import Optional, Dict

from sqlalchemy import Column, String, Text, ForeignKey, DateTime, JSON, Integer, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

# -----------------------------------------------------------------------------
# AI Core Models (Merged from models_revive + New Plan)
# -----------------------------------------------------------------------------

class AISession(Base):
    __tablename__ = "ai_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Core categorization
    pillar = Column(String(20), nullable=False) # 'inquiry', 'troubleshooting', 'revive'
    
    # RE-VIVE specific context
    revive_mode = Column(String(20), nullable=True) # 'grafana', 'aiops'
    
    # General Context
    context_type = Column(String(50), nullable=True) # 'alert', 'dashboard', 'runbook'
    context_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Legacy/Backwards Compat fields from original models_revive (if needed)
    title = Column(String(255), nullable=True)
    context_context_json = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    message_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=True, default=utc_now, onupdate=utc_now)
    
    # PII/Secret mapping for consistent redaction across conversation
    # Structure: {
    #   "[EMAIL_ADDRESS_1]": "john@example.com",
    #   "[EMAIL_ADDRESS_2]": "jane@company.com", 
    #   "_counters": {"EMAIL_ADDRESS": 2, "PHONE_NUMBER": 0, ...},
    #   "_reverse": {"john@example.com": "[EMAIL_ADDRESS_1]", ...}
    # }
    pii_mapping_json = Column(JSON, nullable=True, default=dict)

    # Relationships
    user = relationship("User")
    messages = relationship("AIMessage", back_populates="session", cascade="all, delete-orphan", order_by="AIMessage.created_at")
    tool_executions = relationship("AIToolExecution", back_populates="session", cascade="all, delete-orphan")
    confirmations = relationship("AIActionConfirmation", back_populates="session")

class AIMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    
    role = Column(String(20), nullable=False) # 'user', 'assistant', 'system', 'tool'
    content = Column(Text, nullable=False)
    
    # Assistant Tool Calls
    tool_calls = Column(JSON, nullable=True)
    
    # Tool Response Linkage
    tool_call_id = Column(String(100), nullable=True)
    
    # Metadata / Stats
    tokens_used = Column(Integer, nullable=True)
    metadata_json = Column(JSON, nullable=True) # Backwards compat
    
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    session = relationship("AISession", back_populates="messages")
    tool_executions = relationship("AIToolExecution", back_populates="message")

# -----------------------------------------------------------------------------
# New RBAC & Execution Models
# -----------------------------------------------------------------------------

class AIToolExecution(Base):
    __tablename__ = "ai_tool_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id"), nullable=False)
    message_id = Column(UUID(as_uuid=True), ForeignKey("ai_messages.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    tool_name = Column(String(100), nullable=False)
    tool_category = Column(String(50), nullable=False) # 'inquiry', 'troubleshooting', 'revive_grafana', 'revive_aiops'
    arguments = Column(JSON, nullable=False)
    
    result = Column(Text, nullable=True)
    result_status = Column(String(20), nullable=True) # 'success', 'error', 'blocked', 'pending_approval'
    
    permission_required = Column(String(100), nullable=True)
    permission_granted = Column(Boolean, nullable=True)
    
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("AISession", back_populates="tool_executions")
    message = relationship("AIMessage", back_populates="tool_executions")
    user = relationship("User")

class AIActionConfirmation(Base):
    __tablename__ = "ai_action_confirmations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    action_type = Column(String(100), nullable=False)
    action_details = Column(JSON, nullable=False)
    risk_level = Column(String(20), nullable=True) # 'low', 'medium', 'high', 'critical'
    
    status = Column(String(20), default='pending') # 'pending', 'approved', 'rejected', 'expired'
    
    expires_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("AISession", back_populates="confirmations")
    user = relationship("User")

class AIPermission(Base):
    __tablename__ = "ai_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    
    pillar = Column(String(20), nullable=False)
    tool_category = Column(String(50), nullable=True) # NULL means all
    tool_name = Column(String(100), nullable=True) # NULL means all
    
    permission = Column(String(20), nullable=False) # 'allow', 'deny', 'confirm'
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    
    # Unique constraint to prevent duplicate rules
    __table_args__ = (
        UniqueConstraint('role_id', 'pillar', 'tool_category', 'tool_name', name='uq_ai_permission_role_tool'),
    )
