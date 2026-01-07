"""Add runbook_clicks table for click analytics

Revision ID: 042_add_runbook_clicks
Revises: 041_add_runbook_embeddings
Create Date: 2026-01-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '042_add_runbook_clicks'
down_revision = '041_add_runbook_embeddings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'runbook_clicks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='unknown'),
        sa.Column('query_text', sa.Text(), nullable=True),
        sa.Column('confidence_shown', sa.Float(), nullable=True),
        sa.Column('rank_shown', sa.Integer(), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('context_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['runbook_id'], ['runbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "source IN ('chat_page', 'agent_widget', 'alert_detail', 'runbook_list', 'unknown')",
            name='ck_runbook_clicks_source'
        ),
        sa.CheckConstraint(
            'confidence_shown IS NULL OR (confidence_shown >= 0.0 AND confidence_shown <= 1.0)',
            name='ck_runbook_clicks_confidence_range'
        ),
        sa.CheckConstraint(
            'rank_shown IS NULL OR rank_shown >= 1',
            name='ck_runbook_clicks_rank_positive'
        ),
    )
    
    # Create indexes
    op.create_index('idx_runbook_clicks_runbook_id', 'runbook_clicks', ['runbook_id'])
    op.create_index('idx_runbook_clicks_user_id', 'runbook_clicks', ['user_id'])
    op.create_index('idx_runbook_clicks_clicked_at', 'runbook_clicks', ['clicked_at'])
    op.create_index('idx_runbook_clicks_source', 'runbook_clicks', ['source'])
    op.create_index('idx_runbook_clicks_session_id', 'runbook_clicks', ['session_id'])


def downgrade() -> None:
    op.drop_index('idx_runbook_clicks_session_id', table_name='runbook_clicks')
    op.drop_index('idx_runbook_clicks_source', table_name='runbook_clicks')
    op.drop_index('idx_runbook_clicks_clicked_at', table_name='runbook_clicks')
    op.drop_index('idx_runbook_clicks_user_id', table_name='runbook_clicks')
    op.drop_index('idx_runbook_clicks_runbook_id', table_name='runbook_clicks')
    op.drop_table('runbook_clicks')
