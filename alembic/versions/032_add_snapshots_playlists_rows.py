"""add snapshots, playlists, and panel rows

Revision ID: 032
Revises: 031
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
revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_snapshots table
    create_table_safe(
        'dashboard_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key', sa.String(64), unique=True, nullable=False),
        sa.Column('snapshot_data', sa.JSON, nullable=False),
        sa.Column('is_public', sa.Boolean, default=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
    )
    create_index_safe('ix_dashboard_snapshots_key', 'dashboard_snapshots', ['key'])
    create_index_safe('ix_dashboard_snapshots_dashboard_id', 'dashboard_snapshots', ['dashboard_id'])

    # Create playlists table
    create_table_safe(
        'playlists',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('interval', sa.Integer, default=30),
        sa.Column('loop', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create playlist_items table
    create_table_safe(
        'playlist_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('playlist_id', sa.String(36), sa.ForeignKey('playlists.id'), nullable=False),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=False),
        sa.Column('order', sa.Integer, default=0),
        sa.Column('custom_interval', sa.Integer, nullable=True),
    )
    create_index_safe('ix_playlist_items_playlist_id', 'playlist_items', ['playlist_id'])

    # Create panel_rows table
    create_table_safe(
        'panel_rows',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('order', sa.Integer, default=0),
        sa.Column('is_collapsed', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    create_index_safe('ix_panel_rows_dashboard_id', 'panel_rows', ['dashboard_id'])

    # Add row_id column to dashboard_panels
    add_column_safe('dashboard_panels', sa.Column('row_id', sa.String(36), sa.ForeignKey('panel_rows.id'), nullable=True))


def downgrade() -> None:
    # Remove row_id column from dashboard_panels
    drop_column_safe('dashboard_panels', 'row_id')

    # Drop panel_rows table
    drop_index_safe('ix_panel_rows_dashboard_id', 'panel_rows')
    drop_table_safe('panel_rows')

    # Drop playlist_items table
    drop_index_safe('ix_playlist_items_playlist_id', 'playlist_items')
    drop_table_safe('playlist_items')

    # Drop playlists table
    drop_table_safe('playlists')

    # Drop dashboard_snapshots table
    drop_index_safe('ix_dashboard_snapshots_dashboard_id', 'dashboard_snapshots')
    drop_index_safe('ix_dashboard_snapshots_key', 'dashboard_snapshots')
    drop_table_safe('dashboard_snapshots')
