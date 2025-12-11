"""add_agent_mode_tables

Revision ID: 005_add_agent_mode
Revises: c3031e42d864
Create Date: 2025-12-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '005_add_agent_mode'
down_revision = 'c3031e42d864'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()
    
    # Create agent_sessions table
    if 'agent_sessions' not in existing_tables:
        op.create_table(
            'agent_sessions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('chat_session_id', UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id'), nullable=False),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('server_id', UUID(as_uuid=True), sa.ForeignKey('server_credentials.id'), nullable=True),
            sa.Column('goal', sa.Text(), nullable=False),
            sa.Column('status', sa.String(50), default='idle'),
            sa.Column('auto_approve', sa.Boolean(), default=False),
            sa.Column('max_steps', sa.Integer(), default=20),
            sa.Column('current_step_number', sa.Integer(), default=0),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
        )
        
        # Create indexes for common queries
        op.create_index('ix_agent_sessions_user_id', 'agent_sessions', ['user_id'])
        op.create_index('ix_agent_sessions_chat_session_id', 'agent_sessions', ['chat_session_id'])
        op.create_index('ix_agent_sessions_status', 'agent_sessions', ['status'])
    
    # Create agent_steps table
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
            sa.Column('status', sa.String(20), default='pending'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        )
        
        # Create indexes
        op.create_index('ix_agent_steps_agent_session_id', 'agent_steps', ['agent_session_id'])
        op.create_index('ix_agent_steps_step_number', 'agent_steps', ['agent_session_id', 'step_number'])


def downgrade() -> None:
    op.drop_table('agent_steps')
    op.drop_table('agent_sessions')
