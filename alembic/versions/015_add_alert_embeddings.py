"""Add embedding support to alerts table

Revision ID: 015_add_alert_embeddings
Revises: 014_add_execution_outcomes
Create Date: 2025-12-13 21:13:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '015_add_alert_embeddings'
down_revision = '014_add_execution_outcomes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add embedding columns to alerts table for similarity search."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if columns already exist
    columns = [col['name'] for col in inspector.get_columns('alerts')]
    
    # Add embedding_text column if it doesn't exist
    if 'embedding_text' not in columns:
        op.add_column('alerts', sa.Column('embedding_text', sa.Text, nullable=True))
    
    # Add embedding column as array first, then convert to vector type
    if 'embedding' not in columns:
        # Add as array of floats initially
        op.execute('ALTER TABLE alerts ADD COLUMN embedding float[]')
        
        # Convert to vector(1536) type
        op.execute('ALTER TABLE alerts ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)')
    
    # Create vector index for similarity search (using ivfflat)
    # Check if index already exists
    indexes = [idx['name'] for idx in inspector.get_indexes('alerts')]
    if 'alerts_embedding_idx' not in indexes:
        op.execute(
            'CREATE INDEX IF NOT EXISTS alerts_embedding_idx ON alerts '
            'USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'
        )


def downgrade() -> None:
    """Remove embedding support from alerts table."""
    # Drop index first
    op.execute('DROP INDEX IF EXISTS alerts_embedding_idx')
    
    # Drop columns
    op.drop_column('alerts', 'embedding')
    op.drop_column('alerts', 'embedding_text')
