# API FIELD COVERAGE MATRIX

**Version**: 1.0
**Date**: 2025-12-29
**Purpose**: Ensure complete test coverage of all API fields and options

---

## OVERVIEW

This document provides a comprehensive matrix of all fields, options, and variations for each API endpoint to ensure complete test coverage. It addresses the concern that complex endpoints (like runbook execution) have many fields that need individual testing.

---

## 1. RUNBOOK EXECUTION - COMPLETE FIELD COVERAGE

### 1.1 Runbook Creation Fields

#### **RunbookBase Fields** (19 fields)
| Field | Type | Values/Options | Test Case Required |
|-------|------|----------------|-------------------|
| `name` | string | min=1, max=100 chars | ✅ TC 5.1 (valid), TC (empty), TC (too long) |
| `description` | string | optional | ✅ TC 5.1 (with), TC (without) |
| `category` | string | max=50 chars | ✅ TC 5.1 (web_server, database, network) |
| `tags` | list[string] | empty or multiple | ✅ TC (no tags), TC (multiple tags) |
| `enabled` | boolean | true/false | ✅ TC 5.9 (toggle) |
| `auto_execute` | boolean | true/false | ✅ TC 5.5 (manual), TC 5.6 (auto) |
| `approval_required` | boolean | true/false | ✅ TC 5.5 (true), TC 5.6 (false) |
| `approval_roles` | list[string] | ["operator", "engineer", "admin"] | ⚠️ **MISSING** - Test different role combinations |
| `approval_timeout_minutes` | int | 1-1440 | ⚠️ **MISSING** - Test timeout expiration |
| `max_executions_per_hour` | int | 1-100 | ✅ TC 5.10 (rate limiting) |
| `cooldown_minutes` | int | 0-1440 | ✅ TC 5.11 (cooldown period) |
| `default_server_id` | UUID | optional | ⚠️ **MISSING** - Test with default server |
| `target_os_filter` | list[string] | ["linux", "windows"] | ⚠️ **MISSING** - Test OS filtering |
| `target_from_alert` | boolean | true/false | ⚠️ **MISSING** - Test alert-based targeting |
| `target_alert_label` | string | "instance" (default) | ⚠️ **MISSING** - Test custom label |
| `notifications_json` | dict | {"on_start": [], "on_success": [], "on_failure": []} | ⚠️ **MISSING** - Test notifications |
| `documentation_url` | string | optional URL | ✅ TC 5.1 (included) |
| `steps` | list | RunbookStepCreate[] | ✅ TC 5.1-5.4 (various step types) |
| `triggers` | list | RunbookTriggerCreate[] | ⚠️ **PARTIAL** - Need more trigger tests |

**Missing Test Cases Identified**: 8
**Action Required**: Add test cases for approval roles, timeouts, OS filtering, notifications

---

### 1.2 Runbook Step Fields

#### **RunbookStepBase Fields** (38 fields!)
| Field | Type | Values/Options | Test Coverage |
|-------|------|----------------|---------------|
| **Basic** ||||
| `name` | string | 1-100 chars | ✅ TC 5.1 |
| `description` | string | optional | ✅ TC 5.1 |
| `step_type` | string | "command", "api" | ✅ TC 5.1 (command), TC 5.3 (api) |
| **Command Fields** ||||
| `command_linux` | string | Shell command | ✅ TC 5.1 |
| `command_windows` | string | PowerShell/CMD | ⚠️ **MISSING** - Windows command test |
| `target_os` | string | "any", "linux", "windows" | ⚠️ **MISSING** - OS targeting test |
| **API Fields** (14 fields)||||
| `api_credential_profile_id` | UUID | Reference to credentials | ⚠️ **MISSING** - API credential test |
| `api_method` | string | GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS | ⚠️ **PARTIAL** - Only POST tested in TC 5.3 |
| `api_endpoint` | string | URL with Jinja2 templating | ✅ TC 5.3, TC 5.4 (templating) |
| `api_headers_json` | dict | Custom headers | ✅ TC 5.3 (Authorization) |
| `api_body` | string | JSON payload | ✅ TC 5.3 |
| `api_body_type` | string | "json", "form", "raw", "template" | ⚠️ **MISSING** - Only "json" tested |
| `api_query_params_json` | dict | URL parameters | ⚠️ **MISSING** - Query params test |
| `api_expected_status_codes` | list[int] | [200, 201, 202, 204] | ✅ TC 5.3 |
| `api_response_extract_json` | dict | JSONPath/regex extraction | ⚠️ **MISSING** - Response extraction test |
| `api_follow_redirects` | boolean | true/false | ⚠️ **MISSING** - Redirect test |
| `api_retry_on_status_codes` | list[int] | [408, 429, 500, 502, 503, 504] | ⚠️ **MISSING** - Retry logic test |
| **Execution Options** ||||
| `timeout_seconds` | int | 1-3600 | ✅ TC 5.1 |
| `requires_elevation` | boolean | true/false (sudo) | ⚠️ **MISSING** - Sudo execution test |
| `working_directory` | string | optional path | ⚠️ **MISSING** - Working directory test |
| `environment_json` | dict | Environment variables | ⚠️ **MISSING** - Env vars test |
| **Error Handling** ||||
| `continue_on_fail` | boolean | true/false | ⚠️ **MISSING** - Continue on failure test |
| `retry_count` | int | 0-5 | ⚠️ **MISSING** - Step retry test |
| `retry_delay_seconds` | int | 1-300 | ⚠️ **MISSING** - Retry delay test |
| **Validation** ||||
| `expected_exit_code` | int | 0 (default) | ✅ TC 5.7 (failure detection) |
| `expected_output_pattern` | string | Regex pattern | ⚠️ **MISSING** - Output validation test |
| **Variable Extraction** ||||
| `output_variable` | string | Variable name | ⚠️ **MISSING** - Variable extraction test |
| `output_extract_pattern` | string | Regex for extraction | ⚠️ **MISSING** - Pattern extraction test |
| **Rollback** ||||
| `rollback_command_linux` | string | Rollback command | ✅ TC 5.8 (rollback) |
| `rollback_command_windows` | string | Windows rollback | ⚠️ **MISSING** - Windows rollback test |

