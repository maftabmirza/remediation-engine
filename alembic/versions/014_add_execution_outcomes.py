"""Add execution_outcomes table

Revision ID: 014_add_execution_outcomes
Revises: 013_add_analysis_feedback
Create Date: 2025-12-13 21:12:30.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '014_add_execution_outcomes'
down_revision = '013_add_analysis_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create execution_outcomes table for tracking runbook execution results."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'execution_outcomes' not in tables:
        op.create_table('execution_outcomes',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('execution_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbook_executions.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            
            # Outcome
            sa.Column('resolved_issue', sa.Boolean, nullable=True),
            sa.Column('resolution_type', sa.String(30), nullable=True),
            
            # Timing
            sa.Column('time_to_resolution_minutes', sa.Integer, nullable=True),
            
            # Learning
            sa.Column('recommendation_followed', sa.Boolean, nullable=True),
            sa.Column('manual_steps_taken', sa.Text, nullable=True),
            sa.Column('improvement_suggestion', sa.Text, nullable=True),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), index=True),
            
            # Indexes
            sa.Index('idx_execution_outcomes_execution_id', 'execution_id'),
            sa.Index('idx_execution_outcomes_alert_id', 'alert_id'),
            sa.Index('idx_execution_outcomes_user_id', 'user_id'),
            sa.Index('idx_execution_outcomes_created_at', 'created_at'),
        )
        
        # Add check constraint for resolution_type
        op.create_check_constraint(
            'ck_execution_outcomes_resolution_type',
            'execution_outcomes',
            "resolution_type IS NULL OR resolution_type IN ('full', 'partial', 'no_effect', 'made_worse')"
        )
        
        # Add check constraint for time_to_resolution (must be positive)
        op.create_check_constraint(
            'ck_execution_outcomes_time_positive',
            'execution_outcomes',
            'time_to_resolution_minutes IS NULL OR time_to_resolution_minutes >= 0'
        )


def downgrade() -> None:
    """Drop execution_outcomes table."""
    op.drop_table('execution_outcomes')
