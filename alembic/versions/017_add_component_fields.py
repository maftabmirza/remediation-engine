"""add hostname ip subtype to components

Revision ID: 017_add_component_fields
Revises: 016_add_troubleshooting_tables
Create Date: 2025-12-14 22:09:00

"""
from alembic import op
import sqlalchemy as sa

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    add_column_safe,
    create_check_constraint_safe,
    drop_constraint_safe
)


# revision identifiers, used by Alembic.
revision = '017_add_component_fields'
down_revision = '016_add_troubleshooting_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to application_components
    add_column_safe('application_components', sa.Column('hostname', sa.String(length=255), nullable=True))
    add_column_safe('application_components', sa.Column('ip_address', sa.String(length=45), nullable=True))
    add_column_safe('application_components', sa.Column('subtype', sa.String(length=50), nullable=True))
    
    # Drop old constraint
    drop_constraint_safe('ck_components_type', 'application_components', type_='check')
    
    # Add new constraint with expanded types
    create_check_constraint_safe(
        'ck_components_type',
        'application_components',
        "component_type IN ('compute', 'container', 'vm', 'database', 'cache', 'queue', 'storage', "
        "'load_balancer', 'firewall', 'switch', 'router', 'cloud_function', 'cloud_storage', "
        "'cloud_db', 'external', 'monitoring', 'cdn', 'api_gateway')"
    )


def downgrade():
    # Revert constraint
    drop_constraint_safe('ck_components_type', 'application_components', type_='check')
    create_check_constraint_safe(
        'ck_components_type',
        'application_components',
        "component_type IN ('compute', 'database', 'cache', 'queue', 'storage', 'cdn', 'load_balancer', 'api_gateway', 'external')"
    )
    
    # Drop new columns
    op.drop_column('application_components', 'subtype')
    op.drop_column('application_components', 'ip_address')
    op.drop_column('application_components', 'hostname')
