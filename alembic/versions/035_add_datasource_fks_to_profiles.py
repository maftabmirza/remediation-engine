"""Add foreign key constraints from application_profiles to grafana_datasources

Revision ID: 035_add_datasource_fks_to_profiles
Revises: 034_add_grafana_datasources
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '035_add_datasource_fks_to_profiles'
down_revision = '034_add_grafana_datasources'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add foreign key constraints from application_profiles to grafana_datasources.

    These FKs allow application profiles to reference specific datasource instances
    for Prometheus, Loki, and Tempo, enabling AI-powered queries to know which
    observability backends to query for each application.
    """
    # Add FK constraint for prometheus_datasource_id
    op.create_foreign_key(
        'fk_app_profiles_prometheus_datasource',
        'application_profiles',
        'grafana_datasources',
        ['prometheus_datasource_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add FK constraint for loki_datasource_id
    op.create_foreign_key(
        'fk_app_profiles_loki_datasource',
        'application_profiles',
        'grafana_datasources',
        ['loki_datasource_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add FK constraint for tempo_datasource_id
    op.create_foreign_key(
        'fk_app_profiles_tempo_datasource',
        'application_profiles',
        'grafana_datasources',
        ['tempo_datasource_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    """Remove foreign key constraints."""
    op.drop_constraint('fk_app_profiles_tempo_datasource', 'application_profiles', type_='foreignkey')
    op.drop_constraint('fk_app_profiles_loki_datasource', 'application_profiles', type_='foreignkey')
    op.drop_constraint('fk_app_profiles_prometheus_datasource', 'application_profiles', type_='foreignkey')
