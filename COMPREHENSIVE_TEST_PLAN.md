# COMPREHENSIVE TEST PLAN - REMEDIATION ENGINE

**Version**: 1.0
**Date**: 2025-12-29
**Branch**: claude/review-grafana-docs-Xr3H8

---

## TABLE OF CONTENTS

1. [Test Strategy & Approach](#test-strategy--approach)
2. [Test Environment Setup](#test-environment-setup)
3. [Feature 1: Alert Ingestion & Processing](#feature-1-alert-ingestion--processing)
4. [Feature 2: Rules Engine](#feature-2-rules-engine)
5. [Feature 3: AI Analysis & Chat](#feature-3-ai-analysis--chat)
6. [Feature 4: Alert Clustering](#feature-4-alert-clustering)
7. [Feature 5: Auto-Remediation Engine](#feature-5-auto-remediation-engine)
8. [Feature 6: Scheduled Runbooks](#feature-6-scheduled-runbooks)
9. [Feature 7: Knowledge Base](#feature-7-knowledge-base)
10. [Feature 8: Application Registry](#feature-8-application-registry)
11. [Feature 9: Change Correlation & ITSM Integration](#feature-9-change-correlation--itsm-integration)
12. [Feature 10: Observability Integration](#feature-10-observability-integration)
13. [Feature 11: Dashboard Builder](#feature-11-dashboard-builder)
14. [Feature 12: Grafana Integration](#feature-12-grafana-integration)
15. [Feature 13: Terminal Access](#feature-13-terminal-access)
16. [Feature 14: Agent Mode](#feature-14-agent-mode)
17. [Feature 15: User Management & RBAC](#feature-15-user-management--rbac)
18. [Feature 16: Analytics & Metrics](#feature-16-analytics--metrics)
19. [Feature 17: Audit & Compliance](#feature-17-audit--compliance)
20. [Feature 18: Learning System](#feature-18-learning-system)
21. [Feature 19: Authentication & Security](#feature-19-authentication--security)
22. [Integration Test Scenarios](#integration-test-scenarios)
23. [Performance Test Scenarios](#performance-test-scenarios)
24. [Security Test Scenarios](#security-test-scenarios)

---

## TEST STRATEGY & APPROACH

### Testing Levels
1. **API Testing**: Test all REST endpoints with various inputs
2. **Functional Testing**: Verify business logic and workflows
3. **Integration Testing**: Test feature interactions and data flow
4. **End-to-End Testing**: Complete user journeys
5. **Performance Testing**: Load and stress testing
6. **Security Testing**: Authentication, authorization, data protection

### Test Data Requirements
- Test users with different roles (Admin, Engineer, Operator)
- Sample alerts from Prometheus/Alertmanager
- Sample runbooks (Linux/Windows commands, API calls)
- Knowledge base documents (Markdown, PDF, HTML)
- ITSM integration credentials
- Grafana datasource configurations
- LLM provider credentials

### Success Criteria
- All API endpoints return expected status codes
- Data persistence verified in database
- Business rules enforced correctly
- Error handling works as expected
- Security controls prevent unauthorized access
- Performance meets acceptable thresholds

---

## TEST ENVIRONMENT SETUP

### Prerequisites
```
1. Install dependencies: pip install -r requirements.txt
2. Database setup: PostgreSQL with pgvector extension
3. Environment variables configured (.env file)
4. Test LLM provider API key available
5. Test Prometheus/Alertmanager instance
6. Test Grafana instance (optional)
7. Test SSH server for terminal/runbook testing
```

### Test Users
```
Admin User:
- Username: test_admin
- Email: admin@test.com
- Role: Admin
- Password: Test@123456

Engineer User:
- Username: test_engineer
- Email: engineer@test.com
- Role: Engineer
- Password: Test@123456

Operator User:
- Username: test_operator
- Email: operator@test.com
- Role: Operator
- Password: Test@123456
```

---

## FEATURE 1: ALERT INGESTION & PROCESSING

### Test Case 1.1: Webhook Alert Ingestion - Firing Alert

**Objective**: Verify system can receive and process a firing alert from Alertmanager

**Prerequisites**:
- System is running
- Database is empty or clean state

**API Endpoint**: `POST /webhook/alerts`

**Test Steps**:
1. Send POST request to `/webhook/alerts` with valid Alertmanager payload:
```json
{
  "receiver": "remediation-engine",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighCPUUsage",
        "severity": "critical",
        "instance": "server-01",
        "job": "node-exporter"
      },
      "annotations": {
        "summary": "CPU usage is above 90%",
        "description": "Host server-01 has CPU usage above 90% for 5 minutes"
      },
      "startsAt": "2025-12-29T10:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://prometheus:9090/graph?g0.expr=...",
      "fingerprint": "abc123def456"
    }
  ],
  "groupLabels": {
    "alertname": "HighCPUUsage"
  },
  "commonLabels": {
    "severity": "critical"
  },
  "commonAnnotations": {},
  "externalURL": "http://alertmanager:9093"
}
```

2. Verify HTTP response:
   - Status code: 200
   - Response body: `{"status": "success", "alerts_processed": 1}`

3. Query alert via API: `GET /api/alerts`
   - Verify alert exists in response
   - Check fingerprint matches: "abc123def456"

4. Query specific alert: `GET /api/alerts/{alert_id}`
   - Verify all fields populated correctly
   - Status: "firing"
   - Severity: "critical"
   - Labels and annotations match

**Expected Results**:
- Alert created in database
- Fingerprint correctly generated
- Labels and annotations stored as JSON
- Status set to "firing"
- Timestamps correctly parsed

**Cleanup**:
- Delete test alert from database

---

### Test Case 1.2: Webhook Alert Ingestion - Resolved Alert

**Objective**: Verify system can update alert status when it resolves

**Prerequisites**:
- Alert from Test Case 1.1 exists in database

**API Endpoint**: `POST /webhook/alerts`

**Test Steps**:
1. Send POST request with same fingerprint but status "resolved":
```json
{
  "receiver": "remediation-engine",
  "status": "resolved",
  "alerts": [
    {
      "status": "resolved",
      "labels": {
        "alertname": "HighCPUUsage",
        "severity": "critical",
        "instance": "server-01",
        "job": "node-exporter"
      },
      "annotations": {
        "summary": "CPU usage is above 90%",
        "description": "Host server-01 has CPU usage above 90% for 5 minutes"
      },
      "startsAt": "2025-12-29T10:00:00Z",
      "endsAt": "2025-12-29T10:15:00Z",
      "generatorURL": "http://prometheus:9090/graph?g0.expr=...",
      "fingerprint": "abc123def456"
    }
  ]
}
```

2. Verify HTTP response: Status 200

3. Query alert: `GET /api/alerts/{alert_id}`
   - Verify status changed to "resolved"
   - Verify endsAt timestamp populated

**Expected Results**:
- Existing alert updated (not new alert created)
- Status changed to "resolved"
- Resolution timestamp recorded

---

### Test Case 1.3: Alert Statistics API

**Objective**: Verify alert statistics endpoint returns correct counts

**Prerequisites**:
- Multiple alerts with different severities and statuses

**API Endpoint**: `GET /api/alerts/stats`

**Test Steps**:
1. Create test alerts:
   - 3 critical firing alerts
   - 2 warning firing alerts
   - 1 critical resolved alert
   - 1 warning resolved alert

2. Call `GET /api/alerts/stats`

3. Verify response contains:
   - Total alerts: 7
   - Firing alerts: 5
   - Resolved alerts: 2
   - Critical alerts: 4
   - Warning alerts: 3

**Expected Results**:
- Correct counts by severity
- Correct counts by status
- Proper JSON structure

---

### Test Case 1.4: Alert Filtering and Pagination

**Objective**: Verify alerts can be filtered and paginated

**API Endpoint**: `GET /api/alerts`

**Test Steps**:
1. Create 25 test alerts with various attributes

2. Test pagination:
   - `GET /api/alerts?page=1&page_size=10`
   - Verify 10 alerts returned
   - Verify total count in response

3. Test filtering by severity:
   - `GET /api/alerts?severity=critical`
   - Verify only critical alerts returned

4. Test filtering by status:
   - `GET /api/alerts?status=firing`
   - Verify only firing alerts returned

5. Test filtering by alert name:
   - `GET /api/alerts?alertname=HighCPUUsage`
   - Verify only matching alerts returned

6. Test combined filters:
   - `GET /api/alerts?severity=critical&status=firing`
   - Verify both filters applied

**Expected Results**:
- Pagination works correctly
- Filters applied accurately
- Response includes total count and page info

---

### Test Case 1.5: Alert Detail View

**Objective**: Verify complete alert details can be retrieved

**API Endpoint**: `GET /api/alerts/{alert_id}`

**Test Steps**:
1. Create test alert with full details
2. Query specific alert by ID
3. Verify all fields present:
   - ID, fingerprint, alertname
   - Labels (JSON object)
   - Annotations (JSON object)
   - Status, severity
   - Timestamps (starts_at, ends_at)
   - Generator URL
   - Related entities (rule, cluster, application)

**Expected Results**:
- All alert fields returned
- JSON properly formatted
- Related entities included if applicable

---

## FEATURE 2: RULES ENGINE

### Test Case 2.1: Create Auto-Analyze Rule

**Objective**: Create a rule that triggers auto-analysis on matching alerts

**API Endpoint**: `POST /api/rules`

**Test Steps**:
1. Authenticate as admin user
2. Create rule via POST request:
```json
{
  "name": "Auto-analyze critical CPU alerts",
  "description": "Automatically analyze all critical CPU alerts",
  "pattern_type": "alertname",
  "pattern_value": "HighCPUUsage",
  "severity_filter": "critical",
  "action": "auto_analyze",
  "priority": 10,
  "enabled": true
}
```

3. Verify response:
   - Status: 201 Created
   - Response contains rule ID
   - All fields match request

4. Query rule: `GET /api/rules/{rule_id}`
   - Verify rule exists
   - Verify fields correct

**Expected Results**:
- Rule created successfully
- Rule persisted to database
- Rule returned in list: `GET /api/rules`

---

### Test Case 2.2: Rule Pattern Matching - Alert Name

**Objective**: Verify rule matches alerts by alert name pattern

**Prerequisites**:
- Rule from Test Case 2.1 exists

**Test Steps**:
1. Send alert with matching alertname via webhook
2. Verify alert created
3. Check if alert was auto-analyzed:
   - Query alert: `GET /api/alerts/{alert_id}`
   - Verify `analyzed` field is true
   - Verify `analyzer_id` is set
   - Verify `llm_provider_id` is set

**Expected Results**:
- Alert matched to rule
- Auto-analysis triggered
- Analysis result stored

---

### Test Case 2.3: Rule Pattern Matching - Severity

**Objective**: Verify rule only matches alerts with specified severity

**Prerequisites**:
- Rule from Test Case 2.1 (severity_filter: "critical")

**Test Steps**:
1. Send "critical" alert with matching alertname
   - Verify auto-analyzed

2. Send "warning" alert with same alertname
   - Verify NOT auto-analyzed (severity doesn't match)

**Expected Results**:
- Only critical alerts auto-analyzed
- Warning alerts ignored by rule

---

### Test Case 2.4: Rule Pattern Matching - Instance

**Objective**: Verify rule matches by instance pattern

**API Endpoint**: `POST /api/rules`

**Test Steps**:
1. Create rule with instance pattern:
```json
{
  "name": "Production server alerts",
  "pattern_type": "instance",
  "pattern_value": "prod-.*",
  "action": "auto_analyze",
  "priority": 5,
  "enabled": true
}
```

2. Send alert with instance "prod-server-01"
   - Verify matched and analyzed

3. Send alert with instance "dev-server-01"
   - Verify NOT matched

**Expected Results**:
- Regex pattern matching works
- Only matching instances trigger rule

---

### Test Case 2.5: Rule Pattern Matching - Job

**Objective**: Verify rule matches by job label

**Test Steps**:
1. Create rule with job pattern:
```json
{
  "name": "Node exporter alerts",
  "pattern_type": "job",
  "pattern_value": "node-exporter",
  "action": "auto_analyze",
  "priority": 3,
  "enabled": true
}
```

2. Send alert with job "node-exporter"
   - Verify matched

3. Send alert with job "application"
   - Verify NOT matched

**Expected Results**:
- Job-based matching works correctly

---

### Test Case 2.6: Rule Priority Evaluation

**Objective**: Verify higher priority rules evaluated first

**Test Steps**:
1. Create two overlapping rules:
   - Rule A: priority 10, action "auto_analyze"
   - Rule B: priority 5, action "ignore"
   - Both match same alert pattern

2. Send matching alert

3. Verify Rule A (higher priority) applied
   - Alert should be auto-analyzed (not ignored)

**Expected Results**:
- Higher priority rule takes precedence
- Only one rule action applied per alert

---

### Test Case 2.7: Rule Actions - Ignore

**Objective**: Verify "ignore" action prevents analysis

**Test Steps**:
1. Create rule with action "ignore":
```json
{
  "name": "Ignore info alerts",
  "pattern_type": "severity",
  "pattern_value": "info",
  "action": "ignore",
  "priority": 1,
  "enabled": true
}
```

2. Send alert with severity "info"

3. Verify alert stored but NOT analyzed
   - `analyzed` field should be false or null

**Expected Results**:
- Alert recorded
- No analysis performed
- Rule action "ignore" respected

---

### Test Case 2.8: Rule Actions - Manual

**Objective**: Verify "manual" action requires user trigger

**Test Steps**:
1. Create rule with action "manual"
2. Send matching alert
3. Verify alert NOT auto-analyzed
4. Manually trigger analysis: `POST /api/alerts/{alert_id}/analyze`
5. Verify analysis now performed

**Expected Results**:
- No automatic analysis
- Manual trigger works
- Analysis result stored

---

### Test Case 2.9: Rule Enable/Disable Toggle

**Objective**: Verify disabled rules don't trigger

**API Endpoint**: `PUT /api/rules/{rule_id}`

**Test Steps**:
1. Create enabled rule
2. Send matching alert - verify matched
3. Disable rule: `PUT /api/rules/{rule_id}` with `{"enabled": false}`
4. Send another matching alert - verify NOT matched
5. Re-enable rule
6. Send alert - verify matched again

**Expected Results**:
- Disabled rules ignored
- Enable/disable toggle works immediately

---

### Test Case 2.10: Update Rule

**Objective**: Verify rule can be updated

**API Endpoint**: `PUT /api/rules/{rule_id}`

**Test Steps**:
1. Create rule
2. Update pattern value:
```json
{
  "pattern_value": "NewAlertName"
}
```
3. Verify update successful
4. Send alert with new pattern - verify matched
5. Send alert with old pattern - verify NOT matched

**Expected Results**:
- Rule updated successfully
- New pattern applied immediately

---

### Test Case 2.11: Delete Rule

**Objective**: Verify rule can be deleted

**API Endpoint**: `DELETE /api/rules/{rule_id}`

**Test Steps**:
1. Create rule
2. Delete rule
3. Verify response: 204 No Content
4. Query rule: `GET /api/rules/{rule_id}`
   - Verify 404 Not Found

**Expected Results**:
- Rule deleted from database
- No longer appears in rule list

---

### Test Case 2.12: Test Rule Against Existing Alerts

**Objective**: Verify rule testing endpoint works

**API Endpoint**: `POST /api/rules/test`

**Test Steps**:
1. Create several test alerts in database
2. Test rule without creating it:
```json
{
  "pattern_type": "severity",
  "pattern_value": "critical",
  "severity_filter": null
}
```
3. Verify response shows matching alerts
4. Verify alerts not actually modified

**Expected Results**:
- Dry-run testing works
- Matching alerts identified
- No side effects on actual alerts

---

## FEATURE 3: AI ANALYSIS & CHAT

### Test Case 3.1: Configure LLM Provider - Anthropic

**Objective**: Create and configure Anthropic Claude provider

**API Endpoint**: `POST /api/settings/llm`

**Test Steps**:
1. Authenticate as admin
2. Create Anthropic provider:
```json
{
  "name": "Claude Sonnet",
  "provider_type": "anthropic",
  "api_key": "sk-ant-api03-...",
  "model_name": "claude-3-5-sonnet-20241022",
  "temperature": 0.7,
  "max_tokens": 4096,
  "is_default": true
}
```

3. Verify response: 201 Created
4. Verify API key encrypted in database
5. Test provider: `GET /api/settings/llm/{provider_id}/test`
   - Verify connection successful

**Expected Results**:
- Provider created
- API key encrypted
- Connection test passes

---

### Test Case 3.2: Configure LLM Provider - OpenAI

**Objective**: Configure OpenAI as alternative provider

**Test Steps**:
1. Create OpenAI provider:
```json
{
  "name": "GPT-4",
  "provider_type": "openai",
  "api_key": "sk-...",
  "model_name": "gpt-4-turbo-preview",
  "temperature": 0.5,
  "max_tokens": 8192,
  "is_default": false
}
```

2. Verify provider created
3. Test connection

**Expected Results**:
- Multiple providers can coexist
- Each provider independently configured

---

### Test Case 3.3: Configure LLM Provider - Ollama (Local)

**Objective**: Configure local Ollama provider

**Test Steps**:
1. Create Ollama provider:
```json
{
  "name": "Local Llama",
  "provider_type": "ollama",
  "base_url": "http://localhost:11434",
  "model_name": "llama2",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

2. Test connection (requires Ollama running locally)

**Expected Results**:
- Ollama provider configured
- No API key required

---

### Test Case 3.4: Manual Alert Analysis

**Objective**: Manually trigger AI analysis of an alert

**API Endpoint**: `POST /api/alerts/{alert_id}/analyze`

**Test Steps**:
1. Create test alert via webhook
2. Verify alert not yet analyzed
3. Trigger manual analysis:
   - `POST /api/alerts/{alert_id}/analyze`
   - Optional: specify provider `{"llm_provider_id": 123}`

4. Verify response contains analysis:
   - Root cause assessment
   - Recommended actions
   - Severity justification
   - Related runbooks/documents

5. Query alert again: `GET /api/alerts/{alert_id}`
   - Verify `analyzed` = true
   - Verify `analysis_result` populated
   - Verify `analyzer_id` and `llm_provider_id` set

**Expected Results**:
- AI analysis generated
- Analysis stored with alert
- Structured recommendations provided

---

### Test Case 3.5: Auto-Analysis via Rule

**Objective**: Verify auto-analysis triggered by rule

**Prerequisites**:
- Auto-analyze rule exists
- LLM provider configured

**Test Steps**:
1. Send alert matching auto-analyze rule
2. Wait for analysis to complete
3. Query alert
4. Verify analysis automatically generated

**Expected Results**:
- Analysis triggered automatically
- No manual intervention required

---

### Test Case 3.6: Create Chat Session

**Objective**: Create a chat session for troubleshooting

**API Endpoint**: `POST /api/chat/sessions`

**Test Steps**:
1. Authenticate as engineer
2. Create chat session:
```json
{
  "title": "Troubleshooting High CPU",
  "alert_id": 123,
  "llm_provider_id": 1
}
```

3. Verify response: 201 Created
4. Verify session ID returned
5. Query session: `GET /api/chat/sessions/{session_id}`

**Expected Results**:
- Chat session created
- Associated with alert
- Session persisted

---

### Test Case 3.7: Send Chat Message

**Objective**: Send messages in chat session

**API Endpoint**: `POST /api/chat/sessions/{session_id}/messages`

**Test Steps**:
1. Create chat session
2. Send message:
```json
{
  "content": "What could be causing high CPU usage on this server?"
}
```

3. Verify response contains:
   - User message echoed
   - AI assistant response
   - Message IDs
   - Token usage

4. Send follow-up message
5. Verify context maintained (AI remembers conversation)

**Expected Results**:
- Messages persisted
- AI responses relevant
- Conversation history maintained

---

### Test Case 3.8: Retrieve Chat History

**Objective**: Retrieve all messages in a session

**API Endpoint**: `GET /api/chat/sessions/{session_id}/messages`

**Test Steps**:
1. Create session with multiple messages
2. Query message history
3. Verify all messages returned in chronological order
4. Verify roles (user/assistant) correct

**Expected Results**:
- Complete message history
- Proper ordering
- All metadata included

---

### Test Case 3.9: List User's Chat Sessions

**Objective**: List all chat sessions for current user

**API Endpoint**: `GET /api/chat/sessions`

**Test Steps**:
1. Create multiple chat sessions
2. Query sessions list
3. Verify all user's sessions returned
4. Verify sessions sorted by creation date

**Expected Results**:
- All user sessions listed
- Other users' sessions NOT visible
- Proper filtering by user

---

### Test Case 3.10: Delete Chat Session

**Objective**: Delete a chat session

**API Endpoint**: `DELETE /api/chat/sessions/{session_id}`

**Test Steps**:
1. Create chat session
2. Delete session
3. Verify response: 204 No Content
4. Query session - verify 404
5. Verify associated messages also deleted

**Expected Results**:
- Session deleted
- Cascade delete messages
- No orphaned data

---

### Test Case 3.11: WebSocket Chat (Real-time)

**Objective**: Test real-time chat via WebSocket

**WebSocket Endpoint**: `WS /ws/chat/{session_id}`

**Test Steps**:
1. Create chat session
2. Connect to WebSocket
3. Send message via WebSocket
4. Verify response received via WebSocket
5. Verify streaming (if supported)
6. Close connection

**Expected Results**:
- WebSocket connection established
- Real-time message delivery
- Connection closes gracefully

---

### Test Case 3.12: Chat with Alert Context

**Objective**: Verify chat has access to alert context

**Test Steps**:
1. Create alert with specific details
2. Create chat session linked to alert
3. Ask question: "What alert are we discussing?"
4. Verify AI response includes alert details

**Expected Results**:
- AI has alert context
- Relevant recommendations based on alert

---

### Test Case 3.13: Switch LLM Provider Mid-Session

**Objective**: Verify ability to switch providers

**Test Steps**:
1. Create session with provider A
2. Send message
3. Update session to use provider B
4. Send another message
5. Verify different provider used

**Expected Results**:
- Provider switch successful
- Conversation continues seamlessly

---

## FEATURE 4: ALERT CLUSTERING

### Test Case 4.1: Automatic Alert Clustering

**Objective**: Verify related alerts automatically clustered

**Test Steps**:
1. Send multiple related alerts:
   - Same alertname, different instances
   - Same time window (within 5 minutes)
   - Same severity

2. Query clusters: `GET /api/clusters`

3. Verify cluster created:
   - Cluster contains all related alerts
   - Cluster name/description meaningful

**Expected Results**:
- Alerts grouped into cluster
- Cluster statistics calculated

---

### Test Case 4.2: Cluster Statistics

**Objective**: Verify cluster statistics are accurate

**API Endpoint**: `GET /api/clusters/{cluster_id}`

**Test Steps**:
1. Create cluster with 5 alerts
2. Query cluster details
3. Verify statistics:
   - Alert count: 5
   - Severity: highest severity in cluster
   - Duration: time from first to last alert
   - Frequency: alerts per hour
   - Status: active or closed

**Expected Results**:
- Accurate statistics
- Statistics update when alerts added

---

### Test Case 4.3: Get Alerts in Cluster

**Objective**: Retrieve all alerts in a cluster

**API Endpoint**: `GET /api/clusters/{cluster_id}/alerts`

**Test Steps**:
1. Create cluster
2. Query cluster alerts
3. Verify all cluster alerts returned
4. Verify pagination works

**Expected Results**:
- All cluster alerts listed
- Proper pagination

---

### Test Case 4.4: Close Cluster

**Objective**: Manually close an active cluster

**API Endpoint**: `POST /api/clusters/{cluster_id}/close`

**Test Steps**:
1. Create active cluster
2. Close cluster
3. Verify status changed to "closed"
4. Verify closed_at timestamp set

**Expected Results**:
- Cluster closed
- Timestamp recorded

---

### Test Case 4.5: Reopen Cluster

**Objective**: Reopen a closed cluster

**API Endpoint**: `POST /api/clusters/{cluster_id}/reopen`

**Test Steps**:
1. Close cluster
2. Reopen cluster
3. Verify status back to "active"

**Expected Results**:
- Cluster reopened
- Can add new alerts

---

### Test Case 4.6: Filter Clusters by Status

**Objective**: Filter clusters by active/closed status

**API Endpoint**: `GET /api/clusters?status=active`

**Test Steps**:
1. Create active and closed clusters
2. Filter by status=active
   - Verify only active returned
3. Filter by status=closed
   - Verify only closed returned

**Expected Results**:
- Filtering works correctly

---

## FEATURE 5: AUTO-REMEDIATION ENGINE

### Test Case 5.1: Create Simple Runbook - Linux Command

**Objective**: Create runbook with single Linux command step

**API Endpoint**: `POST /api/remediation/runbooks`

**Test Steps**:
1. Authenticate as engineer
2. Create runbook:
```json
{
  "name": "Restart Apache Service",
  "description": "Restarts Apache web server",
  "category": "web_server",
  "enabled": true,
  "auto_execute": false,
  "approval_required": true,
  "steps": [
    {
      "order": 1,
      "name": "Restart Apache",
      "description": "Systemctl restart",
      "step_type": "command",
      "command": "sudo systemctl restart apache2",
      "os_type": "linux",
      "expected_exit_code": 0,
      "timeout": 30
    }
  ]
}
```

3. Verify response: 201 Created
4. Verify runbook and step created

**Expected Results**:
- Runbook created
- Step order preserved
- Command stored

---

### Test Case 5.2: Create Runbook - Multi-Step

**Objective**: Create runbook with multiple sequential steps

**Test Steps**:
1. Create runbook with 3 steps:
   - Step 1: Check service status
   - Step 2: Stop service
   - Step 3: Start service

2. Verify steps in correct order
3. Verify each step configuration

**Expected Results**:
- All steps created
- Order preserved
- Each step independently configured

---

### Test Case 5.3: Create Runbook - API Call Step

**Objective**: Create runbook with API call step

**Test Steps**:
1. Create runbook with API step:
```json
{
  "steps": [
    {
      "order": 1,
      "name": "Scale deployment",
      "step_type": "api_call",
      "api_url": "https://k8s.example.com/apis/apps/v1/namespaces/default/deployments/myapp",
      "api_method": "PATCH",
      "api_headers": {
        "Authorization": "Bearer {{k8s_token}}",
        "Content-Type": "application/merge-patch+json"
      },
      "api_body": {
        "spec": {
          "replicas": 5
        }
      },
      "expected_status_code": 200,
      "timeout": 60
    }
  ]
}
```

2. Verify API step created
3. Verify templating supported

**Expected Results**:
- API step configured
- Headers and body stored
- Expected status code set

---

### Test Case 5.4: Create Runbook - With Templating

**Objective**: Test Jinja2 templating in commands

**Test Steps**:
1. Create runbook with templated command:
```json
{
  "steps": [
    {
      "command": "echo 'Alert: {{ alert.alertname }} on {{ alert.labels.instance }}'",
      "step_type": "command"
    }
  ]
}
```

2. Execute with alert context
3. Verify template variables resolved

**Expected Results**:
- Template variables replaced
- Command executed with actual values

---

### Test Case 5.5: Execute Runbook - Manual Approval

**Objective**: Execute runbook requiring manual approval

**API Endpoint**: `POST /api/remediation/runbooks/{runbook_id}/execute`

**Test Steps**:
1. Create runbook with `approval_required: true`
2. Execute runbook:
```json
{
  "alert_id": 123,
  "execution_params": {
    "server": "prod-web-01"
  }
}
```

3. Verify response:
   - Execution created
   - Status: "pending_approval"

4. Approve execution: `POST /api/remediation/executions/{execution_id}/approve`

5. Verify execution proceeds:
   - Status changes to "running"
   - Steps execute
   - Final status: "success"

**Expected Results**:
- Approval workflow works
- Execution waits for approval
- Steps execute after approval

---

### Test Case 5.6: Execute Runbook - Auto Execute

**Objective**: Execute runbook without approval

**Test Steps**:
1. Create runbook with:
   - `auto_execute: true`
   - `approval_required: false`

2. Trigger execution
3. Verify executes immediately
   - Status goes directly to "running"
   - No approval step

**Expected Results**:
- Immediate execution
- No approval required

---

### Test Case 5.7: Execution with Step Failure

**Objective**: Handle step failures gracefully

**Test Steps**:
1. Create runbook with command that will fail:
```json
{
  "steps": [
    {
      "command": "exit 1",
      "expected_exit_code": 0
    }
  ]
}
```

2. Execute runbook
3. Verify:
   - Step status: "failed"
   - Execution status: "failed"
   - Error message captured

**Expected Results**:
- Failure detected
- Error logged
- Execution stops

---

### Test Case 5.8: Execution Rollback

**Objective**: Test rollback functionality

**Test Steps**:
1. Create runbook with rollback steps:
```json
{
  "steps": [
    {
      "order": 1,
      "name": "Deploy new version",
      "command": "deploy.sh v2.0"
    }
  ],
  "rollback_steps": [
    {
      "order": 1,
      "name": "Rollback to previous version",
      "command": "deploy.sh v1.0"
    }
  ]
}
```

2. Execute and simulate failure
3. Verify rollback steps execute
4. Verify execution status shows rollback

**Expected Results**:
- Rollback triggered on failure
- Rollback steps execute
- System restored to previous state

---

### Test Case 5.9: Cancel Running Execution

**Objective**: Cancel an in-progress execution

**API Endpoint**: `POST /api/remediation/executions/{execution_id}/cancel`

**Test Steps**:
1. Execute long-running runbook
2. Cancel during execution
3. Verify:
   - Current step terminated
   - Status: "cancelled"
   - Remaining steps not executed

**Expected Results**:
- Execution cancelled
- Cleanup performed
- Status updated

---

### Test Case 5.10: Rate Limiting

**Objective**: Verify rate limiting prevents excessive executions

**Test Steps**:
1. Create runbook with:
   - `max_executions_per_hour: 3`

2. Execute 4 times within 1 hour
3. Verify 4th execution rejected:
   - Response: 429 Too Many Requests
   - Error message about rate limit

**Expected Results**:
- Rate limit enforced
- Executions blocked after limit

---

### Test Case 5.11: Cooldown Period

**Objective**: Verify cooldown period enforced

**Test Steps**:
1. Create runbook with:
   - `cooldown_minutes: 15`

2. Execute runbook
3. Attempt immediate re-execution
4. Verify rejected with cooldown message
5. Wait 15 minutes
6. Verify execution allowed

**Expected Results**:
- Cooldown enforced
- Time-based restriction works

---

### Test Case 5.12: Circuit Breaker

**Objective**: Test circuit breaker pattern

**API Endpoint**: `GET /api/remediation/circuit-breaker/{runbook_id}`

**Test Steps**:
1. Create runbook with circuit breaker:
   - `failure_threshold: 3`

2. Execute and fail 3 times consecutively
3. Verify circuit breaker opens:
   - `GET /api/remediation/circuit-breaker/{runbook_id}`
   - State: "open"

4. Attempt execution - verify blocked
5. Wait for recovery timeout
6. Verify circuit breaker goes to "half_open"
7. Execute successfully
8. Verify circuit breaker "closed"

**Expected Results**:
- Circuit breaker opens after failures
- Prevents further executions
- Recovers after successful execution

---

### Test Case 5.13: Override Circuit Breaker

**Objective**: Manually override circuit breaker

**API Endpoint**: `POST /api/remediation/circuit-breaker/{runbook_id}/override`

**Test Steps**:
1. Open circuit breaker (via failures)
2. Override with admin credentials
3. Verify circuit breaker reset to "closed"
4. Verify executions allowed

**Expected Results**:
- Admin can override
- Circuit breaker reset

---

### Test Case 5.14: Blackout Window

**Objective**: Prevent executions during blackout window

**Test Steps**:
1. Create blackout window:
   - Start: "02:00"
   - End: "04:00"
   - Days: ["Monday", "Tuesday"]

2. Attempt execution during blackout
3. Verify execution blocked
4. Verify error message explains blackout

**Expected Results**:
- Executions blocked during blackout
- Clear error message

---

### Test Case 5.15: Execution History

**Objective**: Retrieve execution history for runbook

**API Endpoint**: `GET /api/remediation/runbooks/{runbook_id}/executions`

**Test Steps**:
1. Execute runbook multiple times
2. Query execution history
3. Verify all executions listed
4. Verify details include:
   - Execution ID, timestamp
   - Status, duration
   - User who triggered
   - Success/failure

**Expected Results**:
- Complete execution history
- Proper sorting (newest first)

---

### Test Case 5.16: Execution Detail View

**Objective**: View detailed execution information

**API Endpoint**: `GET /api/remediation/executions/{execution_id}`

**Test Steps**:
1. Execute runbook
2. Query execution details
3. Verify includes:
   - All step executions
   - Step outputs
   - Exit codes
   - Timestamps for each step
   - Total duration

**Expected Results**:
- Complete execution details
- Step-by-step logs
- Timeline visualization possible

---

### Test Case 5.17: Import Runbook from YAML

**Objective**: Import runbook definition from YAML file

**API Endpoint**: `POST /api/remediation/runbooks/import`

**Test Steps**:
1. Create YAML file:
```yaml
name: "Database Maintenance"
description: "Weekly DB maintenance tasks"
category: "database"
enabled: true
steps:
  - order: 1
    name: "Vacuum database"
    step_type: "command"
    command: "psql -c 'VACUUM ANALYZE;'"
    os_type: "linux"
```

2. Import via API:
   - Upload YAML file
   - Verify parsing successful

3. Verify runbook created
4. Verify steps imported correctly

**Expected Results**:
- YAML parsed successfully
- Runbook created from YAML
- All fields mapped correctly

---

### Test Case 5.18: Export Runbook to YAML

**Objective**: Export runbook as YAML

**API Endpoint**: `GET /api/remediation/runbooks/{runbook_id}/export`

**Test Steps**:
1. Create runbook via API
2. Export to YAML
3. Verify YAML valid
4. Verify all fields present
5. Re-import YAML
6. Verify identical runbook created

**Expected Results**:
- Export generates valid YAML
- Round-trip (export + import) works

---

### Test Case 5.19: Update Runbook

**Objective**: Update existing runbook

**API Endpoint**: `PUT /api/remediation/runbooks/{runbook_id}`

**Test Steps**:
1. Create runbook
2. Update fields:
   - Name, description
   - Add new step
   - Modify existing step
   - Change configuration

3. Verify updates persisted
4. Verify no data loss

**Expected Results**:
- Updates successful
- Version history maintained (if implemented)

---

### Test Case 5.20: Delete Runbook

**Objective**: Delete runbook and cleanup

**API Endpoint**: `DELETE /api/remediation/runbooks/{runbook_id}`

**Test Steps**:
1. Create runbook with executions
2. Delete runbook
3. Verify:
   - Runbook deleted
   - Steps deleted (cascade)
   - Execution history preserved or deleted (check policy)

**Expected Results**:
- Runbook removed
- Proper cleanup
- Execution history handled per policy

---

## FEATURE 6: SCHEDULED RUNBOOKS

### Test Case 6.1: Create Cron Schedule

**Objective**: Schedule runbook using cron expression

**API Endpoint**: `POST /api/schedules`

**Test Steps**:
1. Create schedule:
```json
{
  "name": "Daily DB Backup",
  "runbook_id": 123,
  "schedule_type": "cron",
  "cron_expression": "0 2 * * *",
  "enabled": true,
  "misfire_grace_time": 300
}
```

2. Verify schedule created
3. Verify next run time calculated correctly

**Expected Results**:
- Schedule created
- Cron expression validated
- Next run time accurate

---

### Test Case 6.2: Create Interval Schedule

**Objective**: Schedule runbook at regular intervals

**Test Steps**:
1. Create interval schedule:
```json
{
  "name": "Hourly Health Check",
  "runbook_id": 456,
  "schedule_type": "interval",
  "interval_minutes": 60,
  "enabled": true
}
```

2. Verify schedule created
3. Verify runs every 60 minutes

**Expected Results**:
- Interval schedule works
- Executions occur at correct intervals

---

### Test Case 6.3: Create Date-Based Schedule

**Objective**: Schedule one-time execution

**Test Steps**:
1. Create date schedule:
```json
{
  "name": "Quarterly Report",
  "runbook_id": 789,
  "schedule_type": "date",
  "run_at": "2025-12-31T23:59:00Z",
  "enabled": true
}
```

2. Verify schedule created
3. Verify runs only once at specified time

**Expected Results**:
- One-time execution
- Schedule auto-disables after run

---

### Test Case 6.4: Pause Schedule

**Objective**: Temporarily pause scheduled executions

**API Endpoint**: `POST /api/schedules/{schedule_id}/pause`

**Test Steps**:
1. Create active schedule
2. Pause schedule
3. Verify status: "paused"
4. Verify no executions while paused
5. Resume: `POST /api/schedules/{schedule_id}/resume`
6. Verify executions resume

**Expected Results**:
- Pause prevents executions
- Resume restores normal operation

---

### Test Case 6.5: Schedule Execution History

**Objective**: View history of scheduled executions

**API Endpoint**: `GET /api/schedules/{schedule_id}/history`

**Test Steps**:
1. Create schedule
2. Wait for multiple executions
3. Query history
4. Verify all executions logged:
   - Timestamp
   - Success/failure
   - Duration
   - Output

**Expected Results**:
- Complete execution history
- Audit trail of scheduled runs

---

### Test Case 6.6: Misfire Handling

**Objective**: Test grace period for missed executions

**Test Steps**:
1. Create schedule with `misfire_grace_time: 300` (5 minutes)
2. Simulate missed execution (system down)
3. Restart within grace time
4. Verify execution runs (late but within grace)
5. Simulate missed execution beyond grace time
6. Verify execution skipped

**Expected Results**:
- Grace period honored
- Late executions within grace run
- Too-late executions skipped

---

### Test Case 6.7: Update Schedule

**Objective**: Modify existing schedule

**API Endpoint**: `PUT /api/schedules/{schedule_id}`

**Test Steps**:
1. Create cron schedule
2. Update cron expression:
```json
{
  "cron_expression": "0 3 * * *"
}
```
3. Verify next run time recalculated
4. Verify new schedule applied

**Expected Results**:
- Schedule updated
- Changes take effect immediately

---

### Test Case 6.8: Delete Schedule

**Objective**: Remove scheduled job

**API Endpoint**: `DELETE /api/schedules/{schedule_id}`

**Test Steps**:
1. Create schedule
2. Delete schedule
3. Verify no future executions
4. Verify history preserved

**Expected Results**:
- Schedule deleted
- Future runs cancelled

---

## FEATURE 7: KNOWLEDGE BASE

### Test Case 7.1: Create Document - Markdown

**Objective**: Create knowledge base document from Markdown

**API Endpoint**: `POST /api/knowledge/documents`

**Test Steps**:
1. Create document:
```json
{
  "title": "Database Architecture",
  "content": "# Database Architecture\n\n## Overview\nOur database uses PostgreSQL...",
  "content_type": "markdown",
  "application_id": 123,
  "tags": ["database", "architecture"]
}
```

2. Verify response: 201 Created
3. Verify document chunked
4. Verify embeddings generated

**Expected Results**:
- Document created
- Content chunked appropriately
- Vector embeddings stored

---

### Test Case 7.2: Create Document - PDF Upload

**Objective**: Upload PDF document

**Test Steps**:
1. Upload PDF file via multipart form:
   - File: architecture.pdf
   - Title: "System Architecture"
   - Application ID: 123

2. Verify PDF processed:
   - Text extracted
   - Chunks created
   - Embeddings generated

**Expected Results**:
- PDF ingested
- Text extraction successful
- Searchable content

---

### Test Case 7.3: Create Document - HTML

**Objective**: Import HTML documentation

**Test Steps**:
1. Create HTML document:
```json
{
  "title": "API Documentation",
  "content": "<h1>API Docs</h1><p>Description...</p>",
  "content_type": "html"
}
```

2. Verify HTML parsed
3. Verify text extracted (HTML tags stripped for embedding)

**Expected Results**:
- HTML content stored
- Text properly extracted

---

### Test Case 7.4: Create Document - YAML

**Objective**: Store YAML configuration documentation

**Test Steps**:
1. Create YAML document:
```json
{
  "title": "Kubernetes Config",
  "content": "apiVersion: v1\nkind: Service...",
  "content_type": "yaml"
}
```

2. Verify YAML stored
3. Verify searchable

**Expected Results**:
- YAML preserved
- Searchable via keywords

---

### Test Case 7.5: Upload Design Images

**Objective**: Upload architecture diagrams

**Test Steps**:
1. Upload image with document:
   - PNG/JPG architecture diagram
   - Associate with document

2. Verify image stored
3. Verify thumbnail generated
4. Verify AI analysis of image (if enabled):
   - Components extracted
   - Connections identified

**Expected Results**:
- Image stored
- Thumbnail available
- AI metadata extracted

---

### Test Case 7.6: Search Documents - Full Text

**Objective**: Search documents by keyword

**API Endpoint**: `POST /api/knowledge/search`

**Test Steps**:
1. Create multiple documents
2. Search for keyword:
```json
{
  "query": "database",
  "search_type": "full_text",
  "limit": 10
}
```

3. Verify relevant documents returned
4. Verify results ranked by relevance

**Expected Results**:
- Keyword matching works
- Results sorted by relevance

---

### Test Case 7.7: Search Documents - Similarity Search

**Objective**: Search using vector similarity

**Test Steps**:
1. Search with question:
```json
{
  "query": "How do we handle database failures?",
  "search_type": "similarity",
  "limit": 5
}
```

2. Verify semantically similar documents returned
3. Verify similarity scores included

**Expected Results**:
- Semantic search works
- Similar concepts matched even with different keywords

---

### Test Case 7.8: Search with Application Filter

**Objective**: Filter search by application

**Test Steps**:
1. Create documents for different applications
2. Search with filter:
```json
{
  "query": "architecture",
  "application_id": 123
}
```

3. Verify only matching application's documents returned

**Expected Results**:
- Application filtering works
- Results scoped correctly

---

### Test Case 7.9: Get Document Details

**Objective**: Retrieve full document

**API Endpoint**: `GET /api/knowledge/documents/{doc_id}`

**Test Steps**:
1. Create document
2. Query by ID
3. Verify full content returned
4. Verify metadata included

**Expected Results**:
- Complete document retrieved
- Formatted properly

---

### Test Case 7.10: Update Document

**Objective**: Update existing document

**API Endpoint**: `PUT /api/knowledge/documents/{doc_id}`

**Test Steps**:
1. Create document
2. Update content:
```json
{
  "content": "Updated content...",
  "tags": ["updated", "revised"]
}
```

3. Verify content updated
4. Verify chunks regenerated
5. Verify new embeddings created

**Expected Results**:
- Document updated
- Embeddings refreshed

---

### Test Case 7.11: Delete Document

**Objective**: Remove document from knowledge base

**API Endpoint**: `DELETE /api/knowledge/documents/{doc_id}`

**Test Steps**:
1. Create document
2. Delete document
3. Verify document removed
4. Verify chunks deleted
5. Verify embeddings removed
6. Verify images deleted

**Expected Results**:
- Complete cleanup
- No orphaned data

---

### Test Case 7.12: List Documents

**Objective**: List all documents with pagination

**API Endpoint**: `GET /api/knowledge/documents`

**Test Steps**:
1. Create 25 documents
2. Query with pagination:
   - `GET /api/knowledge/documents?page=1&page_size=10`

3. Verify 10 documents returned
4. Verify total count in response

**Expected Results**:
- Pagination works
- Total count accurate

---

### Test Case 7.13: Filter Documents by Tags

**Objective**: Filter documents using tags

**Test Steps**:
1. Create documents with various tags
2. Filter by tag:
   - `GET /api/knowledge/documents?tags=database,architecture`

3. Verify only matching documents returned

**Expected Results**:
- Tag filtering works
- Multiple tags supported

---

### Test Case 7.14: Get Document Chunk

**Objective**: Retrieve specific content chunk

**API Endpoint**: `GET /api/knowledge/chunks/{chunk_id}`

**Test Steps**:
1. Create document (auto-chunked)
2. Get chunk IDs
3. Query specific chunk
4. Verify chunk content returned

**Expected Results**:
- Individual chunks retrievable
- Content matches source

---

## FEATURE 8: APPLICATION REGISTRY

### Test Case 8.1: Create Application

**Objective**: Register new application

**API Endpoint**: `POST /api/applications`

**Test Steps**:
1. Create application:
```json
{
  "name": "E-Commerce Web App",
  "description": "Main customer-facing web application",
  "team_owner": "Platform Team",
  "criticality": "critical",
  "tech_stack": ["Python", "Django", "PostgreSQL", "Redis"],
  "alert_matching_rules": {
    "job": "ecommerce-web"
  }
}
```

2. Verify response: 201 Created
3. Verify application persisted

**Expected Results**:
- Application created
- Metadata stored

---

### Test Case 8.2: Add Application Component

**Objective**: Add component to application

**API Endpoint**: `POST /api/applications/{app_id}/components`

**Test Steps**:
1. Create application
2. Add component:
```json
{
  "name": "Web Server",
  "component_type": "compute",
  "description": "Django application servers",
  "endpoints": ["https://web.example.com"],
  "health_check_url": "https://web.example.com/health"
}
```

3. Verify component created
4. Verify linked to application

**Expected Results**:
- Component added
- Application relationship established

---

### Test Case 8.3: Add Component Dependency

**Objective**: Define component dependencies

**Test Steps**:
1. Create application with multiple components:
   - Web Server (component_id: 1)
   - Database (component_id: 2)
   - Cache (component_id: 3)

2. Add dependencies:
   - Web Server depends on Database
   - Web Server depends on Cache

3. Query topology: `GET /api/applications/{app_id}/topology`
4. Verify dependency graph returned

**Expected Results**:
- Dependencies recorded
- Topology graph shows relationships

---

### Test Case 8.4: Application Topology Visualization

**Objective**: Retrieve application architecture

**API Endpoint**: `GET /api/applications/{app_id}/topology`

**Test Steps**:
1. Create complex application:
   - 5 components
   - Multiple dependencies

2. Query topology
3. Verify response includes:
   - All components
   - All dependencies
   - Graph structure (nodes/edges)

**Expected Results**:
- Complete topology
- Graph format suitable for visualization

---

### Test Case 8.5: Alert-to-Application Mapping

**Objective**: Verify alerts auto-mapped to applications

**Test Steps**:
1. Create application with matching rule:
```json
{
  "alert_matching_rules": {
    "job": "web-app"
  }
}
```

2. Send alert with label `job="web-app"`
3. Query alert
4. Verify `application_id` set
5. Query application alerts:
   - Verify alert appears

**Expected Results**:
- Automatic mapping works
- Alerts linked to application

---

### Test Case 8.6: Application Statistics

**Objective**: View application metrics

**API Endpoint**: `GET /api/applications/stats`

**Test Steps**:
1. Create multiple applications with alerts
2. Query stats
3. Verify metrics include:
   - Total applications
   - Alert counts per application
   - Criticality distribution

**Expected Results**:
- Accurate statistics
- Aggregations correct

---

### Test Case 8.7: Update Application

**Objective**: Modify application details

**API Endpoint**: `PUT /api/applications/{app_id}`

**Test Steps**:
1. Create application
2. Update fields:
```json
{
  "criticality": "high",
  "tech_stack": ["Python", "Django", "PostgreSQL", "Redis", "Elasticsearch"]
}
```

3. Verify updates persisted

**Expected Results**:
- Application updated
- Changes saved

---

### Test Case 8.8: Delete Application

**Objective**: Remove application

**API Endpoint**: `DELETE /api/applications/{app_id}`

**Test Steps**:
1. Create application with components
2. Delete application
3. Verify:
   - Application deleted
   - Components deleted (cascade)
   - Alert mappings removed

**Expected Results**:
- Complete cleanup
- Cascade deletions work

---

### Test Case 8.9: List Applications

**Objective**: List all registered applications

**API Endpoint**: `GET /api/applications`

**Test Steps**:
1. Create 15 applications
2. Query list with pagination
3. Filter by criticality:
   - `GET /api/applications?criticality=critical`

**Expected Results**:
- All applications listed
- Filtering works

---

### Test Case 8.10: Application Profile - Create

**Objective**: Create monitoring profile for application

**API Endpoint**: `POST /api/application-profiles`

**Test Steps**:
1. Create profile:
```json
{
  "application_id": 123,
  "slo_availability": 99.9,
  "slo_latency_p95": 200,
  "metrics_mappings": {
    "cpu": "instance:cpu_usage:avg",
    "memory": "instance:memory_usage:avg"
  },
  "datasource_id": 1
}
```

2. Verify profile created

**Expected Results**:
- Profile associated with application
- SLOs and metrics defined

---

## FEATURE 9: CHANGE CORRELATION & ITSM INTEGRATION

### Test Case 9.1: Create ITSM Integration - ServiceNow

**Objective**: Configure ServiceNow integration

**API Endpoint**: `POST /api/itsm/integrations`

**Test Steps**:
1. Create integration:
```json
{
  "name": "ServiceNow Production",
  "integration_type": "servicenow",
  "config": {
    "instance_url": "https://dev12345.service-now.com",
    "username": "api_user",
    "password": "encrypted_password",
    "change_table": "change_request",
    "sync_interval": 300
  },
  "enabled": true
}
```

2. Verify integration created
3. Verify config encrypted
4. Test connection: `POST /api/itsm/integrations/{integration_id}/test`

**Expected Results**:
- Integration configured
- Credentials encrypted
- Connection successful

---

### Test Case 9.2: Create ITSM Integration - Jira

**Objective**: Configure Jira integration

**Test Steps**:
1. Create Jira integration:
```json
{
  "name": "Jira Cloud",
  "integration_type": "jira",
  "config": {
    "base_url": "https://company.atlassian.net",
    "email": "api@company.com",
    "api_token": "token123",
    "project_key": "OPS",
    "sync_interval": 600
  },
  "enabled": true
}
```

2. Verify integration created
3. Test connection

**Expected Results**:
- Jira integration works
- Can fetch issues

---

### Test Case 9.3: Manual ITSM Sync

**Objective**: Manually trigger synchronization

**API Endpoint**: `POST /api/itsm/integrations/{integration_id}/sync`

**Test Steps**:
1. Create integration
2. Trigger manual sync
3. Verify:
   - Sync starts
   - Change events fetched
   - Database updated

**Expected Results**:
- Sync completes successfully
- Change events imported

---

### Test Case 9.4: List Change Events

**Objective**: View synced change events

**API Endpoint**: `GET /api/changes`

**Test Steps**:
1. Sync changes from ITSM
2. Query change events:
   - `GET /api/changes?service=web-app`

3. Verify changes listed
4. Verify filtering works

**Expected Results**:
- All changes returned
- Filters applied correctly

---

### Test Case 9.5: Change Timeline

**Objective**: View changes over time

**API Endpoint**: `GET /api/changes/timeline`

**Test Steps**:
1. Query timeline:
   - `GET /api/changes/timeline?start=2025-12-01&end=2025-12-31`

2. Verify timeline data:
   - Changes grouped by time
   - Counts per period

**Expected Results**:
- Timeline visualization data
- Proper time grouping

---

### Test Case 9.6: Change Impact Analysis

**Objective**: Analyze impact of a change

**API Endpoint**: `GET /api/changes/{change_id}/impact`

**Test Steps**:
1. Create change event
2. Create incidents after change
3. Query impact analysis
4. Verify metrics:
   - Number of incidents after change
   - Alert correlation score
   - Affected services

**Expected Results**:
- Impact calculated
- Correlation detected

---

### Test Case 9.7: Correlate Changes with Incidents

**Objective**: Find changes related to incident

**API Endpoint**: `POST /api/changes/correlate`

**Test Steps**:
1. Request correlation:
```json
{
  "incident_id": 123,
  "time_window_minutes": 60
}
```

2. Verify response includes:
   - Changes within time window
   - Correlation scores
   - Recommendations

**Expected Results**:
- Relevant changes identified
- Scoring helps prioritize

---

### Test Case 9.8: Update ITSM Integration

**Objective**: Modify integration settings

**API Endpoint**: `PUT /api/itsm/integrations/{integration_id}`

**Test Steps**:
1. Update sync interval:
```json
{
  "config": {
    "sync_interval": 900
  }
}
```

2. Verify update applied
3. Verify next sync uses new interval

**Expected Results**:
- Integration updated
- Changes take effect

---

### Test Case 9.9: Disable ITSM Integration

**Objective**: Temporarily disable integration

**Test Steps**:
1. Update integration:
```json
{
  "enabled": false
}
```

2. Verify sync stops
3. Re-enable and verify sync resumes

**Expected Results**:
- Enable/disable toggle works
- Sync behavior changes accordingly

---

### Test Case 9.10: Delete ITSM Integration

**Objective**: Remove integration

**API Endpoint**: `DELETE /api/itsm/integrations/{integration_id}`

**Test Steps**:
1. Create integration
2. Delete integration
3. Verify:
   - Integration removed
   - Change events preserved (or deleted per policy)

**Expected Results**:
- Integration deleted
- Data handling per policy

---

## FEATURE 10: OBSERVABILITY INTEGRATION

### Test Case 10.1: Natural Language Query - Logs

**Objective**: Query logs using natural language

**API Endpoint**: `POST /api/observability/query`

**Test Steps**:
1. Submit query:
```json
{
  "query": "Show me error logs from the web service in the last hour",
  "context": {
    "time_range": "1h"
  }
}
```

2. Verify response contains:
   - Detected intent: "logs"
   - Generated LogQL query
   - Query results from Loki
   - Formatted logs

**Expected Results**:
- Natural language understood
- LogQL generated correctly
- Results returned

---

### Test Case 10.2: Natural Language Query - Metrics

**Objective**: Query metrics using natural language

**Test Steps**:
1. Submit query:
```json
{
  "query": "What is the CPU usage of server-01?",
  "context": {}
}
```

2. Verify:
   - Intent: "metrics"
   - PromQL generated
   - Results from Prometheus

**Expected Results**:
- PromQL query correct
- Metric data returned

---

### Test Case 10.3: Natural Language Query - Traces

**Objective**: Query traces using natural language

**Test Steps**:
1. Submit query:
```json
{
  "query": "Show me slow traces for the checkout service",
  "context": {
    "service": "checkout"
  }
}
```

2. Verify:
   - Intent: "traces"
   - TraceQL generated
   - Results from Tempo

**Expected Results**:
- TraceQL correct
- Trace data returned

---

### Test Case 10.4: Parse Query Intent

**Objective**: Test intent detection

**API Endpoint**: `POST /api/observability/query/parse-intent`

**Test Steps**:
1. Parse various queries:
   - "Show me logs" → intent: logs
   - "CPU usage" → intent: metrics
   - "Trace requests" → intent: traces

2. Verify intent correctly detected

**Expected Results**:
- Intent detection accurate
- Confidence scores provided

---

### Test Case 10.5: Translate Query to PromQL

**Objective**: Translate to Prometheus query

**API Endpoint**: `POST /api/observability/query/translate`

**Test Steps**:
1. Translate query:
```json
{
  "query": "Average memory usage by instance",
  "target_language": "promql"
}
```

2. Verify PromQL generated:
   - Example: `avg by (instance) (node_memory_usage)`

**Expected Results**:
- Valid PromQL
- Semantically correct

---

### Test Case 10.6: Translate Query to LogQL

**Objective**: Translate to Loki query

**Test Steps**:
1. Translate:
```json
{
  "query": "Error logs from namespace production",
  "target_language": "logql"
}
```

2. Verify LogQL:
   - Example: `{namespace="production"} |= "error"`

**Expected Results**:
- Valid LogQL
- Filters applied correctly

---

### Test Case 10.7: Translate Query to TraceQL

**Objective**: Translate to Tempo query

**Test Steps**:
1. Translate:
```json
{
  "query": "Spans longer than 1 second for API service",
  "target_language": "traceql"
}
```

2. Verify TraceQL:
   - Example: `{service.name="api" && duration > 1s}`

**Expected Results**:
- Valid TraceQL
- Duration filter correct

---

### Test Case 10.8: Query History

**Objective**: Retrieve user's query history

**API Endpoint**: `GET /api/observability/query/history`

**Test Steps**:
1. Execute multiple queries
2. Query history
3. Verify all queries logged:
   - Original query
   - Intent
   - Generated query
   - Timestamp

**Expected Results**:
- Complete query history
- Chronological order

---

### Test Case 10.9: Clear Query Cache

**Objective**: Clear cached query results

**API Endpoint**: `POST /api/observability/query/cache/clear`

**Test Steps**:
1. Execute query (results cached)
2. Execute same query (should be cached)
3. Clear cache
4. Execute query again (should re-fetch)

**Expected Results**:
- Cache cleared
- Fresh data fetched

---

## FEATURE 11: DASHBOARD BUILDER

### Test Case 11.1: Create Prometheus Datasource

**Objective**: Register Prometheus datasource

**API Endpoint**: `POST /api/datasources`

**Test Steps**:
1. Create datasource:
```json
{
  "name": "Production Prometheus",
  "url": "http://prometheus:9090",
  "auth_type": "none",
  "is_default": true,
  "timeout": 30
}
```

2. Verify datasource created
3. Test connection: `POST /api/datasources/{datasource_id}/test`

**Expected Results**:
- Datasource configured
- Connection test passes

---

### Test Case 11.2: Create Dashboard

**Objective**: Create new dashboard

**API Endpoint**: `POST /api/dashboards`

**Test Steps**:
1. Create dashboard:
```json
{
  "title": "System Overview",
  "description": "Main system monitoring dashboard",
  "time_range": "1h",
  "refresh_interval": 30,
  "is_public": false
}
```

2. Verify dashboard created
3. Verify can be retrieved

**Expected Results**:
- Dashboard created
- Settings persisted

---

### Test Case 11.3: Create Panel - Graph

**Objective**: Create graph panel

**API Endpoint**: `POST /api/panels`

**Test Steps**:
1. Create panel:
```json
{
  "title": "CPU Usage",
  "datasource_id": 1,
  "panel_type": "graph",
  "query": "avg(rate(node_cpu_seconds_total[5m]))",
  "legend_format": "{{instance}}",
  "unit": "percent",
  "threshold": {
    "warning": 70,
    "critical": 90
  }
}
```

2. Verify panel created
3. Test query execution: `POST /api/panels/{panel_id}/query`

**Expected Results**:
- Panel configured
- Query returns data

---

### Test Case 11.4: Create Panel - Gauge

**Objective**: Create gauge panel

**Test Steps**:
1. Create gauge panel:
```json
{
  "title": "Memory Usage",
  "panel_type": "gauge",
  "query": "node_memory_usage_percent",
  "min_value": 0,
  "max_value": 100,
  "threshold": {
    "green": 60,
    "yellow": 80,
    "red": 90
  }
}
```

2. Verify gauge configuration

**Expected Results**:
- Gauge panel created
- Thresholds defined

---

### Test Case 11.5: Create Panel - Stat

**Objective**: Create stat panel (single value)

**Test Steps**:
1. Create stat panel:
```json
{
  "title": "Active Alerts",
  "panel_type": "stat",
  "query": "count(ALERTS{alertstate=\"firing\"})",
  "unit": "short"
}
```

2. Verify stat panel

**Expected Results**:
- Single value display
- Unit formatting

---

### Test Case 11.6: Create Panel - Table

**Objective**: Create table panel

**Test Steps**:
1. Create table panel:
```json
{
  "title": "Top Processes",
  "panel_type": "table",
  "query": "topk(10, process_cpu_usage)"
}
```

2. Verify table format

**Expected Results**:
- Tabular data display
- Multiple rows

---

### Test Case 11.7: Add Panel to Dashboard

**Objective**: Associate panel with dashboard

**API Endpoint**: `POST /api/dashboards/{dashboard_id}/panels`

**Test Steps**:
1. Create dashboard
2. Create panel
3. Add panel to dashboard:
```json
{
  "panel_id": 123,
  "grid_x": 0,
  "grid_y": 0,
  "width": 6,
  "height": 4
}
```

4. Verify panel appears in dashboard

**Expected Results**:
- Panel added
- Grid position set

---

### Test Case 11.8: Remove Panel from Dashboard

**Objective**: Remove panel association

**API Endpoint**: `DELETE /api/dashboards/{dashboard_id}/panels/{panel_id}`

**Test Steps**:
1. Add panel to dashboard
2. Remove panel
3. Verify panel no longer in dashboard
4. Verify panel itself still exists (not deleted)

**Expected Results**:
- Association removed
- Panel preserved

---

### Test Case 11.9: Panel Templates

**Objective**: Use predefined panel templates

**API Endpoint**: `POST /api/panels/templates`

**Test Steps**:
1. Request templates:
   - CPU usage template
   - Memory template
   - Network template

2. Verify templates returned with:
   - Pre-configured queries
   - Visualization settings
   - Thresholds

3. Create panel from template

**Expected Results**:
- Templates available
- Quick panel creation

---

### Test Case 11.10: Dashboard Snapshot - Create

**Objective**: Create shareable dashboard snapshot

**API Endpoint**: `POST /api/dashboards/{dashboard_id}/snapshot`

**Test Steps**:
1. Create dashboard with panels
2. Create snapshot:
```json
{
  "name": "System Status 2025-12-29",
  "expires_at": "2025-12-31T23:59:59Z"
}
```

3. Verify snapshot created
4. Verify unique snapshot key generated

**Expected Results**:
- Snapshot captures current state
- Shareable key created

---

### Test Case 11.11: Dashboard Snapshot - View (Public)

**Objective**: View snapshot without authentication

**API Endpoint**: `GET /api/snapshots/{snapshot_key}`

**Test Steps**:
1. Create snapshot
2. Access snapshot URL (no auth)
3. Verify dashboard data returned
4. Verify frozen state (not live)

**Expected Results**:
- Public access works
- Data frozen at snapshot time

---

### Test Case 11.12: Dashboard Snapshot - Delete

**Objective**: Remove snapshot

**API Endpoint**: `DELETE /api/snapshots/{snapshot_id}`

**Test Steps**:
1. Create snapshot
2. Delete snapshot
3. Verify snapshot key no longer works

**Expected Results**:
- Snapshot deleted
- Link broken

---

### Test Case 11.13: Create Playlist

**Objective**: Create dashboard playlist

**API Endpoint**: `POST /api/playlists`

**Test Steps**:
1. Create playlist:
```json
{
  "name": "Operations Overview",
  "interval_seconds": 60,
  "dashboards": [
    {"dashboard_id": 1, "order": 1},
    {"dashboard_id": 2, "order": 2},
    {"dashboard_id": 3, "order": 3}
  ]
}
```

2. Verify playlist created
3. Verify dashboard order

**Expected Results**:
- Playlist configured
- Rotation timing set

---

### Test Case 11.14: Start Playlist

**Objective**: Play dashboard rotation

**API Endpoint**: `POST /api/playlists/{playlist_id}/play`

**Test Steps**:
1. Create playlist
2. Start playback
3. Verify rotation begins
4. Verify interval timing

**Expected Results**:
- Playback starts
- Dashboards rotate

---

### Test Case 11.15: Update Dashboard

**Objective**: Modify dashboard settings

**API Endpoint**: `PUT /api/dashboards/{dashboard_id}`

**Test Steps**:
1. Create dashboard
2. Update settings:
```json
{
  "refresh_interval": 60,
  "is_favorite": true
}
```

3. Verify updates applied

**Expected Results**:
- Dashboard updated
- Changes persisted

---

### Test Case 11.16: Delete Dashboard

**Objective**: Remove dashboard

**API Endpoint**: `DELETE /api/dashboards/{dashboard_id}`

**Test Steps**:
1. Create dashboard with panels
2. Delete dashboard
3. Verify:
   - Dashboard deleted
   - Panel associations removed
   - Panels themselves preserved

**Expected Results**:
- Dashboard removed
- Cleanup complete

---

## FEATURE 12: GRAFANA INTEGRATION

### Test Case 12.1: Create Grafana Datasource - Loki

**Objective**: Configure Loki datasource via Grafana

**API Endpoint**: `POST /api/grafana-datasources`

**Test Steps**:
1. Create Loki datasource:
```json
{
  "name": "Loki Production",
  "datasource_type": "loki",
  "url": "http://loki:3100",
  "auth_type": "none",
  "is_default": false
}
```

2. Verify datasource created
3. Test connection: `POST /api/grafana-datasources/{datasource_id}/test`

**Expected Results**:
- Loki datasource configured
- Connection successful

---

### Test Case 12.2: Create Grafana Datasource - Tempo

**Objective**: Configure Tempo for traces

**Test Steps**:
1. Create Tempo datasource:
```json
{
  "name": "Tempo Production",
  "datasource_type": "tempo",
  "url": "http://tempo:3200",
  "auth_type": "bearer",
  "auth_credentials": "token123"
}
```

2. Test connection

**Expected Results**:
- Tempo configured
- Traces accessible

---

### Test Case 12.3: Create Grafana Datasource - Prometheus

**Objective**: Configure Prometheus via Grafana

**Test Steps**:
1. Create Prometheus datasource:
```json
{
  "name": "Prometheus",
  "datasource_type": "prometheus",
  "url": "http://prometheus:9090",
  "auth_type": "basic",
  "auth_credentials": {
    "username": "admin",
    "password": "secret"
  }
}
```

2. Test connection

**Expected Results**:
- Prometheus configured
- Metrics queryable

---

### Test Case 12.4: Create Grafana Datasource - Mimir

**Objective**: Configure Mimir for metrics

**Test Steps**:
1. Create Mimir datasource:
```json
{
  "name": "Mimir Production",
  "datasource_type": "mimir",
  "url": "http://mimir:9009",
  "tenant_id": "tenant-1"
}
```

2. Test connection

**Expected Results**:
- Mimir configured
- Multi-tenancy supported

---

### Test Case 12.5: Datasource Health Check

**Objective**: Check datasource health

**API Endpoint**: `GET /api/grafana-datasources/{datasource_id}/health`

**Test Steps**:
1. Create datasource
2. Query health status
3. Verify response includes:
   - Status: healthy/unhealthy
   - Latency
   - Error message (if unhealthy)

**Expected Results**:
- Health status accurate
- Diagnostics helpful

---

### Test Case 12.6: Update Grafana Datasource

**Objective**: Modify datasource configuration

**API Endpoint**: `PUT /api/grafana-datasources/{datasource_id}`

**Test Steps**:
1. Create datasource
2. Update URL or credentials
3. Verify updates applied
4. Test connection with new config

**Expected Results**:
- Datasource updated
- New config works

---

### Test Case 12.7: Delete Grafana Datasource

**Objective**: Remove datasource

**API Endpoint**: `DELETE /api/grafana-datasources/{datasource_id}`

**Test Steps**:
1. Create datasource
2. Delete datasource
3. Verify removed

**Expected Results**:
- Datasource deleted
- No longer queryable

---

### Test Case 12.8: Logs Page Integration

**Objective**: Access Loki logs via Grafana embed

**Test Steps**:
1. Configure Loki datasource
2. Navigate to logs page
3. Verify Grafana Explore embedded
4. Verify can query Loki

**Expected Results**:
- Grafana embed works
- LogQL queries execute

---

### Test Case 12.9: Traces Page Integration

**Objective**: Access Tempo traces via Grafana

**Test Steps**:
1. Configure Tempo datasource
2. Navigate to traces page
3. Verify Grafana Explore embedded
4. Verify can view traces

**Expected Results**:
- Trace viewer works
- TraceQL supported

---

## FEATURE 13: TERMINAL ACCESS

### Test Case 13.1: Create Server Credential - SSH Key

**Objective**: Store SSH credentials for server

**Test Steps**:
1. Create credential:
```json
{
  "name": "Production Web Server",
  "host": "web-01.example.com",
  "port": 22,
  "username": "ubuntu",
  "os_type": "linux",
  "auth_type": "key",
  "ssh_key": "-----BEGIN RSA PRIVATE KEY-----\n..."
}
```

2. Verify credential created
3. Verify SSH key encrypted in database

**Expected Results**:
- Credential stored
- Key encrypted

---

### Test Case 13.2: Create Server Credential - Password

**Objective**: Store password-based credentials

**Test Steps**:
1. Create credential:
```json
{
  "host": "win-server-01",
  "port": 5985,
  "username": "Administrator",
  "os_type": "windows",
  "auth_type": "password",
  "password": "SecurePass123"
}
```

2. Verify password encrypted

**Expected Results**:
- Password stored securely
- Encryption verified

---

### Test Case 13.3: Open Terminal Session

**Objective**: Start web-based SSH session

**Test Steps**:
1. Create server credential
2. Connect to terminal (WebSocket or HTTP)
3. Verify session established
4. Verify prompt displayed

**Expected Results**:
- Connection successful
- Interactive terminal

---

### Test Case 13.4: Execute Terminal Command

**Objective**: Run commands via web terminal

**WebSocket Endpoint**: `WS /ws/terminal/{session_id}`

**Test Steps**:
1. Open terminal session
2. Send command: `ls -la`
3. Verify output received
4. Send another command: `whoami`
5. Verify output

**Expected Results**:
- Commands execute
- Output streamed back

---

### Test Case 13.5: Terminal Session Recording

**Objective**: Verify session recording for audit

**Test Steps**:
1. Open terminal
2. Execute several commands
3. Close session
4. Query audit logs: `GET /api/audit/terminal-sessions`
5. Verify session recorded:
   - User, timestamp
   - Server connected to
   - Commands executed

**Expected Results**:
- Session fully recorded
- Audit trail complete

---

### Test Case 13.6: Multiple Terminal Sessions

**Objective**: Support concurrent sessions

**Test Steps**:
1. Open terminal to server A
2. Open terminal to server B
3. Execute commands in both
4. Verify sessions independent
5. Verify output not mixed

**Expected Results**:
- Multiple sessions supported
- No cross-contamination

---

### Test Case 13.7: Terminal Session Timeout

**Objective**: Auto-close inactive sessions

**Test Steps**:
1. Open terminal
2. Leave idle for timeout period
3. Verify session auto-closed
4. Verify error message on next command

**Expected Results**:
- Idle timeout enforced
- Graceful closure

---

## FEATURE 14: AGENT MODE

### Test Case 14.1: Start Agent Session

**Objective**: Initiate autonomous troubleshooting agent

**API Endpoint**: `POST /api/agent/start`

**Test Steps**:
1. Start agent:
```json
{
  "goal": "Investigate and resolve high CPU alert on server-01",
  "alert_id": 123,
  "auto_approve": false
}
```

2. Verify response:
   - Session ID
   - Status: "running"
   - First step proposed

**Expected Results**:
- Agent session created
- Goal set
- Initial plan generated

---

### Test Case 14.2: Agent Proposes Step

**Objective**: Agent proposes troubleshooting step

**Test Steps**:
1. Start agent session
2. Wait for agent to propose step
3. Verify step includes:
   - Step type (command/analysis/question)
   - Description
   - Rationale
   - Status: "pending_approval"

**Expected Results**:
- Step proposed
- Awaiting user approval

---

### Test Case 14.3: Approve Agent Step

**Objective**: Approve and execute proposed step

**API Endpoint**: `POST /api/agent/sessions/{session_id}/approve-step`

**Test Steps**:
1. Agent proposes step
2. Approve step
3. Verify:
   - Step status: "approved"
   - Step executes
   - Output captured
   - Agent analyzes result
   - Next step proposed

**Expected Results**:
- Step executed
- Agent continues

---

### Test Case 14.4: Reject Agent Step

**Objective**: Reject proposed step

**API Endpoint**: `POST /api/agent/sessions/{session_id}/reject-step`

**Test Steps**:
1. Agent proposes step
2. Reject with reason:
```json
{
  "reason": "Too risky for production"
}
```

3. Verify:
   - Step cancelled
   - Agent proposes alternative

**Expected Results**:
- Rejection handled
- Agent adapts

---

### Test Case 14.5: Agent Asks Question

**Objective**: Agent requests information

**Test Steps**:
1. Agent asks: "Should I restart the service?"
2. Verify step type: "question"
3. Answer question: `POST /api/agent/sessions/{session_id}/answer-question`
```json
{
  "answer": "Yes, proceed with restart"
}
```

4. Verify agent uses answer to proceed

**Expected Results**:
- Interactive questioning works
- Agent incorporates answers

---

### Test Case 14.6: Agent Auto-Approve Mode

**Objective**: Fully autonomous agent

**Test Steps**:
1. Start agent with `auto_approve: true`
2. Verify all steps auto-approved
3. Verify agent runs to completion
4. Verify final summary

**Expected Results**:
- Fully autonomous
- No user intervention needed
- Safe steps only (based on risk assessment)

---

### Test Case 14.7: Agent Session Status

**Objective**: Monitor agent progress

**API Endpoint**: `GET /api/agent/sessions/{session_id}`

**Test Steps**:
1. Start agent
2. Periodically query status
3. Verify response includes:
   - Current step
   - Progress (e.g., "Step 3 of 5")
   - Status: running/paused/completed/failed
   - Step history

**Expected Results**:
- Real-time status
- Progress tracking

---

### Test Case 14.8: Agent WebSocket Updates

**Objective**: Real-time agent updates

**WebSocket Endpoint**: `WS /ws/agent/{session_id}`

**Test Steps**:
1. Connect to WebSocket
2. Start agent
3. Verify real-time messages:
   - Step proposed
   - Step executing
   - Step completed
   - Results

**Expected Results**:
- Live updates
- WebSocket stream works

---

### Test Case 14.9: Agent Completes Successfully

**Objective**: Agent resolves issue

**Test Steps**:
1. Start agent with resolvable issue
2. Approve all steps (or auto-approve)
3. Wait for completion
4. Verify final status:
   - Status: "completed"
   - Goal achieved
   - Summary of actions taken
   - Recommendations

**Expected Results**:
- Successful completion
- Issue resolved
- Complete summary

---

### Test Case 14.10: Agent Fails to Resolve

**Objective**: Handle agent failure gracefully

**Test Steps**:
1. Start agent with unresolvable issue
2. Let agent try multiple approaches
3. Verify:
   - Agent recognizes failure
   - Status: "failed"
   - Explanation provided
   - Escalation recommendation

**Expected Results**:
- Failure handled gracefully
- Escalation path provided

---

## FEATURE 15: USER MANAGEMENT & RBAC

### Test Case 15.1: Create User

**Objective**: Create new user account

**API Endpoint**: `POST /api/users`

**Test Steps**:
1. Authenticate as admin
2. Create user:
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "role": "engineer",
  "full_name": "John Doe"
}
```

3. Verify response: 201 Created
4. Verify password hashed in database

**Expected Results**:
- User created
- Password hashed (bcrypt)
- Role assigned

---

### Test Case 15.2: User Login

**Objective**: Authenticate user

**API Endpoint**: `POST /api/auth/login`

**Test Steps**:
1. Login:
```json
{
  "username": "john_doe",
  "password": "SecurePass123!"
}
```

2. Verify response:
   - JWT token
   - HTTP-only cookie
   - User details

3. Verify token valid
4. Verify cookie attributes (HttpOnly, Secure, SameSite)

**Expected Results**:
- Authentication successful
- Secure token issued

---

### Test Case 15.3: Invalid Login

**Objective**: Reject invalid credentials

**Test Steps**:
1. Login with wrong password
2. Verify response: 401 Unauthorized
3. Verify error message

**Expected Results**:
- Login rejected
- Generic error (no user enumeration)

---

### Test Case 15.4: User Logout

**Objective**: Logout and invalidate token

**API Endpoint**: `POST /api/auth/logout`

**Test Steps**:
1. Login
2. Logout
3. Verify token invalidated
4. Attempt to use old token
5. Verify 401 Unauthorized

**Expected Results**:
- Logout successful
- Token blacklisted or expired

---

### Test Case 15.5: Refresh Token

**Objective**: Refresh JWT token

**API Endpoint**: `POST /api/auth/refresh`

**Test Steps**:
1. Login (get initial token)
2. Wait for token near expiry
3. Refresh token
4. Verify new token issued
5. Verify new expiration extended

**Expected Results**:
- Token refresh works
- Expiry updated

---

### Test Case 15.6: RBAC - Admin Permissions

**Objective**: Verify admin has full access

**Test Steps**:
1. Login as admin
2. Test access to:
   - User management (✓)
   - Create/update/delete runbooks (✓)
   - View all alerts (✓)
   - Access settings (✓)
   - Manage LLM providers (✓)

**Expected Results**:
- Admin has all permissions

---

### Test Case 15.7: RBAC - Engineer Permissions

**Objective**: Verify engineer has appropriate access

**Test Steps**:
1. Login as engineer
2. Test access:
   - View alerts (✓)
   - Create runbooks (✓)
   - Execute runbooks (✓)
   - User management (✗)
   - Delete users (✗)

**Expected Results**:
- Engineer permissions enforced
- Cannot manage users

---

### Test Case 15.8: RBAC - Operator Permissions

**Objective**: Verify operator has limited access

**Test Steps**:
1. Login as operator
2. Test access:
   - View alerts (✓)
   - Acknowledge alerts (✓)
   - Execute runbooks (✓)
   - Create runbooks (✗)
   - Modify rules (✗)
   - User management (✗)

**Expected Results**:
- Read-only + execute
- Cannot create/modify

---

### Test Case 15.9: Create Group

**Objective**: Create user group

**API Endpoint**: `POST /api/groups`

**Test Steps**:
1. Create group:
```json
{
  "name": "Database Team",
  "description": "Database administrators",
  "permissions": ["view_alerts", "execute_runbooks", "manage_applications"]
}
```

2. Verify group created

**Expected Results**:
- Group created
- Permissions assigned

---

### Test Case 15.10: Add User to Group

**Objective**: Add user to group

**API Endpoint**: `POST /api/groups/{group_id}/members`

**Test Steps**:
1. Create group
2. Add user:
```json
{
  "user_id": 123
}
```

3. Verify user inherits group permissions

**Expected Results**:
- User added to group
- Permissions combined

---

### Test Case 15.11: Runbook ACL - Grant Access

**Objective**: Grant user access to specific runbook

**Test Steps**:
1. Create runbook (as admin)
2. Grant access to engineer:
```json
{
  "runbook_id": 123,
  "user_id": 456,
  "permission": "execute"
}
```

3. Login as engineer
4. Verify can execute runbook
5. Verify cannot delete runbook

**Expected Results**:
- Resource-level permissions work
- Granular access control

---

### Test Case 15.12: Runbook ACL - Deny Access

**Objective**: Verify users without ACL cannot access

**Test Steps**:
1. Create private runbook (owner: user A)
2. Login as user B
3. Attempt to view runbook
4. Verify 403 Forbidden

**Expected Results**:
- Access denied
- Proper error code

---

### Test Case 15.13: Change Password

**Objective**: User changes own password

**API Endpoint**: `POST /api/users/{user_id}/change-password`

**Test Steps**:
1. Login as user
2. Change password:
```json
{
  "old_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

3. Verify password changed
4. Login with new password
5. Verify old password no longer works

**Expected Results**:
- Password change successful
- Immediate effect

---

### Test Case 15.14: Update User

**Objective**: Update user details

**API Endpoint**: `PUT /api/users/{user_id}`

**Test Steps**:
1. Update user:
```json
{
  "email": "newemail@example.com",
  "full_name": "John A. Doe"
}
```

2. Verify updates persisted

**Expected Results**:
- User updated
- Email and name changed

---

### Test Case 15.15: Delete User

**Objective**: Remove user account

**API Endpoint**: `DELETE /api/users/{user_id}`

**Test Steps**:
1. Create user
2. Delete user (as admin)
3. Verify user removed
4. Attempt login - verify fails
5. Verify user's data handled (alerts, sessions, etc.)

**Expected Results**:
- User deleted
- Login disabled
- Data cleanup or reassignment

---

### Test Case 15.16: Custom Role Creation

**Objective**: Create custom role

**API Endpoint**: `POST /api/roles`

**Test Steps**:
1. Create custom role:
```json
{
  "name": "Security Auditor",
  "permissions": [
    "view_alerts",
    "view_audit_logs",
    "view_runbooks",
    "view_users"
  ]
}
```

2. Assign role to user
3. Verify permissions enforced

**Expected Results**:
- Custom role works
- Flexible RBAC

---

## FEATURE 16: ANALYTICS & METRICS

### Test Case 16.1: Calculate MTTR - Aggregate

**Objective**: Get overall MTTR statistics

**API Endpoint**: `GET /api/analytics/mttr/aggregate`

**Test Steps**:
1. Create test incidents with resolution times
2. Query aggregate MTTR:
   - `GET /api/analytics/mttr/aggregate?start=2025-12-01&end=2025-12-31`

3. Verify response includes:
   - Average MTTR
   - Median MTTR
   - Min/Max MTTR
   - Total incidents

**Expected Results**:
- Accurate MTTR calculation
- Statistical summary

---

### Test Case 16.2: MTTR Breakdown by Service

**Objective**: MTTR per service

**API Endpoint**: `GET /api/analytics/mttr/breakdown?dimension=service`

**Test Steps**:
1. Create incidents for multiple services
2. Query breakdown
3. Verify MTTR calculated per service

**Expected Results**:
- Service-level MTTR
- Comparison possible

---

### Test Case 16.3: MTTR Breakdown by Severity

**Objective**: MTTR by severity level

**Test Steps**:
1. Create incidents with various severities
2. Query breakdown by severity
3. Verify separate MTTR for critical, warning, info

**Expected Results**:
- Severity-based MTTR
- Trends visible

---

### Test Case 16.4: MTTR Breakdown by Resolution Type

**Objective**: MTTR by how resolved

**Test Steps**:
1. Create incidents with resolution types:
   - Auto-remediated
   - Manual fix
   - Self-resolved

2. Query breakdown
3. Verify MTTR per resolution type

**Expected Results**:
- Resolution type breakdown
- Auto-remediation efficiency visible

---

### Test Case 16.5: MTTR Trends Over Time

**Objective**: Track MTTR improvements

**API Endpoint**: `GET /api/analytics/mttr/trends`

**Test Steps**:
1. Query trends:
   - `GET /api/analytics/mttr/trends?start=2025-01-01&end=2025-12-31&granularity=month`

2. Verify response:
   - MTTR per month
   - Trend direction (improving/degrading)

**Expected Results**:
- Time-series MTTR data
- Trend analysis

---

### Test Case 16.6: Detect MTTR Regressions

**Objective**: Identify MTTR degradation

**API Endpoint**: `GET /api/analytics/mttr/regressions`

**Test Steps**:
1. Create incidents with increasing MTTR
2. Query regressions
3. Verify alerts for degraded MTTR:
   - Services with regression
   - Magnitude of increase
   - Time period

**Expected Results**:
- Regressions detected
- Alerts generated

---

### Test Case 16.7: Incident Metrics - Time to Detect

**Objective**: Measure detection time

**Test Steps**:
1. Create incident with:
   - Event time: 10:00
   - Detected time: 10:05

2. Query incident metrics
3. Verify time_to_detect = 5 minutes

**Expected Results**:
- Detection time calculated

---

### Test Case 16.8: Incident Metrics - Time to Acknowledge

**Objective**: Measure acknowledgment time

**Test Steps**:
1. Create incident:
   - Detected: 10:00
   - Acknowledged: 10:10

2. Verify time_to_acknowledge = 10 minutes

**Expected Results**:
- Acknowledgment time tracked

---

### Test Case 16.9: Incident Metrics - Time to Engage

**Objective**: Measure engagement time

**Test Steps**:
1. Create incident:
   - Detected: 10:00
   - First action: 10:15

2. Verify time_to_engage = 15 minutes

**Expected Results**:
- Engagement time calculated

---

### Test Case 16.10: Incident Metrics - Time to Resolve

**Objective**: Measure full resolution time

**Test Steps**:
1. Create incident:
   - Detected: 10:00
   - Resolved: 11:30

2. Verify time_to_resolve = 90 minutes

**Expected Results**:
- Resolution time (MTTR) calculated

---

## FEATURE 17: AUDIT & COMPLIANCE

### Test Case 17.1: Audit Log - User Action

**Objective**: Log user actions

**Test Steps**:
1. Perform actions as user:
   - Create runbook
   - Execute runbook
   - Delete alert

2. Query audit logs: `GET /api/audit/logs?user_id={user_id}`
3. Verify all actions logged:
   - Timestamp
   - User
   - Action (create/update/delete/execute)
   - Resource type and ID
   - IP address

**Expected Results**:
- All actions logged
- Complete audit trail

---

### Test Case 17.2: Audit Log - Filter by Resource

**Objective**: View audit for specific resource

**Test Steps**:
1. Perform actions on runbook #123
2. Query: `GET /api/audit/logs?resource_type=runbook&resource_id=123`
3. Verify all actions on that runbook

**Expected Results**:
- Resource-specific audit
- Complete history

---

### Test Case 17.3: Audit Log - Filter by Date Range

**Objective**: Audit logs for time period

**Test Steps**:
1. Query: `GET /api/audit/logs?start=2025-12-01&end=2025-12-31`
2. Verify only logs in range returned

**Expected Results**:
- Date filtering works
- Compliance reporting possible

---

### Test Case 17.4: Terminal Session Audit

**Objective**: Audit terminal sessions

**API Endpoint**: `GET /api/audit/terminal-sessions`

**Test Steps**:
1. Open terminal sessions
2. Execute commands
3. Query session audit
4. Verify logs include:
   - User, server, timestamp
   - Commands executed
   - Session duration

**Expected Results**:
- Terminal sessions logged
- Command history available

---

### Test Case 17.5: Chat Session Audit

**Objective**: Audit chat sessions

**API Endpoint**: `GET /api/audit/chat-sessions`

**Test Steps**:
1. Create chat sessions
2. Exchange messages
3. Query audit
4. Verify logs include:
   - User, LLM provider
   - Message count
   - Timestamps

**Expected Results**:
- Chat sessions logged
- Audit trail for AI interactions

---

### Test Case 17.6: Audit Log - IP Address Tracking

**Objective**: Track user IP addresses

**Test Steps**:
1. Perform actions from specific IP
2. Query audit logs
3. Verify IP address logged

**Expected Results**:
- IP addresses tracked
- Geographic analysis possible

---

### Test Case 17.7: Audit Log Retention

**Objective**: Verify audit log retention policy

**Test Steps**:
1. Create audit logs
2. Wait for retention period
3. Verify old logs purged (or archived)
4. Verify recent logs retained

**Expected Results**:
- Retention policy enforced
- Storage managed

---

## FEATURE 18: LEARNING SYSTEM

### Test Case 18.1: Submit Feedback - Analysis Helpful

**Objective**: Rate AI analysis as helpful

**API Endpoint**: `POST /api/v1/learning/alerts/{alert_id}/feedback`

**Test Steps**:
1. Create alert with analysis
2. Submit feedback:
```json
{
  "helpful": true,
  "rating": 5,
  "accuracy": 5,
  "what_worked": "Root cause identification was spot on",
  "what_missing": ""
}
```

3. Verify feedback stored
4. Verify associated with analysis

**Expected Results**:
- Feedback captured
- Linked to analysis

---

### Test Case 18.2: Submit Feedback - Analysis Not Helpful

**Objective**: Rate analysis as unhelpful

**Test Steps**:
1. Submit negative feedback:
```json
{
  "helpful": false,
  "rating": 2,
  "accuracy": 2,
  "what_worked": "",
  "what_missing": "Missed the connection to recent deployment"
}
```

2. Verify feedback stored

**Expected Results**:
- Negative feedback captured
- Improvement areas noted

---

### Test Case 18.3: Get Feedback for Alert

**Objective**: Retrieve feedback

**API Endpoint**: `GET /api/v1/learning/alerts/{alert_id}/feedback`

**Test Steps**:
1. Submit feedback
2. Query feedback
3. Verify all feedback returned

**Expected Results**:
- Feedback retrievable
- Historical tracking

---

### Test Case 18.4: Rate Runbook Effectiveness

**Objective**: Rate runbook execution

**API Endpoint**: `POST /api/v1/learning/runbooks/{runbook_id}/effectiveness`

**Test Steps**:
1. Execute runbook
2. Rate effectiveness:
```json
{
  "execution_id": 123,
  "rating": 4,
  "resolved_issue": true,
  "comments": "Worked well but could be faster"
}
```

3. Verify rating stored

**Expected Results**:
- Runbook effectiveness tracked
- Optimization data collected

---

### Test Case 18.5: Find Similar Incidents

**Objective**: Find similar past incidents

**API Endpoint**: `GET /api/v1/learning/alerts/{alert_id}/similar-incidents`

**Test Steps**:
1. Create alert
2. Search for similar:
   - Based on embeddings
   - Based on labels

3. Verify similar incidents returned:
   - Similarity score
   - Past resolution methods

**Expected Results**:
- Similar incidents found
- Learning from history

---

### Test Case 18.6: Execution Outcome Tracking

**Objective**: Track runbook success/failure

**Test Steps**:
1. Execute runbook multiple times
2. Track outcomes:
   - Success count
   - Failure count
   - Average duration
   - Cost metrics

3. Query execution statistics
4. Verify trends visible

**Expected Results**:
- Outcome tracking works
- Success rate calculable

---

### Test Case 18.7: Improve Recommendations Over Time

**Objective**: Verify system learns from feedback

**Test Steps**:
1. Create similar alerts over time
2. Submit feedback on analyses
3. Observe recommendations improve
4. Verify feedback incorporated

**Expected Results**:
- Learning improves recommendations
- Feedback loop functional

---

## FEATURE 19: AUTHENTICATION & SECURITY

### Test Case 19.1: JWT Token Generation

**Objective**: Verify JWT token structure

**Test Steps**:
1. Login user
2. Inspect JWT token
3. Verify claims:
   - User ID
   - Username
   - Role
   - Issued at (iat)
   - Expiration (exp)

**Expected Results**:
- Valid JWT structure
- Claims correct

---

### Test Case 19.2: JWT Token Expiration

**Objective**: Verify token expiration enforced

**Test Steps**:
1. Login (get token)
2. Wait for expiration (or mock)
3. Use expired token
4. Verify 401 Unauthorized
5. Verify error: "Token expired"

**Expected Results**:
- Expiration enforced
- Access denied

---

### Test Case 19.3: HTTP-Only Cookie

**Objective**: Verify cookie attributes

**Test Steps**:
1. Login
2. Inspect cookie
3. Verify attributes:
   - HttpOnly: true
   - Secure: true (if HTTPS)
   - SameSite: Lax or Strict

**Expected Results**:
- Secure cookie attributes
- XSS protection

---

### Test Case 19.4: Rate Limiting - Auth Endpoints

**Objective**: Prevent brute force attacks

**Test Steps**:
1. Attempt login 10 times rapidly
2. Verify rate limit triggered
3. Verify 429 Too Many Requests
4. Wait for rate limit reset
5. Verify access restored

**Expected Results**:
- Rate limiting active
- Brute force prevented

---

### Test Case 19.5: Password Hashing - bcrypt

**Objective**: Verify password security

**Test Steps**:
1. Create user with password
2. Query database directly
3. Verify password hashed (bcrypt)
4. Verify plaintext not stored

**Expected Results**:
- Passwords hashed
- bcrypt algorithm used

---

### Test Case 19.6: API Key Encryption - Fernet

**Objective**: Verify API keys encrypted

**Test Steps**:
1. Create LLM provider with API key
2. Query database
3. Verify API key encrypted (Fernet)
4. Verify decryption works for usage

**Expected Results**:
- API keys encrypted at rest
- Decryption on-demand

---

### Test Case 19.7: SSH Key Encryption

**Objective**: Verify SSH keys encrypted

**Test Steps**:
1. Create server credential with SSH key
2. Query database
3. Verify SSH key encrypted
4. Verify decryption for terminal connection

**Expected Results**:
- SSH keys encrypted
- Secure storage

---

### Test Case 19.8: SQL Injection Prevention

**Objective**: Test for SQL injection vulnerabilities

**Test Steps**:
1. Attempt injection in various endpoints:
   - Login: `username: "admin' OR '1'='1"`
   - Alert filter: `alertname: "'; DROP TABLE alerts; --"`

2. Verify:
   - No SQL error messages
   - No unauthorized data access
   - Inputs properly sanitized

**Expected Results**:
- SQL injection prevented
- Parameterized queries used

---

### Test Case 19.9: XSS Prevention

**Objective**: Test for XSS vulnerabilities

**Test Steps**:
1. Inject scripts in inputs:
   - Alert annotation: `<script>alert('XSS')</script>`
   - Runbook name: `"><script>alert('XSS')</script>`

2. Verify:
   - Scripts not executed
   - Content escaped/sanitized
   - CSP headers present

**Expected Results**:
- XSS prevented
- Content properly escaped

---

### Test Case 19.10: Authorization Bypass Prevention

**Objective**: Verify authorization checks

**Test Steps**:
1. Login as operator
2. Attempt to access admin endpoint:
   - `POST /api/users` (create user)

3. Verify 403 Forbidden
4. Verify consistent authorization checks

**Expected Results**:
- Authorization enforced
- Privilege escalation prevented

---

---

## INTEGRATION TEST SCENARIOS

### Integration Test 1: Alert → Analysis → Remediation Flow

**Objective**: End-to-end automated remediation

**Steps**:
1. Configure LLM provider
2. Create auto-analyze rule
3. Create runbook with auto-execute
4. Link runbook to alert pattern
5. Send alert via webhook
6. Verify:
   - Alert ingested
   - Auto-analyzed
   - Runbook triggered
   - Execution successful
   - Alert resolved

**Expected Results**:
- Complete automation
- No manual intervention

---

### Integration Test 2: Alert → Clustering → Impact Analysis

**Objective**: Alert correlation and analysis

**Steps**:
1. Send related alerts (same service, time window)
2. Verify alerts clustered
3. Query ITSM for recent changes
4. Correlate changes with cluster
5. Verify impact analysis

**Expected Results**:
- Alerts grouped
- Changes correlated
- Root cause identified

---

### Integration Test 3: Knowledge Base → AI Analysis Enhancement

**Objective**: Context-aware analysis using KB

**Steps**:
1. Upload architecture documents to KB
2. Create alert for service documented in KB
3. Trigger AI analysis
4. Verify analysis includes KB context

**Expected Results**:
- KB searched automatically
- Relevant docs used in analysis
- More accurate recommendations

---

### Integration Test 4: Scheduled Runbook → Execution → Audit

**Objective**: Scheduled maintenance workflow

**Steps**:
1. Create maintenance runbook
2. Schedule for specific time
3. Wait for execution
4. Verify execution logged
5. Verify audit trail

**Expected Results**:
- Scheduled execution works
- Complete audit trail

---

### Integration Test 5: Dashboard → Panels → Snapshots

**Objective**: Dashboard workflow

**Steps**:
1. Create Prometheus datasource
2. Create dashboard
3. Add multiple panels
4. Create snapshot
5. Share snapshot (public URL)
6. Verify snapshot accessible

**Expected Results**:
- Dashboard fully functional
- Snapshot sharing works

---

### Integration Test 6: User → RBAC → Runbook ACL

**Objective**: Multi-level access control

**Steps**:
1. Create operator user
2. Create runbook with ACL
3. Grant execute permission to operator
4. Login as operator
5. Execute runbook
6. Attempt to delete runbook (should fail)

**Expected Results**:
- Granular permissions work
- Role + resource-level ACL enforced

---

### Integration Test 7: Terminal → Command Execution → Audit

**Objective**: Terminal workflow with audit

**Steps**:
1. Create server credential
2. Open terminal session
3. Execute commands
4. Close session
5. Verify session audit
6. Verify commands recorded

**Expected Results**:
- Terminal functional
- Complete audit trail

---

### Integration Test 8: Agent → Runbook → Feedback

**Objective**: Agent-driven remediation with learning

**Steps**:
1. Start agent session
2. Agent proposes runbook execution
3. Approve and execute
4. Submit effectiveness feedback
5. Verify feedback stored

**Expected Results**:
- Agent autonomy works
- Feedback loop complete

---

---

## PERFORMANCE TEST SCENARIOS

### Performance Test 1: High Alert Volume

**Objective**: Handle alert bursts

**Test**:
- Send 1000 alerts via webhook in 1 minute
- Measure:
  - Ingestion rate (alerts/sec)
  - Processing time per alert
  - Database write performance
  - API response time

**Success Criteria**:
- >100 alerts/sec ingestion
- <500ms average processing time
- No data loss

---

### Performance Test 2: Concurrent Runbook Executions

**Objective**: Parallel runbook execution

**Test**:
- Execute 50 runbooks concurrently
- Measure:
  - Execution concurrency
  - Resource utilization (CPU, memory)
  - Completion time
  - Failure rate

**Success Criteria**:
- All executions complete
- <5% failure rate
- Linear scaling

---

### Performance Test 3: Large Knowledge Base Search

**Objective**: Vector search performance

**Test**:
- Upload 10,000 documents
- Generate embeddings
- Perform 100 similarity searches
- Measure:
  - Search latency
  - Result accuracy
  - Database query time

**Success Criteria**:
- <1 second per search
- Relevant results in top 10

---

### Performance Test 4: Dashboard Query Performance

**Objective**: Dashboard rendering speed

**Test**:
- Create dashboard with 20 panels
- Each panel queries Prometheus
- Measure:
  - Time to load all panels
  - Query execution time
  - Data transfer size

**Success Criteria**:
- <5 seconds full load
- Parallel query execution

---

### Performance Test 5: WebSocket Connection Scale

**Objective**: Concurrent WebSocket connections

**Test**:
- Open 100 WebSocket connections (chat/terminal)
- Send messages on all connections
- Measure:
  - Connection stability
  - Message latency
  - Memory usage

**Success Criteria**:
- All connections stable
- <100ms message latency

---

---

## SECURITY TEST SCENARIOS

### Security Test 1: Authentication Bypass

**Objective**: Attempt to bypass authentication

**Tests**:
- Access protected endpoints without token
- Use invalid token
- Use expired token
- Use token with modified claims

**Expected**:
- All attempts rejected with 401

---

### Security Test 2: Authorization Bypass

**Objective**: Attempt privilege escalation

**Tests**:
- Operator tries to create users
- Engineer tries to access admin settings
- User tries to access another user's data

**Expected**:
- All attempts rejected with 403

---

### Security Test 3: Injection Attacks

**Objective**: Test input validation

**Tests**:
- SQL injection in all inputs
- NoSQL injection
- Command injection in runbook commands
- LDAP injection (if applicable)

**Expected**:
- All inputs sanitized
- No code execution

---

### Security Test 4: Sensitive Data Exposure

**Objective**: Verify data protection

**Tests**:
- Check API responses for exposed secrets
- Verify password hashes not returned
- Verify API keys encrypted in database
- Check logs for sensitive data

**Expected**:
- No sensitive data leaked
- Proper encryption

---

### Security Test 5: CORS and CSRF

**Objective**: Cross-origin protections

**Tests**:
- Attempt CORS bypass
- CSRF attack simulation
- Origin validation

**Expected**:
- CORS policy enforced
- CSRF tokens validated

---

---

## TEST EXECUTION CHECKLIST

### Pre-Test Setup
- [ ] Environment configured
- [ ] Database initialized
- [ ] Test data prepared
- [ ] LLM provider configured
- [ ] External dependencies ready (Prometheus, Grafana)

### Test Execution
- [ ] All API endpoints tested
- [ ] All CRUD operations verified
- [ ] Edge cases covered
- [ ] Error handling tested
- [ ] Integration flows validated

### Post-Test Validation
- [ ] No data corruption
- [ ] Database cleanup
- [ ] Logs reviewed
- [ ] Performance metrics captured
- [ ] Security scan passed

### Documentation
- [ ] Test results documented
- [ ] Bugs filed
- [ ] Coverage report generated
- [ ] Performance baseline established

---

## APPENDIX

### Test Data Templates

#### Sample Alert JSON
```json
{
  "receiver": "remediation-engine",
  "status": "firing",
  "alerts": [{
    "status": "firing",
    "labels": {
      "alertname": "HighCPUUsage",
      "severity": "critical",
      "instance": "server-01",
      "job": "node-exporter"
    },
    "annotations": {
      "summary": "CPU usage is above 90%",
      "description": "Host server-01 has CPU usage above 90%"
    },
    "startsAt": "2025-12-29T10:00:00Z",
    "fingerprint": "abc123"
  }]
}
```

#### Sample Runbook YAML
```yaml
name: "Restart Web Service"
description: "Restarts the web service and clears cache"
category: "web"
enabled: true
auto_execute: false
approval_required: true
steps:
  - order: 1
    name: "Check service status"
    step_type: "command"
    command: "systemctl status nginx"
    os_type: "linux"
  - order: 2
    name: "Restart service"
    step_type: "command"
    command: "sudo systemctl restart nginx"
    os_type: "linux"
    expected_exit_code: 0
```

---

**END OF COMPREHENSIVE TEST PLAN**

---

This test plan covers all 19 features with detailed test cases, integration scenarios, performance tests, and security tests. Each test case includes:
- Clear objectives
- API endpoints
- Step-by-step instructions
- Expected results
- Sample data

Total Test Cases: 200+ individual test cases across all features.
