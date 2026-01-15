from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class KnowledgeSyncHistory(Base):
    __tablename__ = 'knowledge_sync_history'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    status = Column(String(50), default='running')
    documents_added = Column(Integer, default=0)
    documents_updated = Column(Integer, default=0)
    documents_deleted = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    source_id = Column(UUID(as_uuid=True), nullable=True)

class AIHelperSession(Base):
    __tablename__ = 'ai_helper_sessions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    last_activity_at = Column(DateTime(timezone=True), default=utc_now)
    status = Column(String(50), default='active')
    session_type = Column(String(50), default='general')
    total_queries = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)
    total_cost_usd = Column(Numeric(10, 6), default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

class AIHelperAuditLog(Base):
    __tablename__ = 'ai_helper_audit_logs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    executed = Column(Boolean, default=False)
    action_blocked = Column(Boolean, default=False)
    permission_checked = Column(Boolean, default=True)
    is_error = Column(Boolean, default=False)
    ai_suggested_action = Column(String, nullable=True) 
    correlation_id = Column(String, nullable=True)
    execution_result = Column(String, nullable=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('ai_helper_sessions.id'), nullable=True)
    user_action = Column(String, nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)

class AIFeedbackInternal(Base):
    # Using 'Internal' suffix to avoid collision with models_learning.AnalysisFeedback which might be aliased
    __tablename__ = 'ai_feedback'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    message_id = Column(UUID(as_uuid=True), nullable=True)
    runbook_id = Column(UUID(as_uuid=True), nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)

class RunbookClick(Base):
    __tablename__ = 'runbook_clicks'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)
    clicked_at = Column(DateTime(timezone=True), default=utc_now)
    runbook_id = Column(UUID(as_uuid=True), nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