**Total Fields**: 38
**Tested Fields**: 12
**Missing Test Coverage**: 26 fields (68% untested!)

**Critical Missing Tests**:
1. Windows commands and rollback
2. All HTTP methods (GET, PUT, DELETE, PATCH, HEAD, OPTIONS)
3. API body types (form, raw, template)
4. API query parameters
5. Response extraction (JSONPath/regex)
6. Retry logic with delays
7. Environment variables
8. Working directory
9. Sudo/elevation
10. Output pattern validation
11. Variable extraction
12. Continue on failure

---

### 1.3 Runbook Execution Fields

#### **ExecuteRunbookRequest Fields** (6 fields)
| Field | Type | Values/Options | Test Coverage |
|-------|------|----------------|---------------|
| `server_id` | UUID | Optional server override | ⚠️ **MISSING** - Server override test |
| `alert_id` | UUID | Link to alert context | ✅ TC 5.5 (with alert) |
| `dry_run` | boolean | true/false | ⚠️ **MISSING** - Dry run test |
| `variables` | dict | Runtime parameters | ⚠️ **MISSING** - Runtime variables test |
| `bypass_cooldown` | boolean | true/false | ⚠️ **MISSING** - Cooldown bypass test |
| `bypass_blackout` | boolean | true/false | ⚠️ **MISSING** - Blackout bypass test |

**Coverage**: 1/6 (17%)
**Missing**: 5 critical execution options

---

### 1.4 Runbook Trigger Fields

#### **RunbookTriggerBase Fields** (11 fields)
| Field | Type | Values/Options | Test Coverage |
|-------|------|----------------|---------------|
| `alert_name_pattern` | string | Glob/regex pattern | ⚠️ **MISSING** - Trigger pattern test |
| `severity_pattern` | string | critical, warning, info | ⚠️ **MISSING** |
| `instance_pattern` | string | server pattern | ⚠️ **MISSING** |
| `job_pattern` | string | job pattern | ⚠️ **MISSING** |
| `label_matchers_json` | dict | Custom label matching | ⚠️ **MISSING** |
| `annotation_matchers_json` | dict | Annotation matching | ⚠️ **MISSING** |
| `min_duration_seconds` | int | Alert duration threshold | ⚠️ **MISSING** |
| `min_occurrences` | int | Alert count threshold | ⚠️ **MISSING** |
| `priority` | int | 1-1000 | ⚠️ **MISSING** |
| `enabled` | boolean | true/false | ⚠️ **MISSING** |

**Coverage**: 0/11 (0%)
**All trigger fields untested!**

---

### 1.5 Circuit Breaker Fields

