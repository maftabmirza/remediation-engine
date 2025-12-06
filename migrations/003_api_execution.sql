-- Migration 003: Add API Execution Support
-- Adds support for HTTP/REST API calls in addition to command execution
-- Use cases: Ansible AWX, Jenkins, REST APIs, webhooks, etc.

-- ============================================================================
-- 1. Extend server_credentials for API endpoints
-- ============================================================================

-- Add API-related fields to server_credentials
ALTER TABLE server_credentials
ADD COLUMN IF NOT EXISTS api_base_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS api_auth_type VARCHAR(30) DEFAULT 'none',  -- none, api_key, bearer, basic, oauth, custom
ADD COLUMN IF NOT EXISTS api_auth_header VARCHAR(100),  -- e.g., "X-API-Key", "Authorization"
ADD COLUMN IF NOT EXISTS api_token_encrypted TEXT,  -- encrypted API token/key
ADD COLUMN IF NOT EXISTS api_verify_ssl BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS api_timeout_seconds INTEGER DEFAULT 30,
ADD COLUMN IF NOT EXISTS api_headers_json JSON DEFAULT '{}'::json,  -- default headers for all requests
ADD COLUMN IF NOT EXISTS api_metadata_json JSON DEFAULT '{}'::json;  -- provider-specific config (e.g., AWX job template ID)

-- Add index for API protocol type
CREATE INDEX IF NOT EXISTS idx_server_credentials_protocol ON server_credentials(protocol);

-- Add comment for documentation
COMMENT ON COLUMN server_credentials.api_base_url IS 'Base URL for API endpoints (e.g., https://awx.example.com)';
COMMENT ON COLUMN server_credentials.api_auth_type IS 'Authentication method: none, api_key, bearer, basic, oauth, custom';
COMMENT ON COLUMN server_credentials.api_auth_header IS 'Header name for authentication (e.g., X-API-Key, Authorization)';
COMMENT ON COLUMN server_credentials.api_token_encrypted IS 'Encrypted API token, key, or password for API authentication';
COMMENT ON COLUMN server_credentials.api_metadata_json IS 'Provider-specific metadata (e.g., AWX organization ID, Jenkins job name)';


-- ============================================================================
-- 2. Extend runbook_steps for API execution
-- ============================================================================

-- Add API execution fields to runbook_steps
ALTER TABLE runbook_steps
ADD COLUMN IF NOT EXISTS step_type VARCHAR(20) DEFAULT 'command',  -- 'command', 'api'
ADD COLUMN IF NOT EXISTS api_method VARCHAR(10),  -- GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
ADD COLUMN IF NOT EXISTS api_endpoint TEXT,  -- endpoint path or full URL (supports Jinja2 templates)
ADD COLUMN IF NOT EXISTS api_headers_json JSON,  -- custom headers for this request (merged with server defaults)
ADD COLUMN IF NOT EXISTS api_body TEXT,  -- request body (JSON string or Jinja2 template)
ADD COLUMN IF NOT EXISTS api_body_type VARCHAR(30) DEFAULT 'json',  -- json, form, raw, template
ADD COLUMN IF NOT EXISTS api_query_params_json JSON,  -- URL query parameters
ADD COLUMN IF NOT EXISTS api_expected_status_codes INTEGER[] DEFAULT ARRAY[200, 201, 202, 204],  -- acceptable HTTP status codes
ADD COLUMN IF NOT EXISTS api_response_extract_json JSON,  -- JSONPath or regex patterns to extract from response
ADD COLUMN IF NOT EXISTS api_follow_redirects BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS api_retry_on_status_codes INTEGER[] DEFAULT ARRAY[408, 429, 500, 502, 503, 504];  -- retry on these codes

-- Add index for step_type
CREATE INDEX IF NOT EXISTS idx_runbook_steps_type ON runbook_steps(step_type);

-- Add check constraint for step_type
ALTER TABLE runbook_steps
ADD CONSTRAINT chk_step_type CHECK (step_type IN ('command', 'api'));

-- Add check constraint for api_method
ALTER TABLE runbook_steps
ADD CONSTRAINT chk_api_method CHECK (
    api_method IS NULL OR
    api_method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS')
);

-- Add check constraint for api_body_type
ALTER TABLE runbook_steps
ADD CONSTRAINT chk_api_body_type CHECK (
    api_body_type IS NULL OR
    api_body_type IN ('json', 'form', 'raw', 'template')
);

-- Add comments for documentation
COMMENT ON COLUMN runbook_steps.step_type IS 'Type of step: command (SSH/WinRM) or api (HTTP/REST)';
COMMENT ON COLUMN runbook_steps.api_method IS 'HTTP method for API calls: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS';
COMMENT ON COLUMN runbook_steps.api_endpoint IS 'API endpoint path (e.g., /api/v2/job_templates/123/launch/) - supports Jinja2 templates';
COMMENT ON COLUMN runbook_steps.api_headers_json IS 'Custom headers for this API request (merged with server defaults)';
COMMENT ON COLUMN runbook_steps.api_body IS 'Request body - can be JSON string or Jinja2 template';
COMMENT ON COLUMN runbook_steps.api_body_type IS 'Body format: json, form, raw, or template';
COMMENT ON COLUMN runbook_steps.api_query_params_json IS 'URL query parameters as JSON object';
COMMENT ON COLUMN runbook_steps.api_expected_status_codes IS 'Array of acceptable HTTP status codes (default: 200, 201, 202, 204)';
COMMENT ON COLUMN runbook_steps.api_response_extract_json IS 'JSONPath or regex patterns to extract values from response';
COMMENT ON COLUMN runbook_steps.api_retry_on_status_codes IS 'HTTP status codes that should trigger a retry';


