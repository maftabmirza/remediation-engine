"""fix_schema_drift_ai_sessions_updated_at

Revision ID: e352288a28d6
Revises: 07e4c065d440
Create Date: 2026-01-18 14:53:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e352288a28d6'
down_revision = '07e4c065d440'
branch_labels = None
depends_on = None


def upgrade():
    # Add updated_at column to ai_sessions if it doesn't exist
    op.execute("""
        ALTER TABLE ai_sessions 
        ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone;
    """)
    
    # Ensure apscheduler_jobs table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS apscheduler_jobs (
            id text PRIMARY KEY,
            next_run_time double precision,
            job_state bytea
        );
    """)
    
    # Ensure index exists
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_apscheduler_jobs_next_run_time 
        ON apscheduler_jobs (next_run_time);
    """)


def downgrade():
    # Remove updated_at column from ai_sessions
    op.execute("ALTER TABLE ai_sessions DROP COLUMN IF EXISTS updated_at;")
    
    # Drop apscheduler index and table
    op.execute("DROP INDEX IF EXISTS ix_apscheduler_jobs_next_run_time;")
    op.execute("DROP TABLE IF EXISTS apscheduler_jobs;")
