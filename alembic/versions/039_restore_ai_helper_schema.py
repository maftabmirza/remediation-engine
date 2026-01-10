"""restore_ai_helper_schema

Revision ID: 039_restore_ai_helper
Revises: 038_add_solution_outcomes
Create Date: 2026-01-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '039_restore_ai_helper'
down_revision = '038_add_solution_outcomes'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    # Create AI Helper Sessions table (matches models_zombies.AIHelperSession)
    if not table_exists('ai_helper_sessions'):
        op.create_table('ai_helper_sessions',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=True, server_default='active'),
            sa.Column('session_type', sa.String(length=50), nullable=True, server_default='general'),
            sa.Column('total_queries', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('total_tokens_used', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('total_cost_usd', sa.Numeric(10, 6), nullable=True, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created table: ai_helper_sessions")
    else:
        print("Skipping ai_helper_sessions: table already exists")

    # Create AI Helper Audit Logs table (matches models_zombies.AIHelperAuditLog)
    if not table_exists('ai_helper_audit_logs'):
        op.create_table('ai_helper_audit_logs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
            sa.Column('executed', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('action_blocked', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('permission_checked', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('is_error', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('ai_suggested_action', sa.String(), nullable=True),
            sa.Column('correlation_id', sa.String(), nullable=True),
            sa.Column('execution_result', sa.String(), nullable=True),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('user_action', sa.String(), nullable=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['ai_helper_sessions.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created table: ai_helper_audit_logs")
    else:
        print("Skipping ai_helper_audit_logs: table already exists")

    # Create AI Feedback table (matches models_zombies.AIFeedbackInternal)
    if not table_exists('ai_feedback'):
        op.create_table('ai_feedback',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        # Create indexes
        op.create_index('ix_ai_feedback_created_at', 'ai_feedback', ['created_at'], unique=False)
        op.create_index('ix_ai_feedback_message_id', 'ai_feedback', ['message_id'], unique=False)
        op.create_index('ix_ai_feedback_runbook_id', 'ai_feedback', ['runbook_id'], unique=False)
        op.create_index('ix_ai_feedback_session_id', 'ai_feedback', ['session_id'], unique=False)
        op.create_index('ix_ai_feedback_user_id', 'ai_feedback', ['user_id'], unique=False)
        print("Created table: ai_feedback")
    else:
        print("Skipping ai_feedback: table already exists")

    # Create Runbook Clicks table (matches models_zombies.RunbookClick)
    if not table_exists('runbook_clicks'):
        op.create_table('runbook_clicks',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
            sa.Column('source', sa.String(length=50), nullable=False),
            sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created table: runbook_clicks")
    else:
        print("Skipping runbook_clicks: table already exists")

    # Create Knowledge Sync History table (matches models_zombies.KnowledgeSyncHistory)
    if not table_exists('knowledge_sync_history'):
        op.create_table('knowledge_sync_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=True, server_default='running'),
            sa.Column('documents_added', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('documents_updated', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('documents_deleted', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('chunks_created', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created table: knowledge_sync_history")
    else:
        print("Skipping knowledge_sync_history: table already exists")

    # Also create ai_sessions and ai_messages for backwards compatibility
    if not table_exists('ai_sessions'):
        op.create_table('ai_sessions',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('context_context_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created table: ai_sessions")
    else:
        print("Skipping ai_sessions: table already exists")

    if not table_exists('ai_messages'):
        op.create_table('ai_messages',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['ai_sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created table: ai_messages")
    else:
        print("Skipping ai_messages: table already exists")


def downgrade():
    # Drop in reverse order
    if table_exists('ai_messages'):
        op.drop_table('ai_messages')
    if table_exists('ai_sessions'):
        op.drop_table('ai_sessions')
    if table_exists('knowledge_sync_history'):
        op.drop_table('knowledge_sync_history')
    if table_exists('runbook_clicks'):
        op.drop_table('runbook_clicks')
    if table_exists('ai_feedback'):
        op.drop_index('ix_ai_feedback_user_id', table_name='ai_feedback')
        op.drop_index('ix_ai_feedback_session_id', table_name='ai_feedback')
        op.drop_index('ix_ai_feedback_runbook_id', table_name='ai_feedback')
        op.drop_index('ix_ai_feedback_message_id', table_name='ai_feedback')
        op.drop_index('ix_ai_feedback_created_at', table_name='ai_feedback')
        op.drop_table('ai_feedback')
    if table_exists('ai_helper_audit_logs'):
        op.drop_table('ai_helper_audit_logs')
    if table_exists('ai_helper_sessions'):
        op.drop_table('ai_helper_sessions')
