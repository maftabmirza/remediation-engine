-- =============================================================================
-- Auto-Remediation Database Migration
-- Version: 1.0.0
-- Date: 2025-11-30
-- Description: Creates tables for enterprise auto-remediation feature
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. UPDATE EXISTING TABLES
-- -----------------------------------------------------------------------------

-- Add new columns to server_credentials for Windows/WinRM support
ALTER TABLE server_credentials 
ADD COLUMN IF NOT EXISTS os_type VARCHAR(20) DEFAULT 'linux',
ADD COLUMN IF NOT EXISTS protocol VARCHAR(20) DEFAULT 'ssh',
ADD COLUMN IF NOT EXISTS winrm_transport VARCHAR(20),
ADD COLUMN IF NOT EXISTS winrm_use_ssl BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS winrm_cert_validation BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS domain VARCHAR(100),
ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]',
ADD COLUMN IF NOT EXISTS last_connection_test TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_connection_status VARCHAR(20),
ADD COLUMN IF NOT EXISTS last_connection_error TEXT;

-- Add index for os_type
CREATE INDEX IF NOT EXISTS idx_server_credentials_os_type ON server_credentials(os_type);

-- -----------------------------------------------------------------------------
-- 2. RUNBOOK TABLES
-- -----------------------------------------------------------------------------

-- Runbooks - main runbook definitions
CREATE TABLE IF NOT EXISTS runbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Basic Info
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50),
    tags VARCHAR[] DEFAULT '{}',
    
    -- Execution Settings
    enabled BOOLEAN DEFAULT TRUE,
    auto_execute BOOLEAN DEFAULT FALSE,
    approval_required BOOLEAN DEFAULT TRUE,
    approval_roles VARCHAR[] DEFAULT ARRAY['operator', 'engineer', 'admin'],
    approval_timeout_minutes INTEGER DEFAULT 30,
    
    -- Safety Settings
    max_executions_per_hour INTEGER DEFAULT 5,
    cooldown_minutes INTEGER DEFAULT 10,
    
    -- Target Configuration
    default_server_id UUID REFERENCES server_credentials(id),
    target_os_filter VARCHAR[] DEFAULT ARRAY['linux', 'windows'],
    target_from_alert BOOLEAN DEFAULT TRUE,
    target_alert_label VARCHAR(50) DEFAULT 'instance',
    
    -- Versioning (IaC support)
    version INTEGER DEFAULT 1,
    source VARCHAR(20) DEFAULT 'ui',
    source_path VARCHAR(255),
    checksum VARCHAR(64),
    
    -- Notifications
    notifications_json JSONB DEFAULT '{"on_start": [], "on_success": ["slack"], "on_failure": ["slack", "email"]}',
    
    -- Documentation
    documentation_url VARCHAR(500),
    
    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runbooks_enabled_auto ON runbooks(enabled, auto_execute);
CREATE INDEX IF NOT EXISTS idx_runbooks_category ON runbooks(category);

-- Runbook Steps
CREATE TABLE IF NOT EXISTS runbook_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runbook_id UUID NOT NULL REFERENCES runbooks(id) ON DELETE CASCADE,
    
    -- Step Definition
    step_order INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Commands
    command_linux TEXT,
    command_windows TEXT,
    target_os VARCHAR(10) DEFAULT 'any',
    
    -- Execution Options
    timeout_seconds INTEGER DEFAULT 60,
    requires_elevation BOOLEAN DEFAULT FALSE,
    working_directory VARCHAR(255),
    environment_json JSONB,
    
    -- Error Handling
    continue_on_fail BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    retry_delay_seconds INTEGER DEFAULT 5,
    
    -- Validation
    expected_exit_code INTEGER DEFAULT 0,
    expected_output_pattern VARCHAR(500),
    
    -- Rollback
    rollback_command_linux TEXT,
    rollback_command_windows TEXT,
    
    CONSTRAINT uq_runbook_step_order UNIQUE (runbook_id, step_order)
);

CREATE INDEX IF NOT EXISTS idx_runbook_steps_runbook_id ON runbook_steps(runbook_id);

-- Runbook Triggers
CREATE TABLE IF NOT EXISTS runbook_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runbook_id UUID NOT NULL REFERENCES runbooks(id) ON DELETE CASCADE,
    
    -- Matching Patterns
    alert_name_pattern VARCHAR(255) DEFAULT '*',
    severity_pattern VARCHAR(50) DEFAULT '*',
    instance_pattern VARCHAR(255) DEFAULT '*',
    job_pattern VARCHAR(255) DEFAULT '*',
    
    -- Advanced Matching
    label_matchers_json JSONB,
    annotation_matchers_json JSONB,
    
    -- Trigger Conditions
    min_duration_seconds INTEGER DEFAULT 0,
    min_occurrences INTEGER DEFAULT 1,
    
    -- Priority & Status
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_triggers_enabled_priority ON runbook_triggers(enabled, priority);
CREATE INDEX IF NOT EXISTS idx_triggers_alert_name ON runbook_triggers(alert_name_pattern);

