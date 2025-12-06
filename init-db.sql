-- AIOps Platform Database Schema
-- This file runs automatically on first PostgreSQL startup

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'operator' CHECK (role IN ('owner', 'admin', 'maintainer', 'operator', 'viewer', 'auditor', 'user')),
    default_llm_provider_id UUID,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- LLM Providers table
CREATE TABLE IF NOT EXISTS llm_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    provider_type VARCHAR(50) NOT NULL CHECK (provider_type IN ('anthropic', 'openai', 'google', 'ollama', 'azure')),
    model_id VARCHAR(100) NOT NULL,
    api_key_encrypted TEXT,
    api_base_url VARCHAR(255),
    is_default BOOLEAN DEFAULT false,
    is_enabled BOOLEAN DEFAULT true,
    config_json JSONB DEFAULT '{"temperature": 0.3, "max_tokens": 2000}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Auto-analyze rules table
CREATE TABLE IF NOT EXISTS auto_analyze_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 100,
    alert_name_pattern VARCHAR(255) DEFAULT '*',
    severity_pattern VARCHAR(50) DEFAULT '*',
    instance_pattern VARCHAR(255) DEFAULT '*',
    job_pattern VARCHAR(255) DEFAULT '*',
    action VARCHAR(20) DEFAULT 'manual' CHECK (action IN ('auto_analyze', 'ignore', 'manual')),
    enabled BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fingerprint VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    alert_name VARCHAR(255) NOT NULL,
    severity VARCHAR(50),
    instance VARCHAR(255),
    job VARCHAR(100),
    status VARCHAR(20) DEFAULT 'firing' CHECK (status IN ('firing', 'resolved')),
    labels_json JSONB,
    annotations_json JSONB,
    raw_alert_json JSONB,
    matched_rule_id UUID REFERENCES auto_analyze_rules(id),
    action_taken VARCHAR(20) CHECK (action_taken IN ('auto_analyze', 'ignore', 'manual', 'pending')),
    analyzed BOOLEAN DEFAULT false,
    analyzed_at TIMESTAMP WITH TIME ZONE,
    analyzed_by UUID REFERENCES users(id),
    llm_provider_id UUID REFERENCES llm_providers(id),
    ai_analysis TEXT,
    recommendations_json JSONB,
    analysis_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Index for faster queries
    CONSTRAINT unique_alert_fingerprint_timestamp UNIQUE (fingerprint, timestamp)
);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    details_json JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Chat Sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) NOT NULL,
    alert_id UUID REFERENCES alerts(id),
    title VARCHAR(255),
    llm_provider_id UUID REFERENCES llm_providers(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Chat Messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Server grouping table
CREATE TABLE IF NOT EXISTS server_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES server_groups(id) ON DELETE SET NULL,
    path VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Server Credentials table
CREATE TABLE IF NOT EXISTS server_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    port INTEGER DEFAULT 22,
    username VARCHAR(100) NOT NULL,
    auth_type VARCHAR(20) DEFAULT 'key' CHECK (auth_type IN ('key', 'password')),
    ssh_key_encrypted TEXT,
    password_encrypted TEXT,
    group_id UUID REFERENCES server_groups(id),
    environment VARCHAR(50) DEFAULT 'production',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Terminal Sessions table
CREATE TABLE IF NOT EXISTS terminal_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) NOT NULL,
    server_credential_id UUID REFERENCES server_credentials(id) NOT NULL,
    alert_id UUID REFERENCES alerts(id),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    recording_path VARCHAR(255)
);

-- System Config table
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(50) PRIMARY KEY,
    value_json JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID REFERENCES users(id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_alert_name ON alerts(alert_name);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_analyzed ON alerts(analyzed);
CREATE INDEX IF NOT EXISTS idx_alerts_fingerprint ON alerts(fingerprint);
CREATE INDEX IF NOT EXISTS idx_rules_priority ON auto_analyze_rules(priority);
CREATE INDEX IF NOT EXISTS idx_rules_enabled ON auto_analyze_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_alert ON chat_sessions(alert_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_server_creds_env ON server_credentials(environment);
CREATE INDEX IF NOT EXISTS idx_server_creds_group ON server_credentials(group_id);
CREATE INDEX IF NOT EXISTS idx_server_groups_parent ON server_groups(parent_id);
CREATE INDEX IF NOT EXISTS idx_terminal_sessions_user ON terminal_sessions(user_id);

-- Insert default LLM provider (Claude)
INSERT INTO llm_providers (name, provider_type, model_id, is_default, is_enabled, config_json)
VALUES (
    'Claude Sonnet 4',
    'anthropic',
    'claude-sonnet-4-20250514',
    true,
    true,
    '{"temperature": 0.3, "max_tokens": 2000}'
) ON CONFLICT DO NOTHING;

-- Insert default rule (manual for all)
INSERT INTO auto_analyze_rules (name, description, priority, alert_name_pattern, severity_pattern, instance_pattern, job_pattern, action, enabled)
VALUES (
    'Default - Manual Analysis',
    'Default fallback rule: all alerts require manual analysis',
    1000,
    '*',
    '*',
    '*',
    '*',
    'manual',
    true
) ON CONFLICT DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_llm_providers_updated_at ON llm_providers;
CREATE TRIGGER update_llm_providers_updated_at
    BEFORE UPDATE ON llm_providers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_rules_updated_at ON auto_analyze_rules;
CREATE TRIGGER update_rules_updated_at
    BEFORE UPDATE ON auto_analyze_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_server_creds_updated_at ON server_credentials;
CREATE TRIGGER update_server_creds_updated_at
    BEFORE UPDATE ON server_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
