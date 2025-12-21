"""Add ITSM integration and change correlation

Revision ID: 020_add_itsm_integration
Revises: 019_add_incident_metrics
Create Date: 2025-12-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '020_add_itsm_integration'
down_revision = '019_add_incident_metrics'
branch_labels = None
depends_on = None


def upgrade():
    # ITSM integrations table
    op.create_table('itsm_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('connector_type', sa.String(50), nullable=False, server_default='generic_api'),
        sa.Column('config_encrypted', sa.Text(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_sync', sa.DateTime(timezone=True)),
        sa.Column('last_sync_status', sa.String(50)),
        sa.Column('last_error', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_index('idx_itsm_enabled', 'itsm_integrations', ['is_enabled'])
    op.create_index('idx_itsm_last_sync', 'itsm_integrations', ['last_sync'])

    # Change events table
    op.create_table('change_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('change_id', sa.String(255), nullable=False, unique=True),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('service_name', sa.String(255)),
        sa.Column('description', sa.Text()),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(100)),
        sa.Column('change_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('correlation_score', sa.Float()),
        sa.Column('impact_level', sa.String(20)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_index('idx_change_id', 'change_events', ['change_id'], unique=True)
    op.create_index('idx_change_timestamp', 'change_events', ['timestamp'])
    op.create_index('idx_change_service', 'change_events', ['service_name'])
    op.create_index('idx_change_source', 'change_events', ['source'])
    op.create_index('idx_change_correlation', 'change_events', ['correlation_score'])

    # Change impact analysis table
    op.create_table('change_impact_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('incidents_after', sa.Integer(), server_default='0'),
        sa.Column('critical_incidents', sa.Integer(), server_default='0'),
        sa.Column('correlation_score', sa.Float(), nullable=False),
        sa.Column('impact_level', sa.String(20), nullable=False),
        sa.Column('recommendation', sa.Text()),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_foreign_key('fk_impact_change', 'change_impact_analysis', 'change_events',
                         ['change_event_id'], ['id'], ondelete='CASCADE')

    op.create_index('idx_impact_change', 'change_impact_analysis', ['change_event_id'])
    op.create_index('idx_impact_score', 'change_impact_analysis', ['correlation_score'])


def downgrade():
    op.drop_index('idx_impact_score', table_name='change_impact_analysis')
    op.drop_index('idx_impact_change', table_name='change_impact_analysis')
    op.drop_constraint('fk_impact_change', 'change_impact_analysis', type_='foreignkey')
    op.drop_table('change_impact_analysis')

    op.drop_index('idx_change_correlation', table_name='change_events')
    op.drop_index('idx_change_source', table_name='change_events')
    op.drop_index('idx_change_service', table_name='change_events')
    op.drop_index('idx_change_timestamp', table_name='change_events')
    op.drop_index('idx_change_id', table_name='change_events')
    op.drop_table('change_events')

    op.drop_index('idx_itsm_last_sync', table_name='itsm_integrations')
    op.drop_index('idx_itsm_enabled', table_name='itsm_integrations')
    op.drop_table('itsm_integrations')
