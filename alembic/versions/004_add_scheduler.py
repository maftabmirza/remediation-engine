"""
Add scheduler tables

Revision ID: 004_add_scheduler
Create Date: 2025-12-08 22:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers
# revision identifiers
revision = '004_add_scheduler'
down_revision = '486c4c57b545'  # Points to 001_initial_schema.py
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # Create scheduled_jobs table
    if 'scheduled_jobs' not in tables:
        op.create_table(
            'scheduled_jobs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('runbook_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbooks.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text),
            
            # Schedule Configuration
            sa.Column('schedule_type', sa.String(50), nullable=False),
            sa.Column('cron_expression', sa.String(100)),
            sa.Column('interval_seconds', sa.Integer),
            sa.Column('start_date', sa.DateTime(timezone=True)),
            sa.Column('end_date', sa.DateTime(timezone=True)),
            sa.Column('timezone', sa.String(50), server_default='UTC'),
            
            # Execution Configuration
            sa.Column('target_server_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_credentials.id')),
            sa.Column('execution_params', postgresql.JSON),
            sa.Column('max_instances', sa.Integer, server_default='1'),
            sa.Column('misfire_grace_time', sa.Integer, server_default='300'),
            
            # Status
            sa.Column('enabled', sa.Boolean, server_default='true'),
            sa.Column('last_run_at', sa.DateTime(timezone=True)),
            sa.Column('last_run_status', sa.String(50)),
            sa.Column('next_run_at', sa.DateTime(timezone=True)),
            sa.Column('run_count', sa.Integer, server_default='0'),
            sa.Column('failure_count', sa.Integer, server_default='0'),
            
            # Audit
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            
            sa.CheckConstraint("schedule_type IN ('cron', 'interval', 'date')", name='valid_schedule_type'),
        )
        
        # Create indexes for scheduled_jobs
        op.create_index('idx_scheduled_jobs_runbook', 'scheduled_jobs', ['runbook_id'])
        op.create_index('idx_scheduled_jobs_enabled', 'scheduled_jobs', ['enabled'], postgresql_where=sa.text('enabled = true'))
        op.create_index('idx_scheduled_jobs_next_run', 'scheduled_jobs', ['next_run_at'], postgresql_where=sa.text('enabled = true'))
    
    # Create schedule_execution_history table
    if 'schedule_execution_history' not in tables:
        op.create_table(
            'schedule_execution_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('scheduled_job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheduled_jobs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('runbook_execution_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbook_executions.id')),
            
            sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('executed_at', sa.DateTime(timezone=True)),
            sa.Column('completed_at', sa.DateTime(timezone=True)),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('error_message', sa.Text),
            sa.Column('duration_ms', sa.Integer),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        
        # Create indexes for schedule_execution_history
        op.create_index('idx_schedule_history_job', 'schedule_execution_history', ['scheduled_job_id'])
        op.create_index('idx_schedule_history_status', 'schedule_execution_history', ['status'])
        op.create_index('idx_schedule_history_created', 'schedule_execution_history', ['created_at'])


def downgrade():
    op.drop_index('idx_schedule_history_created', table_name='schedule_execution_history')
    op.drop_index('idx_schedule_history_status', table_name='schedule_execution_history')
    op.drop_index('idx_schedule_history_job', table_name='schedule_execution_history')
    op.drop_table('schedule_execution_history')
    
    op.drop_index('idx_scheduled_jobs_next_run', table_name='scheduled_jobs')
    op.drop_index('idx_scheduled_jobs_enabled', table_name='scheduled_jobs')
    op.drop_index('idx_scheduled_jobs_runbook', table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')
