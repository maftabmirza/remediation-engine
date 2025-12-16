"""Add analysis_feedback table

Revision ID: 013_add_analysis_feedback
Revises: 012_seed_default_roles
Create Date: 2025-12-13 21:12:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '013_add_analysis_feedback'
down_revision = '012_seed_default_roles'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create analysis_feedback table for tracking user feedback on AI analysis."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'analysis_feedback' not in tables:
        op.create_table('analysis_feedback',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            
            # Feedback flags
            sa.Column('helpful', sa.Boolean, nullable=True),
            sa.Column('rating', sa.Integer, nullable=True),
            sa.Column('accuracy', sa.String(30), nullable=True),
            
            # Qualitative feedback
            sa.Column('what_was_missing', sa.Text, nullable=True),
            sa.Column('what_actually_worked', sa.Text, nullable=True),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), index=True),
            
            # Indexes
            sa.Index('idx_analysis_feedback_alert_id', 'alert_id'),
            sa.Index('idx_analysis_feedback_user_id', 'user_id'),
            sa.Index('idx_analysis_feedback_created_at', 'created_at'),
        )
        
        # Add check constraint for rating (1-5)
        op.create_check_constraint(
            'ck_analysis_feedback_rating',
            'analysis_feedback',
            'rating IS NULL OR (rating >= 1 AND rating <= 5)'
        )
        
        # Add check constraint for accuracy
        op.create_check_constraint(
            'ck_analysis_feedback_accuracy',
            'analysis_feedback',
            "accuracy IS NULL OR accuracy IN ('accurate', 'partially_accurate', 'inaccurate')"
        )


def downgrade() -> None:
    """Drop analysis_feedback table."""
    op.drop_table('analysis_feedback')