-- -----------------------------------------------------------------------------
-- 3. EXECUTION TRACKING TABLES
-- -----------------------------------------------------------------------------

-- Runbook Executions
CREATE TABLE IF NOT EXISTS runbook_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What was executed
    runbook_id UUID NOT NULL REFERENCES runbooks(id),
    runbook_version INTEGER NOT NULL,
    runbook_snapshot_json JSONB,
    
    -- Context
    alert_id UUID REFERENCES alerts(id),
    server_id UUID REFERENCES server_credentials(id),
    trigger_id UUID REFERENCES runbook_triggers(id),
    
    -- Execution Mode & Status
    execution_mode VARCHAR(20) DEFAULT 'manual',
    status VARCHAR(20) DEFAULT 'pending',
    dry_run BOOLEAN DEFAULT FALSE,
    
    -- Approval Workflow
    triggered_by UUID REFERENCES users(id),
    triggered_by_system BOOLEAN DEFAULT FALSE,
    
    approval_required BOOLEAN DEFAULT FALSE,
    approval_token VARCHAR(64) UNIQUE,
    approval_requested_at TIMESTAMPTZ,
    approval_expires_at TIMESTAMPTZ,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    
    -- Timing
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Results
    result_summary TEXT,
    error_message TEXT,
    steps_total INTEGER DEFAULT 0,
    steps_completed INTEGER DEFAULT 0,
    steps_failed INTEGER DEFAULT 0,
    
    -- Rollback
    rollback_executed BOOLEAN DEFAULT FALSE,
    rollback_execution_id UUID,
    
    -- Variables
    variables_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_executions_status ON runbook_executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_runbook_status ON runbook_executions(runbook_id, status);
CREATE INDEX IF NOT EXISTS idx_executions_alert ON runbook_executions(alert_id);
CREATE INDEX IF NOT EXISTS idx_executions_queued_at ON runbook_executions(queued_at);
CREATE INDEX IF NOT EXISTS idx_executions_approval_token ON runbook_executions(approval_token);

-- Step Executions
CREATE TABLE IF NOT EXISTS step_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES runbook_executions(id) ON DELETE CASCADE,
    step_id UUID REFERENCES runbook_steps(id),
    
    -- Step Info (snapshot)
    step_order INTEGER NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    
    -- Execution Details
    status VARCHAR(20) DEFAULT 'pending',
    command_executed TEXT,
    
    -- Output
    stdout TEXT,
    stderr TEXT,
    exit_code INTEGER,
    
    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    
    -- Retry Tracking
    retry_attempt INTEGER DEFAULT 0,
    
    -- Error Info
    error_type VARCHAR(50),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_step_executions_execution_id ON step_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_step_executions_status ON step_executions(status);

-- -----------------------------------------------------------------------------
-- 4. SAFETY MECHANISM TABLES
-- -----------------------------------------------------------------------------

-- Circuit Breakers
CREATE TABLE IF NOT EXISTS circuit_breakers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Scope
    scope VARCHAR(20) NOT NULL,
    scope_id UUID,
    
    -- State
    state VARCHAR(20) DEFAULT 'closed',
    
    -- Counters
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    
    -- Timing
    last_failure_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    
    -- Configuration
    failure_threshold INTEGER DEFAULT 3,
    failure_window_minutes INTEGER DEFAULT 60,
    open_duration_minutes INTEGER DEFAULT 30,
    
    -- Manual Override
    manually_opened BOOLEAN DEFAULT FALSE,
    manually_opened_by UUID REFERENCES users(id),
    manually_opened_reason TEXT,
    
    -- Audit
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_circuit_breaker_scope UNIQUE (scope, scope_id)
);

CREATE INDEX IF NOT EXISTS idx_circuit_breaker_state ON circuit_breakers(state);

-- Blackout Windows
CREATE TABLE IF NOT EXISTS blackout_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Basic Info
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    
    -- Schedule
    recurrence VARCHAR(20) DEFAULT 'once',
    
    -- For "once"
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    
    -- For recurring
    daily_start_time VARCHAR(5),
    daily_end_time VARCHAR(5),
    days_of_week INTEGER[],
    days_of_month INTEGER[],
    
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Scope
    applies_to VARCHAR(20) DEFAULT 'auto_only',
    applies_to_runbook_ids UUID[],
    
    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blackout_enabled ON blackout_windows(enabled);

