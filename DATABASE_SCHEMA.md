
# Database Schema Documentation

This document outlines the database structure for the AIOps Platform. The application uses PostgreSQL as its primary data store.

## Overview

The database is designed to support:
1.  **User Management & Authentication**
2.  **Infrastructure Management** (Server Credentials)
3.  **Incident Management** (Alerts, Rules)
4.  **AI Operations** (LLM Providers, Analysis, Chat)
5.  **Auto-Remediation** (Runbooks, Executions, Safety)
6.  **Auditing & Observability** (Audit Logs, Terminal Sessions)

## Tables

### 1. Core System

#### `users`
Stores user account information and authentication details.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `username` | String(50) | Unique username |
| `email` | String(255) | Unique email address |
| `full_name` | String(100) | User's display name |
| `password_hash` | String(255) | Hashed password |
| `role` | String(20) | User role (e.g., 'user', 'admin') |
| `default_llm_provider_id` | UUID | FK to `llm_providers`. User's preferred AI model |
| `is_active` | Boolean | Account status |
| `created_at` | DateTime | Account creation timestamp |
| `last_login` | DateTime | Timestamp of last successful login |

#### `system_config`
Stores global application configuration as key-value pairs.

| Column | Type | Description |
|--------|------|-------------|
| `key` | String(50) | Primary Key. Configuration key name |
| `value_json` | JSON | Configuration value (flexible structure) |
| `updated_at` | DateTime | Last update timestamp |
| `updated_by` | UUID | FK to `users`. Who made the change |

#### `audit_log`
Records significant user actions for security and compliance.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `user_id` | UUID | FK to `users`. Who performed the action |
| `action` | String(50) | Type of action (e.g., 'login', 'create_server') |
| `resource_type` | String(50) | Type of resource affected (e.g., 'server', 'user') |
| `resource_id` | UUID | ID of the affected resource |
| `details_json` | JSON | Additional context about the action |
| `ip_address` | String(45) | IP address of the user |
| `created_at` | DateTime | Timestamp of the action |

### 2. Infrastructure & Connectivity

#### `server_credentials`
Stores connection details for managed servers. Supports both Linux (SSH) and Windows (WinRM). Sensitive data is encrypted.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `name` | String(100) | Friendly name for the server |
| `hostname` | String(255) | IP address or hostname |
| `port` | Integer | Connection port (default: 22 for SSH, 5986 for WinRM) |
| `username` | String(100) | Connection username |
| `os_type` | String(20) | 'linux' or 'windows' |
| `protocol` | String(20) | 'ssh' or 'winrm' |
| `auth_type` | String(20) | 'key' or 'password' |
| `ssh_key_encrypted` | Text | Encrypted SSH private key |
| `password_encrypted` | Text | Encrypted password |
| `winrm_transport` | String(20) | 'kerberos', 'ntlm', or 'certificate' |
| `winrm_use_ssl` | Boolean | Use SSL for WinRM (default: true) |
| `winrm_cert_validation` | Boolean | Validate SSL certificate |
| `domain` | String(100) | AD domain for Windows auth |
| `environment` | String(50) | e.g., 'production', 'staging' |
| `tags` | JSON | Server tags for filtering |
| `last_connection_test` | DateTime | Last connectivity test |
| `last_connection_status` | String(20) | 'success' or 'failed' |
| `created_by` | UUID | FK to `users` |
| `created_at` | DateTime | Creation timestamp |

#### `terminal_sessions`
Metadata for SSH terminal sessions. Actual session output is stored in files.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `user_id` | UUID | FK to `users`. Who initiated the session |
| `server_credential_id` | UUID | FK to `server_credentials`. Target server |
| `alert_id` | UUID | FK to `alerts`. Optional link to an incident |
| `started_at` | DateTime | Session start time |
| `ended_at` | DateTime | Session end time |
| `recording_path` | String(255) | File path to the session recording log |

### 3. Incident Management

#### `alerts`
The central table for alerts received from Alertmanager.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `fingerprint` | String(100) | Unique identifier from Alertmanager |
| `timestamp` | DateTime | Time the alert was received |
| `alert_name` | String(255) | Name of the alert |
| `severity` | String(50) | e.g., 'critical', 'warning' |
| `instance` | String(255) | Affected instance |
| `job` | String(100) | Prometheus job name |
| `status` | String(20) | 'firing' or 'resolved' |
| `labels_json` | JSON | All alert labels |
| `annotations_json` | JSON | All alert annotations |
| `raw_alert_json` | JSON | Full original payload |
| `matched_rule_id` | UUID | FK to `auto_analyze_rules` |
| `action_taken` | String(20) | 'auto_analyze', 'ignore', 'manual' |
| `analyzed` | Boolean | Whether AI analysis has been performed |
| `analyzed_at` | DateTime | Timestamp of analysis |
| `ai_analysis` | Text | AI-generated root cause analysis |
| `recommendations_json` | JSON | AI-generated remediation steps |