#### **CircuitBreakerResponse Fields** (15 fields)
| Field | Type | Purpose | Test Coverage |
|-------|------|---------|---------------|
| `state` | string | "closed", "open", "half_open" | ✅ TC 5.12 |
| `failure_count` | int | Consecutive failures | ✅ TC 5.12 |
| `failure_threshold` | int | Max failures before open | ✅ TC 5.12 |
| `failure_window_minutes` | int | Window for failure counting | ⚠️ **MISSING** |
| `open_duration_minutes` | int | How long circuit stays open | ⚠️ **MISSING** |
| `manually_opened` | boolean | Manual override flag | ✅ TC 5.13 |
| Other tracking fields | - | timestamps, counts | ✅ Implicit |

**Coverage**: 3/7 core fields

---

### 1.6 Blackout Window Fields

#### **BlackoutWindowBase Fields** (14 fields)
| Field | Type | Values/Options | Test Coverage |
|-------|------|----------------|---------------|
| `name` | string | Window name | ✅ TC 5.14 |
| `description` | string | Optional description | ✅ TC 5.14 |
| `recurrence` | string | "once", "daily", "weekly", "monthly" | ⚠️ **PARTIAL** - Only "once" tested |
| `start_time` | datetime | For "once" recurrence | ✅ TC 5.14 |
| `end_time` | datetime | For "once" recurrence | ✅ TC 5.14 |
| `daily_start_time` | string | "HH:MM" format | ⚠️ **MISSING** - Daily recurrence |
| `daily_end_time` | string | "HH:MM" format | ⚠️ **MISSING** |
| `days_of_week` | list[int] | 0-6 (Monday-Sunday) | ⚠️ **MISSING** - Weekly recurrence |
| `days_of_month` | list[int] | 1-31 | ⚠️ **MISSING** - Monthly recurrence |
| `timezone` | string | "UTC", "America/New_York", etc. | ⚠️ **MISSING** - Timezone test |
| `applies_to` | string | "auto_only", "all" | ⚠️ **MISSING** |
| `applies_to_runbook_ids` | list[UUID] | Specific runbooks | ⚠️ **MISSING** |
| `enabled` | boolean | true/false | ✅ TC 5.14 |

**Coverage**: 4/14 (29%)
**Missing**: Recurring blackout windows, timezone handling, selective application

---

## 2. ALERT API - COMPLETE FIELD COVERAGE

### 2.1 Alert Webhook Fields

#### **AlertmanagerWebhook Fields** (9 fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `version` | string | "4" | ✅ TC 1.1 |
| `groupKey` | string | Alert group ID | ✅ TC 1.1 |
| `status` | string | "firing", "resolved" | ✅ TC 1.1, TC 1.2 |
| `receiver` | string | "remediation-engine" | ✅ TC 1.1 |
| `groupLabels` | dict | Grouping labels | ✅ TC 1.1 |
| `commonLabels` | dict | Common labels | ✅ TC 1.1 |
| `commonAnnotations` | dict | Common annotations | ✅ TC 1.1 |
| `externalURL` | string | Alertmanager URL | ✅ TC 1.1 |
| `alerts` | list | AlertmanagerAlert[] | ✅ TC 1.1 |

**Coverage**: 9/9 (100%) ✅

#### **AlertmanagerAlert Fields** (7 fields)
| Field | Type | Test Coverage |
|-------|------|---------------|
| `status` | string | ✅ TC 1.1, TC 1.2 |
| `labels` | dict | ✅ TC 1.1 (alertname, severity, instance, job) |
| `annotations` | dict | ✅ TC 1.1 (summary, description) |
| `startsAt` | string | ✅ TC 1.1 |
| `endsAt` | string | ✅ TC 1.2 (resolved) |
| `generatorURL` | string | ✅ TC 1.1 |
| `fingerprint` | string | ✅ TC 1.1 |

**Coverage**: 7/7 (100%) ✅

---

### 2.2 Alert Query Parameters

#### **GET /api/alerts Query Parameters**
| Parameter | Type | Values | Test Coverage |
|-----------|------|--------|---------------|
| `page` | int | ≥1 | ✅ TC 1.4 |
| `page_size` | int | 1-100 | ✅ TC 1.4 |
| `status` | string | "firing", "resolved" | ✅ TC 1.4 |
| `severity` | string | "critical", "warning", "info" | ✅ TC 1.4 |
| `alertname` | string | Alert name filter | ✅ TC 1.4 |
| `instance` | string | Instance filter | ⚠️ **MISSING** |
| `job` | string | Job filter | ⚠️ **MISSING** |
| `analyzed` | boolean | true/false | ⚠️ **MISSING** |
| `from_date` | datetime | Date range start | ⚠️ **MISSING** |
| `to_date` | datetime | Date range end | ⚠️ **MISSING** |
| `sort_by` | string | "timestamp", "severity" | ⚠️ **MISSING** |
| `sort_order` | string | "asc", "desc" | ⚠️ **MISSING** |

