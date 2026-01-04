"""
SQLAlchemy models for AI Helper
Handles AI interactions, audit logging, knowledge sources, and sessions
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, CheckConstraint, Index, ARRAY, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime, timezone

from app.database import Base


def utc_now():
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class KnowledgeSource(Base):
    """Configurable knowledge sources for git docs, code, and local files"""
    __tablename__ = "knowledge_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Source metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=False, index=True)

    # Configuration (flexible per type)
    config = Column(JSONB, nullable=False, default={})

    # Sync settings
    enabled = Column(Boolean, default=True, index=True)
    sync_schedule = Column(String(100), nullable=True)
    auto_sync = Column(Boolean, default=True)

    # Sync status
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_commit_sha = Column(String(64), nullable=True)
    last_sync_status = Column(String(50), default='pending')
    last_sync_error = Column(Text, nullable=True)
    sync_count = Column(Integer, default=0)

    # Document counts
    total_documents = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)

    # Status
    status = Column(String(50), default='active', index=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    sync_history = relationship("KnowledgeSyncHistory", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            source_type.in_(['git_docs', 'git_code', 'local_files', 'external_api']),
            name='ck_knowledge_sources_type'
        ),
        CheckConstraint(
            status.in_(['active', 'inactive', 'error', 'archived']),
            name='ck_knowledge_sources_status'
        ),
    )


class KnowledgeSyncHistory(Base):
    """History of knowledge source synchronization"""
    __tablename__ = "knowledge_sync_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)

    # Sync details
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default='running')

    # Git details
    previous_commit_sha = Column(String(64), nullable=True)
    new_commit_sha = Column(String(64), nullable=True)

    # Results
    documents_added = Column(Integer, default=0)
    documents_updated = Column(Integer, default=0)
    documents_deleted = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)

    # Performance
    duration_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    source = relationship("KnowledgeSource", back_populates="sync_history")

    __table_args__ = (
        CheckConstraint(
            status.in_(['running', 'success', 'failed', 'partial']),
            name='ck_sync_history_status'
        ),
    )


class AIHelperAuditLog(Base):
    """Comprehensive audit logging for all AI helper interactions"""
    __tablename__ = "ai_helper_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User & Session Context
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(255), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_helper_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    correlation_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Request Context
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    user_query = Column(Text, nullable=False)
    page_context = Column(JSONB, nullable=True)

    # LLM Interaction
    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    llm_request = Column(JSONB, nullable=True)
    llm_response = Column(JSONB, nullable=True)
    llm_tokens_input = Column(Integer, nullable=True)
    llm_tokens_output = Column(Integer, nullable=True)
    llm_tokens_total = Column(Integer, nullable=True)
    llm_latency_ms = Column(Integer, nullable=True)
    llm_cost_usd = Column(Numeric(10, 6), nullable=True)

    # Knowledge Base Usage
    knowledge_sources_used = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    knowledge_chunks_used = Column(Integer, nullable=True)
    rag_search_time_ms = Column(Integer, nullable=True)

    # Code Understanding Usage
    code_files_referenced = Column(ARRAY(Text), nullable=True)
    code_functions_referenced = Column(ARRAY(Text), nullable=True)

    # AI Action
    ai_suggested_action = Column(String(100), nullable=True, index=True)
    ai_action_details = Column(JSONB, nullable=True)
    ai_confidence_score = Column(Numeric(3, 2), nullable=True)
    ai_reasoning = Column(Text, nullable=True)

    # User Response
    user_action = Column(String(50), nullable=True, index=True)
    user_action_timestamp = Column(DateTime(timezone=True), nullable=True)
    user_modifications = Column(JSONB, nullable=True)
    user_feedback = Column(String(20), nullable=True)
    user_feedback_comment = Column(Text, nullable=True)

    # Execution
    executed = Column(Boolean, default=False, index=True)
    execution_timestamp = Column(DateTime(timezone=True), nullable=True)
    execution_result = Column(String(50), nullable=True, index=True)
    execution_details = Column(JSONB, nullable=True)
    affected_resources = Column(JSONB, nullable=True)

    # Security
    action_blocked = Column(Boolean, default=False, index=True)
    block_reason = Column(String(255), nullable=True)
    permission_checked = Column(Boolean, default=True)
    permissions_required = Column(ARRAY(Text), nullable=True)
    permissions_granted = Column(ARRAY(Text), nullable=True)

    # Request metadata
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(255), nullable=True)

    # Performance tracking
    total_duration_ms = Column(Integer, nullable=True)
    context_assembly_ms = Column(Integer, nullable=True)

    # Error tracking
    is_error = Column(Boolean, default=False, index=True)
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    error_stack_trace = Column(Text, nullable=True)

    # Relationships
    user = relationship("User")
    session = relationship("AIHelperSession", foreign_keys=[session_id])

    __table_args__ = (
        CheckConstraint(
            user_action.in_(['approved', 'rejected', 'modified', 'ignored', 'pending']),
            name='ck_ai_audit_user_action'
        ),
        CheckConstraint(
            user_feedback.in_(['helpful', 'not_helpful', 'partially_helpful']),
            name='ck_ai_audit_user_feedback'
        ),
        CheckConstraint(
            execution_result.in_(['success', 'failed', 'blocked', 'timeout']),
            name='ck_ai_audit_execution_result'
        ),
        Index('idx_ai_audit_page_context', 'page_context', postgresql_using='gin'),
        Index('idx_ai_audit_llm_request', 'llm_request', postgresql_using='gin'),
    )


class AIHelperSession(Base):
    """AI Helper conversation sessions"""
    __tablename__ = "ai_helper_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Session metadata
    session_type = Column(String(50), default='general')
    context = Column(JSONB, nullable=True)

    # Status
    status = Column(String(50), default='active', index=True)

    # Metrics
    total_queries = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)
    total_cost_usd = Column(Numeric(10, 6), default=0)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_activity_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            session_type.in_(['general', 'form_assistance', 'troubleshooting', 'learning']),
            name='ck_ai_session_type'
        ),
        CheckConstraint(
            status.in_(['active', 'completed', 'abandoned', 'error']),
            name='ck_ai_session_status'
        ),
    )


class AIHelperConfig(Base):
    """System-wide AI Helper configuration"""
    __tablename__ = "ai_helper_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    config_key = Column(String(255), unique=True, nullable=False, index=True)
    config_value = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)
    config_type = Column(String(50), default='system', index=True)

    # Validation
    schema = Column(JSONB, nullable=True)
    is_encrypted = Column(Boolean, default=False)

    # Status
    enabled = Column(Boolean, default=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        CheckConstraint(
            config_type.in_(['system', 'user', 'tenant']),
            name='ck_ai_config_type'
        ),
    )
