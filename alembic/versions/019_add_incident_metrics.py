"""Add incident metrics

Revision ID: 019_add_incident_metrics
Revises: 018_add_alert_clustering
Create Date: 2025-12-19 22:00:00

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
revision = '019_add_incident_metrics'
down_revision = '018_add_alert_clustering'
branch_labels = None
depends_on = None


def upgrade():
    create_table_safe('incident_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_name', sa.String(255)),
        sa.Column('severity', sa.String(20)),
        sa.Column('incident_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('incident_end', sa.DateTime(timezone=True)),
        sa.Column('incident_resolved', sa.Boolean(), server_default='false'),
        sa.Column('resolution_type', sa.String(50)),
        sa.Column('mttr_minutes', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    create_index_safe('idx_metrics_alert', 'incident_metrics', ['alert_id'])
    create_index_safe('idx_metrics_service', 'incident_metrics', ['service_name'])
    create_index_safe('idx_metrics_severity', 'incident_metrics', ['severity'])
    create_index_safe('idx_metrics_resolved', 'incident_metrics', ['incident_resolved'])
    create_index_safe('idx_metrics_resolution', 'incident_metrics', ['resolution_type'])


def downgrade():
    drop_index_safe('idx_metrics_resolution', table_name='incident_metrics')
    drop_index_safe('idx_metrics_resolved', table_name='incident_metrics')
    drop_index_safe('idx_metrics_severity', table_name='incident_metrics')
    drop_index_safe('idx_metrics_service', table_name='incident_metrics')
    drop_index_safe('idx_metrics_alert', table_name='incident_metrics')
    drop_table_safe('incident_metrics')
