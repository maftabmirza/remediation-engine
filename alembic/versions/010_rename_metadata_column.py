"""Rename metadata to chunk_metadata

Revision ID: 010_rename_metadata_column
Revises: 009_create_knowledge_tables
Create Date: 2025-12-13 14:42:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '010_rename_metadata_column'
down_revision = '009_create_knowledge_tables'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Rename metadata column to chunk_metadata to avoid SQLAlchemy reserved word."""
    if _column_exists("design_chunks", "metadata"):
        op.alter_column("design_chunks", "metadata", new_column_name="chunk_metadata")


def downgrade() -> None:
    """Rename chunk_metadata back to metadata."""
    if _column_exists("design_chunks", "chunk_metadata"):
        op.alter_column("design_chunks", "chunk_metadata", new_column_name="metadata")