#### `auto_analyze_rules`
Rules to automate alert handling (e.g., auto-analyze critical DB alerts).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `name` | String(100) | Rule name |
| `priority` | Integer | Execution order (lower = higher priority) |
| `alert_name_pattern` | String | Glob pattern for matching alert names |
| `severity_pattern` | String | Glob pattern for matching severity |
| `action` | String(20) | Action to take on match |
| `enabled` | Boolean | Rule status |

### 4. AI & Chat

#### `llm_providers`
Configuration for AI models (OpenAI, Anthropic, etc.).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `name` | String(100) | Provider name |
| `provider_type` | String(50) | e.g., 'openai', 'anthropic' |
| `model_id` | String(100) | Specific model (e.g., 'gpt-4') |
| `api_key_encrypted` | Text | Encrypted API key |
| `is_default` | Boolean | Whether this is the system default |
| `config_json` | JSON | Model parameters (temperature, etc.) |

#### `chat_sessions`
Groups chat messages into conversations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `user_id` | UUID | FK to `users` |
| `alert_id` | UUID | FK to `alerts`. Context for the chat |
| `title` | String(255) | Conversation title |
| `llm_provider_id` | UUID | FK to `llm_providers` |

#### `chat_messages`
Individual messages within a chat session.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `session_id` | UUID | FK to `chat_sessions` |
| `role` | String(20) | 'user', 'assistant', or 'system' |
| `content` | Text | The message content |
| `tokens_used` | Integer | Token usage for this message |
| `created_at` | DateTime | Timestamp |

### 5. Auto-Remediation

The auto-remediation subsystem provides enterprise-grade runbook automation with safety controls, RBAC, and Infrastructure-as-Code support.

#### ENUM Types

```sql
-- Execution mode for runbooks
CREATE TYPE execution_mode AS ENUM ('auto', 'semi_auto', 'manual');

-- Status of runbook (active, disabled, draft)
CREATE TYPE runbook_status AS ENUM ('active', 'disabled', 'draft');

-- Execution state tracking
CREATE TYPE execution_status AS ENUM ('pending', 'approved', 'running', 'completed', 'failed', 'cancelled', 'timeout');

-- Circuit breaker states
CREATE TYPE circuit_state AS ENUM ('closed', 'open', 'half_open');

-- Operating system type
CREATE TYPE os_type AS ENUM ('linux', 'windows');
```

#### `runbooks`
Core runbook definitions containing automation metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `name` | String(200) | Unique runbook name |
| `description` | Text | Detailed description |
| `category` | String(100) | Grouping category (e.g., 'database', 'network') |
| `mode` | execution_mode | 'auto', 'semi_auto', or 'manual' |
| `status` | runbook_status | 'active', 'disabled', or 'draft' |
| `target_os` | os_type | 'linux' or 'windows' |
| `version` | Integer | Current version number |
| `timeout_seconds` | Integer | Max execution time (default: 300) |
| `max_retries` | Integer | Retry count on failure (default: 0) |
| `retry_delay_seconds` | Integer | Delay between retries (default: 60) |
| `rate_limit_count` | Integer | Max executions per window |
| `rate_limit_window_seconds` | Integer | Rate limit window duration |
| `requires_approval` | Boolean | Needs human approval before execution |
| `approval_roles` | ARRAY[String] | Roles that can approve (default: ['admin', 'engineer']) |
| `allowed_servers` | JSON | Server restrictions by tag/group |
| `environment_vars` | JSON | Variables passed to execution |
| `config` | JSON | Additional configuration |
| `created_by` | UUID | FK to `users` |
| `created_at` | DateTime | Created timestamp |
| `updated_at` | DateTime | Auto-updated timestamp |

**Indexes:**
- `idx_runbooks_name` (name) - Fast lookup by name
- `idx_runbooks_category` (category) - Filter by category
- `idx_runbooks_status_mode` (status, mode) - Active runbook queries

