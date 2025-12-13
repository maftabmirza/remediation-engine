-- =============================================================================
-- Scheduler Database Migration
-- Version: 1.0.0
-- Date: 2025-12-08
-- Description: Creates tables for scheduler feature
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. SCHEDULED JOBS TABLE
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runbook_id UUID NOT NULL REFERENCES runbooks(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Schedule Configuration
    schedule_type VARCHAR(50) NOT NULL CHECK (schedule_type IN ('cron', 'interval', 'date')),
    cron_expression VARCHAR(100),
    interval_seconds INTEGER,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Execution Configuration
    target_server_id UUID REFERENCES server_credentials(id),
    execution_params JSONB,
    max_instances INTEGER DEFAULT 1,
    misfire_grace_time INTEGER DEFAULT 300,
    
    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    last_run_status VARCHAR(50),
    next_run_at TIMESTAMPTZ,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    
    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_runbook ON scheduled_jobs(runbook_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_enabled ON scheduled_jobs(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_next_run ON scheduled_jobs(next_run_at) WHERE enabled = TRUE;

-- -----------------------------------------------------------------------------
-- 2. SCHEDULE EXECUTION HISTORY TABLE
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schedule_execution_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheduled_job_id UUID NOT NULL REFERENCES scheduled_jobs(id) ON DELETE CASCADE,
    runbook_execution_id UUID REFERENCES runbook_executions(id),
    
    scheduled_at TIMESTAMPTZ NOT NULL,
    executed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    duration_ms INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_schedule_history_job ON schedule_execution_history(scheduled_job_id);
CREATE INDEX IF NOT EXISTS idx_schedule_history_status ON schedule_execution_history(status);
CREATE INDEX IF NOT EXISTS idx_schedule_history_created ON schedule_execution_history(created_at);

-- -----------------------------------------------------------------------------
-- 3. UPDATE TRIGGER FOR updated_at
-- -----------------------------------------------------------------------------

DROP TRIGGER IF EXISTS update_scheduled_jobs_updated_at ON scheduled_jobs;
CREATE TRIGGER update_scheduled_jobs_updated_at
    BEFORE UPDATE ON scheduled_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- Done!
-- -----------------------------------------------------------------------------
