"""Add start_time and end_time to change_events

Revision ID: 021_add_change_times
Revises: 020_add_itsm_integration
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa


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
revision = '021_add_change_times'
down_revision = '020_add_itsm_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add start_time and end_time columns to change_events
    add_column_safe('change_events', sa.Column('start_time', sa.DateTime(timezone=True), nullable=True))
    add_column_safe('change_events', sa.Column('end_time', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    drop_column_safe('change_events', 'end_time')
    drop_column_safe('change_events', 'start_time')