#### `runbook_steps`
Individual execution steps within a runbook.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `runbook_id` | UUID | FK to `runbooks` (CASCADE delete) |
| `step_order` | Integer | Execution sequence |
| `name` | String(200) | Step name |
| `description` | Text | What this step does |
| `command` | Text | Shell command (supports Jinja2 templates) |
| `expected_exit_codes` | ARRAY[Integer] | Success codes (default: [0]) |
| `timeout_seconds` | Integer | Step timeout (default: 60) |
| `continue_on_failure` | Boolean | Continue to next step on failure |
| `condition` | Text | Jinja2 condition for execution |
| `rollback_command` | Text | Command to undo this step |
| `retry_count` | Integer | Step-level retries |
| `retry_delay_seconds` | Integer | Delay between step retries |
| `capture_output` | Boolean | Store output for later steps |
| `sensitive` | Boolean | Mask output in logs |

**Constraint:** Unique (runbook_id, step_order)

#### `runbook_triggers`
Alert patterns that trigger runbook execution.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `runbook_id` | UUID | FK to `runbooks` (CASCADE delete) |
| `name` | String(200) | Trigger name |
| `priority` | Integer | Match priority (lower = higher) |
| `alert_name_pattern` | String | Glob/regex for alert name |
| `severity_pattern` | String | Glob for severity (e.g., 'critical*') |
| `source_pattern` | String | Pattern for alert source |
| `labels_match` | JSON | Label key-value matching |
| `time_window_start` | Time | Active window start |
| `time_window_end` | Time | Active window end |
| `enabled` | Boolean | Trigger status |
| `cooldown_seconds` | Integer | Min time between triggers |
| `last_triggered_at` | DateTime | Last trigger timestamp |

**Indexes:**
- `idx_triggers_runbook` (runbook_id) - Find triggers for runbook
- `idx_triggers_enabled_priority` (enabled, priority) - Active trigger queries

#### `runbook_versions`
Version history for runbook changes (IaC support).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `runbook_id` | UUID | FK to `runbooks` (CASCADE delete) |
| `version` | Integer | Version number |
| `yaml_content` | Text | Full runbook as YAML |
| `change_summary` | Text | What changed in this version |
| `created_by` | UUID | FK to `users` |
| `created_at` | DateTime | Version timestamp |

**Constraint:** Unique (runbook_id, version)

#### `runbook_executions`
Tracks each runbook execution instance.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `runbook_id` | UUID | FK to `runbooks` (SET NULL on delete) |
| `runbook_version` | Integer | Version at execution time |
| `server_id` | UUID | FK to `server_credentials` |
| `alert_id` | UUID | FK to `alerts` (optional) |
| `trigger_id` | UUID | FK to `runbook_triggers` (optional) |
| `status` | execution_status | Current execution state |
| `mode` | execution_mode | Mode at execution time |
| `started_at` | DateTime | Execution start |
| `completed_at` | DateTime | Execution end |
| `duration_ms` | Integer | Total duration |
| `initiated_by` | UUID | FK to `users` (manual runs) |
| `approved_by` | UUID | FK to `users` (semi-auto approval) |
| `approved_at` | DateTime | Approval timestamp |
| `error_message` | Text | Failure reason |
| `output_summary` | Text | Execution summary |
| `context_vars` | JSON | Variables passed to execution |
| `execution_log` | JSON | Detailed execution log |

**Indexes:**
- `idx_executions_runbook` (runbook_id) - Find executions for runbook
- `idx_executions_server` (server_id) - Find executions for server
- `idx_executions_status` (status) - Filter by status
- `idx_executions_started_at` (started_at DESC) - Recent executions

#### `step_executions`
Individual step results within an execution.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `execution_id` | UUID | FK to `runbook_executions` (CASCADE) |
| `step_id` | UUID | FK to `runbook_steps` (SET NULL) |
| `step_order` | Integer | Preserved order |
| `step_name` | String(200) | Preserved name |
| `status` | execution_status | Step status |
| `started_at` | DateTime | Step start |
| `completed_at` | DateTime | Step end |
| `duration_ms` | Integer | Step duration |
| `exit_code` | Integer | Command exit code |
| `stdout` | Text | Standard output |
| `stderr` | Text | Standard error |
| `retry_attempt` | Integer | Current retry number |

**Index:** `idx_step_executions_execution` (execution_id)

#### `circuit_breakers`
Safety mechanism to prevent cascading failures.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `runbook_id` | UUID | FK to `runbooks` (CASCADE) - Unique |
| `state` | circuit_state | 'closed', 'open', or 'half_open' |
| `failure_count` | Integer | Consecutive failures |
| `success_count` | Integer | Consecutive successes (half_open) |
| `last_failure_at` | DateTime | Most recent failure |
| `opened_at` | DateTime | When circuit opened |
| `half_open_at` | DateTime | When entered half_open |
| `failure_threshold` | Integer | Failures before opening (default: 5) |
| `success_threshold` | Integer | Successes to close (default: 3) |
| `reset_timeout_seconds` | Integer | Time in open before half_open |
| `updated_at` | DateTime | Auto-updated timestamp |

