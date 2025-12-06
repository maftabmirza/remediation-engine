# API Execution Feature

## Overview

The Remediation Engine now supports executing HTTP/REST API calls as part of runbook workflows, in addition to SSH and WinRM command execution. This enables integration with external automation platforms like Ansible AWX, Jenkins, Kubernetes APIs, and custom REST APIs.

## Features

- ✅ **Multiple Authentication Methods**: API Key, Bearer Token, Basic Auth, OAuth, Custom Headers
- ✅ **HTTP Method Support**: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- ✅ **Request Body Types**: JSON, Form Data, Raw Text, Jinja2 Templates
- ✅ **Response Validation**: Expected status codes, regex pattern matching
- ✅ **Value Extraction**: Extract values from responses using JSONPath or regex
- ✅ **Retry Logic**: Automatic retries for transient failures (408, 429, 5xx errors)
- ✅ **SSL/TLS Control**: Option to verify or skip SSL certificate validation
- ✅ **Template Variables**: Full Jinja2 templating support for dynamic requests
- ✅ **Query Parameters**: Support for URL query string parameters
- ✅ **Custom Headers**: Per-request and server-default headers

## Use Cases

### 1. **Ansible AWX Integration**
Trigger Ansible playbooks via AWX API to perform complex remediation tasks:
- Service restarts across multiple servers
- Configuration updates
- Package installations
- Infrastructure provisioning

### 2. **Jenkins CI/CD**
Trigger deployment rollbacks or rebuilds:
- Rollback failed deployments
- Trigger emergency patches
- Run cleanup jobs

### 3. **Container Orchestration**
Interact with Kubernetes, Docker Swarm, or other container platforms:
- Scale deployments
- Restart failed pods
- Update configurations

### 4. **Custom APIs**
Integrate with any REST API:
- Update load balancer configurations
- Modify firewall rules
- Send notifications to custom systems
- Query/update CMDB

## Architecture

```
┌─────────────────┐
│  Runbook Step   │
│  (step_type:api)│
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  Runbook Executor   │  Builds API request config (JSON)
│  (Jinja2 rendering) │  Renders templates with context
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Executor Factory   │  Creates appropriate executor
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   API Executor      │  Makes HTTP requests via httpx
│  (HTTPClient+Auth)  │  Handles auth, retries, SSL
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  External API       │  Ansible AWX, Jenkins, K8s, etc.
└─────────────────────┘
```

## Configuration

### Step 1: Create API Server Credential

First, create a server credential with API configuration:

```json
{
  "name": "Ansible AWX Production",
  "hostname": "awx.example.com",
  "port": 443,
  "username": "api-user",
  "protocol": "api",

  "api_base_url": "https://awx.example.com/api/v2",
  "api_auth_type": "bearer",
  "api_auth_header": "Authorization",
  "api_token_encrypted": "<encrypted-token>",
  "api_verify_ssl": true,
  "api_timeout_seconds": 30,
  "api_headers_json": {
    "User-Agent": "AIOps-Remediation/1.0"
  },
  "api_metadata_json": {
    "organization_id": 1,
    "inventory_id": 2
  }
}
```

**Authentication Types:**

- `none` - No authentication
- `api_key` - API key in custom header (e.g., `X-API-Key`)
- `bearer` - Bearer token in `Authorization` header
- `basic` - Basic auth (username + password)
- `oauth` - OAuth2 token (similar to bearer)
- `custom` - Custom authentication header

### Step 2: Create API Runbook Step

Create a runbook step with `step_type: "api"`:

```json
{
  "name": "Launch AWX Job",
  "step_type": "api",
  "step_order": 1,

  "api_method": "POST",
  "api_endpoint": "/job_templates/123/launch/",
  "api_body_type": "json",
  "api_body": "{\"extra_vars\": {\"target\": \"{{ alert.labels.instance }}\"}}",

  "api_headers_json": {
    "Content-Type": "application/json"
  },

  "api_query_params_json": {
    "verbose": "true"
  },

  "api_expected_status_codes": [200, 201, 202],

  "api_response_extract_json": {
    "job_id": "$.id",
    "job_url": "$.url"
  },

  "timeout_seconds": 30,
  "retry_count": 3,
  "retry_delay_seconds": 5
}
```

