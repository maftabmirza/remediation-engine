"""Add pgvector extension

Revision ID: 008_add_pgvector
Revises: 007_fix_missing_columns
Create Date: 2025-12-13 14:01:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_add_pgvector'
down_revision = '007_fix_missing_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable pgvector extension for vector similarity search if available."""
    # Try to enable pgvector extension - skip if not available
    try:
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    except Exception as e:
        print(f"Warning: pgvector extension not available ({e}). Vector search features will be disabled.")


def downgrade() -> None:
    """Remove pgvector extension if it exists."""
    try:
        op.execute('DROP EXTENSION IF EXISTS vector CASCADE')
    except Exception:
        pass

