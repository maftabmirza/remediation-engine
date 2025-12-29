"""Add foreign key constraints from application_profiles to grafana_datasources

Revision ID: 035_add_datasource_fks_to_profiles
Revises: 034_add_grafana_datasources
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    create_table_safe, create_index_safe, add_column_safe,
    create_foreign_key_safe, create_unique_constraint_safe, create_check_constraint_safe,
    drop_index_safe, drop_constraint_safe, drop_column_safe, drop_table_safe
)

# revision identifiers, used by Alembic.
revision = '035_add_ds_fks'
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
    create_foreign_key_safe(
        'fk_app_profiles_prometheus_datasource',
        'application_profiles',
        'grafana_datasources',
        ['prometheus_datasource_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add FK constraint for loki_datasource_id
    create_foreign_key_safe(
        'fk_app_profiles_loki_datasource',
        'application_profiles',
        'grafana_datasources',
        ['loki_datasource_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add FK constraint for tempo_datasource_id
    create_foreign_key_safe(
        'fk_app_profiles_tempo_datasource',
        'application_profiles',
        'grafana_datasources',
        ['tempo_datasource_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    """Remove foreign key constraints."""
    drop_constraint_safe('fk_app_profiles_tempo_datasource', 'application_profiles', type_='foreignkey')
    drop_constraint_safe('fk_app_profiles_loki_datasource', 'application_profiles', type_='foreignkey')
    drop_constraint_safe('fk_app_profiles_prometheus_datasource', 'application_profiles', type_='foreignkey')
