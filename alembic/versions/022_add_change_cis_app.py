"""Add associated_cis and application to change_events

Revision ID: 022_add_change_cis_app
Revises: 021_add_change_times
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '022_add_change_cis_app'
down_revision = '021_add_change_times'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add associated_cis (JSONB array for CI items) and application columns
    op.add_column('change_events', sa.Column('associated_cis', JSONB, server_default='[]', nullable=True))
    op.add_column('change_events', sa.Column('application', sa.String(255), nullable=True))
    op.create_index('ix_change_events_application', 'change_events', ['application'])


def downgrade() -> None:
    op.drop_index('ix_change_events_application', table_name='change_events')
    op.drop_column('change_events', 'application')
    op.drop_column('change_events', 'associated_cis')
