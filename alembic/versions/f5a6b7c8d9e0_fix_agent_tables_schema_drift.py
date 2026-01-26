"""fix_agent_tables_schema_drift

Revision ID: f5a6b7c8d9e0
Revises: e9a1c2d3e4f5
Create Date: 2026-01-25

Aligns agent_audit_logs and agent_rate_limits tables with the correct schema
from database_schema_20260125.sql

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'f5a6b7c8d9e0'
down_revision = 'c29fb7c84bd2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix agent_audit_logs table
    # Drop the old table and recreate with correct schema
    op.execute('DROP TABLE IF EXISTS agent_audit_logs CASCADE')
    
    op.create_table('agent_audit_logs',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), nullable=True),
        sa.Column('step_id', UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('validation_result', sa.String(length=20), nullable=True),
        sa.Column('blocked_reason', sa.String(length=500), nullable=True),
        sa.Column('output_preview', sa.String(length=1000), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('server_id', UUID(as_uuid=True), nullable=True),
        sa.Column('server_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['agent_steps.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Recreate indexes for agent_audit_logs
    op.create_index('idx_audit_action', 'agent_audit_logs', ['action'], unique=False)
    op.create_index('idx_audit_session', 'agent_audit_logs', ['session_id'], unique=False)
    op.create_index('idx_audit_user_created', 'agent_audit_logs', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_agent_audit_logs_created_at'), 'agent_audit_logs', ['created_at'], unique=False)
    
    # Fix agent_rate_limits table - remove default values where needed
    op.alter_column('agent_rate_limits', 'commands_this_minute',
                    existing_type=sa.Integer(),
                    server_default=None,
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'sessions_this_hour',
                    existing_type=sa.Integer(),
                    server_default=None,
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'max_commands_per_minute',
                    existing_type=sa.Integer(),
                    server_default=None,
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'max_sessions_per_hour',
                    existing_type=sa.Integer(),
                    server_default=None,
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'is_rate_limited',
                    existing_type=sa.Boolean(),
                    server_default=None,
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    existing_nullable=True)


def downgrade() -> None:
    # Revert agent_rate_limits changes
    op.alter_column('agent_rate_limits', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'is_rate_limited',
                    existing_type=sa.Boolean(),
                    server_default=sa.text('false'),
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'max_sessions_per_hour',
                    existing_type=sa.Integer(),
                    server_default=sa.text('10'),
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'max_commands_per_minute',
                    existing_type=sa.Integer(),
                    server_default=sa.text('10'),
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'sessions_this_hour',
                    existing_type=sa.Integer(),
                    server_default=sa.text('0'),
                    existing_nullable=True)
    
    op.alter_column('agent_rate_limits', 'commands_this_minute',
                    existing_type=sa.Integer(),
                    server_default=sa.text('0'),
                    existing_nullable=True)
    
    # Revert agent_audit_logs table
    op.drop_index(op.f('ix_agent_audit_logs_created_at'), table_name='agent_audit_logs')
    op.drop_index('idx_audit_user_created', table_name='agent_audit_logs')
    op.drop_index('idx_audit_session', table_name='agent_audit_logs')
    op.drop_index('idx_audit_action', table_name='agent_audit_logs')
    op.drop_table('agent_audit_logs')
    
    # Recreate old schema
    op.create_table('agent_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
