"""Add troubleshooting tables

Revision ID: 016_add_troubleshooting_tables
Revises: 015_add_alert_embeddings
Create Date: 2025-12-13 21:26:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '016_add_troubleshooting_tables'
down_revision = '015_add_alert_embeddings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create alert_correlations and failure_patterns tables."""
    
    # 1. Create alert_correlations table
    op.create_table('alert_correlations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('summary', sa.String(255), nullable=False),
        sa.Column('root_cause_analysis', sa.Text, nullable=True),
        sa.Column('status', sa.String(50), server_default='active', nullable=False),  # active, resolved, false_positive
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()')),
    )
    
    # 2. Add correlation_id to alerts table
    op.add_column('alerts', sa.Column('correlation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alert_correlations.id', ondelete='SET NULL'), nullable=True))
    op.create_index('idx_alerts_correlation_id', 'alerts', ['correlation_id'])

    # 3. Create failure_patterns table
    op.create_table('failure_patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('pattern_signature', sa.Text, nullable=False),  # JSON or text representation of the pattern
        sa.Column('root_cause_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('recommended_action', sa.Text, nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('occurrence_count', sa.Integer, server_default='1'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_failure_patterns_root_cause', 'failure_patterns', ['root_cause_type'])


def downgrade() -> None:
    """Drop troubleshooting tables."""
    # 1. Remove correlation_id from alerts
    op.drop_index('idx_alerts_correlation_id', table_name='alerts')
    op.drop_column('alerts', 'correlation_id')
    
    # 2. Drop tables
    op.drop_table('failure_patterns')
    op.drop_table('alert_correlations')
