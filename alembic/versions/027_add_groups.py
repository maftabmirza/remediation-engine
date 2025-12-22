"""add groups for rbac

Revision ID: 027
Revises: 026
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade():
    # Create groups table
    op.create_table('groups',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('role_id', UUID(as_uuid=True), sa.ForeignKey('roles.id'), nullable=True),
        sa.Column('ad_group_dn', sa.String(500), nullable=True),
        sa.Column('sync_enabled', sa.Boolean, default=False, index=True),
        sa.Column('last_synced', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )
    
    # Create group_members junction table
    op.create_table('group_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('group_id', UUID(as_uuid=True), sa.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source', sa.String(20), default='manual', index=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('group_id', 'user_id', name='uq_group_member'),
    )


def downgrade():
    op.drop_table('group_members')
    op.drop_table('groups')
