"""add_application_knowledge_config_manual

Revision ID: ddf455edf0de
Revises: 040_remove_legacy_chat
Create Date: 2026-01-10 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ddf455edf0de'
down_revision = '040_remove_legacy_chat'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('application_knowledge_configs',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('app_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('git_repo_url', sa.String(), nullable=True),
        sa.Column('git_branch', sa.String(), server_default='main', nullable=True),
        sa.Column('git_auth_type', sa.String(), server_default='none', nullable=True),
        sa.Column('git_token', sa.String(), nullable=True),
        sa.Column('sync_docs', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('sync_code', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('doc_patterns', sa.JSON(), server_default='["*.md", "docs/**/*"]', nullable=True),
        sa.Column('exclude_patterns', sa.JSON(), server_default='["**/node_modules/**", "**/.git/**"]', nullable=True),
        sa.Column('auto_sync_enabled', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('sync_interval_hours', sa.Integer(), server_default='24', nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(), nullable=True),
        sa.Column('last_sync_stats', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('app_id'),
        sa.ForeignKeyConstraint(['app_id'], ['applications.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    op.drop_table('application_knowledge_configs')
