"""Add troubleshooting tables

Revision ID: 016_add_troubleshooting_tables
Revises: 015_add_alert_embeddings
Create Date: 2025-12-17 22:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    create_table_safe, create_index_safe, create_foreign_key_safe,
    drop_index_safe, drop_constraint_safe, drop_table_safe
)

# revision identifiers, used by Alembic.
revision = '016_add_troubleshooting_tables'
down_revision = '015_add_alert_embeddings'
branch_labels = None
depends_on = None


def upgrade():
    # Create alert_correlations table
    create_table_safe('alert_correlations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('related_alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('correlation_type', sa.String(50), nullable=False),
        sa.Column('correlation_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    create_index_safe('idx_alert_correlations_alert_id', 'alert_correlations', ['alert_id'])
    create_index_safe('idx_alert_correlations_related_alert_id', 'alert_correlations', ['related_alert_id'])
    create_index_safe('idx_alert_correlations_correlation_type', 'alert_correlations', ['correlation_type'])

    # Create failure_patterns table
    create_table_safe('failure_patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('pattern_name', sa.String(255), nullable=False),
        sa.Column('pattern_description', sa.Text()),
        sa.Column('root_cause_type', sa.String(100), nullable=False),
        sa.Column('symptoms', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('resolution_steps', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('occurrence_count', sa.Integer(), server_default='1'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    create_index_safe('idx_failure_patterns_root_cause', 'failure_patterns', ['root_cause_type'])


def downgrade():
    drop_table_safe('failure_patterns')
    drop_index_safe('idx_alert_correlations_correlation_type', table_name='alert_correlations')
    drop_index_safe('idx_alert_correlations_related_alert_id', table_name='alert_correlations')
    drop_index_safe('idx_alert_correlations_alert_id', table_name='alert_correlations')
    drop_table_safe('alert_correlations')