-- ============================================================================
-- 3. Extend step_executions for API responses
-- ============================================================================

-- Add API response fields to step_executions
ALTER TABLE step_executions
ADD COLUMN IF NOT EXISTS http_status_code INTEGER,  -- HTTP response status code
ADD COLUMN IF NOT EXISTS http_response_headers_json JSON,  -- response headers
ADD COLUMN IF NOT EXISTS http_response_body TEXT,  -- raw response body
ADD COLUMN IF NOT EXISTS http_request_url TEXT,  -- actual URL that was called
ADD COLUMN IF NOT EXISTS http_request_method VARCHAR(10),  -- HTTP method used
ADD COLUMN IF NOT EXISTS extracted_values_json JSON;  -- values extracted from response using api_response_extract_json

-- Add comments
COMMENT ON COLUMN step_executions.http_status_code IS 'HTTP response status code for API steps';
COMMENT ON COLUMN step_executions.http_response_headers_json IS 'HTTP response headers for API steps';
COMMENT ON COLUMN step_executions.http_response_body IS 'HTTP response body for API steps (stored in stdout for commands)';
COMMENT ON COLUMN step_executions.http_request_url IS 'Full URL that was called for API steps';
COMMENT ON COLUMN step_executions.http_request_method IS 'HTTP method used for API steps';
COMMENT ON COLUMN step_executions.extracted_values_json IS 'Values extracted from API response using JSONPath/regex';


-- ============================================================================
-- 4. Add validation trigger to ensure step has required fields
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_runbook_step_fields()
RETURNS TRIGGER AS $$
BEGIN
    -- For command steps, require at least one command
    IF NEW.step_type = 'command' THEN
        IF NEW.command_linux IS NULL AND NEW.command_windows IS NULL THEN
            RAISE EXCEPTION 'Command steps must have at least one of command_linux or command_windows';
        END IF;
    END IF;

    -- For API steps, require method and endpoint
    IF NEW.step_type = 'api' THEN
        IF NEW.api_method IS NULL THEN
            RAISE EXCEPTION 'API steps must have api_method specified';
        END IF;
        IF NEW.api_endpoint IS NULL OR NEW.api_endpoint = '' THEN
            RAISE EXCEPTION 'API steps must have api_endpoint specified';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_runbook_step
    BEFORE INSERT OR UPDATE ON runbook_steps
    FOR EACH ROW
    EXECUTE FUNCTION validate_runbook_step_fields();


-- ============================================================================
-- 5. Create sample API configurations
-- ============================================================================

-- Insert example API server configurations (commented out - users can uncomment)

-- Example 1: Ansible AWX
/*
INSERT INTO server_credentials (
    id, name, hostname, port, username, os_type, protocol,
    api_base_url, api_auth_type, api_auth_header, api_verify_ssl,
    api_metadata_json, environment, tags
) VALUES (
    gen_random_uuid(),
    'Ansible AWX Production',
    'awx.example.com',
    443,
    'api-user',
    'linux',
    'api',
    'https://awx.example.com/api/v2',
    'bearer',
    'Authorization',
    true,
    '{"organization_id": 1, "inventory_id": 2}'::json,
    'production',
    '["ansible", "automation"]'::json
) ON CONFLICT DO NOTHING;
*/

-- Example 2: Jenkins
/*
INSERT INTO server_credentials (
    id, name, hostname, port, username, os_type, protocol,
    api_base_url, api_auth_type, api_auth_header, api_verify_ssl,
    api_metadata_json, environment, tags
) VALUES (
    gen_random_uuid(),
    'Jenkins CI/CD',
    'jenkins.example.com',
    8080,
    'jenkins-api',
    'linux',
    'api',
    'https://jenkins.example.com',
    'basic',
    'Authorization',
    true,
    '{"default_job": "deploy-app"}'::json,
    'production',
    '["jenkins", "cicd"]'::json
) ON CONFLICT DO NOTHING;
*/

-- Example 3: Generic REST API
/*
INSERT INTO server_credentials (
    id, name, hostname, port, username, os_type, protocol,
    api_base_url, api_auth_type, api_auth_header, api_verify_ssl,
    api_metadata_json, environment, tags
) VALUES (
    gen_random_uuid(),
    'Custom REST API',
    'api.example.com',
    443,
    'api-key-user',
    'linux',
    'api',
    'https://api.example.com/v1',
    'api_key',
    'X-API-Key',
    true,
    '{}'::json,
    'production',
    '["rest-api"]'::json
) ON CONFLICT DO NOTHING;
*/


-- ============================================================================
-- 6. Migration metadata
-- ============================================================================

-- Track migration version
INSERT INTO system_config (key, value_json, updated_at)
VALUES ('db_migration_version', '"003"', NOW())
ON CONFLICT (key) DO UPDATE SET value_json = '"003"', updated_at = NOW();

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 003: API Execution Support - COMPLETED';
    RAISE NOTICE 'Added API execution fields to runbook_steps and server_credentials';
    RAISE NOTICE 'New step_type values: "command" (default), "api"';
    RAISE NOTICE 'Supported protocols: ssh, winrm, api';
    RAISE NOTICE 'Supported auth types: none, api_key, bearer, basic, oauth, custom';
END $$;
