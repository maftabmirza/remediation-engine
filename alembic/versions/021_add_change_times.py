"""Add start_time and end_time to change_events

Revision ID: 021_add_change_times
Revises: 020_add_itsm_integration
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '021_add_change_times'
down_revision = '020_add_itsm_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add start_time and end_time columns to change_events
    op.add_column('change_events', sa.Column('start_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('change_events', sa.Column('end_time', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('change_events', 'end_time')
    op.drop_column('change_events', 'start_time')
