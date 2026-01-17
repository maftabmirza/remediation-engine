"""add_iteration_loops

Revision ID: a3c55b6b9914
Revises: 8a0c5800c559
Create Date: 2026-01-16 16:46:56.376183

"""
from alembic import op
import sqlalchemy as sa

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import create_table_safe, add_column_safe


# revision identifiers, used by Alembic.
revision = 'a3c55b6b9914'
down_revision = '8a0c5800c559'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create iteration_loops table
    create_table_safe(
        'iteration_loops',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_task_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('iteration_number', sa.Integer(), nullable=False),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('error_detected', sa.Boolean(), nullable=True),
        sa.Column('error_type', sa.String(length=255), nullable=True),
        sa.Column('error_analysis', sa.Text(), nullable=True),
        sa.Column('fix_proposed', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agent_task_id'], ['agent_tasks.id'], )
    )
    
    # Add columns to agent_tasks
    add_column_safe('agent_tasks', sa.Column('auto_iterate', sa.Boolean(), nullable=True, server_default='false'))
    add_column_safe('agent_tasks', sa.Column('max_iterations', sa.Integer(), nullable=True, server_default='5'))


def downgrade() -> None:
    # Remove columns from agent_tasks
    op.drop_column('agent_tasks', 'max_iterations')
    op.drop_column('agent_tasks', 'auto_iterate')
    
    # Drop iteration_loops table
    op.drop_table('iteration_loops')
