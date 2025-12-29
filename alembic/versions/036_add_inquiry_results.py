"""Add inquiry_results table for persisting observability query outputs

Revision ID: 036_add_inquiry_results
Revises: 035_add_datasource_fks_to_profiles
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    create_table_safe, create_index_safe, add_column_safe,
    create_foreign_key_safe, create_unique_constraint_safe, create_check_constraint_safe,
    drop_index_safe, drop_constraint_safe, drop_column_safe, drop_table_safe
)

# revision identifiers, used by Alembic.
revision = '036_add_inquiry_results'
down_revision = '035_add_ds_fks'
branch_labels = None
depends_on = None


def upgrade():
    """Create inquiry_results table for storing observability query results."""
    create_table_safe(
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
    create_index_safe('ix_inquiry_results_user_id', 'inquiry_results', ['user_id'])
    create_index_safe('ix_inquiry_results_created_at', 'inquiry_results', ['created_at'])


def downgrade():
    """Drop inquiry_results table."""
    drop_index_safe('ix_inquiry_results_created_at')
    drop_index_safe('ix_inquiry_results_user_id')
    drop_table_safe('inquiry_results')