**Coverage**: 5/12 (42%)
**Missing**: Instance/job filtering, analyzed flag, date range, sorting

---

### 2.3 Analyze Request Fields

#### **AnalyzeRequest Fields** (2 fields)
| Field | Type | Purpose | Test Coverage |
|-------|------|---------|---------------|
| `force` | boolean | Re-analyze even if already analyzed | ⚠️ **MISSING** - Force re-analysis |
| `llm_provider_id` | UUID | Use specific LLM provider | ⚠️ **MISSING** - Provider selection |

**Coverage**: 0/2 (0%)
**Both fields untested!**

---

## 3. CHAT API - COMPLETE FIELD COVERAGE

### 3.1 Chat Session Creation

#### **ChatSessionCreate Fields** (estimated 5-6 fields)
| Field | Type | Purpose | Test Coverage |
|-------|------|---------|---------------|
| `title` | string | Session title | ✅ TC 3.6 |
| `alert_id` | UUID | Link to alert | ✅ TC 3.6 |
| `llm_provider_id` | UUID | Select provider | ✅ TC 3.6 |
| `system_prompt` | string | Custom system prompt | ⚠️ **MISSING** |
| `context_json` | dict | Additional context | ⚠️ **MISSING** |
| `max_history` | int | Message history limit | ⚠️ **MISSING** |

**Coverage**: 3/6 (50%)

---

### 3.2 Chat Message Fields

#### **ChatMessageCreate Fields**
| Field | Type | Purpose | Test Coverage |
|-------|------|---------|---------------|
| `content` | string | Message text | ✅ TC 3.7 |
| `role` | string | "user", "assistant", "system" | ⚠️ **PARTIAL** - Only "user" tested |
| `attachments` | list | File attachments | ⚠️ **MISSING** |
| `metadata_json` | dict | Custom metadata | ⚠️ **MISSING** |

**Coverage**: 1/4 (25%)

---

## 4. KNOWLEDGE BASE API - COMPLETE FIELD COVERAGE

### 4.1 Document Creation Fields

#### **DesignDocumentCreate Fields** (8-10 fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `title` | string | Document title | ✅ TC 7.1, 7.2, 7.3, 7.4 |
| `content` | string | Document content | ✅ TC 7.1-7.4 |
| `content_type` | string | "markdown", "pdf", "html", "yaml" | ✅ All 4 types tested |
| `application_id` | UUID | Link to application | ✅ TC 7.1 |
| `tags` | list[string] | Searchable tags | ✅ TC 7.1, TC 7.13 |
| `source_url` | string | Original URL | ⚠️ **MISSING** |
| `version` | string | Document version | ⚠️ **MISSING** |
| `authors` | list[string] | Document authors | ⚠️ **MISSING** |
| `metadata_json` | dict | Custom metadata | ⚠️ **MISSING** |

**Coverage**: 5/9 (56%)

---

### 4.2 Document Search Fields

#### **DocumentSearchRequest Fields**
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `query` | string | Search query | ✅ TC 7.6, TC 7.7 |
| `search_type` | string | "full_text", "similarity" | ✅ Both tested |
| `application_id` | UUID | Filter by app | ✅ TC 7.8 |
| `tags` | list[string] | Filter by tags | ⚠️ **MISSING** |
| `content_type` | string | Filter by type | ⚠️ **MISSING** |
| `limit` | int | Result limit | ✅ TC 7.6, TC 7.7 |
| `min_score` | float | Similarity threshold | ⚠️ **MISSING** |
| `date_from` | datetime | Date range filter | ⚠️ **MISSING** |
| `date_to` | datetime | Date range filter | ⚠️ **MISSING** |

**Coverage**: 4/9 (44%)

---

## 5. SCHEDULER API - COMPLETE FIELD COVERAGE

### 5.1 Schedule Creation Fields

#### **ScheduledJobCreate Fields** (10+ fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `name` | string | Schedule name | ✅ TC 6.1, 6.2, 6.3 |
| `runbook_id` | UUID | Runbook to execute | ✅ All schedule tests |
| `schedule_type` | string | "cron", "interval", "date" | ✅ All 3 tested |
| `cron_expression` | string | Cron syntax | ✅ TC 6.1 |
| `interval_minutes` | int | Interval in minutes | ✅ TC 6.2 |
| `run_at` | datetime | Specific datetime | ✅ TC 6.3 |
| `enabled` | boolean | Active/inactive | ✅ TC 6.4 (pause/resume) |
| `misfire_grace_time` | int | Late execution grace period | ✅ TC 6.6 |
| `max_instances` | int | Prevent concurrent runs | ⚠️ **MISSING** |
| `execution_params` | dict | Parameters for runbook | ⚠️ **MISSING** |
| `timezone` | string | Timezone for scheduling | ⚠️ **MISSING** |
| `end_date` | datetime | Schedule expiration | ⚠️ **MISSING** |

