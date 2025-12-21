"""Add Prometheus dashboards, panels, and datasources

Revision ID: 023
Revises: 022
Create Date: 2025-12-21 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022_add_change_cis_app'
branch_labels = None
depends_on = None


def upgrade():
    # Create prometheus_datasources table
    op.create_table(
        'prometheus_datasources',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('url', sa.String(512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('auth_type', sa.String(50), default='none'),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('password', sa.String(512), nullable=True),
        sa.Column('bearer_token', sa.String(512), nullable=True),
        sa.Column('timeout', sa.Integer(), default=30),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('is_enabled', sa.Boolean(), default=True),
        sa.Column('custom_headers', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create prometheus_panels table
    op.create_table(
        'prometheus_panels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('datasource_id', sa.String(36), sa.ForeignKey('prometheus_datasources.id'), nullable=False),
        sa.Column('promql_query', sa.Text(), nullable=False),
        sa.Column('legend_format', sa.String(255), nullable=True),
        sa.Column('time_range', sa.String(50), default='24h'),
        sa.Column('refresh_interval', sa.Integer(), default=30),
        sa.Column('step', sa.String(20), default='auto'),
        sa.Column('panel_type', sa.Enum('graph', 'gauge', 'stat', 'table', 'heatmap', 'bar', 'pie', name='paneltype'), default='graph'),
        sa.Column('visualization_config', sa.JSON(), nullable=True),
        sa.Column('thresholds', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('is_template', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create dashboards table
    op.create_table(
        'dashboards',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('layout', sa.JSON(), nullable=True),
        sa.Column('time_range', sa.String(50), default='24h'),
        sa.Column('refresh_interval', sa.Integer(), default=60),
        sa.Column('auto_refresh', sa.Boolean(), default=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('folder', sa.String(255), nullable=True),
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('is_favorite', sa.Boolean(), default=False),
        sa.Column('is_home', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create dashboard_panels junction table
    op.create_table(
        'dashboard_panels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('prometheus_panels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('grid_x', sa.Integer(), default=0),
        sa.Column('grid_y', sa.Integer(), default=0),
        sa.Column('grid_width', sa.Integer(), default=6),
        sa.Column('grid_height', sa.Integer(), default=4),
        sa.Column('override_time_range', sa.String(50), nullable=True),
        sa.Column('override_refresh_interval', sa.Integer(), nullable=True),
        sa.Column('display_order', sa.Integer(), default=0),
    )

    # Create indexes
    op.create_index('ix_prometheus_panels_datasource', 'prometheus_panels', ['datasource_id'])
    op.create_index('ix_dashboard_panels_dashboard', 'dashboard_panels', ['dashboard_id'])
    op.create_index('ix_dashboard_panels_panel', 'dashboard_panels', ['panel_id'])


def downgrade():
    op.drop_table('dashboard_panels')
    op.drop_table('dashboards')
    op.drop_table('prometheus_panels')
    op.drop_table('prometheus_datasources')
    op.execute('DROP TYPE IF EXISTS paneltype')
