"""Rename metadata to chunk_metadata

Revision ID: 010_rename_metadata_column
Revises: 009_create_knowledge_tables
Create Date: 2025-12-13 14:42:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_rename_metadata_column'
down_revision = '009_create_knowledge_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename metadata column to chunk_metadata to avoid SQLAlchemy reserved word."""
    op.alter_column('design_chunks', 'metadata', new_column_name='chunk_metadata')


def downgrade() -> None:
    """Rename chunk_metadata back to metadata."""
    op.alter_column('design_chunks', 'chunk_metadata', new_column_name='metadata')
