"""add dashboard_annotations table

Revision ID: 025
Revises: 024
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
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_annotations table
    create_table_safe(
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
    create_index_safe('ix_dashboard_annotations_dashboard_id', 'dashboard_annotations', ['dashboard_id'])
    create_index_safe('ix_dashboard_annotations_time', 'dashboard_annotations', ['time'])


def downgrade() -> None:
    drop_index_safe('ix_dashboard_annotations_time', 'dashboard_annotations')
    drop_index_safe('ix_dashboard_annotations_dashboard_id', 'dashboard_annotations')
    drop_table_safe('dashboard_annotations')