**Coverage**: 7/12 (58%)

---

## 6. APPLICATION REGISTRY - COMPLETE FIELD COVERAGE

### 6.1 Application Creation Fields

#### **ApplicationCreate Fields** (10+ fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `name` | string | Application name | ✅ TC 8.1 |
| `description` | string | Description | ✅ TC 8.1 |
| `team_owner` | string | Owning team | ✅ TC 8.1 |
| `criticality` | string | "critical", "high", "medium", "low" | ✅ TC 8.1, TC 8.7 |
| `tech_stack` | list[string] | Technologies used | ✅ TC 8.1, TC 8.7 |
| `alert_matching_rules` | dict | Auto-mapping rules | ✅ TC 8.5 |
| `repository_url` | string | Source code URL | ⚠️ **MISSING** |
| `documentation_url` | string | Docs URL | ⚠️ **MISSING** |
| `runbook_ids` | list[UUID] | Associated runbooks | ⚠️ **MISSING** |
| `on_call_rotation` | dict | PagerDuty/etc config | ⚠️ **MISSING** |
| `slo_targets` | dict | SLO definitions | ⚠️ **MISSING** |

**Coverage**: 6/11 (55%)

---

### 6.2 Component Creation Fields

#### **ComponentCreate Fields** (8 fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `name` | string | Component name | ✅ TC 8.2 |
| `component_type` | string | "compute", "database", "cache", "queue", "storage", "network" | ⚠️ **PARTIAL** - Only "compute" tested |
| `description` | string | Description | ✅ TC 8.2 |
| `endpoints` | list[string] | API/service endpoints | ✅ TC 8.2 |
| `health_check_url` | string | Health check endpoint | ✅ TC 8.2 |
| `version` | string | Component version | ⚠️ **MISSING** |
| `replicas` | int | Instance count | ⚠️ **MISSING** |
| `metadata_json` | dict | Custom metadata | ⚠️ **MISSING** |

**Coverage**: 4/8 (50%)

---

## 7. ITSM INTEGRATION - COMPLETE FIELD COVERAGE

### 7.1 ITSM Integration Fields

#### **ITSMIntegrationCreate Fields** (8+ fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `name` | string | Integration name | ✅ TC 9.1, 9.2 |
| `integration_type` | string | "servicenow", "jira", "github", "generic" | ✅ ServiceNow & Jira tested |
| `config` | dict | Provider-specific config | ✅ TC 9.1, 9.2 |
| `enabled` | boolean | Active/inactive | ✅ TC 9.9 |
| `sync_interval` | int | Minutes between syncs | ⚠️ **PARTIAL** - Config included but not tested |
| `retry_failed` | boolean | Auto-retry failed syncs | ⚠️ **MISSING** |
| `filters` | dict | Filter which changes to sync | ⚠️ **MISSING** |
| `field_mappings` | dict | Map fields to internal schema | ⚠️ **MISSING** |

**Coverage**: 4/8 (50%)

---

### 7.2 ServiceNow-Specific Config Fields

#### **ServiceNow Config** (8+ subfields)
| Field | Type | Purpose | Test Coverage |
|-------|------|---------|---------------|
| `instance_url` | string | ServiceNow instance | ✅ TC 9.1 |
| `username` | string | API username | ✅ TC 9.1 |
| `password` | string | API password (encrypted) | ✅ TC 9.1 |
| `change_table` | string | Table name | ✅ TC 9.1 |
| `sync_interval` | int | Sync frequency | ✅ TC 9.1 |
| `query_filter` | string | ServiceNow query | ⚠️ **MISSING** |
| `fields_to_sync` | list | Specific fields | ⚠️ **MISSING** |
| `use_oauth` | boolean | OAuth vs Basic auth | ⚠️ **MISSING** |

**Coverage**: 5/8 (63%)

---

### 7.3 Jira-Specific Config Fields

#### **Jira Config** (7+ subfields)
| Field | Type | Purpose | Test Coverage |
|-------|------|---------|---------------|
| `base_url` | string | Jira instance URL | ✅ TC 9.2 |
| `email` | string | API email | ✅ TC 9.2 |
| `api_token` | string | API token | ✅ TC 9.2 |
| `project_key` | string | Jira project | ✅ TC 9.2 |
| `sync_interval` | int | Sync frequency | ✅ TC 9.2 |
| `jql_filter` | string | JQL query for filtering | ⚠️ **MISSING** |
| `issue_types` | list | Types to sync | ⚠️ **MISSING** |

