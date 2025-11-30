# Database Schema Documentation

This document outlines the database structure for the AIOps Platform. The application uses PostgreSQL as its primary data store.

## Overview

The database is designed to support:
1.  **User Management & Authentication**
2.  **Infrastructure Management** (Server Credentials)
3.  **Incident Management** (Alerts, Rules)
4.  **AI Operations** (LLM Providers, Analysis, Chat)
5.  **Auditing & Observability** (Audit Logs, Terminal Sessions)

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
Stores connection details for managed servers. Sensitive data is encrypted.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `name` | String(100) | Friendly name for the server |
| `hostname` | String(255) | IP address or hostname |
| `port` | Integer | SSH port (default: 22) |
| `username` | String(100) | SSH username |
| `auth_type` | String(20) | 'key' or 'password' |
| `ssh_key_encrypted` | Text | Encrypted private key |
| `password_encrypted` | Text | Encrypted password |
| `environment` | String(50) | e.g., 'production', 'staging' |
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
