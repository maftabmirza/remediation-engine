-- Seed default roles
INSERT INTO roles (id, name, description, permissions, is_custom, created_at, updated_at) VALUES
(gen_random_uuid(), 'owner', 'Built-in owner role', '["manage_users","manage_servers","manage_server_groups","manage_providers","execute","update","read","view_audit","view_knowledge","upload_documents","manage_knowledge"]', false, NOW(), NOW()),
(gen_random_uuid(), 'admin', 'Built-in admin role', '["manage_users","manage_servers","manage_server_groups","manage_providers","execute","update","read","view_audit","view_knowledge","upload_documents","manage_knowledge"]', false, NOW(), NOW()),
(gen_random_uuid(), 'maintainer', 'Built-in maintainer role', '["manage_servers","manage_server_groups","manage_providers","update","execute","read","view_knowledge","upload_documents","manage_knowledge"]', false, NOW(), NOW()),
(gen_random_uuid(), 'operator', 'Built-in operator role', '["execute","read","view_knowledge","upload_documents"]', false, NOW(), NOW()),
(gen_random_uuid(), 'viewer', 'Built-in viewer role', '["read","view_knowledge"]', false, NOW(), NOW()),
(gen_random_uuid(), 'auditor', 'Built-in auditor role', '["read","view_audit","view_knowledge"]', false, NOW(), NOW())
ON CONFLICT (name) DO NOTHING;
