"""Add pgvector extension

Revision ID: 008_add_pgvector
Revises: 007_fix_missing_columns
Create Date: 2025-12-13 14:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '008_add_pgvector'
down_revision = '007_fix_missing_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable pgvector extension for vector similarity search if available."""
    # Check if pgvector is available before trying to create it
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT * FROM pg_available_extensions WHERE name = 'vector'"
    ))
    if result.fetchone():
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    else:
        print("Warning: pgvector extension not available. Vector search features will be disabled.")


def downgrade() -> None:
    """Remove pgvector extension if it exists."""
    try:
        op.execute('DROP EXTENSION IF EXISTS vector CASCADE')
    except Exception:
        pass
