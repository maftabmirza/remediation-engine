"""add query history

Revision ID: 028_add_query_history
Revises: 027_add_snapshots_playlists_rows
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '028_add_query_history'
down_revision = '027_add_snapshots_playlists_rows'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create query_history table
    op.create_table(
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
    op.create_index('ix_query_history_executed_at', 'query_history', ['executed_at'])
    op.create_index('ix_query_history_executed_by', 'query_history', ['executed_by'])
    op.create_index('ix_query_history_dashboard_id', 'query_history', ['dashboard_id'])


def downgrade() -> None:
    op.drop_index('ix_query_history_dashboard_id', 'query_history')
    op.drop_index('ix_query_history_executed_by', 'query_history')
    op.drop_index('ix_query_history_executed_at', 'query_history')
    op.drop_table('query_history')
