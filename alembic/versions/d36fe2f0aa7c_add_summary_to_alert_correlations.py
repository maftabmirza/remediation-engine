"""add_summary_to_alert_correlations

Revision ID: d36fe2f0aa7c
Revises: e352288a28d6
Create Date: 2026-01-25 16:31:09.777938

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd36fe2f0aa7c'
down_revision = 'e352288a28d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add summary column to alert_correlations
    op.add_column('alert_correlations', sa.Column('summary', sa.String(length=255), nullable=False, server_default='Auto Correlation'))


def downgrade() -> None:
    op.drop_column('alert_correlations', 'summary')
