"""Add inquiry_sessions table for proper session management

Revision ID: 037_add_inquiry_sessions
Revises: 036_add_inquiry_results
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


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
revision = '037_add_inquiry_sessions'
down_revision = '036_add_inquiry_results'
branch_labels = None
depends_on = None


def upgrade():
    """Create inquiry_sessions table and link inquiry_results to sessions."""
    # Create inquiry_sessions table
    create_table_safe(
        'inquiry_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Index for user sessions lookup
    create_index_safe('ix_inquiry_sessions_user_id', 'inquiry_sessions', ['user_id'])
    create_index_safe('ix_inquiry_sessions_updated_at', 'inquiry_sessions', ['updated_at'])
    
    # Add session_id column to inquiry_results
    add_column_safe('inquiry_results', 
        sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('inquiry_sessions.id', ondelete='CASCADE'), nullable=True)
    )
    create_index_safe('ix_inquiry_results_session_id', 'inquiry_results', ['session_id'])


def downgrade():
    """Drop inquiry_sessions table and session_id column."""
    drop_index_safe('ix_inquiry_results_session_id')
    drop_column_safe('inquiry_results', 'session_id')
    drop_index_safe('ix_inquiry_sessions_updated_at')
    drop_index_safe('ix_inquiry_sessions_user_id')
    drop_table_safe('inquiry_sessions')