**State Transitions:**
- `closed` → `open`: After failure_threshold consecutive failures
- `open` → `half_open`: After reset_timeout_seconds
- `half_open` → `closed`: After success_threshold consecutive successes
- `half_open` → `open`: On any failure

#### `blackout_windows`
Maintenance periods where auto-remediation is disabled.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `name` | String(200) | Window name |
| `description` | Text | Purpose of blackout |
| `start_time` | DateTime | Window start |
| `end_time` | DateTime | Window end |
| `recurrence` | String(50) | 'none', 'daily', 'weekly', 'monthly' |
| `recurrence_pattern` | JSON | Cron-like pattern |
| `affected_servers` | JSON | Server tags/groups affected |
| `affected_runbooks` | JSON | Runbook IDs/categories affected |
| `created_by` | UUID | FK to `users` |
| `created_at` | DateTime | Created timestamp |
| `enabled` | Boolean | Window status |

**Constraint:** CHECK (end_time > start_time)

---

### 6. Relationships Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AUTO-REMEDIATION FLOW                              │
└──────────────────────────────────────────────────────────────────────────────┘

    alerts                    runbook_triggers              runbooks
    ┌────────┐               ┌──────────────────┐          ┌──────────────────┐
    │        │──matches───▶  │ alert_name_pattern│──links─▶│ steps[]          │
    │ source │               │ severity_pattern  │          │ mode             │
    │ labels │               │ labels_match      │          │ requires_approval│
    └────────┘               └──────────────────┘          └────────┬─────────┘
                                                                    │
                                                           ┌────────▼─────────┐
                                                           │ runbook_versions │
                                                           │ (YAML snapshots) │
                                                           └──────────────────┘
                                                                    │
         server_credentials                                         │
         ┌──────────────────┐        circuit_breaker               │
         │ os_type          │        ┌──────────────┐              │
         │ protocol         │◀──────▶│ state        │              │
         │ tags             │        │ failure_count│              │
         └────────┬─────────┘        └──────────────┘              │
                  │                                                 │
                  │          ┌─────────────────────┐               │
                  └─────────▶│ runbook_executions  │◀──────────────┘
                             │ status              │
                             │ context_vars        │
                             └─────────┬───────────┘
                                       │
                             ┌─────────▼───────────┐
                             │  step_executions    │
                             │  stdout/stderr      │
                             │  exit_code          │
                             └─────────────────────┘
                                       │
                             ┌─────────▼───────────┐
                             │   blackout_windows  │
                             │   (blocks execution)│
                             └─────────────────────┘
```

---

### 7. Database Views

#### `execution_stats`
Aggregated execution statistics per runbook.

```sql
CREATE VIEW execution_stats AS
SELECT 
    r.id AS runbook_id,
    r.name AS runbook_name,
    COUNT(e.id) AS total_executions,
    COUNT(*) FILTER (WHERE e.status = 'completed') AS successful,
    COUNT(*) FILTER (WHERE e.status = 'failed') AS failed,
    AVG(e.duration_ms) AS avg_duration_ms,
    MAX(e.started_at) AS last_execution
FROM runbooks r
LEFT JOIN runbook_executions e ON r.id = e.runbook_id
GROUP BY r.id, r.name;
```

---

### 8. IaC Export Format

Runbooks can be exported as YAML for version control:

```yaml
name: restart-service
description: Restart a failing service
category: service-management
mode: semi_auto
target_os: linux
timeout_seconds: 300
requires_approval: true
approval_roles:
  - admin
  - engineer
environment_vars:
  SERVICE_NAME: "{{ alert.labels.service }}"

steps:
  - name: Check service status
    command: systemctl status {{ SERVICE_NAME }}
    expected_exit_codes: [0, 3]  # 3 = stopped
    timeout_seconds: 30

  - name: Restart service
    command: sudo systemctl restart {{ SERVICE_NAME }}
    timeout_seconds: 60
    rollback_command: sudo systemctl stop {{ SERVICE_NAME }}

  - name: Verify service
    command: systemctl is-active {{ SERVICE_NAME }}
    expected_exit_codes: [0]
    timeout_seconds: 30

triggers:
  - name: Service down alert
    alert_name_pattern: "ServiceDown*"
    severity_pattern: "critical"
    labels_match:
      type: service
    cooldown_seconds: 300
```
