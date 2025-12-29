"""Add associated_cis and application to change_events

Revision ID: 022_add_change_cis_app
Revises: 021_add_change_times
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    create_table_safe, create_index_safe, add_column_safe,
    create_foreign_key_safe, create_unique_constraint_safe, create_check_constraint_safe,
    drop_index_safe, drop_constraint_safe, drop_column_safe, drop_table_safe
)

# revision identifiers
revision = '022_add_change_cis_app'
down_revision = '021_add_change_times'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add associated_cis (JSONB array for CI items) and application columns
    add_column_safe('change_events', sa.Column('associated_cis', JSONB, server_default='[]', nullable=True))
    add_column_safe('change_events', sa.Column('application', sa.String(255), nullable=True))
    create_index_safe('ix_change_events_application', 'change_events', ['application'])


def downgrade() -> None:
    drop_index_safe('ix_change_events_application', table_name='change_events')
    drop_column_safe('change_events', 'application')
    drop_column_safe('change_events', 'associated_cis')
