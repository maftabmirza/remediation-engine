"""Add solution_outcomes table for learning from feedback

Revision ID: 038_add_solution_outcomes
Revises: 037_add_inquiry_sessions
Create Date: 2026-01-09 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '038_add_solution_outcomes'
down_revision = '4182a90197d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create solution_outcomes table for tracking what solutions worked."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'solution_outcomes' not in tables:
        op.create_table('solution_outcomes',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            
            # Session context
            sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
            
            # Problem context (for similarity matching)
            sa.Column('problem_description', sa.Text, nullable=False),
            sa.Column('problem_embedding', Vector(1536), nullable=True),  # For similarity search
            sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('server_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_credentials.id', ondelete='SET NULL'), nullable=True, index=True),
            
            # What was suggested
            sa.Column('solution_type', sa.String(50), nullable=False),  # 'runbook', 'command', 'knowledge', 'agent_suggestion'
            sa.Column('solution_reference', sa.Text, nullable=True),     # runbook_id, command text, knowledge doc id
            sa.Column('solution_summary', sa.Text, nullable=True),       # Brief description
            
            # Outcome (from user feedback or auto-detection)
            sa.Column('success', sa.Boolean, nullable=True),
            sa.Column('auto_detected', sa.Boolean, default=False),  # Was success auto-detected from terminal?
            sa.Column('user_feedback', sa.Text, nullable=True),
            sa.Column('feedback_timestamp', sa.DateTime(timezone=True), nullable=True),
            
            # Metadata
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), index=True),
        )
        
        # Create index for vector similarity search
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_solution_outcomes_embedding 
            ON solution_outcomes 
            USING ivfflat (problem_embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        
        # Add check constraint for solution_type
        op.create_check_constraint(
            'ck_solution_outcomes_solution_type',
            'solution_outcomes',
            "solution_type IN ('runbook', 'command', 'knowledge', 'agent_suggestion', 'session')"
        )


def downgrade() -> None:
    """Drop solution_outcomes table."""
    op.execute("DROP INDEX IF EXISTS idx_solution_outcomes_embedding")
    op.drop_table('solution_outcomes')
