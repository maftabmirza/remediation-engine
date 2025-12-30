"""add dashboard_variables table

Revision ID: 024
Revises: 023
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
revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_variables table
    create_table_safe(
        'dashboard_variables',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('label', sa.String(255), nullable=True),
        sa.Column('type', sa.String(50), nullable=False, default='query'),
        sa.Column('query', sa.Text, nullable=True),
        sa.Column('datasource_id', sa.String(36), sa.ForeignKey('prometheus_datasources.id'), nullable=True),
        sa.Column('regex', sa.String(255), nullable=True),
        sa.Column('custom_values', sa.JSON, nullable=True),
        sa.Column('default_value', sa.Text, nullable=True),
        sa.Column('current_value', sa.Text, nullable=True),
        sa.Column('multi_select', sa.Boolean, default=False),
        sa.Column('include_all', sa.Boolean, default=False),
        sa.Column('all_value', sa.String(255), nullable=True),
        sa.Column('hide', sa.Integer, default=0),
        sa.Column('sort', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create index on dashboard_id for faster lookups
    create_index_safe('ix_dashboard_variables_dashboard_id', 'dashboard_variables', ['dashboard_id'])


def downgrade() -> None:
    drop_index_safe('ix_dashboard_variables_dashboard_id', 'dashboard_variables')
    drop_table_safe('dashboard_variables')
