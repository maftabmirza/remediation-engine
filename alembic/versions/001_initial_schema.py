"""Initial Schema Baseline

Revision ID: 486c4c57b545
Revises: 
Create Date: 2025-12-10 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '486c4c57b545'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # --- Core Tables ---

    if 'users' not in tables:
        op.create_table('users',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('username', sa.String(50), unique=True, nullable=False, index=True),
            sa.Column('email', sa.String(255), unique=True, nullable=True),
            sa.Column('full_name', sa.String(100), nullable=True),
            sa.Column('password_hash', sa.String(255), nullable=False),
            sa.Column('role', sa.String(20), default="operator"),
            sa.Column('default_llm_provider_id', postgresql.UUID(as_uuid=True), nullable=True), # FK added later
            sa.Column('is_active', sa.Boolean, default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        )

    if 'roles' not in tables:
        op.create_table('roles',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(50), unique=True, nullable=False, index=True),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('permissions', postgresql.JSON, default=[], nullable=False),
            sa.Column('is_custom', sa.Boolean, default=True),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'llm_providers' not in tables:
        op.create_table('llm_providers',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('provider_type', sa.String(50), nullable=False, index=True),
            sa.Column('model_id', sa.String(100), nullable=False),
            sa.Column('api_key_encrypted', sa.Text, nullable=True),
            sa.Column('api_base_url', sa.String(255), nullable=True),
            sa.Column('is_default', sa.Boolean, default=False, index=True),
            sa.Column('is_enabled', sa.Boolean, default=True, index=True),
            sa.Column('config_json', postgresql.JSON, default={}),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'auto_analyze_rules' not in tables:
        op.create_table('auto_analyze_rules',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('priority', sa.Integer, default=100, index=True),
            sa.Column('condition_json', postgresql.JSON, nullable=True),
            sa.Column('alert_name_pattern', sa.String(255), default="*"),
            sa.Column('severity_pattern', sa.String(50), default="*"),
            sa.Column('instance_pattern', sa.String(255), default="*"),
            sa.Column('job_pattern', sa.String(255), default="*"),
            sa.Column('action', sa.String(20), default="manual"),
            sa.Column('enabled', sa.Boolean, default=True, index=True),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'alerts' not in tables:
        op.create_table('alerts',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('fingerprint', sa.String(100), index=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.Column('alert_name', sa.String(255), nullable=False, index=True),
            sa.Column('severity', sa.String(50), index=True),
            sa.Column('instance', sa.String(255)),
            sa.Column('job', sa.String(100)),
            sa.Column('status', sa.String(20), default="firing", index=True),
            sa.Column('labels_json', postgresql.JSON),
            sa.Column('annotations_json', postgresql.JSON),
            sa.Column('raw_alert_json', postgresql.JSON),
            sa.Column('matched_rule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('auto_analyze_rules.id')),
            sa.Column('action_taken', sa.String(20), index=True),
            sa.Column('analyzed', sa.Boolean, default=False, index=True),
            sa.Column('analyzed_at', sa.DateTime(timezone=True)),
            sa.Column('analyzed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('llm_provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('llm_providers.id')),
            sa.Column('ai_analysis', sa.Text),
            sa.Column('recommendations_json', postgresql.JSON),
            sa.Column('analysis_count', sa.Integer, default=0),
            sa.Column('created_at', sa.DateTime(timezone=True)),
        )

    if 'server_groups' not in tables:
        op.create_table('server_groups',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False, index=True),
            sa.Column('description', sa.Text),
            sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_groups.id')),
            sa.Column('path', sa.String(255), index=True),
            sa.Column('created_at', sa.DateTime(timezone=True)),
        )

    if 'credential_profiles' not in tables:
        op.create_table('credential_profiles',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False, unique=True, index=True),
            sa.Column('description', sa.Text),
            sa.Column('username', sa.String(100), index=True),
            sa.Column('credential_type', sa.String(30), default="key", index=True),
            sa.Column('backend', sa.String(30), default="inline", index=True),
            sa.Column('secret_encrypted', sa.Text),
            sa.Column('metadata_json', postgresql.JSON, default={}),
            sa.Column('last_rotated', sa.DateTime(timezone=True)),
            sa.Column('group_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_groups.id')),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'api_credential_profiles' not in tables:
        op.create_table('api_credential_profiles',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False, unique=True, index=True),
            sa.Column('description', sa.Text),
            sa.Column('credential_type', sa.String(50), default="api", index=True),
            sa.Column('base_url', sa.String(500), nullable=False),
            sa.Column('auth_type', sa.String(30), default="none", index=True),
            sa.Column('auth_header', sa.String(100)),
            sa.Column('token_encrypted', sa.Text),
            sa.Column('username', sa.String(255)),
            sa.Column('verify_ssl', sa.Boolean, default=True),
            sa.Column('timeout_seconds', sa.Integer, default=30),
            sa.Column('default_headers', postgresql.JSON, default={}),
            sa.Column('oauth_token_url', sa.String(500)),
            sa.Column('oauth_client_id', sa.String(255)),
            sa.Column('oauth_client_secret_encrypted', sa.Text),
            sa.Column('oauth_scope', sa.Text),
            sa.Column('tags', postgresql.JSON, default=[]),
            sa.Column('profile_metadata', postgresql.JSON, default={}),
            sa.Column('enabled', sa.Boolean, default=True, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('last_used_at', sa.DateTime(timezone=True)),
        )

    if 'server_credentials' not in tables:
        op.create_table('server_credentials',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('hostname', sa.String(255), nullable=False, index=True),
            sa.Column('port', sa.Integer, default=22),
            sa.Column('username', sa.String(100), nullable=False),
            sa.Column('os_type', sa.String(20), default="linux", index=True),
            sa.Column('protocol', sa.String(20), default="ssh", index=True),
            sa.Column('auth_type', sa.String(20), default="key"),
            sa.Column('ssh_key_encrypted', sa.Text),
            sa.Column('password_encrypted', sa.Text),
            sa.Column('credential_source', sa.String(30), default="inline", index=True),
            sa.Column('credential_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('credential_profiles.id'), index=True),
            sa.Column('credential_metadata', postgresql.JSON, default={}),
            sa.Column('winrm_transport', sa.String(20)),
            sa.Column('winrm_use_ssl', sa.Boolean, default=True),
            sa.Column('winrm_cert_validation', sa.Boolean, default=True),
            sa.Column('domain', sa.String(100)),
            sa.Column('api_base_url', sa.String(500)),
            sa.Column('api_auth_type', sa.String(30), default="none"),
            sa.Column('api_auth_header', sa.String(100)),
            sa.Column('api_token_encrypted', sa.Text),
            sa.Column('api_verify_ssl', sa.Boolean, default=True),
            sa.Column('api_timeout_seconds', sa.Integer, default=30),
            sa.Column('api_headers_json', postgresql.JSON, default={}),
            sa.Column('api_metadata_json', postgresql.JSON, default={}),
            sa.Column('environment', sa.String(50), default="production", index=True),
            sa.Column('tags', postgresql.JSON, default=[]),
            sa.Column('group_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_groups.id'), index=True),
            sa.Column('last_connection_test', sa.DateTime(timezone=True)),
            sa.Column('last_connection_status', sa.String(20)),
            sa.Column('last_connection_error', sa.Text),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    # --- Remediation Tables ---

    if 'runbooks' not in tables:
        op.create_table('runbooks',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False, unique=True),
            sa.Column('description', sa.Text),
            sa.Column('category', sa.String(50), index=True),
            # tags is ARRAY(String)
            sa.Column('tags', postgresql.ARRAY(sa.String), default=[]),
            sa.Column('enabled', sa.Boolean, default=True, index=True),
            sa.Column('auto_execute', sa.Boolean, default=False, index=True),
            sa.Column('approval_required', sa.Boolean, default=True),
            sa.Column('approval_roles', postgresql.ARRAY(sa.String), default=["operator", "engineer", "admin"]),
            sa.Column('approval_timeout_minutes', sa.Integer, default=30),
            sa.Column('max_executions_per_hour', sa.Integer, default=5),
            sa.Column('cooldown_minutes', sa.Integer, default=10),
            sa.Column('default_server_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_credentials.id')),
            sa.Column('target_os_filter', postgresql.ARRAY(sa.String), default=["linux", "windows"]),
            sa.Column('target_from_alert', sa.Boolean, default=True),
            sa.Column('target_alert_label', sa.String(50), default="instance"),
            sa.Column('version', sa.Integer, default=1),
            sa.Column('source', sa.String(20), default="ui"),
            sa.Column('source_path', sa.String(255)),
            sa.Column('checksum', sa.String(64)),
            sa.Column('notifications_json', postgresql.JSON, default={}),
            sa.Column('documentation_url', sa.String(500)),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'runbook_steps' not in tables:
        op.create_table('runbook_steps',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('runbook_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbooks.id', ondelete="CASCADE"), nullable=False),
            sa.Column('step_order', sa.Integer, nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text),
            sa.Column('step_type', sa.String(20), default="command"),
            sa.Column('command_linux', sa.Text),
            sa.Column('command_windows', sa.Text),
            sa.Column('target_os', sa.String(10), default="any"),
            sa.Column('api_credential_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('api_credential_profiles.id', ondelete="SET NULL")),
            sa.Column('api_method', sa.String(10)),
            sa.Column('api_endpoint', sa.Text),
            sa.Column('api_headers_json', postgresql.JSON),
            sa.Column('api_body', sa.Text),
            sa.Column('api_body_type', sa.String(30), default="json"),
            sa.Column('api_query_params_json', postgresql.JSON),
            sa.Column('api_expected_status_codes', postgresql.ARRAY(sa.Integer), default=[200, 201]),
            sa.Column('api_response_extract_json', postgresql.JSON),
            sa.Column('api_follow_redirects', sa.Boolean, default=True),
            sa.Column('api_retry_on_status_codes', postgresql.ARRAY(sa.Integer)),
            sa.Column('timeout_seconds', sa.Integer, default=60),
            sa.Column('requires_elevation', sa.Boolean, default=False),
            sa.Column('working_directory', sa.String(255)),
            sa.Column('environment_json', postgresql.JSON),
            sa.Column('continue_on_fail', sa.Boolean, default=False),
            sa.Column('retry_count', sa.Integer, default=0),
            sa.Column('retry_delay_seconds', sa.Integer, default=5),
            sa.Column('expected_exit_code', sa.Integer, default=0),
            sa.Column('expected_output_pattern', sa.String(500)),
            sa.Column('rollback_command_linux', sa.Text),
            sa.Column('rollback_command_windows', sa.Text),
            
            # NOTE: output_variable and output_extract_pattern are OMITTED here
            # because they are added in migration c3031e42d864
        )
        op.create_unique_constraint("uq_runbook_step_order", "runbook_steps", ["runbook_id", "step_order"])
        op.create_index("idx_runbook_steps_runbook_id", "runbook_steps", ["runbook_id"])

    if 'runbook_triggers' not in tables:
        op.create_table('runbook_triggers',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('runbook_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbooks.id', ondelete="CASCADE"), nullable=False),
            sa.Column('alert_name_pattern', sa.String(255), default="*"),
            sa.Column('severity_pattern', sa.String(50), default="*"),
            sa.Column('instance_pattern', sa.String(255), default="*"),
            sa.Column('job_pattern', sa.String(255), default="*"),
            sa.Column('label_matchers_json', postgresql.JSON),
            sa.Column('annotation_matchers_json', postgresql.JSON),
            sa.Column('min_duration_seconds', sa.Integer, default=0),
            sa.Column('min_occurrences', sa.Integer, default=1),
            sa.Column('priority', sa.Integer, default=100, index=True),
            sa.Column('enabled', sa.Boolean, default=True, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'runbook_executions' not in tables:
        op.create_table('runbook_executions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('runbook_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbooks.id'), nullable=False),
            sa.Column('runbook_version', sa.Integer, nullable=False),
            sa.Column('runbook_snapshot_json', postgresql.JSON),
            sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id')),
            sa.Column('server_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_credentials.id')),
            sa.Column('trigger_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbook_triggers.id')),
            sa.Column('execution_mode', sa.String(20), default="manual"),
            sa.Column('status', sa.String(20), default="pending", index=True),
            sa.Column('dry_run', sa.Boolean, default=False),
            sa.Column('triggered_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('triggered_by_system', sa.Boolean, default=False),
            sa.Column('approval_required', sa.Boolean, default=False),
            sa.Column('approval_token', sa.String(64), unique=True),
            sa.Column('approval_requested_at', sa.DateTime(timezone=True)),
            sa.Column('approval_expires_at', sa.DateTime(timezone=True)),
            sa.Column('approved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('approved_at', sa.DateTime(timezone=True)),
            sa.Column('rejection_reason', sa.Text),
            sa.Column('queued_at', sa.DateTime(timezone=True)),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('completed_at', sa.DateTime(timezone=True)),
            sa.Column('result_summary', sa.Text),
            sa.Column('error_message', sa.Text),
            sa.Column('steps_total', sa.Integer, default=0),
            sa.Column('steps_completed', sa.Integer, default=0),
            sa.Column('steps_failed', sa.Integer, default=0),
            sa.Column('rollback_executed', sa.Boolean, default=False),
            sa.Column('rollback_execution_id', postgresql.UUID(as_uuid=True)),
            sa.Column('variables_json', postgresql.JSON),
        )

    if 'step_executions' not in tables:
        op.create_table('step_executions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('execution_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbook_executions.id', ondelete="CASCADE"), nullable=False),
            sa.Column('step_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runbook_steps.id')),
            sa.Column('step_order', sa.Integer, nullable=False),
            sa.Column('step_name', sa.String(100), nullable=False),
            sa.Column('status', sa.String(20), default="pending"),
            sa.Column('command_executed', sa.Text),
            sa.Column('stdout', sa.Text),
            sa.Column('stderr', sa.Text),
            sa.Column('exit_code', sa.Integer),
            sa.Column('http_status_code', sa.Integer),
            sa.Column('http_response_headers_json', postgresql.JSON),
            sa.Column('http_response_body', sa.Text),
            sa.Column('http_request_url', sa.Text),
            sa.Column('http_request_method', sa.String(10)),
            sa.Column('extracted_values_json', postgresql.JSON),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('completed_at', sa.DateTime(timezone=True)),
            sa.Column('duration_ms', sa.Integer),
            sa.Column('retry_attempt', sa.Integer, default=0),
            sa.Column('error_type', sa.String(50)),
            sa.Column('error_message', sa.Text),
        )

    # --- Other Tables ---

    if 'audit_log' not in tables:
        op.create_table('audit_log',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('action', sa.String(50), nullable=False, index=True),
            sa.Column('resource_type', sa.String(50), index=True),
            sa.Column('resource_id', postgresql.UUID(as_uuid=True)),
            sa.Column('details_json', postgresql.JSON),
            sa.Column('ip_address', sa.String(45)),
            sa.Column('created_at', sa.DateTime(timezone=True)),
        )

    if 'system_config' not in tables:
        op.create_table('system_config',
            sa.Column('key', sa.String(50), primary_key=True),
            sa.Column('value_json', postgresql.JSON, nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
            sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        )

    if 'command_blocklist' not in tables:
        op.create_table('command_blocklist',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('pattern', sa.String(500), nullable=False, unique=True),
            sa.Column('pattern_type', sa.String(20), default="regex"),
            sa.Column('os_type', sa.String(10), default="any"),
            sa.Column('description', sa.Text),
            sa.Column('severity', sa.String(20), default="critical"),
            sa.Column('enabled', sa.Boolean, default=True),
            sa.Column('created_at', sa.DateTime(timezone=True)),
        )

    if 'command_allowlist' not in tables:
        op.create_table('command_allowlist',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('pattern', sa.String(500), nullable=False, unique=True),
            sa.Column('pattern_type', sa.String(20), default="regex"),
            sa.Column('os_type', sa.String(10), default="any"),
            sa.Column('description', sa.Text),
            sa.Column('category', sa.String(50)),
            sa.Column('enabled', sa.Boolean, default=True),
            sa.Column('created_at', sa.DateTime(timezone=True)),
        )

    if 'circuit_breakers' not in tables:
        op.create_table('circuit_breakers',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('scope', sa.String(20), nullable=False),
            sa.Column('scope_id', postgresql.UUID(as_uuid=True)),
            sa.Column('state', sa.String(20), default="closed"),
            sa.Column('failure_count', sa.Integer, default=0),
            sa.Column('success_count', sa.Integer, default=0),
            sa.Column('last_failure_at', sa.DateTime(timezone=True)),
            sa.Column('last_success_at', sa.DateTime(timezone=True)),
            sa.Column('opened_at', sa.DateTime(timezone=True)),
            sa.Column('closes_at', sa.DateTime(timezone=True)),
            sa.Column('failure_threshold', sa.Integer, default=3),
            sa.Column('failure_window_minutes', sa.Integer, default=60),
            sa.Column('open_duration_minutes', sa.Integer, default=30),
            sa.Column('manually_opened', sa.Boolean, default=False),
            sa.Column('manually_opened_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('manually_opened_reason', sa.Text),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )
        op.create_unique_constraint("uq_circuit_breaker_scope", "circuit_breakers", ["scope", "scope_id"])

    if 'blackout_windows' not in tables:
        op.create_table('blackout_windows',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False, unique=True),
            sa.Column('description', sa.Text),
            sa.Column('recurrence', sa.String(20), default="once"),
            sa.Column('start_time', sa.DateTime(timezone=True)),
            sa.Column('end_time', sa.DateTime(timezone=True)),
            sa.Column('daily_start_time', sa.String(5)),
            sa.Column('daily_end_time', sa.String(5)),
            sa.Column('days_of_week', postgresql.ARRAY(sa.Integer)),
            sa.Column('days_of_month', postgresql.ARRAY(sa.Integer)),
            sa.Column('timezone', sa.String(50), default="UTC"),
            sa.Column('applies_to', sa.String(20), default="auto_only"),
            sa.Column('applies_to_runbook_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
            sa.Column('enabled', sa.Boolean, default=True),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'execution_rate_limits' not in tables:
        op.create_table('execution_rate_limits',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('scope', sa.String(20), nullable=False),
            sa.Column('scope_id', postgresql.UUID(as_uuid=True)),
            sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
            sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
            sa.Column('execution_count', sa.Integer, default=0),
            sa.Column('last_execution_at', sa.DateTime(timezone=True)),
        )
        op.create_unique_constraint("uq_rate_limit_window", "execution_rate_limits", ["scope", "scope_id", "window_start"])

    if 'chat_sessions' not in tables:
        op.create_table('chat_sessions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id'), nullable=True),
            sa.Column('title', sa.String(255), nullable=True),
            sa.Column('llm_provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('llm_providers.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if 'chat_messages' not in tables:
        op.create_table('chat_messages',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id'), nullable=False),
            sa.Column('role', sa.String(20), nullable=False),
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('tokens_used', sa.Integer, default=0),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if 'terminal_sessions' not in tables:
        op.create_table('terminal_sessions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('server_credential_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('server_credentials.id'), nullable=False),
            sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.id')),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('ended_at', sa.DateTime(timezone=True)),
            sa.Column('recording_path', sa.String(255)),
        )


def downgrade() -> None:
    # Drop tables in reverse order of creation/dependencies
    # Usually strictly reverse info, but using check here is simple.
    # Note: downgrade is risky if tables already existed. But baseline assumes we own them.
    op.drop_table('terminal_sessions')
    op.drop_table('execution_rate_limits')
    op.drop_table('blackout_windows')
    op.drop_table('circuit_breakers')
    op.drop_table('command_allowlist')
    op.drop_table('command_blocklist')
    op.drop_table('system_config')
    op.drop_table('audit_log')
    op.drop_table('step_executions')
    op.drop_table('runbook_executions')
    op.drop_table('runbook_triggers')
    op.drop_table('runbook_steps')
    op.drop_table('runbooks')
    op.drop_table('server_credentials')
    op.drop_table('api_credential_profiles')
    op.drop_table('credential_profiles')
    op.drop_table('server_groups')
    op.drop_table('alerts')
    op.drop_table('auto_analyze_rules')
    op.drop_table('llm_providers')
    op.drop_table('roles')
    op.drop_table('users')
