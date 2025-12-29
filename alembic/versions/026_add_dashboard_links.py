"""add dashboard_links table

Revision ID: 026
Revises: 025
Create Date: 2025-12-22 00:00:00.000000

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

# revision identifiers, used by Alembic.
revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_links table
    create_table_safe(
        'dashboard_links',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('url', sa.String(512), nullable=False),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('type', sa.String(50), default='link'),
        sa.Column('sort_order', sa.Integer, default=0),
        sa.Column('open_in_new_tab', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create index on dashboard_id for faster lookups
    create_index_safe('ix_dashboard_links_dashboard_id', 'dashboard_links', ['dashboard_id'])


def downgrade() -> None:
    drop_index_safe('ix_dashboard_links_dashboard_id', 'dashboard_links')
    drop_table_safe('dashboard_links')