**Coverage**: 5/7 (71%)

---

## 8. OBSERVABILITY QUERY API - FIELD COVERAGE

### 8.1 Query Request Fields

#### **ObservabilityQueryRequest Fields** (6+ fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `query` | string | Natural language query | ✅ TC 10.1, 10.2, 10.3 |
| `context` | dict | Additional context | ✅ TC 10.1 (time_range), TC 10.3 (service) |
| `target_language` | string | "promql", "logql", "traceql", "auto" | ⚠️ **MISSING** - "auto" detection |
| `datasource_id` | UUID | Specific datasource | ⚠️ **MISSING** |
| `time_range` | string | "1h", "24h", "7d" | ✅ TC 10.1 |
| `limit` | int | Result limit | ⚠️ **MISSING** |
| `format` | string | Response format | ⚠️ **MISSING** |

**Coverage**: 3/7 (43%)

---

## 9. DASHBOARD API - FIELD COVERAGE

### 9.1 Panel Creation Fields

#### **PanelCreate Fields** (15+ fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `title` | string | Panel title | ✅ TC 11.3-11.6 |
| `datasource_id` | UUID | Datasource reference | ✅ TC 11.3 |
| `panel_type` | string | "graph", "gauge", "stat", "table", "heatmap", "bar", "pie" | ⚠️ **PARTIAL** - Only 4/7 types tested |
| `query` | string | PromQL query | ✅ TC 11.3-11.6 |
| `legend_format` | string | Legend template | ✅ TC 11.3 |
| `unit` | string | Value unit | ✅ TC 11.3, 11.4 |
| `threshold` | dict | Warning/critical thresholds | ✅ TC 11.3, 11.4 |
| `min_value` | int/float | Gauge min | ✅ TC 11.4 |
| `max_value` | int/float | Gauge max | ✅ TC 11.4 |
| `decimals` | int | Decimal places | ⚠️ **MISSING** |
| `refresh_interval` | int | Auto-refresh seconds | ⚠️ **MISSING** |
| `time_range_override` | string | Panel-specific time range | ⚠️ **MISSING** |
| `transformations` | list | Data transformations | ⚠️ **MISSING** |
| `alert_rules` | dict | Panel alerting | ⚠️ **MISSING** |

**Coverage**: 8/14 (57%)
**Missing Panel Types**: Heatmap, Bar, Pie

---

### 9.2 Dashboard Creation Fields

#### **DashboardCreate Fields** (12+ fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `title` | string | Dashboard title | ✅ TC 11.2 |
| `description` | string | Description | ✅ TC 11.2 |
| `time_range` | string | Default time range | ✅ TC 11.2 |
| `refresh_interval` | int | Auto-refresh seconds | ✅ TC 11.2 |
| `is_public` | boolean | Public/private | ✅ TC 11.2 |
| `is_favorite` | boolean | Starred dashboard | ⚠️ **PARTIAL** - TC 11.15 update only |
| `tags` | list[string] | Dashboard tags | ⚠️ **MISSING** |
| `folder_id` | UUID | Organization folder | ⚠️ **MISSING** |
| `layout` | string | "grid", "list" | ⚠️ **MISSING** |
| `template_variables` | list | Dashboard variables | ⚠️ **MISSING** |
| `annotations` | list | Event annotations | ⚠️ **MISSING** |
| `timezone` | string | Dashboard timezone | ⚠️ **MISSING** |

**Coverage**: 5/12 (42%)

---

## 10. USER MANAGEMENT - FIELD COVERAGE

### 10.1 User Creation Fields

#### **UserCreate Fields** (6 fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `username` | string | Unique username | ✅ TC 15.1 |
| `email` | string | Email address | ✅ TC 15.1 |
| `password` | string | Plain text (hashed) | ✅ TC 15.1 |
| `role` | string | "admin", "engineer", "operator" | ✅ TC 15.1 |
| `full_name` | string | Display name | ✅ TC 15.1 |
| `is_active` | boolean | Account status | ⚠️ **MISSING** - Inactive user test |

**Coverage**: 5/6 (83%)

---

### 10.2 Group Creation Fields

#### **GroupCreate Fields** (3+ fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `name` | string | Group name | ✅ TC 15.9 |
| `description` | string | Description | ✅ TC 15.9 |
| `permissions` | list[string] | Permission list | ✅ TC 15.9 |
| `parent_group_id` | UUID | Nested groups | ⚠️ **MISSING** |

