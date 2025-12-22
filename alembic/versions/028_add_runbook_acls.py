"""add runbook ACLs

Revision ID: 028
Revises: 027
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create runbook_acls table
    op.create_table(
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
    op.create_unique_constraint('uq_runbook_group_acl', 'runbook_acls', ['runbook_id', 'group_id'])
    
    # Create indexes
    op.create_index('idx_runbook_acl_runbook', 'runbook_acls', ['runbook_id'])
    op.create_index('idx_runbook_acl_group', 'runbook_acls', ['group_id'])


def downgrade() -> None:
    op.drop_index('idx_runbook_acl_group', 'runbook_acls')
    op.drop_index('idx_runbook_acl_runbook', 'runbook_acls')
    op.drop_constraint('uq_runbook_group_acl', 'runbook_acls', type_='unique')
    op.drop_table('runbook_acls')
