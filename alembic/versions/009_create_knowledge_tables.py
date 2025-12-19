"""Create knowledge tables

Revision ID: 009_create_knowledge_tables
Revises: 008_add_pgvector
Create Date: 2025-12-13 14:02:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '009_create_knowledge_tables'
down_revision = '008_add_pgvector'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create design_documents, design_images, and design_chunks tables."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    # Create design_documents table
    if 'design_documents' not in tables:
        op.create_table('design_documents',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('slug', sa.String(500), unique=True, index=True),
            sa.Column('doc_type', sa.String(50), nullable=False, index=True),
            sa.Column('format', sa.String(20), nullable=False),
            sa.Column('raw_content', sa.Text, nullable=True),
            sa.Column('source_url', sa.String(1000), nullable=True),
            sa.Column('source_type', sa.String(50), nullable=True),
            sa.Column('version', sa.Integer, default=1),
            sa.Column('status', sa.String(20), default='active', index=True),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
        )
        
        # Add check constraint for doc_type
        op.create_check_constraint(
            'ck_design_documents_doc_type',
            'design_documents',
            "doc_type IN ('architecture', 'api_spec', 'runbook', 'sop', 'troubleshooting', 'design_doc', 'postmortem', 'onboarding')"
        )
        
        # Add check constraint for format
        op.create_check_constraint(
            'ck_design_documents_format',
            'design_documents',
            "format IN ('markdown', 'pdf', 'html', 'yaml')"
        )
    
    # Create design_images table
    if 'design_images' not in tables:
        op.create_table('design_images',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('design_documents.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('image_type', sa.String(50), nullable=False, index=True),
            sa.Column('storage_path', sa.String(1000), nullable=False),
            sa.Column('thumbnail_path', sa.String(1000), nullable=True),
            sa.Column('file_size_bytes', sa.Integer, nullable=True),
            sa.Column('mime_type', sa.String(100), nullable=True),
            
            # AI-extracted information
            sa.Column('ai_description', sa.Text, nullable=True),
            sa.Column('extracted_text', sa.Text, nullable=True),
            sa.Column('identified_components', postgresql.JSONB, nullable=True),
            sa.Column('identified_connections', postgresql.JSONB, nullable=True),
            sa.Column('failure_scenarios', postgresql.JSONB, nullable=True),
            
            sa.Column('processing_status', sa.String(20), default='pending', index=True),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
        )
        
        # Add check constraint for image_type
        op.create_check_constraint(
            'ck_design_images_image_type',
            'design_images',
            "image_type IN ('architecture', 'flowchart', 'sequence', 'erd', 'network', 'deployment', 'component', 'other')"
        )
    
    # Create design_chunks table with vector embeddings
    if 'design_chunks' not in tables:
        op.create_table('design_chunks',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=True, index=True),
            
            # Source tracking
            sa.Column('source_type', sa.String(50), nullable=False),
            sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('chunk_index', sa.Integer, default=0),
            
            # Content
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('content_type', sa.String(50), nullable=False),
            
            # Vector embedding (1536 dimensions for OpenAI text-embedding-3-small)
            sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),  # Will be converted to vector type
            
            # Metadata for filtering
            sa.Column('metadata', postgresql.JSONB, default=sa.text("'{}'::jsonb")),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
        )
        
        # Add check constraint for source_type
        op.create_check_constraint(
            'ck_design_chunks_source_type',
            'design_chunks',
            "source_type IN ('document', 'image', 'component', 'alert_history')"
        )
        
        # Add check constraint for content_type
        op.create_check_constraint(
            'ck_design_chunks_content_type',
            'design_chunks',
            "content_type IN ('text', 'image_description', 'ocr', 'component_info', 'failure_mode', 'troubleshooting', 'dependency_info')"
        )
        
        # Convert embedding column to vector type
        op.execute('ALTER TABLE design_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)')
        
        # Create vector index for similarity search (using ivfflat)
        op.execute(
            'CREATE INDEX IF NOT EXISTS design_chunks_embedding_idx ON design_chunks '
            'USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'
        )
        
        # Create index for source lookups
        op.create_index('design_chunks_source_idx', 'design_chunks', ['source_type', 'source_id'])
        
        # Create GIN index for metadata
        op.execute('CREATE INDEX IF NOT EXISTS design_chunks_metadata_idx ON design_chunks USING gin(metadata)')


def downgrade() -> None:
    """Drop knowledge tables."""
    op.drop_table('design_chunks')
    op.drop_table('design_images')
    op.drop_table('design_documents')
