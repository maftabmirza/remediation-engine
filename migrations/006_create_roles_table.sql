-- Create roles table
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_custom BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_roles_name ON roles (name);

-- Insert default roles
INSERT INTO roles (name, description, permissions, is_custom) VALUES
(
    'owner',
    'Full platform control and ownership',
    '["manage_users", "manage_servers", "manage_server_groups", "manage_providers", "execute", "update", "read", "view_audit"]'::jsonb,
    FALSE
),
(
    'admin',
    'Administrative access to all resources',
    '["manage_users", "manage_servers", "manage_server_groups", "manage_providers", "execute", "update", "read", "view_audit"]'::jsonb,
    FALSE
),
(
    'maintainer',
    'Manage servers and providers, execute runbooks',
    '["manage_servers", "manage_server_groups", "manage_providers", "update", "execute", "read"]'::jsonb,
    FALSE
),
(
    'operator',
    'Execute runbooks and view resources',
    '["execute", "read"]'::jsonb,
    FALSE
),
(
    'viewer',
    'Read-only access',
    '["read"]'::jsonb,
    FALSE
),
(
    'auditor',
    'Read-only access plus audit logs',
    '["read", "view_audit"]'::jsonb,
    FALSE
)
ON CONFLICT (name) DO NOTHING;
