-- =============================================================================
-- RBAC & Server Credential Enhancements
-- Adds credential profile support, missing columns for users and server metadata
-- =============================================================================

-- Users table additions (email + full_name)
ALTER TABLE IF EXISTS users
    ADD COLUMN IF NOT EXISTS email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS full_name VARCHAR(100);

-- Ensure grouping table exists before referencing it
CREATE TABLE IF NOT EXISTS server_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES server_groups(id) ON DELETE SET NULL,
    path VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_server_groups_parent ON server_groups(parent_id);

-- Credential profiles (reusable / external secrets)
CREATE TABLE IF NOT EXISTS credential_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) UNIQUE NOT NULL,
    description TEXT,
    username VARCHAR(100),
    credential_type VARCHAR(30) DEFAULT 'key',
    backend VARCHAR(30) DEFAULT 'inline',
    secret_encrypted TEXT,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    last_rotated TIMESTAMPTZ,
    group_id UUID REFERENCES server_groups(id),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credential_profiles_backend ON credential_profiles(backend);
CREATE INDEX IF NOT EXISTS idx_credential_profiles_group ON credential_profiles(group_id);

-- Extend server_credentials for richer auth metadata and profile linkage
CREATE TABLE IF NOT EXISTS server_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    port INTEGER DEFAULT 22,
    username VARCHAR(100) NOT NULL,
    auth_type VARCHAR(20) DEFAULT 'key' CHECK (auth_type IN ('key', 'password')),
    ssh_key_encrypted TEXT,
    password_encrypted TEXT,
    environment VARCHAR(50) DEFAULT 'production',
    group_id UUID REFERENCES server_groups(id),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE IF EXISTS server_credentials
    ADD COLUMN IF NOT EXISTS credential_source VARCHAR(30) DEFAULT 'inline',
    ADD COLUMN IF NOT EXISTS credential_profile_id UUID REFERENCES credential_profiles(id),
    ADD COLUMN IF NOT EXISTS credential_metadata JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS os_type VARCHAR(20) DEFAULT 'linux',
    ADD COLUMN IF NOT EXISTS protocol VARCHAR(20) DEFAULT 'ssh',
    ADD COLUMN IF NOT EXISTS winrm_transport VARCHAR(20),
    ADD COLUMN IF NOT EXISTS winrm_use_ssl BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS winrm_cert_validation BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS domain VARCHAR(100),
    ADD COLUMN IF NOT EXISTS environment VARCHAR(50) DEFAULT 'production',
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS last_connection_test TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_connection_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS last_connection_error TEXT;

ALTER TABLE IF EXISTS credential_profiles
    ADD COLUMN IF NOT EXISTS username VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_server_credentials_profile ON server_credentials(credential_profile_id);
CREATE INDEX IF NOT EXISTS idx_server_credentials_os_type ON server_credentials(os_type);
CREATE INDEX IF NOT EXISTS idx_server_credentials_env ON server_credentials(environment);
CREATE INDEX IF NOT EXISTS idx_server_credentials_group ON server_credentials(group_id);
