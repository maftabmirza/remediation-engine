"""add dashboard_annotations table

Revision ID: 025
Revises: 024
Create Date: 2025-12-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_annotations table
    op.create_table(
        'dashboard_annotations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id'), nullable=True),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('prometheus_panels.id'), nullable=True),
        sa.Column('time', sa.DateTime, nullable=False),
        sa.Column('time_end', sa.DateTime, nullable=True),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('tags', sa.JSON, nullable=True),
        sa.Column('color', sa.String(50), default='#FF6B6B'),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create indexes for faster lookups
    op.create_index('ix_dashboard_annotations_dashboard_id', 'dashboard_annotations', ['dashboard_id'])
    op.create_index('ix_dashboard_annotations_time', 'dashboard_annotations', ['time'])


def downgrade() -> None:
    op.drop_index('ix_dashboard_annotations_time', 'dashboard_annotations')
    op.drop_index('ix_dashboard_annotations_dashboard_id', 'dashboard_annotations')
    op.drop_table('dashboard_annotations')