-- Execution Rate Limits
CREATE TABLE IF NOT EXISTS execution_rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Scope
    scope VARCHAR(20) NOT NULL,
    scope_id UUID,
    
    -- Window
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    
    -- Counter
    execution_count INTEGER DEFAULT 0,
    last_execution_at TIMESTAMPTZ,
    
    CONSTRAINT uq_rate_limit_window UNIQUE (scope, scope_id, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_scope_window ON execution_rate_limits(scope, scope_id, window_start);

-- -----------------------------------------------------------------------------
-- 5. COMMAND SAFETY TABLES
-- -----------------------------------------------------------------------------

-- Command Blocklist
CREATE TABLE IF NOT EXISTS command_blocklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    pattern VARCHAR(500) NOT NULL UNIQUE,
    pattern_type VARCHAR(20) DEFAULT 'regex',
    os_type VARCHAR(10) DEFAULT 'any',
    
    description TEXT,
    severity VARCHAR(20) DEFAULT 'critical',
    
    enabled BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blocklist_enabled_os ON command_blocklist(enabled, os_type);

-- Command Allowlist
CREATE TABLE IF NOT EXISTS command_allowlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    pattern VARCHAR(500) NOT NULL UNIQUE,
    pattern_type VARCHAR(20) DEFAULT 'regex',
    os_type VARCHAR(10) DEFAULT 'any',
    
    description TEXT,
    category VARCHAR(50),
    
    enabled BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_allowlist_enabled_os ON command_allowlist(enabled, os_type);

-- -----------------------------------------------------------------------------
-- 6. INSERT DEFAULT BLOCKLIST ENTRIES
-- -----------------------------------------------------------------------------

INSERT INTO command_blocklist (pattern, pattern_type, os_type, description, severity) VALUES
-- Linux dangerous commands
('rm\s+-rf\s+/', 'regex', 'linux', 'Recursive force delete from root', 'critical'),
('rm\s+-fr\s+/', 'regex', 'linux', 'Recursive force delete from root (alt)', 'critical'),
('dd\s+if=/dev/zero', 'regex', 'linux', 'Write zeros to device', 'critical'),
('dd\s+if=/dev/random', 'regex', 'linux', 'Write random data to device', 'critical'),
('mkfs\.', 'regex', 'linux', 'Format filesystem', 'critical'),
(':\(\)\{\s*:\|:&\s*\};:', 'regex', 'linux', 'Fork bomb', 'critical'),
('chmod\s+-R\s+777\s+/', 'regex', 'linux', 'Chmod 777 on root', 'critical'),
('>\s*/dev/sda', 'regex', 'linux', 'Write to disk device', 'critical'),
('>\s*/dev/hda', 'regex', 'linux', 'Write to disk device (alt)', 'critical'),
('\|\s*bash', 'regex', 'linux', 'Pipe to bash (arbitrary code)', 'warning'),
('\|\s*sh', 'regex', 'linux', 'Pipe to shell (arbitrary code)', 'warning'),
('wget.*\|\s*bash', 'regex', 'linux', 'Download and execute', 'critical'),
('curl.*\|\s*bash', 'regex', 'linux', 'Download and execute', 'critical'),

-- Windows dangerous commands
('Format-Volume', 'contains', 'windows', 'Format disk volume', 'critical'),
('Remove-Item\s+-Recurse\s+-Force\s+C:\\', 'regex', 'windows', 'Delete C drive', 'critical'),
('Remove-Item\s+-Recurse\s+-Force\s+\$env:SystemRoot', 'regex', 'windows', 'Delete Windows directory', 'critical'),
('Stop-Computer\s+-Force', 'regex', 'windows', 'Force shutdown', 'critical'),
('Restart-Computer\s+-Force', 'regex', 'windows', 'Force restart', 'warning'),
('Clear-Disk', 'contains', 'windows', 'Clear entire disk', 'critical'),
('Initialize-Disk', 'contains', 'windows', 'Initialize disk (data loss)', 'critical'),
('Invoke-Expression', 'contains', 'windows', 'Arbitrary code execution', 'warning'),
('iex\s*\(', 'regex', 'windows', 'Arbitrary code execution (iex)', 'warning'),
('Set-ExecutionPolicy\s+Unrestricted', 'regex', 'windows', 'Disable execution policy', 'warning')

ON CONFLICT (pattern) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 7. CREATE GLOBAL CIRCUIT BREAKER
-- -----------------------------------------------------------------------------

INSERT INTO circuit_breakers (scope, scope_id, state, failure_threshold, failure_window_minutes, open_duration_minutes)
VALUES ('global', NULL, 'closed', 5, 60, 30)
ON CONFLICT (scope, scope_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 8. UPDATE TRIGGER FOR updated_at
-- -----------------------------------------------------------------------------

-- Create function if not exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to new tables
DROP TRIGGER IF EXISTS update_runbooks_updated_at ON runbooks;
CREATE TRIGGER update_runbooks_updated_at
    BEFORE UPDATE ON runbooks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_runbook_triggers_updated_at ON runbook_triggers;
CREATE TRIGGER update_runbook_triggers_updated_at
    BEFORE UPDATE ON runbook_triggers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_blackout_windows_updated_at ON blackout_windows;
CREATE TRIGGER update_blackout_windows_updated_at
    BEFORE UPDATE ON blackout_windows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_circuit_breakers_updated_at ON circuit_breakers;
CREATE TRIGGER update_circuit_breakers_updated_at
    BEFORE UPDATE ON circuit_breakers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- Done!
-- -----------------------------------------------------------------------------
