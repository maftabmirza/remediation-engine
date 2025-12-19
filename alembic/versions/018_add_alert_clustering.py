"""Add alert clustering

Revision ID: 018_add_alert_clustering
Revises: 017_add_component_fields
Create Date: 2025-12-18 22:50:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '018_add_alert_clustering'
down_revision = '017_add_component_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Create alert_clusters table
    op.create_table('alert_clusters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('cluster_key', sa.String(255), nullable=False, unique=True),
        sa.Column('alert_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('cluster_type', sa.String(50), nullable=False, server_default='exact'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_reason', sa.String(100), nullable=True),
        sa.Column('cluster_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # Create indexes
    op.create_index('idx_cluster_key', 'alert_clusters', ['cluster_key'], unique=True)
    op.create_index('idx_cluster_first_seen', 'alert_clusters', ['first_seen'])
    op.create_index('idx_cluster_last_seen', 'alert_clusters', ['last_seen'])
    op.create_index('idx_cluster_severity', 'alert_clusters', ['severity'])
    op.create_index('idx_cluster_active', 'alert_clusters', ['is_active'])

    # Add columns to alerts
    op.add_column('alerts', sa.Column('cluster_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('alerts', sa.Column('clustered_at', sa.DateTime(timezone=True), nullable=True))

    # Add foreign key
    op.create_foreign_key('fk_alert_cluster', 'alerts', 'alert_clusters', ['cluster_id'], ['id'], ondelete='SET NULL')

    # Create index
    op.create_index('idx_alert_cluster', 'alerts', ['cluster_id'])


def downgrade():
    op.drop_index('idx_alert_cluster', table_name='alerts')
    op.drop_constraint('fk_alert_cluster', 'alerts', type_='foreignkey')
    op.drop_column('alerts', 'clustered_at')
    op.drop_column('alerts', 'cluster_id')

    op.drop_index('idx_cluster_active', table_name='alert_clusters')
    op.drop_index('idx_cluster_severity', table_name='alert_clusters')
    op.drop_index('idx_cluster_last_seen', table_name='alert_clusters')
    op.drop_index('idx_cluster_first_seen', table_name='alert_clusters')
    op.drop_index('idx_cluster_key', table_name='alert_clusters')

    op.drop_table('alert_clusters')
