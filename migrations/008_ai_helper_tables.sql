-- =============================================================================
-- AI Helper Database Migration
-- Version: 1.0.0
-- Date: 2025-01-04
-- Description: Creates tables for AI Helper with strict security controls
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. KNOWLEDGE SOURCES TABLE (Configurable Git Sync)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Multi-tenancy support
    tenant_id UUID,

    -- Source metadata
    name VARCHAR(255) NOT NULL,
    description TEXT,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('git_docs', 'git_code', 'local_files', 'external_api')),

    -- Configuration (flexible per type)
    config JSONB NOT NULL DEFAULT '{}',
    -- Example for git_docs: {"repo": "github.com/org/docs", "path": "/docs", "branch": "main"}
    -- Example for git_code: {"repo": "github.com/org/app", "path": "/app", "index_mode": "metadata_only"}

    -- Sync settings
    enabled BOOLEAN DEFAULT TRUE,
    sync_schedule VARCHAR(100),  -- Cron expression, e.g., "0 */6 * * *"
    auto_sync BOOLEAN DEFAULT TRUE,

    -- Sync status
    last_sync_at TIMESTAMPTZ,
    last_commit_sha VARCHAR(64),
    last_sync_status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'syncing', 'success', 'error'
    last_sync_error TEXT,
    sync_count INTEGER DEFAULT 0,

    -- Document counts
    total_documents INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error', 'archived')),

    -- Audit
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_source_name_per_tenant UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_sources_type ON knowledge_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_enabled ON knowledge_sources(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_status ON knowledge_sources(status);
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_tenant ON knowledge_sources(tenant_id);

-- -----------------------------------------------------------------------------
-- 2. KNOWLEDGE SYNC HISTORY TABLE
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS knowledge_sync_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,

    -- Sync details
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed', 'partial')),

    -- Git details (if applicable)
    previous_commit_sha VARCHAR(64),
    new_commit_sha VARCHAR(64),

    -- Results
    documents_added INTEGER DEFAULT 0,
    documents_updated INTEGER DEFAULT 0,
    documents_deleted INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,

    -- Error tracking
    error_message TEXT,
    error_details JSONB,

    -- Performance
    duration_ms INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_history_source ON knowledge_sync_history(source_id);
CREATE INDEX IF NOT EXISTS idx_sync_history_status ON knowledge_sync_history(status);
CREATE INDEX IF NOT EXISTS idx_sync_history_created ON knowledge_sync_history(created_at DESC);

-- -----------------------------------------------------------------------------
-- 3. AI HELPER AUDIT LOGS TABLE (CRITICAL - Comprehensive Logging)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ai_helper_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- User & Session Context
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL,
    session_id UUID,
    correlation_id UUID,  -- Link related actions

    -- Request Context
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_query TEXT NOT NULL,
    page_context JSONB,  -- {url, page_type, form_id, current_data}

    -- LLM Interaction (CRITICAL - Full logging)
    llm_provider VARCHAR(50),  -- 'anthropic', 'openai', 'ollama', etc.
    llm_model VARCHAR(100),
    llm_request JSONB,  -- Full request payload sent to LLM
    llm_response JSONB,  -- Full response received from LLM
    llm_tokens_input INTEGER,
    llm_tokens_output INTEGER,
    llm_tokens_total INTEGER,
    llm_latency_ms INTEGER,
    llm_cost_usd DECIMAL(10, 6),  -- Track costs

    -- Knowledge Base Usage
    knowledge_sources_used UUID[],  -- Array of source IDs used
    knowledge_chunks_used INTEGER,
    rag_search_time_ms INTEGER,

    -- Code Understanding Usage
    code_files_referenced TEXT[],
    code_functions_referenced TEXT[],

    -- AI Action (What AI suggested)
    ai_suggested_action VARCHAR(100),  -- From whitelist
    ai_action_details JSONB,  -- Detailed action data
    ai_confidence_score DECIMAL(3, 2),  -- 0.00 to 1.00
    ai_reasoning TEXT,  -- Why AI suggested this

    -- User Response
    user_action VARCHAR(50) CHECK (user_action IN ('approved', 'rejected', 'modified', 'ignored', 'pending')),
    user_action_timestamp TIMESTAMPTZ,
    user_modifications JSONB,  -- If user changed AI suggestion
    user_feedback VARCHAR(20) CHECK (user_feedback IN ('helpful', 'not_helpful', 'partially_helpful')),
    user_feedback_comment TEXT,

    -- Execution (if applicable)
    executed BOOLEAN DEFAULT FALSE,
    execution_timestamp TIMESTAMPTZ,
    execution_result VARCHAR(50) CHECK (execution_result IN ('success', 'failed', 'blocked', 'timeout')),
    execution_details JSONB,
    affected_resources JSONB,  -- What was created/modified

    -- Security
    action_blocked BOOLEAN DEFAULT FALSE,
    block_reason VARCHAR(255),
    permission_checked BOOLEAN DEFAULT TRUE,
    permissions_required TEXT[],
    permissions_granted TEXT[],

    -- Request metadata
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(255),

    -- Performance tracking
    total_duration_ms INTEGER,
    context_assembly_ms INTEGER,

    -- Flags
    is_error BOOLEAN DEFAULT FALSE,
    error_type VARCHAR(100),
    error_message TEXT,
    error_stack_trace TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ai_audit_user_time ON ai_helper_audit_logs(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ai_audit_session ON ai_helper_audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_audit_correlation ON ai_helper_audit_logs(correlation_id);
CREATE INDEX IF NOT EXISTS idx_ai_audit_executed ON ai_helper_audit_logs(executed, execution_result);
CREATE INDEX IF NOT EXISTS idx_ai_audit_timestamp ON ai_helper_audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ai_audit_action ON ai_helper_audit_logs(ai_suggested_action);
CREATE INDEX IF NOT EXISTS idx_ai_audit_user_action ON ai_helper_audit_logs(user_action);
CREATE INDEX IF NOT EXISTS idx_ai_audit_blocked ON ai_helper_audit_logs(action_blocked) WHERE action_blocked = TRUE;
CREATE INDEX IF NOT EXISTS idx_ai_audit_error ON ai_helper_audit_logs(is_error) WHERE is_error = TRUE;

-- JSONB indexes for filtering
CREATE INDEX IF NOT EXISTS idx_ai_audit_page_context ON ai_helper_audit_logs USING gin(page_context);
CREATE INDEX IF NOT EXISTS idx_ai_audit_llm_request ON ai_helper_audit_logs USING gin(llm_request);

-- -----------------------------------------------------------------------------
-- 4. AI HELPER SESSIONS TABLE (Track ongoing conversations)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ai_helper_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Session metadata
    session_type VARCHAR(50) DEFAULT 'general' CHECK (session_type IN ('general', 'form_assistance', 'troubleshooting', 'learning')),
    context JSONB,  -- Session context that persists

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned', 'error')),

    -- Metrics
    total_queries INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 6) DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_sessions_user ON ai_helper_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_status ON ai_helper_sessions(status);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_activity ON ai_helper_sessions(last_activity_at DESC);

-- -----------------------------------------------------------------------------
-- 5. AI HELPER CONFIGURATION TABLE (System-wide settings)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ai_helper_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    config_key VARCHAR(255) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    description TEXT,
    config_type VARCHAR(50) DEFAULT 'system' CHECK (config_type IN ('system', 'user', 'tenant')),

    -- Validation
    schema JSONB,  -- JSON schema for validation
    is_encrypted BOOLEAN DEFAULT FALSE,

    -- Status
    enabled BOOLEAN DEFAULT TRUE,

    -- Audit
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_config_key ON ai_helper_config(config_key);
CREATE INDEX IF NOT EXISTS idx_ai_config_type ON ai_helper_config(config_type);

-- Insert default configurations
INSERT INTO ai_helper_config (config_key, config_value, description, config_type) VALUES
    ('allowed_actions',
     '["suggest_form_values", "search_knowledge", "explain_concept", "show_example", "validate_input", "generate_preview"]'::jsonb,
     'Whitelisted AI actions that are permitted',
     'system'),
    ('blocked_actions',
     '["execute_runbook", "ssh_connect", "submit_form", "api_call_modify", "auto_execute_any"]'::jsonb,
     'Blacklisted AI actions that are forbidden',
     'system'),
    ('strict_mode',
     'true'::jsonb,
     'Enforce strict security controls (no auto-execution)',
     'system'),
    ('rate_limits',
     '{"per_user_per_minute": 10, "per_user_per_day": 500}'::jsonb,
     'Rate limiting configuration',
     'system'),
    ('logging_config',
     '{"log_llm_requests": true, "log_llm_responses": true, "retention_days": 365}'::jsonb,
     'Audit logging configuration',
     'system')
ON CONFLICT (config_key) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 6. UPDATE DESIGN_DOCUMENTS AND DESIGN_CHUNKS (Link to knowledge sources)
-- -----------------------------------------------------------------------------

-- Add source_id column to design_documents if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='design_documents' AND column_name='source_id') THEN
        ALTER TABLE design_documents ADD COLUMN source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_design_documents_source ON design_documents(source_id);
    END IF;
END $$;

-- Add source_id column to design_chunks if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='design_chunks' AND column_name='knowledge_source_id') THEN
        ALTER TABLE design_chunks ADD COLUMN knowledge_source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_design_chunks_knowledge_source ON design_chunks(knowledge_source_id);
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 7. UPDATE TRIGGERS
-- -----------------------------------------------------------------------------

-- Update trigger for knowledge_sources
DROP TRIGGER IF EXISTS update_knowledge_sources_updated_at ON knowledge_sources;
CREATE TRIGGER update_knowledge_sources_updated_at
    BEFORE UPDATE ON knowledge_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Update trigger for ai_helper_config
DROP TRIGGER IF EXISTS update_ai_helper_config_updated_at ON ai_helper_config;
CREATE TRIGGER update_ai_helper_config_updated_at
    BEFORE UPDATE ON ai_helper_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- Done!
-- -----------------------------------------------------------------------------
