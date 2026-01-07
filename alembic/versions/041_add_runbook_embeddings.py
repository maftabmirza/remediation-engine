"""add_runbook_embeddings

Revision ID: 041_add_runbook_embeddings
Revises: 040_sync_schema_drift
Create Date: 2026-01-05 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '041_add_runbook_embeddings'
down_revision = '040_sync_schema_drift'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure vector extension exists
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Add embedding column
    # Use Vector type from pgvector
    op.add_column('runbooks', sa.Column('embedding', Vector(1536), nullable=True))
    
    # Create index using raw SQL because alembic support for vector index might be limited
    op.execute('CREATE INDEX IF NOT EXISTS idx_runbooks_embedding ON runbooks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_runbooks_embedding')
    op.drop_column('runbooks', 'embedding')
