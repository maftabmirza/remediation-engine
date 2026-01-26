"""fix_agent_steps_column_types

Revision ID: g6b7c8d9e0f1
Revises: f5a6b7c8d9e0, e352288a28d6
Create Date: 2026-01-26

Merges two migration branches and fixes agent_steps column types to match 
the working schema from database_schema_20260125.sql:
- validation_result: JSONB -> VARCHAR(20)
- blocked_reason: TEXT -> VARCHAR(500)  
- step_metadata: JSONB -> TEXT

These columns were auto-created by SQLAlchemy from model definitions but with wrong types.
The model used Column(JSON) which PostgreSQL maps to JSONB, but the working schema uses TEXT/VARCHAR.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'g6b7c8d9e0f1'
down_revision = ('f5a6b7c8d9e0', 'e352288a28d6')  # Merge two heads
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if agent_steps table exists
    if 'agent_steps' not in inspector.get_table_names():
        return
    
    # Get current column types
    columns = {col['name']: col for col in inspector.get_columns('agent_steps')}
    
    # Fix validation_result: should be VARCHAR(20), not JSONB
    if 'validation_result' in columns:
        col_type = str(columns['validation_result']['type'])
        if 'jsonb' in col_type.lower() or 'json' in col_type.lower():
            op.execute("""
                ALTER TABLE agent_steps 
                ALTER COLUMN validation_result TYPE character varying(20) 
                USING validation_result::text::character varying(20)
            """)
    
    # Fix blocked_reason: should be VARCHAR(500), not TEXT
    if 'blocked_reason' in columns:
        col_type = str(columns['blocked_reason']['type'])
        if 'text' in col_type.lower():
            op.execute("""
                ALTER TABLE agent_steps 
                ALTER COLUMN blocked_reason TYPE character varying(500)
            """)
    
    # Fix step_metadata: should be TEXT, not JSONB
    if 'step_metadata' in columns:
        col_type = str(columns['step_metadata']['type'])
        if 'jsonb' in col_type.lower() or 'json' in col_type.lower():
            op.execute("""
                ALTER TABLE agent_steps 
                ALTER COLUMN step_metadata TYPE text 
                USING step_metadata::text
            """)


def downgrade() -> None:
    # Reverting would change back to JSONB which causes the error
    # So we leave the columns as-is in downgrade
    pass