**Coverage**: 3/4 (75%)

---

### 10.3 Role Creation Fields

#### **RoleCreate Fields** (3 fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `name` | string | Role name | ✅ TC 15.16 |
| `permissions` | list[string] | Permission list | ✅ TC 15.16 |
| `description` | string | Role description | ⚠️ **MISSING** |

**Coverage**: 2/3 (67%)

---

## 11. LLM PROVIDER - FIELD COVERAGE

### 11.1 Provider Creation Fields

#### **LLMProviderCreate Fields** (9 fields)
| Field | Type | Values | Test Coverage |
|-------|------|--------|---------------|
| `name` | string | Provider name | ✅ TC 3.1, 3.2, 3.3 |
| `provider_type` | string | "anthropic", "openai", "google", "ollama", "azure" | ✅ All 5 tested (TC 3.1-3.3) |
| `model_id` | string | Model name | ✅ TC 3.1-3.3 |
| `api_key` | string | API key (encrypted) | ✅ TC 3.1, 3.2 |
| `api_base_url` | string | Custom endpoint | ✅ TC 3.3 (Ollama) |
| `is_default` | boolean | Default provider | ✅ TC 3.1 |
| `is_enabled` | boolean | Active/inactive | ⚠️ **MISSING** - Disabled provider test |
| `config_json` | dict | temp, max_tokens, etc. | ✅ TC 3.1, 3.2 |
| `timeout` | int | Request timeout | ⚠️ **MISSING** |

**Coverage**: 7/9 (78%)

---

## SUMMARY OF FIELD COVERAGE GAPS

### Critical Gaps (High Priority)

#### **1. Runbook Execution - 26 untested fields**
- Windows commands and rollback
- All HTTP methods besides POST
- API body types (form, raw, template)
- Retry logic and delays
- Environment variables
- Output validation and extraction
- Runtime variables
- Dry run mode
- Server override
- Cooldown/blackout bypass

#### **2. Runbook Triggers - 11 untested fields**
- All trigger pattern matching
- Label and annotation matchers
- Duration and occurrence thresholds
- Priority evaluation

#### **3. Alert Query Parameters - 7 untested parameters**
- Instance/job filtering
- Analyzed flag filtering
- Date range filtering
- Sorting options

#### **4. Scheduler - 5 untested fields**
- Max concurrent instances
- Execution parameters
- Timezone handling
- Schedule expiration

#### **5. Dashboard Panels - Missing panel types**
- Heatmap panels
- Bar chart panels
- Pie chart panels
- Panel transformations
- Alert rules on panels

---

## RECOMMENDED ADDITIONAL TEST CASES

### Phase 1: Critical Missing Fields (40 new test cases)

**Runbook Execution (20 tests)**:
1. TC 5.21: Windows command execution
2. TC 5.22: Windows rollback execution
3. TC 5.23: API GET request
4. TC 5.24: API PUT request
5. TC 5.25: API DELETE request
6. TC 5.26: API PATCH request
7. TC 5.27: API form body type
8. TC 5.28: API raw body type
9. TC 5.29: API template body type
10. TC 5.30: API query parameters
11. TC 5.31: API response extraction (JSONPath)
12. TC 5.32: Step retry with delay
13. TC 5.33: Environment variables
14. TC 5.34: Working directory
15. TC 5.35: Sudo/elevation
16. TC 5.36: Output pattern validation
17. TC 5.37: Variable extraction
18. TC 5.38: Continue on failure
19. TC 5.39: Dry run execution
20. TC 5.40: Runtime variables

**Runbook Triggers (10 tests)**:
21. TC 5.41: Alert name pattern trigger
22. TC 5.42: Severity pattern trigger
23. TC 5.43: Instance pattern trigger
24. TC 5.44: Job pattern trigger
25. TC 5.45: Label matchers
26. TC 5.46: Annotation matchers
27. TC 5.47: Min duration threshold
28. TC 5.48: Min occurrences threshold
29. TC 5.49: Trigger priority evaluation
30. TC 5.50: Enable/disable trigger

**Alert Query Parameters (7 tests)**:
31. TC 1.6: Filter by instance
32. TC 1.7: Filter by job
33. TC 1.8: Filter by analyzed flag
34. TC 1.9: Date range filtering
35. TC 1.10: Sort by timestamp
36. TC 1.11: Sort by severity
37. TC 1.12: Descending sort order

