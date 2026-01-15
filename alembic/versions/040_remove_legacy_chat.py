"""remove_legacy_chat

Revision ID: 040_remove_legacy_chat
Revises: 039_restore_ai_helper
Create Date: 2026-01-09 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '040_remove_legacy_chat'
down_revision = '039_restore_ai_helper'
branch_labels = None
depends_on = None

def upgrade():
    # Upgrade: DROP the legacy tables
    # Dropping dependent tables first
    
    # 0. Drop agent tables (dependent on chat_sessions)
    op.drop_table('agent_steps')
    op.drop_table('agent_sessions')

    # 1. Drop chat_messages
    op.drop_table('chat_messages')
    
    # 2. Drop chat_sessions
    op.drop_table('chat_sessions')
    
    # 3. Drop inquiry_results
    op.drop_table('inquiry_results')
    
    # 4. Drop inquiry_sessions
    op.drop_table('inquiry_sessions')


def downgrade():
    # Downgrade: Re-create the legacy tables (simplified schema)
    # This best effort attempt to allow rollback
    
    ### Chat Session ###
    op.create_table('chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id'), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('llm_provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('llm_providers.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    ### Chat Messages ###
    op.create_table('chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('tokens_used', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    ### Inquiry Sessions ###
    op.create_table('inquiry_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    ### Inquiry Results ###
    op.create_table('inquiry_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inquiry_sessions.id'), nullable=True),
        sa.Column('query', sa.Text, nullable=False),
        sa.Column('result_json', postgresql.JSONB, nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('intent_type', sa.String(50), nullable=True),
        sa.Column('execution_time_ms', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
