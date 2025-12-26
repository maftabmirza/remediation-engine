"""Add inquiry_results table for persisting observability query outputs

Revision ID: 036_add_inquiry_results
Revises: 035_add_datasource_fks_to_profiles
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '036_add_inquiry_results'
down_revision = '035_add_datasource_fks_to_profiles'
branch_labels = None
depends_on = None


def upgrade():
    """Create inquiry_results table for storing observability query results."""
    op.create_table(
        'inquiry_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('result_json', JSONB(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('intent_type', sa.String(50), nullable=True),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Index for user queries lookup
    op.create_index('ix_inquiry_results_user_id', 'inquiry_results', ['user_id'])
    op.create_index('ix_inquiry_results_created_at', 'inquiry_results', ['created_at'])


def downgrade():
    """Drop inquiry_results table."""
    op.drop_index('ix_inquiry_results_created_at')
    op.drop_index('ix_inquiry_results_user_id')
    op.drop_table('inquiry_results')
