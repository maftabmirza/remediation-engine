"""Merge heads 038 and 4e706f8

Revision ID: 039_merge_heads
Revises: 038_add_ai_helper_schema, 4e706f82cee5
Create Date: 2026-01-05 13:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '039_merge_heads'
down_revision = ('038_add_ai_helper_schema', '4e706f82cee5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
