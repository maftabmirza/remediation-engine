"""Initial base schema - consolidated from all previous migrations.

This is the consolidated base schema representing the current database state.
All previous migrations have been squashed into this single migration.

Revision ID: 001_initial_base
Revises: 
Create Date: 2026-01-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_base'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create all tables from SQLAlchemy models.
    
    This migration uses the target metadata from env.py to create
    all tables defined in the application models.
    """
    # Enable required extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    
    # Create enum types first
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE paneltype AS ENUM (
                'graph', 'gauge', 'stat', 'table', 'heatmap', 'bar', 'pie'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # ========================================
    # Independent tables (no foreign keys)
    # ========================================
    
    # llm_providers (needed by users)
    op.create_table('llm_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('api_base_url', sa.String(255), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('config_json', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_llm_providers_provider_type', 'llm_providers', ['provider_type'])
    op.create_index('ix_llm_providers_is_default', 'llm_providers', ['is_default'])
    op.create_index('ix_llm_providers_is_enabled', 'llm_providers', ['is_enabled'])
    
    # users
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(100), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=True, default='operator'),
        sa.Column('default_llm_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ai_preferences', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['default_llm_provider_id'], ['llm_providers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_username', 'users', ['username'])
    
    # roles
    op.create_table('roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('permissions', postgresql.JSON(), nullable=False, default=[]),
        sa.Column('is_custom', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_roles_name', 'roles', ['name'])
    
    # credential_profiles
    op.create_table('credential_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('password_encrypted', sa.Text(), nullable=True),
        sa.Column('private_key_encrypted', sa.Text(), nullable=True),
        sa.Column('passphrase_encrypted', sa.Text(), nullable=True),
        sa.Column('auth_type', sa.String(20), nullable=False, default='password'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # server_groups
    op.create_table('server_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['server_groups.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # server_credentials
    op.create_table('server_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True, default=22),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('password_encrypted', sa.Text(), nullable=True),
        sa.Column('private_key_encrypted', sa.Text(), nullable=True),
        sa.Column('passphrase_encrypted', sa.Text(), nullable=True),
        sa.Column('auth_type', sa.String(20), nullable=False, default='password'),
        sa.Column('os_type', sa.String(50), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('environment', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('credential_profile_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True, default=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['group_id'], ['server_groups.id']),
        sa.ForeignKeyConstraint(['credential_profile_id'], ['credential_profiles.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_server_credentials_hostname', 'server_credentials', ['hostname'])
    op.create_index('ix_server_credentials_name', 'server_credentials', ['name'])
    
    # alert_clusters
    op.create_table('alert_clusters',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('pattern', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alert_count', sa.Integer(), nullable=True, default=0),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('centroid_embedding', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # auto_analyze_rules
    op.create_table('auto_analyze_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True, default=100),
        sa.Column('condition_json', postgresql.JSON(), nullable=True),
        sa.Column('alert_name_pattern', sa.String(255), nullable=True, default='*'),
        sa.Column('severity_pattern', sa.String(50), nullable=True, default='*'),
        sa.Column('instance_pattern', sa.String(255), nullable=True, default='*'),
        sa.Column('job_pattern', sa.String(255), nullable=True, default='*'),
        sa.Column('action', sa.String(20), nullable=True, default='manual'),
        sa.Column('enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_auto_analyze_rules_priority', 'auto_analyze_rules', ['priority'])
    op.create_index('ix_auto_analyze_rules_enabled', 'auto_analyze_rules', ['enabled'])
    
    # alerts
    op.create_table('alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('alert_id', sa.String(255), nullable=True),
        sa.Column('fingerprint', sa.String(255), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('severity', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('instance', sa.String(255), nullable=True),
        sa.Column('job', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('labels', postgresql.JSON(), nullable=True),
        sa.Column('annotations', postgresql.JSON(), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('analyzed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('analysis_result', postgresql.JSON(), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('matched_rule_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('cluster_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('generator_url', sa.String(500), nullable=True),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['analyzed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['matched_rule_id'], ['auto_analyze_rules.id']),
        sa.ForeignKeyConstraint(['cluster_id'], ['alert_clusters.id']),
        sa.ForeignKeyConstraint(['server_id'], ['server_credentials.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alerts_alert_id', 'alerts', ['alert_id'])
    op.create_index('ix_alerts_fingerprint', 'alerts', ['fingerprint'])
    op.create_index('ix_alerts_name', 'alerts', ['name'])
    op.create_index('ix_alerts_status', 'alerts', ['status'])
    op.create_index('ix_alerts_severity', 'alerts', ['severity'])
    op.create_index('ix_alerts_created_at', 'alerts', ['created_at'])
    
    # runbooks
    op.create_table('runbooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('alert_patterns', postgresql.JSON(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=True, default=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=True, default=5),
        sa.Column('max_retries', sa.Integer(), nullable=True, default=0),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True, default=300),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, default=1),
        sa.Column('execution_count', sa.Integer(), nullable=True, default=0),
        sa.Column('success_count', sa.Integer(), nullable=True, default=0),
        sa.Column('acl_enabled', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_runbooks_name', 'runbooks', ['name'])
    op.create_index('ix_runbooks_category', 'runbooks', ['category'])
    op.create_index('ix_runbooks_is_enabled', 'runbooks', ['is_enabled'])
    
    # runbook_steps
    op.create_table('runbook_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('step_type', sa.String(50), nullable=False),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('script_content', sa.Text(), nullable=True),
        sa.Column('expected_output', sa.Text(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True, default=60),
        sa.Column('on_failure', sa.String(50), nullable=True, default='stop'),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=0),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=True, default=5),
        sa.Column('parameters', postgresql.JSON(), nullable=True),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('condition_type', sa.String(50), nullable=True),
        sa.Column('condition_expression', sa.Text(), nullable=True),
        sa.Column('branch_on_success', sa.Integer(), nullable=True),
        sa.Column('branch_on_failure', sa.Integer(), nullable=True),
        sa.Column('output_variable', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['runbook_id'], ['runbooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_runbook_steps_runbook_id', 'runbook_steps', ['runbook_id'])
    op.create_index('ix_runbook_steps_step_order', 'runbook_steps', ['step_order'])
    
    # runbook_executions
    op.create_table('runbook_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('triggered_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('trigger_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('current_step', sa.Integer(), nullable=True, default=0),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('output_log', sa.Text(), nullable=True),
        sa.Column('variables', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correlation_id', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['runbook_id'], ['runbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['server_id'], ['server_credentials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_runbook_executions_runbook_id', 'runbook_executions', ['runbook_id'])
    op.create_index('ix_runbook_executions_status', 'runbook_executions', ['status'])
    op.create_index('ix_runbook_executions_created_at', 'runbook_executions', ['created_at'])
    
    # step_executions
    op.create_table('step_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('command_executed', sa.Text(), nullable=True),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('error_output', sa.Text(), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('retry_attempt', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['runbook_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['runbook_steps.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_step_executions_execution_id', 'step_executions', ['execution_id'])
    
    # system_config
    op.create_table('system_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('value_type', sa.String(20), nullable=True, default='string'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('is_secret', sa.Boolean(), nullable=True, default=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('ix_system_config_key', 'system_config', ['key'])
    op.create_index('ix_system_config_category', 'system_config', ['category'])
    
    # audit_logs
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    
    # terminal_sessions
    op.create_table('terminal_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('server_credential_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_token', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=True, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['server_credential_id'], ['server_credentials.id']),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_terminal_sessions_session_token', 'terminal_sessions', ['session_token'])
    
    # ========================================
    # Scheduler tables
    # ========================================
    
    op.create_table('scheduled_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_server_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('cron_expression', sa.String(100), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=True, default='UTC'),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(50), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True, default=0),
        sa.Column('success_count', sa.Integer(), nullable=True, default=0),
        sa.Column('failure_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['runbook_id'], ['runbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_server_id'], ['server_credentials.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduled_jobs_is_enabled', 'scheduled_jobs', ['is_enabled'])
    op.create_index('ix_scheduled_jobs_next_run_at', 'scheduled_jobs', ['next_run_at'])
    
    op.create_table('schedule_execution_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('scheduled_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('scheduled_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['scheduled_job_id'], ['scheduled_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['execution_id'], ['runbook_executions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ========================================
    # AI/Chat tables  
    # ========================================
    
    op.create_table('ai_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('context_type', sa.String(50), nullable=True),
        sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('llm_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('metadata_', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['llm_provider_id'], ['llm_providers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_sessions_user_id', 'ai_sessions', ['user_id'])
    op.create_index('ix_ai_sessions_is_active', 'ai_sessions', ['is_active'])
    
    op.create_table('ai_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('tool_calls', postgresql.JSON(), nullable=True),
        sa.Column('tool_results', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['ai_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_messages_session_id', 'ai_messages', ['session_id'])
    op.create_index('ix_ai_messages_created_at', 'ai_messages', ['created_at'])
    
    # ========================================
    # Agent tables
    # ========================================
    
    op.create_table('agent_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('chat_session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True, default='planning'),
        sa.Column('auto_approve', sa.Boolean(), nullable=True, default=False),
        sa.Column('max_steps', sa.Integer(), nullable=True, default=20),
        sa.Column('current_step_number', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('agent_type', sa.String(50), nullable=True),
        sa.Column('pool_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('worktree_path', sa.String(1024), nullable=True),
        sa.Column('auto_iterate', sa.Boolean(), nullable=True, default=False),
        sa.Column('max_auto_iterations', sa.Integer(), nullable=True, default=3),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['chat_session_id'], ['ai_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['server_id'], ['server_credentials.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_sessions_user_id', 'agent_sessions', ['user_id'])
    op.create_index('ix_agent_sessions_status', 'agent_sessions', ['status'])
    
    op.create_table('agent_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('requires_approval', sa.Boolean(), nullable=True, default=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('error_output', sa.Text(), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('safety_check', postgresql.JSON(), nullable=True),
        sa.Column('tool_name', sa.String(100), nullable=True),
        sa.Column('tool_args', postgresql.JSON(), nullable=True),
        sa.Column('tool_result', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_steps_session_id', 'agent_steps', ['session_id'])
    op.create_index('ix_agent_steps_status', 'agent_steps', ['status'])
    
    op.create_table('agent_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('validation_result', sa.String(20), nullable=True),
        sa.Column('blocked_reason', sa.String(500), nullable=True),
        sa.Column('output_preview', sa.String(1000), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('server_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['step_id'], ['agent_steps.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('agent_rate_limits',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('commands_this_minute', sa.Integer(), nullable=True),
        sa.Column('sessions_this_hour', sa.Integer(), nullable=True),
        sa.Column('minute_window_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hour_window_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_commands_per_minute', sa.Integer(), nullable=True),
        sa.Column('max_sessions_per_hour', sa.Integer(), nullable=True),
        sa.Column('is_rate_limited', sa.Boolean(), nullable=True),
        sa.Column('rate_limited_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # agent_pools
    op.create_table('agent_pools',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('max_concurrent_agents', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('agent_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('pool_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('priority', sa.Integer(), nullable=True, default=0),
        sa.Column('depends_on', postgresql.JSON(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['pool_id'], ['agent_pools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_session_id'], ['agent_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('action_proposals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('safety_level', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # iteration_loops
    op.create_table('iteration_loops',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('iteration_number', sa.Integer(), nullable=False, default=1),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, default='running'),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ========================================
    # Knowledge/Learning tables
    # ========================================
    
    op.create_table('knowledge_base',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_base_category', 'knowledge_base', ['category'])
    
    op.create_table('analysis_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('feedback_type', sa.String(50), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('original_analysis', postgresql.JSON(), nullable=True),
        sa.Column('corrected_analysis', postgresql.JSON(), nullable=True),
        sa.Column('is_helpful', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['execution_id'], ['runbook_executions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('solution_outcomes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('problem_description', sa.Text(), nullable=True),
        sa.Column('solution_applied', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(50), nullable=True),
        sa.Column('effectiveness_score', sa.Float(), nullable=True),
        sa.Column('time_to_resolve_seconds', sa.Integer(), nullable=True),
        sa.Column('recurrence_count', sa.Integer(), nullable=True, default=0),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['execution_id'], ['runbook_executions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['server_id'], ['server_credentials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ========================================
    # Troubleshooting tables
    # ========================================
    
    op.create_table('troubleshooting_guides',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('symptoms', postgresql.JSON(), nullable=True),
        sa.Column('causes', postgresql.JSON(), nullable=True),
        sa.Column('solutions', postgresql.JSON(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('alert_patterns', postgresql.JSON(), nullable=True),
        sa.Column('related_runbooks', postgresql.JSON(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('alert_correlations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('primary_alert_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correlated_alert_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correlation_type', sa.String(50), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('time_delta_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['primary_alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['correlated_alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('incident_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('time_to_detect_seconds', sa.Integer(), nullable=True),
        sa.Column('time_to_acknowledge_seconds', sa.Integer(), nullable=True),
        sa.Column('time_to_resolve_seconds', sa.Integer(), nullable=True),
        sa.Column('resolution_type', sa.String(50), nullable=True),
        sa.Column('was_automated', sa.Boolean(), nullable=True, default=False),
        sa.Column('escalation_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['execution_id'], ['runbook_executions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('inquiry_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('response_type', sa.String(50), nullable=True, default='text'),
        sa.Column('options', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('responded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['runbook_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['runbook_steps.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['responded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ========================================
    # Application/ITSM tables
    # ========================================
    
    op.create_table('applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('app_type', sa.String(50), nullable=True),
        sa.Column('owner', sa.String(100), nullable=True),
        sa.Column('team', sa.String(100), nullable=True),
        sa.Column('criticality', sa.String(20), nullable=True),
        sa.Column('environment', sa.String(50), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('metadata_', postgresql.JSON(), nullable=True),
        sa.Column('health_status', sa.String(50), nullable=True),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_applications_name', 'applications', ['name'])
    
    op.create_table('application_components',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('component_type', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('health_endpoint', sa.String(500), nullable=True),
        sa.Column('metrics_endpoint', sa.String(500), nullable=True),
        sa.Column('dependencies', postgresql.JSON(), nullable=True),
        sa.Column('config', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['server_id'], ['server_credentials.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('application_knowledge_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('knowledge_source', sa.String(50), nullable=False),
        sa.Column('source_config', postgresql.JSON(), nullable=True),
        sa.Column('sync_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_status', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('application_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('profile_type', sa.String(50), nullable=False),
        sa.Column('profile_data', postgresql.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('itsm_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('password_encrypted', sa.Text(), nullable=True),
        sa.Column('config_json', postgresql.JSON(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('change_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('itsm_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('change_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('impact', sa.String(20), nullable=True),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('affected_cis', postgresql.JSON(), nullable=True),
        sa.Column('affected_applications', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['itsm_provider_id'], ['itsm_providers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_change_requests_external_id', 'change_requests', ['external_id'])
    op.create_index('ix_change_requests_status', 'change_requests', ['status'])
    
    # ========================================
    # Dashboards/Grafana tables
    # ========================================
    
    op.create_table('grafana_datasources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('access', sa.String(20), nullable=True, default='proxy'),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('basic_auth', sa.Boolean(), nullable=True, default=False),
        sa.Column('basic_auth_user', sa.String(100), nullable=True),
        sa.Column('basic_auth_password_encrypted', sa.Text(), nullable=True),
        sa.Column('json_data', postgresql.JSON(), nullable=True),
        sa.Column('secure_json_data_encrypted', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    op.create_table('prometheus_dashboards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('uid', sa.String(40), nullable=True),
        sa.Column('folder', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('refresh_interval', sa.String(20), nullable=True),
        sa.Column('time_range', sa.String(50), nullable=True),
        sa.Column('datasource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['datasource_id'], ['grafana_datasources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_prometheus_dashboards_uid', 'prometheus_dashboards', ['uid'])
    
    op.create_table('dashboard_panels',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('dashboard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('panel_type', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('grid_pos', postgresql.JSON(), nullable=True),
        sa.Column('datasource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('targets', postgresql.JSON(), nullable=True),
        sa.Column('options', postgresql.JSON(), nullable=True),
        sa.Column('field_config', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['prometheus_dashboards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['datasource_id'], ['grafana_datasources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('dashboard_variables',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('dashboard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('label', sa.String(100), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('datasource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('refresh', sa.Integer(), nullable=True),
        sa.Column('options', postgresql.JSON(), nullable=True),
        sa.Column('current', postgresql.JSON(), nullable=True),
        sa.Column('multi', sa.Boolean(), nullable=True, default=False),
        sa.Column('include_all', sa.Boolean(), nullable=True, default=False),
        sa.Column('sort', sa.Integer(), nullable=True),
        sa.Column('hide', sa.Integer(), nullable=True),
        sa.Column('depends_on', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['prometheus_dashboards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['datasource_id'], ['grafana_datasources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('dashboard_annotations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('dashboard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('datasource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('hidden', sa.Boolean(), nullable=True, default=False),
        sa.Column('icon_color', sa.String(20), nullable=True),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['prometheus_dashboards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['datasource_id'], ['grafana_datasources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('dashboard_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('dashboard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('target_blank', sa.Boolean(), nullable=True, default=True),
        sa.Column('include_vars', sa.Boolean(), nullable=True, default=False),
        sa.Column('keep_time', sa.Boolean(), nullable=True, default=False),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['prometheus_dashboards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('dashboard_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('dashboard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('role', sa.String(50), nullable=True),
        sa.Column('permission', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['prometheus_dashboards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('dashboard_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('dashboard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key', sa.String(100), nullable=True),
        sa.Column('delete_key', sa.String(100), nullable=True),
        sa.Column('snapshot_data', postgresql.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['prometheus_dashboards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('dashboard_playlists',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('interval', sa.String(20), nullable=True, default='5m'),
        sa.Column('dashboard_ids', postgresql.JSON(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('dashboard_rows',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('dashboard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('collapsed', sa.Boolean(), nullable=True, default=False),
        sa.Column('grid_pos', postgresql.JSON(), nullable=True),
        sa.Column('panel_ids', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['prometheus_dashboards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('query_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('datasource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('query_type', sa.String(50), nullable=True),
        sa.Column('starred', sa.Boolean(), nullable=True, default=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['datasource_id'], ['grafana_datasources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ========================================
    # Runbook ACL tables
    # ========================================
    
    op.create_table('runbook_acls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('runbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('role', sa.String(50), nullable=True),
        sa.Column('permission', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['runbook_id'], ['runbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ========================================
    # File operations tables
    # ========================================
    
    op.create_table('file_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('file_path', sa.String(1024), nullable=False),
        sa.Column('content_before', sa.Text(), nullable=True),
        sa.Column('content_after', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['agent_steps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('file_backups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_path', sa.String(1024), nullable=False),
        sa.Column('backup_path', sa.String(1024), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['operation_id'], ['file_operations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ========================================
    # PII Detection tables
    # ========================================
    
    op.create_table('pii_scan_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled_detectors', postgresql.JSON(), nullable=True),
        sa.Column('confidence_threshold', sa.Float(), nullable=True, default=0.8),
        sa.Column('scan_inputs', sa.Boolean(), nullable=True, default=True),
        sa.Column('scan_outputs', sa.Boolean(), nullable=True, default=True),
        sa.Column('redaction_strategy', sa.String(50), nullable=True, default='mask'),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    op.create_table('pii_detections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('scan_config_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('pii_type', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('original_text_hash', sa.String(64), nullable=True),
        sa.Column('context_snippet', sa.Text(), nullable=True),
        sa.Column('redacted', sa.Boolean(), nullable=True, default=False),
        sa.Column('reviewed', sa.Boolean(), nullable=True, default=False),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('false_positive', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['scan_config_id'], ['pii_scan_configs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pii_detections_source_type', 'pii_detections', ['source_type'])
    op.create_index('ix_pii_detections_pii_type', 'pii_detections', ['pii_type'])
    
    # ========================================
    # Seed default data
    # ========================================
    
    # Default roles
    op.execute("""
        INSERT INTO roles (id, name, description, permissions, is_custom, created_at, updated_at)
        VALUES 
            (uuid_generate_v4(), 'admin', 'Full system administrator with all permissions', 
             '["*"]'::jsonb, false, NOW(), NOW()),
            (uuid_generate_v4(), 'operator', 'Operations team member with execution permissions',
             '["read:alerts", "write:alerts", "read:runbooks", "execute:runbooks", "read:servers", "read:dashboards"]'::jsonb, false, NOW(), NOW()),
            (uuid_generate_v4(), 'viewer', 'Read-only access to dashboards and alerts',
             '["read:alerts", "read:runbooks", "read:servers", "read:dashboards"]'::jsonb, false, NOW(), NOW()),
            (uuid_generate_v4(), 'developer', 'Developer with runbook creation permissions',
             '["read:alerts", "write:alerts", "read:runbooks", "write:runbooks", "execute:runbooks", "read:servers", "read:dashboards", "write:dashboards"]'::jsonb, false, NOW(), NOW())
        ON CONFLICT (name) DO NOTHING;
    """)


def downgrade() -> None:
    """Drop all tables (in reverse order of creation)."""
    # Drop tables in reverse dependency order
    tables_to_drop = [
        'pii_detections', 'pii_scan_configs',
        'file_backups', 'file_operations',
        'runbook_acls',
        'dashboard_rows', 'dashboard_playlists', 'dashboard_snapshots',
        'dashboard_permissions', 'dashboard_links', 'dashboard_annotations',
        'dashboard_variables', 'dashboard_panels', 'prometheus_dashboards',
        'grafana_datasources', 'query_history',
        'change_requests', 'itsm_providers',
        'application_profiles', 'application_knowledge_config',
        'application_components', 'applications',
        'inquiry_sessions', 'incident_metrics', 'alert_correlations',
        'troubleshooting_guides', 'solution_outcomes', 'analysis_feedback',
        'knowledge_base',
        'iteration_loops', 'action_proposals', 'agent_tasks', 'agent_pools',
        'agent_rate_limits', 'agent_audit_logs', 'agent_steps', 'agent_sessions',
        'ai_messages', 'ai_sessions',
        'schedule_execution_history', 'scheduled_jobs',
        'terminal_sessions', 'audit_logs', 'system_config',
        'step_executions', 'runbook_executions', 'runbook_steps', 'runbooks',
        'alerts', 'auto_analyze_rules', 'alert_clusters',
        'server_credentials', 'server_groups', 'credential_profiles',
        'roles', 'users', 'llm_providers',
    ]
    
    for table in tables_to_drop:
        op.drop_table(table)
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS paneltype')