## API Step Configuration Reference

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `step_type` | Must be `"api"` | `"api"` |
| `api_method` | HTTP method | `"POST"`, `"GET"`, `"PUT"`, `"DELETE"`, `"PATCH"` |
| `api_endpoint` | Endpoint path or full URL | `"/api/v2/jobs"` or `"https://api.example.com/jobs"` |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api_headers_json` | Object | `{}` | Custom headers (merged with server defaults) |
| `api_query_params_json` | Object | `{}` | URL query parameters |
| `api_body` | String | `null` | Request body (JSON, form data, or template) |
| `api_body_type` | String | `"json"` | Body format: `json`, `form`, `raw`, `template` |
| `api_expected_status_codes` | Array | `[200,201,202,204]` | Acceptable HTTP status codes |
| `api_response_extract_json` | Object | `{}` | JSONPath/regex patterns to extract values |
| `api_follow_redirects` | Boolean | `true` | Whether to follow HTTP redirects |
| `api_retry_on_status_codes` | Array | `[408,429,500,502,503,504]` | Status codes that trigger retry |
| `timeout_seconds` | Integer | `60` | Request timeout |
| `retry_count` | Integer | `0` | Number of retry attempts |
| `retry_delay_seconds` | Integer | `5` | Delay between retries |

## Template Variables

API steps support full Jinja2 templating in all string fields. Available context:

```jinja2
{{ server.hostname }}          # Server hostname
{{ server.os_type }}           # Server OS type
{{ server.environment }}       # Environment (prod, staging, dev)

{{ alert.alert_name }}         # Alert name
{{ alert.alert_severity }}     # Alert severity
{{ alert.labels.instance }}    # Alert labels (dynamic)
{{ alert.annotations.summary }}# Alert annotations

{{ vars.custom_var }}          # Custom variables passed at runtime

{{ execution.id }}             # Execution ID
{{ execution.mode }}           # Execution mode (auto, manual)

{{ now }}                      # Current timestamp
```

### Template Example

```json
{
  "api_method": "POST",
  "api_endpoint": "/job_templates/{{ vars.awx_job_id }}/launch/",
  "api_body": "{
    \"extra_vars\": {
      \"target_host\": \"{{ alert.labels.instance }}\",
      \"service_name\": \"{{ vars.service_name }}\",
      \"alert_severity\": \"{{ alert.alert_severity }}\",
      \"remediation_id\": \"{{ execution.id }}\"
    }
  }"
}
```

## Response Extraction

Extract values from API responses to use in subsequent steps:

### JSONPath Extraction

```json
{
  "api_response_extract_json": {
    "job_id": "$.id",
    "job_status": "$.status",
    "created_at": "$.created",
    "nested_value": "$.data.results[0].name"
  }
}
```

For response:
```json
{
  "id": 12345,
  "status": "pending",
  "created": "2025-01-01T10:00:00Z",
  "data": {
    "results": [
      {"name": "result1"}
    ]
  }
}
```

Extracted values: `job_id=12345`, `job_status="pending"`, etc.

### Regex Extraction

```json
{
  "api_response_extract_json": {
    "build_number": "Build #(\\d+)",
    "status": "Status:\\s+(\\w+)"
  }
}
```

For text response: `"Build #42 completed. Status: SUCCESS"`

Extracted values: `build_number="42"`, `status="SUCCESS"`

### Using Extracted Values

Access extracted values in subsequent steps:

```json
{
  "api_endpoint": "/jobs/{{ extracted_values.job_id }}/status"
}
```

## Error Handling

### Expected Status Codes

Define which HTTP status codes are considered successful:

```json
{
  "api_expected_status_codes": [200, 201, 202, 204]
}
```

If the response status code is not in this list, the step fails.

### Automatic Retries

The API executor automatically retries on these status codes:
- `408` - Request Timeout
- `429` - Too Many Requests (rate limiting)
- `500` - Internal Server Error
- `502` - Bad Gateway
- `503` - Service Unavailable
- `504` - Gateway Timeout

Configure retry behavior:

```json
{
  "retry_count": 3,
  "retry_delay_seconds": 5
}
```

### Custom Retry Status Codes

Override default retry status codes:

```json
{
  "api_retry_on_status_codes": [408, 429, 503]
}
```

### Pattern Matching

Validate response body contains expected content:

```json
{
  "expected_output_pattern": "\"status\":\\s*\"success\""
}
```

Uses regex to search response body. Step fails if pattern not found.

## Best Practices

### 1. **Use Idempotent API Calls**
Ensure API operations are idempotent to handle retries safely:
```
✅ PUT /servers/123/status (idempotent)
❌ POST /servers/create (not idempotent - creates duplicate)
```

### 2. **Set Appropriate Timeouts**
- Quick APIs: 10-30 seconds
- Long-running jobs: 60-300 seconds
- Polling: Short timeout + many retries

```json
{
  "timeout_seconds": 30,
  "retry_count": 10,
  "retry_delay_seconds": 10
}
```

### 3. **Extract Operation IDs**
For async APIs, extract operation/job IDs for tracking:

```json
{
  "api_response_extract_json": {
    "operation_id": "$.id"
  }
}
```

Then poll status in subsequent step:

```json
{
  "api_endpoint": "/operations/{{ extracted_values.operation_id }}"
}
```

### 4. **Use Template Variables**
Avoid hardcoding values - use templates:

```
❌ "api_endpoint": "/jobs/123/launch/"
✅ "api_endpoint": "/jobs/{{ vars.job_id }}/launch/"
```

### 5. **Verify SSL Certificates**
Always verify SSL in production:

```json
{
  "api_verify_ssl": true
}
```

Only disable for testing:

```json
{
  "api_verify_ssl": false  // ⚠️ Use only for testing!
}
```

### 6. **Handle Failures Gracefully**
Use `continue_on_fail` for non-critical steps:

```json
{
  "name": "Post notification (optional)",
  "continue_on_fail": true
}
```

### 7. **Rate Limiting**
Configure cooldowns to respect API rate limits:

```yaml
spec:
  safety:
    max_executions_per_hour: 60
    cooldown_minutes: 1
