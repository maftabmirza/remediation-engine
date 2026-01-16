"""add_ivipa_workflow_support

Revision ID: 006_add_ivipa_workflow
Revises: 005_add_agent_mode
Create Date: 2025-01-16

Adds IVIPA workflow support to agent tables:
- Identify, Verify, Investigate, Plan, Act phases
- Visible thinking for each step
- Investigation policy tracking
- Plan mode support
- Task list tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '006_add_ivipa_workflow'
down_revision = '005_add_agent_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add IVIPA columns to agent_sessions
    op.add_column('agent_sessions', sa.Column('current_phase', sa.String(20), server_default='identify'))
    op.add_column('agent_sessions', sa.Column('investigation_tool_count', sa.Integer(), server_default='0'))
    op.add_column('agent_sessions', sa.Column('phase_history', JSON, nullable=True))
    op.add_column('agent_sessions', sa.Column('current_plan', JSON, nullable=True))
    op.add_column('agent_sessions', sa.Column('plan_step_index', sa.Integer(), server_default='0'))
    op.add_column('agent_sessions', sa.Column('autonomy_level', sa.Integer(), server_default='1'))
    op.add_column('agent_sessions', sa.Column('task_list', JSON, nullable=True))

    # Update max_steps default from 20 to 30
    op.alter_column('agent_sessions', 'max_steps', server_default='30')

    # Add IVIPA columns to agent_steps
    op.add_column('agent_steps', sa.Column('ivipa_phase', sa.String(20), nullable=True))
    op.add_column('agent_steps', sa.Column('thinking', sa.Text(), nullable=True))
    op.add_column('agent_steps', sa.Column('tool_name', sa.String(100), nullable=True))
    op.add_column('agent_steps', sa.Column('tool_input', JSON, nullable=True))
    op.add_column('agent_steps', sa.Column('tool_output', JSON, nullable=True))
    op.add_column('agent_steps', sa.Column('output_analysis', sa.Text(), nullable=True))

    # Create index for phase queries
    op.create_index('ix_agent_sessions_current_phase', 'agent_sessions', ['current_phase'])
    op.create_index('ix_agent_steps_ivipa_phase', 'agent_steps', ['ivipa_phase'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_agent_steps_ivipa_phase', table_name='agent_steps')
    op.drop_index('ix_agent_sessions_current_phase', table_name='agent_sessions')

    # Remove columns from agent_steps
    op.drop_column('agent_steps', 'output_analysis')
    op.drop_column('agent_steps', 'tool_output')
    op.drop_column('agent_steps', 'tool_input')
    op.drop_column('agent_steps', 'tool_name')
    op.drop_column('agent_steps', 'thinking')
    op.drop_column('agent_steps', 'ivipa_phase')

    # Remove columns from agent_sessions
    op.drop_column('agent_sessions', 'task_list')
    op.drop_column('agent_sessions', 'autonomy_level')
    op.drop_column('agent_sessions', 'plan_step_index')
    op.drop_column('agent_sessions', 'current_plan')
    op.drop_column('agent_sessions', 'phase_history')
    op.drop_column('agent_sessions', 'investigation_tool_count')
    op.drop_column('agent_sessions', 'current_phase')

    # Revert max_steps default
    op.alter_column('agent_sessions', 'max_steps', server_default='20')
