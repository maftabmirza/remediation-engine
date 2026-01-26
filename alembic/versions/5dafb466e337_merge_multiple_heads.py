"""merge_multiple_heads

Revision ID: 5dafb466e337
Revises: g6b7c8d9e0f1, d36fe2f0aa7c
Create Date: 2026-01-26 17:21:44.143107

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5dafb466e337'
down_revision = ('g6b7c8d9e0f1', 'd36fe2f0aa7c')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
