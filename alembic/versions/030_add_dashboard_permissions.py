"""add dashboard permissions

Revision ID: 030_add_dashboard_permissions
Revises: 029_add_variable_dependencies
Create Date: 2025-01-01 00:00:02.000000

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
revision = '030_add_dashboard_permissions'
down_revision = '029_add_variable_dependencies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_permissions table
    create_table_safe(
        'dashboard_permissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('role', sa.String(50), nullable=True),
        sa.Column('permission', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create indexes
    create_index_safe('ix_dashboard_permissions_dashboard_id', 'dashboard_permissions', ['dashboard_id'])
    create_index_safe('ix_dashboard_permissions_user_id', 'dashboard_permissions', ['user_id'])
    create_index_safe('ix_dashboard_permissions_role', 'dashboard_permissions', ['role'])


def downgrade() -> None:
    drop_index_safe('ix_dashboard_permissions_role', 'dashboard_permissions')
    drop_index_safe('ix_dashboard_permissions_user_id', 'dashboard_permissions')
    drop_index_safe('ix_dashboard_permissions_dashboard_id', 'dashboard_permissions')
    drop_table_safe('dashboard_permissions')
