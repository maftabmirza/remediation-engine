
-- 1. Create server_groups if it doesn't exist
CREATE TABLE IF NOT EXISTS server_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES server_groups(id) ON DELETE SET NULL,
    path VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add missing columns to server_groups (for existing deployments)
ALTER TABLE server_groups ADD COLUMN IF NOT EXISTS color VARCHAR(7);
ALTER TABLE server_groups ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]';

-- 3. Create indexes for server_groups
CREATE INDEX IF NOT EXISTS idx_server_groups_parent ON server_groups(parent_id);

-- 4. Create credential_profiles if it doesn't exist
CREATE TABLE IF NOT EXISTS credential_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    credential_type VARCHAR(30) DEFAULT 'key',
    backend VARCHAR(30) DEFAULT 'inline',
    secret_encrypted TEXT,
    metadata_json JSONB DEFAULT '{}',
    last_rotated TIMESTAMPTZ,
    group_id UUID REFERENCES server_groups(id),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Add missing columns to credential_profiles
ALTER TABLE credential_profiles ADD COLUMN IF NOT EXISTS username VARCHAR(100);

-- 6. Create indexes for credential_profiles
CREATE INDEX IF NOT EXISTS idx_credential_profiles_backend ON credential_profiles(backend);
CREATE INDEX IF NOT EXISTS idx_credential_profiles_group ON credential_profiles(group_id);
