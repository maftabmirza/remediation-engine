"""add dashboard permissions

Revision ID: 030_add_dashboard_permissions
Revises: 029_add_variable_dependencies
Create Date: 2025-01-01 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '030_add_dashboard_permissions'
down_revision = '029_add_variable_dependencies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dashboard_permissions table
    op.create_table(
        'dashboard_permissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dashboard_id', sa.String(36), sa.ForeignKey('dashboards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('role', sa.String(50), nullable=True),
        sa.Column('permission', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create indexes
    op.create_index('ix_dashboard_permissions_dashboard_id', 'dashboard_permissions', ['dashboard_id'])
    op.create_index('ix_dashboard_permissions_user_id', 'dashboard_permissions', ['user_id'])
    op.create_index('ix_dashboard_permissions_role', 'dashboard_permissions', ['role'])


def downgrade() -> None:
    op.drop_index('ix_dashboard_permissions_role', 'dashboard_permissions')
    op.drop_index('ix_dashboard_permissions_user_id', 'dashboard_permissions')
    op.drop_index('ix_dashboard_permissions_dashboard_id', 'dashboard_permissions')
    op.drop_table('dashboard_permissions')
