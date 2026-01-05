"""Add AI helper specific tables

Revision ID: 038_add_ai_helper_schema
Revises: 037_add_inquiry_sessions
Create Date: 2026-01-05 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '038_add_ai_helper_schema'
down_revision = '037_add_inquiry_sessions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 1. Create knowledge_sources
    if 'knowledge_sources' not in tables:
        op.create_table('knowledge_sources',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('source_type', sa.String(50), nullable=False, index=True),
            sa.Column('config', postgresql.JSONB, nullable=False, server_default='{}'),
            sa.Column('enabled', sa.Boolean, default=True, index=True),
            sa.Column('sync_schedule', sa.String(100), nullable=True),
            sa.Column('auto_sync', sa.Boolean, default=True),
            sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_commit_sha', sa.String(64), nullable=True),
            sa.Column('last_sync_status', sa.String(50), default='pending'),
            sa.Column('last_sync_error', sa.Text, nullable=True),
            sa.Column('sync_count', sa.Integer, default=0),
            sa.Column('total_documents', sa.Integer, default=0),
            sa.Column('total_chunks', sa.Integer, default=0),
            sa.Column('status', sa.String(50), default='active', index=True),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
        )
        # Constraints
        op.create_check_constraint(
            'ck_knowledge_sources_type',
            'knowledge_sources',
            "source_type IN ('git_docs', 'git_code', 'local_files', 'external_api')"
        )
        op.create_check_constraint(
            'ck_knowledge_sources_status',
            'knowledge_sources',
            "status IN ('active', 'inactive', 'error', 'archived')"
        )

    # 2. Create knowledge_sync_history
    if 'knowledge_sync_history' not in tables:
        op.create_table('knowledge_sync_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('knowledge_sources.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', sa.String(50), nullable=False, default='running'),
            sa.Column('previous_commit_sha', sa.String(64), nullable=True),
            sa.Column('new_commit_sha', sa.String(64), nullable=True),
            sa.Column('documents_added', sa.Integer, default=0),
            sa.Column('documents_updated', sa.Integer, default=0),
            sa.Column('documents_deleted', sa.Integer, default=0),
            sa.Column('chunks_created', sa.Integer, default=0),
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('error_details', postgresql.JSONB, nullable=True),
            sa.Column('duration_ms', sa.Integer, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
        )
        op.create_check_constraint(
            'ck_sync_history_status',
            'knowledge_sync_history',
            "status IN ('running', 'success', 'failed', 'partial')"
        )

    # 3. Create ai_helper_sessions
    if 'ai_helper_sessions' not in tables:
        op.create_table('ai_helper_sessions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('session_type', sa.String(50), default='general'),
            sa.Column('context', postgresql.JSONB, nullable=True),
            sa.Column('status', sa.String(50), default='active', index=True),
            sa.Column('total_queries', sa.Integer, default=0),
            sa.Column('total_tokens_used', sa.Integer, default=0),
            sa.Column('total_cost_usd', sa.Numeric(10, 6), default=0),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
            sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), index=True),
            sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('duration_seconds', sa.Integer, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
        )
        op.create_check_constraint(
            'ck_ai_session_type',
            'ai_helper_sessions',
            "session_type IN ('general', 'form_assistance', 'troubleshooting', 'learning')"
        )
        op.create_check_constraint(
            'ck_ai_session_status',
            'ai_helper_sessions',
            "status IN ('active', 'completed', 'abandoned', 'error')"
        )

    # 4. Create ai_helper_audit_logs
    if 'ai_helper_audit_logs' not in tables:
        op.create_table('ai_helper_audit_logs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('username', sa.String(255), nullable=False),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_helper_sessions.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'), index=True),
            sa.Column('user_query', sa.Text, nullable=False),
            sa.Column('page_context', postgresql.JSONB, nullable=True),
            sa.Column('llm_provider', sa.String(50), nullable=True),
            sa.Column('llm_model', sa.String(100), nullable=True),
            sa.Column('llm_request', postgresql.JSONB, nullable=True),
            sa.Column('llm_response', postgresql.JSONB, nullable=True),
            sa.Column('llm_tokens_input', sa.Integer, nullable=True),
            sa.Column('llm_tokens_output', sa.Integer, nullable=True),
            sa.Column('llm_tokens_total', sa.Integer, nullable=True),
            sa.Column('llm_latency_ms', sa.Integer, nullable=True),
            sa.Column('llm_cost_usd', sa.Numeric(10, 6), nullable=True),
            sa.Column('knowledge_sources_used', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
            sa.Column('knowledge_chunks_used', sa.Integer, nullable=True),
            sa.Column('rag_search_time_ms', sa.Integer, nullable=True),
            sa.Column('code_files_referenced', postgresql.ARRAY(sa.Text), nullable=True),
            sa.Column('code_functions_referenced', postgresql.ARRAY(sa.Text), nullable=True),
            sa.Column('ai_suggested_action', sa.String(100), nullable=True, index=True),
            sa.Column('ai_action_details', postgresql.JSONB, nullable=True),
            sa.Column('ai_confidence_score', sa.Numeric(3, 2), nullable=True),
            sa.Column('ai_reasoning', sa.Text, nullable=True),
            sa.Column('user_action', sa.String(50), nullable=True, index=True),
            sa.Column('user_action_timestamp', sa.DateTime(timezone=True), nullable=True),
            sa.Column('user_modifications', postgresql.JSONB, nullable=True),
            sa.Column('user_feedback', sa.String(20), nullable=True),
            sa.Column('user_feedback_comment', sa.Text, nullable=True),
            sa.Column('executed', sa.Boolean, default=False, index=True),
            sa.Column('execution_timestamp', sa.DateTime(timezone=True), nullable=True),
            sa.Column('execution_result', sa.String(50), nullable=True, index=True),
            sa.Column('execution_details', postgresql.JSONB, nullable=True),
            sa.Column('affected_resources', postgresql.JSONB, nullable=True),
            sa.Column('action_blocked', sa.Boolean, default=False, index=True),
            sa.Column('block_reason', sa.String(255), nullable=True),
            sa.Column('permission_checked', sa.Boolean, default=True),
            sa.Column('permissions_required', postgresql.ARRAY(sa.Text), nullable=True),
            sa.Column('permissions_granted', postgresql.ARRAY(sa.Text), nullable=True),
            sa.Column('ip_address', postgresql.INET, nullable=True),
            sa.Column('user_agent', sa.Text, nullable=True),
            sa.Column('request_id', sa.String(255), nullable=True),
            sa.Column('total_duration_ms', sa.Integer, nullable=True),
            sa.Column('context_assembly_ms', sa.Integer, nullable=True),
            sa.Column('is_error', sa.Boolean, default=False, index=True),
            sa.Column('error_type', sa.String(100), nullable=True),
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('error_stack_trace', sa.Text, nullable=True)
        )
        op.create_index('idx_ai_audit_page_context', 'ai_helper_audit_logs', ['page_context'], postgresql_using='gin')
        op.create_index('idx_ai_audit_llm_request', 'ai_helper_audit_logs', ['llm_request'], postgresql_using='gin')
        
        op.create_check_constraint(
            'ck_ai_audit_user_action',
            'ai_helper_audit_logs',
            "user_action IN ('approved', 'rejected', 'modified', 'ignored', 'pending')"
        )
        op.create_check_constraint(
            'ck_ai_audit_user_feedback',
            'ai_helper_audit_logs',
            "user_feedback IN ('helpful', 'not_helpful', 'partially_helpful')"
        )
        op.create_check_constraint(
            'ck_ai_audit_execution_result',
            'ai_helper_audit_logs',
            "execution_result IN ('success', 'failed', 'blocked', 'timeout')"
        )

    # 5. Create ai_helper_config
    if 'ai_helper_config' not in tables:
        op.create_table('ai_helper_config',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('config_key', sa.String(255), nullable=False, unique=True, index=True),
            sa.Column('config_value', postgresql.JSONB, nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('config_type', sa.String(50), default='system', index=True),
            sa.Column('schema', postgresql.JSONB, nullable=True),
            sa.Column('is_encrypted', sa.Boolean, default=False),
            sa.Column('enabled', sa.Boolean, default=True),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
            sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
        )
        op.create_check_constraint(
            'ck_ai_config_type',
            'ai_helper_config',
            "config_type IN ('system', 'user', 'tenant')"
        )


def downgrade() -> None:
    op.drop_table('ai_helper_config')
    op.drop_table('ai_helper_audit_logs')
    op.drop_table('ai_helper_sessions')
    op.drop_table('knowledge_sync_history')
    op.drop_table('knowledge_sources')