```

## Examples

### Example 1: Ansible AWX Job Launch

```yaml
steps:
  - name: Launch AWX Job
    step_type: api
    step_order: 1
    api_method: POST
    api_endpoint: /job_templates/{{ vars.template_id }}/launch/
    api_body_type: json
    api_body: |
      {
        "extra_vars": {
          "target": "{{ alert.labels.instance }}",
          "action": "restart_service"
        }
      }
    api_expected_status_codes: [200, 201]
    api_response_extract_json:
      job_id: $.id
    timeout_seconds: 30

  - name: Poll Job Status
    step_type: api
    step_order: 2
    api_method: GET
    api_endpoint: /jobs/{{ extracted_values.job_id }}/
    expected_output_pattern: '"status":\s*"successful"'
    timeout_seconds: 300
    retry_count: 30
    retry_delay_seconds: 10
```

### Example 2: Kubernetes Scale Deployment

```yaml
steps:
  - name: Scale Deployment
    step_type: api
    step_order: 1
    api_method: PATCH
    api_endpoint: /apis/apps/v1/namespaces/{{ vars.namespace }}/deployments/{{ vars.deployment }}
    api_headers_json:
      Content-Type: application/strategic-merge-patch+json
    api_body_type: json
    api_body: |
      {
        "spec": {
          "replicas": {{ vars.target_replicas }}
        }
      }
    api_expected_status_codes: [200]
    timeout_seconds: 30
```

### Example 3: Jenkins Build Trigger

```yaml
steps:
  - name: Trigger Build
    step_type: api
    step_order: 1
    api_method: POST
    api_endpoint: /job/{{ vars.job_name }}/buildWithParameters
    api_body_type: form
    api_body: environment={{ vars.env }}&version={{ vars.version }}
    api_expected_status_codes: [200, 201]
    timeout_seconds: 30
```

## Troubleshooting

### Authentication Failures (401/403)

**Problem**: API returns 401 or 403 status

**Solutions**:
1. Verify API token is correct and not expired
2. Check auth_type matches API requirements
3. Ensure auth_header name is correct
4. Verify user has necessary permissions

### Connection Timeouts

**Problem**: Requests timeout

**Solutions**:
1. Increase `timeout_seconds`
2. Check network connectivity
3. Verify `api_base_url` is correct
4. Check firewall rules

### Invalid Response Format

**Problem**: Response extraction fails

**Solutions**:
1. Check JSONPath syntax: `$.field.subfield`
2. Verify response is actually JSON
3. Use regex for non-JSON responses
4. Test extraction patterns manually

### SSL Certificate Errors

**Problem**: SSL verification fails

**Solutions**:
1. Ensure certificates are valid
2. Check system trust store
3. For self-signed certs in testing only: set `api_verify_ssl: false`

## Security Considerations

1. **API Tokens**: Always encrypt tokens using the platform's encryption
2. **SSL/TLS**: Always verify SSL certificates in production
3. **Least Privilege**: Use API accounts with minimal required permissions
4. **Audit Logging**: All API calls are logged with full request/response
5. **Rate Limiting**: Configure appropriate cooldowns and execution limits
6. **Secret Management**: Consider using external vaults (HashiCorp Vault, AWS Secrets Manager)

## Migration Guide

### Migrating from Command-Based to API-Based

**Before** (SSH command):
```yaml
- name: Restart Service
  step_type: command
  command_linux: systemctl restart nginx
```

**After** (API call):
```yaml
- name: Restart Service via AWX
  step_type: api
  api_method: POST
  api_endpoint: /job_templates/123/launch/
  api_body: '{"extra_vars": {"service": "nginx"}}'
```

**Benefits**:
- ✅ Centralized execution (AWX handles all servers)
- ✅ Better logging and audit trail
- ✅ No direct SSH access required
- ✅ Leverage existing Ansible playbooks

## API Reference

See [API_EXECUTION_REFERENCE.md](./API_EXECUTION_REFERENCE.md) for detailed API documentation.

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-org/remediation-engine/issues
- Documentation: https://docs.your-org.com/remediation-engine
- Slack: #remediation-engine
