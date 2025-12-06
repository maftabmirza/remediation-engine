-- Migration 004: Separate Credential Profiles for API Authentication
-- This migration creates a dedicated table for API credentials, separating them
-- from server inventory (server_credentials table)

-- Create api_credential_profiles table for external API authentication
CREATE TABLE IF NOT EXISTS api_credential_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,

    -- Credential type
    credential_type VARCHAR(50) NOT NULL DEFAULT 'api',  -- 'api', 'oauth', 'custom'

    -- API Configuration
    base_url VARCHAR(500) NOT NULL,
    auth_type VARCHAR(30) NOT NULL DEFAULT 'none',  -- 'none', 'api_key', 'bearer', 'basic', 'oauth', 'custom'
    auth_header VARCHAR(100),  -- e.g., 'Authorization', 'X-API-Key'
    token_encrypted TEXT,  -- Encrypted API token/password
    username VARCHAR(255),  -- For basic auth or OAuth

    -- HTTP Configuration
    verify_ssl BOOLEAN DEFAULT TRUE,
    timeout_seconds INTEGER DEFAULT 30,
    default_headers JSON DEFAULT '{}',

    -- OAuth specific (for future)
    oauth_token_url VARCHAR(500),
    oauth_client_id VARCHAR(255),
    oauth_client_secret_encrypted TEXT,
    oauth_scope TEXT,

    -- Metadata and tags
    tags JSON DEFAULT '[]',
    profile_metadata JSON DEFAULT '{}',

    -- Status
    enabled BOOLEAN DEFAULT TRUE,

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_api_credential_profiles_name ON api_credential_profiles(name);
CREATE INDEX IF NOT EXISTS idx_api_credential_profiles_type ON api_credential_profiles(credential_type);
CREATE INDEX IF NOT EXISTS idx_api_credential_profiles_enabled ON api_credential_profiles(enabled);
CREATE INDEX IF NOT EXISTS idx_api_credential_profiles_auth_type ON api_credential_profiles(auth_type);

-- Add api_credential_profile_id to runbook_steps for API steps
ALTER TABLE runbook_steps
ADD COLUMN IF NOT EXISTS api_credential_profile_id UUID REFERENCES api_credential_profiles(id) ON DELETE SET NULL;

-- Create index for credential profile reference
CREATE INDEX IF NOT EXISTS idx_runbook_steps_api_credential_profile ON runbook_steps(api_credential_profile_id);

-- Add comments for documentation
COMMENT ON TABLE api_credential_profiles IS 'External API credentials and authentication profiles (e.g., Ansible AWX, Jenkins, Kubernetes API)';
COMMENT ON COLUMN api_credential_profiles.credential_type IS 'Type of credential: api (REST API), oauth (OAuth 2.0), custom';
COMMENT ON COLUMN api_credential_profiles.base_url IS 'Base URL for the API endpoint (e.g., https://awx.example.com/api/v2)';
COMMENT ON COLUMN api_credential_profiles.auth_type IS 'Authentication method: none, api_key, bearer, basic, oauth, custom';
COMMENT ON COLUMN api_credential_profiles.token_encrypted IS 'Encrypted API token, password, or secret';
COMMENT ON COLUMN api_credential_profiles.default_headers IS 'Default HTTP headers to include with every request';
COMMENT ON COLUMN api_credential_profiles.profile_metadata IS 'Additional metadata and custom configuration';

COMMENT ON COLUMN runbook_steps.api_credential_profile_id IS 'Reference to API credential profile for API steps (NULL for command steps)';

-- Migration complete
