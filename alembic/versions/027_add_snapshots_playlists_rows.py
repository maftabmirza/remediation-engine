"""add snapshots, playlists, and panel rows

Revision ID: 027
Revises: 026
Create Date: 2025-12-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_snapshots table
    op.create_table(
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
    op.create_index('ix_dashboard_snapshots_key', 'dashboard_snapshots', ['key'])
    op.create_index('ix_dashboard_snapshots_dashboard_id', 'dashboard_snapshots', ['dashboard_id'])

    # Create playlists table
    op.create_table(
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
    op.create_table(
        'playlist_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('playlist_id', sa.String(36), sa.ForeignKey('playlists.id'), nullable=False),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=False),
        sa.Column('order', sa.Integer, default=0),
        sa.Column('custom_interval', sa.Integer, nullable=True),
    )
    op.create_index('ix_playlist_items_playlist_id', 'playlist_items', ['playlist_id'])

    # Create panel_rows table
    op.create_table(
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
    op.create_index('ix_panel_rows_dashboard_id', 'panel_rows', ['dashboard_id'])

    # Add row_id column to dashboard_panels
    op.add_column('dashboard_panels', sa.Column('row_id', sa.String(36), sa.ForeignKey('panel_rows.id'), nullable=True))


def downgrade() -> None:
    # Remove row_id column from dashboard_panels
    op.drop_column('dashboard_panels', 'row_id')

    # Drop panel_rows table
    op.drop_index('ix_panel_rows_dashboard_id', 'panel_rows')
    op.drop_table('panel_rows')

    # Drop playlist_items table
    op.drop_index('ix_playlist_items_playlist_id', 'playlist_items')
    op.drop_table('playlist_items')

    # Drop playlists table
    op.drop_table('playlists')

    # Drop dashboard_snapshots table
    op.drop_index('ix_dashboard_snapshots_dashboard_id', 'dashboard_snapshots')
    op.drop_index('ix_dashboard_snapshots_key', 'dashboard_snapshots')
    op.drop_table('dashboard_snapshots')
