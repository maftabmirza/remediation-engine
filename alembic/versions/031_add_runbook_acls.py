"""add runbook ACLs

Revision ID: 031
Revises: 030_add_dashboard_permissions
Create Date: 2025-12-22

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
revision = '031'
down_revision = '030_add_dashboard_permissions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create runbook_acls table
    create_table_safe(
        'runbook_acls',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('runbook_id', UUID(as_uuid=True), sa.ForeignKey('runbooks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id', UUID(as_uuid=True), sa.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('can_view', sa.Boolean, default=True),
        sa.Column('can_edit', sa.Boolean, default=False),
        sa.Column('can_execute', sa.Boolean, default=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create unique constraint
    create_unique_constraint_safe('uq_runbook_group_acl', 'runbook_acls', ['runbook_id', 'group_id'])
    
    # Create indexes
    create_index_safe('idx_runbook_acl_runbook', 'runbook_acls', ['runbook_id'])
    create_index_safe('idx_runbook_acl_group', 'runbook_acls', ['group_id'])


def downgrade() -> None:
    drop_index_safe('idx_runbook_acl_group', 'runbook_acls')
    drop_index_safe('idx_runbook_acl_runbook', 'runbook_acls')
    drop_constraint_safe('uq_runbook_group_acl', 'runbook_acls', type_='unique')
    drop_table_safe('runbook_acls')
