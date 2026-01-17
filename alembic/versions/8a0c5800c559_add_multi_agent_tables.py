"""add_multi_agent_tables

Revision ID: 8a0c5800c559
Revises: c29fb7c84bd2
Create Date: 2026-01-16 16:33:44.381292

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import create_table_safe, add_column_safe, column_exists

# revision identifiers, used by Alembic.
revision = '8a0c5800c559'
down_revision = 'c29fb7c84bd2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create agent_pools table
    create_table_safe(
        'agent_pools',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('max_concurrent_agents', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['ai_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Create agent_tasks table
    create_table_safe(
        'agent_tasks',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('pool_id', UUID(as_uuid=True), nullable=False),
        sa.Column('agent_session_id', UUID(as_uuid=True), nullable=True),
        sa.Column('agent_type', sa.String(length=50), nullable=True),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('worktree_path', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_session_id'], ['agent_sessions.id'], ),
        sa.ForeignKeyConstraint(['pool_id'], ['agent_pools.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Add columns to agent_sessions
    add_column_safe('agent_sessions', sa.Column('agent_type', sa.String(length=50), nullable=True, server_default='local'))
    add_column_safe('agent_sessions', sa.Column('pool_id', UUID(as_uuid=True), nullable=True))
    add_column_safe('agent_sessions', sa.Column('worktree_path', sa.String(length=1024), nullable=True))
    add_column_safe('agent_sessions', sa.Column('auto_iterate', sa.Boolean(), nullable=True, server_default='false'))
    add_column_safe('agent_sessions', sa.Column('max_auto_iterations', sa.Integer(), nullable=True, server_default='5'))
    
    if column_exists('agent_sessions', 'pool_id') and column_exists('agent_pools', 'id'):
        op.create_foreign_key(None, 'agent_sessions', 'agent_pools', ['pool_id'], ['id'])

    # 4. Add columns to agent_steps
    add_column_safe('agent_steps', sa.Column('iteration_count', sa.Integer(), nullable=True, server_default='0'))
    add_column_safe('agent_steps', sa.Column('change_set_id', UUID(as_uuid=True), nullable=True))
    
    if column_exists('agent_steps', 'change_set_id') and column_exists('change_sets', 'id'):
        op.create_foreign_key(None, 'agent_steps', 'change_sets', ['change_set_id'], ['id'])


def downgrade() -> None:
    # Remove columns from agent_steps
    op.drop_constraint(None, 'agent_steps', type_='foreignkey')
    op.drop_column('agent_steps', 'change_set_id')
    op.drop_column('agent_steps', 'iteration_count')

    # Remove columns from agent_sessions
    op.drop_constraint(None, 'agent_sessions', type_='foreignkey')
    op.drop_column('agent_sessions', 'max_auto_iterations')
    op.drop_column('agent_sessions', 'auto_iterate')
    op.drop_column('agent_sessions', 'worktree_path')
    op.drop_column('agent_sessions', 'pool_id')
    op.drop_column('agent_sessions', 'agent_type')

    # Drop tables
    op.drop_table('agent_tasks')
    op.drop_table('agent_pools')
