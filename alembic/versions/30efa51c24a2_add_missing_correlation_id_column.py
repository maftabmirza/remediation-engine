"""add_missing_correlation_id_column

Revision ID: 30efa51c24a2
Revises: 037
Create Date: 2025-12-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import add_column_safe, drop_column_safe

# revision identifiers, used by Alembic.
revision = '30efa51c24a2'
down_revision = '037_add_inquiry_sessions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add correlation_id column to alerts table if it doesn't exist
    add_column_safe('alerts', sa.Column('correlation_id', postgresql.UUID(as_uuid=True), 
                                        sa.ForeignKey('alert_correlations.id', ondelete='SET NULL'), 
                                        nullable=True))


def downgrade() -> None:
    # Drop correlation_id column if it exists
    drop_column_safe('alerts', 'correlation_id')
