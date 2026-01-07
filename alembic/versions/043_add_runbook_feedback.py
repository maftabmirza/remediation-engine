"""Add ai_feedback table for thumbs up/down on runbooks and LLM responses

Revision ID: 043_add_ai_feedback
Revises: 042_add_runbook_clicks
Create Date: 2026-01-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '043_add_ai_feedback'
down_revision = '042_add_runbook_clicks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('feedback_type', sa.String(20), nullable=False),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['runbook_id'], ['runbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "feedback_type IN ('thumbs_up', 'thumbs_down')",
            name='ck_ai_feedback_type'
        ),
        sa.CheckConstraint(
            "target_type IN ('runbook', 'llm_response')",
            name='ck_ai_feedback_target_type'
        ),
    )
    
    # Create indexes
    op.create_index('idx_ai_feedback_runbook_id', 'ai_feedback', ['runbook_id'])
    op.create_index('idx_ai_feedback_user_id', 'ai_feedback', ['user_id'])
    op.create_index('idx_ai_feedback_created_at', 'ai_feedback', ['created_at'])
    op.create_index('idx_ai_feedback_feedback_type', 'ai_feedback', ['feedback_type'])
    op.create_index('idx_ai_feedback_target_type', 'ai_feedback', ['target_type'])
    op.create_index('idx_ai_feedback_session_id', 'ai_feedback', ['session_id'])
    op.create_index('idx_ai_feedback_message_id', 'ai_feedback', ['message_id'])


def downgrade() -> None:
    op.drop_index('idx_ai_feedback_message_id', table_name='ai_feedback')
    op.drop_index('idx_ai_feedback_session_id', table_name='ai_feedback')
    op.drop_index('idx_ai_feedback_target_type', table_name='ai_feedback')
    op.drop_index('idx_ai_feedback_feedback_type', table_name='ai_feedback')
    op.drop_index('idx_ai_feedback_created_at', table_name='ai_feedback')
    op.drop_index('idx_ai_feedback_user_id', table_name='ai_feedback')
    op.drop_index('idx_ai_feedback_runbook_id', table_name='ai_feedback')
    op.drop_table('ai_feedback')