**Scheduler (3 tests)**:
38. TC 6.10: Max concurrent instances
39. TC 6.11: Execution parameters
40. TC 6.12: Timezone handling

---

### Phase 2: Secondary Gaps (30 new test cases)

**Dashboard Panels (10 tests)**:
41. TC 11.17: Heatmap panel
42. TC 11.18: Bar chart panel
43. TC 11.19: Pie chart panel
44. TC 11.20: Panel decimals formatting
45. TC 11.21: Panel refresh interval
46. TC 11.22: Time range override
47. TC 11.23: Panel transformations
48. TC 11.24: Panel alert rules
49. TC 11.25: Panel template from library
50. TC 11.26: Multi-query panel

**Blackout Windows (5 tests)**:
51. TC 5.51: Daily recurring blackout
52. TC 5.52: Weekly recurring blackout
53. TC 5.53: Monthly recurring blackout
54. TC 5.54: Timezone-aware blackout
55. TC 5.55: Runbook-specific blackout

**Knowledge Base (5 tests)**:
56. TC 7.15: Document version tracking
57. TC 7.16: Document source URL
58. TC 7.17: Document authors
59. TC 7.18: Search with tag filter
60. TC 7.19: Search with content type filter

**Application Registry (5 tests)**:
61. TC 8.11: All component types (database, cache, queue, storage, network)
62. TC 8.12: Component version tracking
63. TC 8.13: Component replicas
64. TC 8.14: Application repository URL
65. TC 8.15: Application SLO targets

**ITSM Integration (5 tests)**:
66. TC 9.11: ServiceNow query filter
67. TC 9.12: ServiceNow OAuth authentication
68. TC 9.13: Jira JQL filter
69. TC 9.14: Jira issue type filter
70. TC 9.15: Generic ITSM connector

---

## FIELD COVERAGE SCORECARD

| API / Feature | Total Fields | Tested Fields | Coverage % | Status |
|---------------|--------------|---------------|------------|--------|
| **Runbook Step** | 38 | 12 | 32% | 🔴 Critical |
| **Runbook Execution** | 6 | 1 | 17% | 🔴 Critical |
| **Runbook Trigger** | 11 | 0 | 0% | 🔴 Critical |
| **Blackout Window** | 14 | 4 | 29% | 🔴 Critical |
| **Alert Webhook** | 16 | 16 | 100% | ✅ Complete |
| **Alert Query** | 12 | 5 | 42% | 🟡 Moderate |
| **Analyze Request** | 2 | 0 | 0% | 🔴 Critical |
| **Chat Session** | 6 | 3 | 50% | 🟡 Moderate |
| **Chat Message** | 4 | 1 | 25% | 🔴 Critical |
| **Knowledge Doc** | 9 | 5 | 56% | 🟡 Moderate |
| **Knowledge Search** | 9 | 4 | 44% | 🟡 Moderate |
| **Scheduler** | 12 | 7 | 58% | 🟡 Moderate |
| **Application** | 11 | 6 | 55% | 🟡 Moderate |
| **Component** | 8 | 4 | 50% | 🟡 Moderate |
| **ITSM Integration** | 8 | 4 | 50% | 🟡 Moderate |
| **ServiceNow Config** | 8 | 5 | 63% | 🟡 Moderate |
| **Jira Config** | 7 | 5 | 71% | 🟡 Moderate |
| **Observability Query** | 7 | 3 | 43% | 🟡 Moderate |
| **Panel** | 14 | 8 | 57% | 🟡 Moderate |
| **Dashboard** | 12 | 5 | 42% | 🟡 Moderate |
| **User** | 6 | 5 | 83% | 🟢 Good |
| **Group** | 4 | 3 | 75% | 🟢 Good |
| **Role** | 3 | 2 | 67% | 🟡 Moderate |
| **LLM Provider** | 9 | 7 | 78% | 🟢 Good |
| **Circuit Breaker** | 7 | 3 | 43% | 🟡 Moderate |

**Overall Coverage**: ~48% (estimated)
**Target**: 90%+
**Gap**: 70 additional test cases needed

---

## ACTION PLAN

### Immediate (Week 1)
1. Add 20 runbook execution field tests (highest priority)
2. Add 10 runbook trigger tests
3. Add 7 alert query parameter tests

### Short-term (Week 2-3)
4. Add 10 dashboard panel tests (missing types)
5. Add 5 blackout window tests (recurring)
6. Add 5 ITSM filter tests

### Medium-term (Week 4-5)
7. Add remaining knowledge base tests
8. Add application/component field tests
9. Add chat/analyze request tests

---

**END OF API FIELD COVERAGE MATRIX**
