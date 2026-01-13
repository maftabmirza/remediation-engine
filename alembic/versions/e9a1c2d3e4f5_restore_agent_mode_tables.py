"""restore_agent_mode_tables

Revision ID: e9a1c2d3e4f5
Revises: ddf455edf0de
Create Date: 2026-01-13

Re-create Agent Mode tables (agent_sessions, agent_steps) after they were removed
by legacy-chat cleanup migrations.

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'e9a1c2d3e4f5'
down_revision = 'ddf455edf0de'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    # --- agent_sessions ---
    if 'agent_sessions' not in existing_tables:
        op.create_table(
            'agent_sessions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            # Optional link back to AI chat sessions (new schema uses ai_sessions)
            sa.Column('chat_session_id', UUID(as_uuid=True), sa.ForeignKey('ai_sessions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('server_id', UUID(as_uuid=True), sa.ForeignKey('server_credentials.id'), nullable=True),
            sa.Column('goal', sa.Text(), nullable=False),
            sa.Column('status', sa.String(50), nullable=True, server_default='idle'),
            sa.Column('auto_approve', sa.Boolean(), nullable=True, server_default=sa.text('false')),
            sa.Column('max_steps', sa.Integer(), nullable=True, server_default='20'),
            sa.Column('current_step_number', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
        )

        op.create_index('ix_agent_sessions_user_id', 'agent_sessions', ['user_id'])
        op.create_index('ix_agent_sessions_chat_session_id', 'agent_sessions', ['chat_session_id'])
        op.create_index('ix_agent_sessions_status', 'agent_sessions', ['status'])

    # --- agent_steps ---
    existing_tables = set(Inspector.from_engine(conn).get_table_names())
    if 'agent_steps' not in existing_tables:
        op.create_table(
            'agent_steps',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('agent_session_id', UUID(as_uuid=True), sa.ForeignKey('agent_sessions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('step_number', sa.Integer(), nullable=False),
            sa.Column('step_type', sa.String(20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('reasoning', sa.Text(), nullable=True),
            sa.Column('output', sa.Text(), nullable=True),
            sa.Column('exit_code', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        )

        op.create_index('ix_agent_steps_agent_session_id', 'agent_steps', ['agent_session_id'])
        op.create_index('ix_agent_steps_step_number', 'agent_steps', ['agent_session_id', 'step_number'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    if 'agent_steps' in existing_tables:
        op.drop_table('agent_steps')

    # Refresh table list after dropping
    existing_tables = set(Inspector.from_engine(conn).get_table_names())
    if 'agent_sessions' in existing_tables:
        op.drop_table('agent_sessions')
