"""Add incident metrics

Revision ID: 019
Revises: 018
Create Date: 2025-12-19 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '019_add_incident_metrics'
down_revision = '018_add_alert_clustering'
branch_labels = None
depends_on = None

def upgrade():
    # Create incident_metrics table
    op.create_table('incident_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Lifecycle timestamps
        sa.Column('incident_started', sa.DateTime(timezone=True), nullable=False),
        sa.Column('incident_detected', sa.DateTime(timezone=True), nullable=False),
        sa.Column('incident_acknowledged', sa.DateTime(timezone=True), nullable=True),
        sa.Column('incident_engaged', sa.DateTime(timezone=True), nullable=True),
        sa.Column('incident_resolved', sa.DateTime(timezone=True), nullable=True),
        
        # Calculated durations (in seconds)
        sa.Column('time_to_detect', sa.Integer(), nullable=True),
        sa.Column('time_to_acknowledge', sa.Integer(), nullable=True),
        sa.Column('time_to_engage', sa.Integer(), nullable=True),
        sa.Column('time_to_resolve', sa.Integer(), nullable=True),
        
        # Context for breakdowns
        sa.Column('service_name', sa.String(length=255), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('resolution_type', sa.String(length=50), nullable=True),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True)
    )

    # Add unique constraint to alert_id separately
    op.create_unique_constraint('uq_incident_metrics_alert_id', 'incident_metrics', ['alert_id'])

    # Foreign keys
    op.create_foreign_key('fk_metrics_alert', 'incident_metrics', 'alerts', ['alert_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_metrics_user', 'incident_metrics', 'users', ['assigned_to'], ['id'], ondelete='SET NULL')

    # Indexes
    op.create_index('idx_metrics_resolved', 'incident_metrics', ['incident_resolved'])
    op.create_index('idx_metrics_service', 'incident_metrics', ['service_name'])
    op.create_index('idx_metrics_severity', 'incident_metrics', ['severity'])
    op.create_index('idx_metrics_resolution', 'incident_metrics', ['resolution_type'])
    op.create_index('idx_metrics_alert', 'incident_metrics', ['alert_id'])

def downgrade():
    op.drop_index('idx_metrics_alert', table_name='incident_metrics')
    op.drop_index('idx_metrics_resolution', table_name='incident_metrics')
    op.drop_index('idx_metrics_severity', table_name='incident_metrics')
    op.drop_index('idx_metrics_service', table_name='incident_metrics')
    op.drop_index('idx_metrics_resolved', table_name='incident_metrics')
    
    op.drop_constraint('fk_metrics_user', 'incident_metrics', type_='foreignkey')
    op.drop_constraint('fk_metrics_alert', 'incident_metrics', type_='foreignkey')
    op.drop_constraint('uq_incident_metrics_alert_id', 'incident_metrics', type_='unique')
    
    op.drop_table('incident_metrics')
