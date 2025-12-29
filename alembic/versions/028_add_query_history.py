"""add query history

Revision ID: 028_add_query_history
Revises: 027
Create Date: 2025-01-01 00:00:00.000000

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
revision = '028_add_query_history'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create query_history table
    create_table_safe(
        'query_history',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('query', sa.Text, nullable=False),
        sa.Column('datasource_id', sa.String(36), sa.ForeignKey('prometheus_datasources.id'), nullable=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=True),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('prometheus_panels.id'), nullable=True),
        sa.Column('time_range', sa.String(50), nullable=True),
        sa.Column('execution_time_ms', sa.Integer, nullable=True),
        sa.Column('series_count', sa.Integer, nullable=True),
        sa.Column('status', sa.String(20), server_default='success'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('executed_by', sa.String(255), nullable=True),
        sa.Column('is_favorite', sa.Boolean, server_default='false'),
        sa.Column('executed_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Create indexes for better query performance
    create_index_safe('ix_query_history_executed_at', 'query_history', ['executed_at'])
    create_index_safe('ix_query_history_executed_by', 'query_history', ['executed_by'])
    create_index_safe('ix_query_history_dashboard_id', 'query_history', ['dashboard_id'])


def downgrade() -> None:
    drop_index_safe('ix_query_history_dashboard_id', 'query_history')
    drop_index_safe('ix_query_history_executed_by', 'query_history')
    drop_index_safe('ix_query_history_executed_at', 'query_history')
    drop_table_safe('query_history')
