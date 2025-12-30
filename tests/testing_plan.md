# PYTEST TEST PLAN - LOCAL & INTEGRATION TESTING

**Version**: 1.0
**Date**: 2025-12-30
**Purpose**: Comprehensive pytest-based testing plan (Planning Only - No Code)

---

## TABLE OF CONTENTS

1. [Test Environment Setup](#test-environment-setup)
2. [Test Directory Structure](#test-directory-structure)
3. [Test Fixtures & Shared Resources](#test-fixtures--shared-resources)
4. [Unit Test Cases](#unit-test-cases)
5. [Integration Test Cases](#integration-test-cases)
6. [API Test Cases](#api-test-cases)
7. [Database Test Cases](#database-test-cases)
8. [Test Execution Strategy](#test-execution-strategy)
9. [Test Data Management](#test-data-management)
10. [CI/CD Integration](#cicd-integration)

---

## TEST ENVIRONMENT SETUP

### 1.1 Local Development Environment

**Prerequisites**:
- Python 3.9+
- PostgreSQL 14+ with pgvector extension
- Redis (optional, for caching tests)
- Docker (for containerized dependencies)

**Environment Variables** (`.env.test`):
```
DATABASE_URL=postgresql://test_user:test_pass@localhost:5432/remediation_test
REDIS_URL=redis://localhost:6379/1
SECRET_KEY=test-secret-key-for-testing-only
ANTHROPIC_API_KEY=test-key-or-mock
ENVIRONMENT=test
LOG_LEVEL=DEBUG
```

**Test Database**:
- Name: `remediation_test`
- Isolated from development and production
- Reset before each test run
- Separate schema for test data

---

### 1.2 Test Dependencies

**Production Dependencies** (from `requirements.txt`):
- Already installed

**Test-Only Dependencies** (add to `requirements-dev.txt`):
```
# Testing framework
pytest==7.4.3
pytest-asyncio==0.21.1          # For async tests
pytest-cov==4.1.0               # Coverage reporting
pytest-xdist==3.5.0             # Parallel execution
pytest-timeout==2.2.0           # Timeout for slow tests
pytest-mock==3.12.0             # Mocking utilities

# Test utilities
httpx==0.25.2                   # FastAPI test client
faker==20.1.0                   # Fake data generation
factory-boy==3.3.0              # Test fixture factories
freezegun==1.4.0                # Mock datetime
responses==0.24.1               # Mock HTTP requests

# Database testing
pytest-postgresql==5.0.0        # PostgreSQL fixtures
sqlalchemy-utils==0.41.1        # Database utilities

# API testing
requests-mock==1.11.0           # Mock external APIs
```

---

### 1.3 Docker Test Environment

**docker-compose.test.yml**:
```yaml
version: '3.8'

services:
  postgres-test:
    image: postgres:14
    environment:
      POSTGRES_DB: remediation_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
    ports:
      - "5433:5432"  # Different port to avoid conflicts
    volumes:
      - postgres-test-data:/var/lib/postgresql/data
    command: postgres -c shared_preload_libraries=vector

  redis-test:
    image: redis:7-alpine
    ports:
      - "6380:6379"

volumes:
  postgres-test-data:
```

**Usage**:
```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run tests
pytest

# Stop test environment
docker-compose -f docker-compose.test.yml down -v
```

---

## TEST DIRECTORY STRUCTURE

```
tests/
├── conftest.py                    # Global fixtures and configuration
├── pytest.ini                     # Pytest configuration
├── __init__.py
│
├── fixtures/                      # Shared test fixtures
│   ├── __init__.py
│   ├── database.py               # DB fixtures (test_db, session)
│   ├── auth.py                   # Auth fixtures (test users, tokens)
│   ├── llm.py                    # LLM provider mocks
│   └── factories.py              # Factory Boy model factories
│
├── test_data/                     # Static test data
│   ├── alerts/
│   │   ├── firing_alerts.json
│   │   ├── resolved_alerts.json
│   │   └── malformed_alerts.json
│   ├── runbooks/
│   │   ├── linux_runbook.yaml
│   │   ├── windows_runbook.yaml
│   │   └── api_runbook.yaml
│   ├── knowledge/
│   │   ├── sample_doc.md
│   │   ├── sample_doc.pdf
│   │   └── sample_image.png
│   └── users.json
│
├── unit/                          # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── test_models/              # Model tests
│   │   ├── test_alert_model.py
│   │   ├── test_user_model.py
│   │   ├── test_runbook_model.py
│   │   └── test_knowledge_model.py
│   ├── test_services/            # Service layer tests
│   │   ├── test_alert_service.py
│   │   ├── test_remediation_service.py
│   │   ├── test_llm_service.py
│   │   └── test_knowledge_service.py
│   ├── test_utils/               # Utility function tests
│   │   ├── test_validators.py
│   │   ├── test_templating.py
│   │   └── test_encryption.py
│   └── test_schemas/             # Pydantic schema tests
│       ├── test_alert_schemas.py
│       └── test_runbook_schemas.py
│
├── integration/                   # Integration tests (slower)
│   ├── __init__.py
│   ├── test_alert_flow.py        # Alert ingestion → analysis
│   ├── test_remediation_flow.py  # Runbook execution flow
│   ├── test_knowledge_flow.py    # Document upload → search
│   ├── test_chat_flow.py         # Chat session workflow
│   ├── test_scheduler_flow.py    # Scheduled job execution
│   └── test_itsm_flow.py         # ITSM integration flow
│
├── api/                           # API endpoint tests
│   ├── __init__.py
│   ├── test_auth_api.py
│   ├── test_alerts_api.py
│   ├── test_rules_api.py
│   ├── test_remediation_api.py
│   ├── test_chat_api.py
│   ├── test_knowledge_api.py
│   ├── test_applications_api.py
│   ├── test_dashboard_api.py
│   └── test_webhook_api.py
│
├── database/                      # Database-specific tests
│   ├── __init__.py
│   ├── test_migrations.py
│   ├── test_queries.py
│   ├── test_transactions.py
│   └── test_constraints.py
│
├── security/                      # Security tests
│   ├── __init__.py
│   ├── test_authentication.py
│   ├── test_authorization.py
│   ├── test_rbac.py
│   ├── test_injection.py
│   └── test_encryption.py
│
└── performance/                   # Performance tests
    ├── __init__.py
    ├── test_query_performance.py
    ├── test_embedding_performance.py
    └── test_concurrent_execution.py
```

---

## TEST FIXTURES & SHARED RESOURCES

### 3.1 Database Fixtures

**Purpose**: Provide clean database for each test

**Fixtures Needed**:

1. **test_db_engine**: SQLAlchemy engine for test database
2. **test_db_session**: Database session (rolled back after test)
3. **clean_db**: Fresh database with tables created
4. **seeded_db**: Database with basic seed data

**Scope**:
- `test_db_engine`: session (reuse across module)
- `test_db_session`: function (new for each test)
- `clean_db`: function
- `seeded_db`: module (reuse for read-only tests)

---

### 3.2 Authentication Fixtures

**Fixtures Needed**:

1. **test_admin_user**: Admin user instance
2. **test_engineer_user**: Engineer user instance
3. **test_operator_user**: Operator user instance
4. **admin_token**: Valid JWT token for admin
5. **engineer_token**: Valid JWT token for engineer
6. **operator_token**: Valid JWT token for operator
7. **expired_token**: Expired JWT token
8. **invalid_token**: Malformed JWT token

**Usage**:
- Test RBAC permissions
- Test API authentication
- Test token validation

---

### 3.3 LLM Provider Mocks

**Fixtures Needed**:

1. **mock_anthropic**: Mock Anthropic API responses
2. **mock_openai**: Mock OpenAI API responses
3. **mock_llm_provider**: Generic LLM provider instance
4. **mock_analysis_response**: Predefined analysis response

**Purpose**:
- Avoid actual API calls during tests
- Control LLM responses for deterministic tests
- Test error handling (rate limits, timeouts)

---

### 3.4 Factory Fixtures

**Factories Needed**:

1. **UserFactory**: Generate test users
2. **AlertFactory**: Generate test alerts
3. **RunbookFactory**: Generate test runbooks
4. **RuleFactory**: Generate test rules
5. **DesignDocumentFactory**: Generate test documents
6. **ApplicationFactory**: Generate test applications

**Benefits**:
- Generate test data on-demand
- Customize attributes per test
- Avoid hardcoded test data

---

### 3.5 FastAPI Test Client

**Fixture Needed**:
- **client**: TestClient instance for API testing

**Purpose**:
- Make HTTP requests to API
- No actual server needed
- Fast and isolated

---

## UNIT TEST CASES

### 4.1 Model Tests

#### Test Case Group: Alert Model

**Test File**: `tests/unit/test_models/test_alert_model.py`

**Test Cases**:

1. **test_alert_creation**
   - Create alert with all required fields
   - Verify all fields persisted correctly
   - Verify timestamps set automatically

2. **test_alert_fingerprint_generation**
   - Create alert without fingerprint
   - Verify fingerprint auto-generated
   - Verify fingerprint uniqueness

3. **test_alert_status_transitions**
   - Create firing alert
   - Change status to resolved
   - Verify status updated
   - Verify resolved_at timestamp set

4. **test_alert_labels_json**
   - Create alert with labels
   - Verify labels stored as JSON
   - Verify labels retrievable

5. **test_alert_relationship_to_rule**
   - Create alert with matched rule
   - Verify relationship established
   - Verify can access rule from alert

6. **test_alert_relationship_to_cluster**
   - Create alert in cluster
   - Verify cluster relationship
   - Verify bidirectional access

7. **test_alert_validation_required_fields**
   - Attempt to create alert without alertname
   - Verify validation error raised
   - Verify error message clear

8. **test_alert_cascade_delete**
   - Create alert with related entities
   - Delete alert
   - Verify cascade behavior (keep/delete related)

---

#### Test Case Group: User Model

**Test File**: `tests/unit/test_models/test_user_model.py`

**Test Cases**:

1. **test_user_creation**
   - Create user with valid data
   - Verify user persisted
   - Verify password hashed (not plaintext)

2. **test_user_password_hashing**
   - Create user with password "Test123"
   - Verify password_hash != "Test123"
   - Verify password_hash is bcrypt format

3. **test_user_password_verification**
   - Create user
   - Verify correct password validates
   - Verify incorrect password fails

4. **test_user_unique_username**
   - Create user with username "test"
   - Attempt to create another user "test"
   - Verify IntegrityError raised

5. **test_user_unique_email**
   - Create user with email
   - Attempt duplicate email
   - Verify error raised

6. **test_user_role_validation**
   - Create user with valid role
   - Attempt invalid role
   - Verify validation

7. **test_user_is_active_default**
   - Create user without specifying is_active
   - Verify defaults to True

8. **test_user_last_login_tracking**
   - Create user
   - Simulate login
   - Verify last_login updated

---

#### Test Case Group: Runbook Model

**Test File**: `tests/unit/test_models/test_runbook_model.py`

**Test Cases**:

1. **test_runbook_creation**
   - Create runbook with basic fields
   - Verify persisted

2. **test_runbook_version_increment**
   - Create runbook (version 1)
   - Update runbook
   - Verify version incremented to 2

3. **test_runbook_steps_relationship**
   - Create runbook with 3 steps
   - Verify steps count = 3
   - Verify step order preserved

4. **test_runbook_triggers_relationship**
   - Create runbook with 2 triggers
   - Verify triggers accessible
   - Verify can filter by trigger

5. **test_runbook_safety_defaults**
   - Create runbook without safety settings
   - Verify max_executions_per_hour defaults
   - Verify cooldown_minutes defaults

6. **test_runbook_enable_disable**
   - Create enabled runbook
   - Set enabled=False
   - Verify execution blocked when disabled

7. **test_runbook_cascade_delete_steps**
   - Create runbook with steps
   - Delete runbook
   - Verify steps also deleted

---

### 4.2 Service Layer Tests

#### Test Case Group: Alert Service

**Test File**: `tests/unit/test_services/test_alert_service.py`

**Test Cases**:

1. **test_ingest_alert_firing**
   - Call ingest_alert() with firing alert
   - Verify alert created in database
   - Verify status = "firing"

2. **test_ingest_alert_duplicate_fingerprint**
   - Ingest alert with fingerprint "abc123"
   - Ingest same alert again
   - Verify only 1 alert in database (update, not create)

3. **test_ingest_alert_resolved**
   - Ingest firing alert
   - Ingest resolved alert with same fingerprint
   - Verify status updated to "resolved"
   - Verify endsAt timestamp set

4. **test_match_alert_to_rule**
   - Create rule matching "HighCPU"
   - Ingest alert "HighCPU"
   - Verify alert matched to rule
   - Verify matched_rule_id set

5. **test_match_alert_priority**
   - Create 2 overlapping rules (priority 10 and 5)
   - Ingest matching alert
   - Verify higher priority rule matched

6. **test_auto_analyze_alert**
   - Create auto-analyze rule
   - Ingest matching alert
   - Verify analyze_alert() called
   - Verify analyzed=True

7. **test_ignore_alert_action**
   - Create rule with action="ignore"
   - Ingest matching alert
   - Verify alert stored but not analyzed

8. **test_get_alert_stats**
   - Create 10 firing, 5 resolved alerts
   - Call get_alert_stats()
   - Verify counts accurate

9. **test_filter_alerts_by_severity**
   - Create alerts with mixed severities
   - Call filter_alerts(severity="critical")
   - Verify only critical returned

10. **test_pagination_alerts**
    - Create 100 alerts
    - Call get_alerts(page=2, page_size=20)
    - Verify returns alerts 21-40

---

#### Test Case Group: Remediation Service

**Test File**: `tests/unit/test_services/test_remediation_service.py`

**Test Cases**:

1. **test_create_runbook**
   - Call create_runbook() with valid data
   - Verify runbook created
   - Verify steps created with correct order

2. **test_execute_runbook_approval_required**
   - Create runbook with approval_required=True
   - Call execute_runbook()
   - Verify execution status = "pending_approval"

3. **test_execute_runbook_auto_execute**
   - Create runbook with auto_execute=True
   - Call execute_runbook()
   - Verify status goes to "running"

4. **test_execute_runbook_rate_limit**
   - Create runbook with max_executions_per_hour=3
   - Execute 3 times successfully
   - Execute 4th time
   - Verify rate limit error raised

5. **test_execute_runbook_cooldown**
   - Create runbook with cooldown_minutes=10
   - Execute runbook
   - Immediately try to execute again
   - Verify cooldown error raised

6. **test_execute_step_linux_command**
   - Create step with Linux command
   - Call execute_step()
   - Verify command executed (mock SSH)
   - Verify output captured

7. **test_execute_step_api_call**
   - Create step with API call
   - Call execute_step()
   - Verify HTTP request made (mock)
   - Verify response captured

8. **test_execute_step_timeout**
   - Create step with timeout=5 seconds
   - Mock long-running command (10 seconds)
   - Verify execution times out
   - Verify error captured

9. **test_execute_step_retry**
   - Create step with retry_count=3
   - Mock command fails twice, succeeds third time
   - Verify step eventually succeeds
   - Verify retry count tracked

10. **test_rollback_execution**
    - Create runbook with rollback steps
    - Execute runbook (simulate failure)
    - Verify rollback steps executed
    - Verify rollback status tracked

11. **test_circuit_breaker_opens**
    - Execute runbook 3 times (all fail)
    - Verify circuit breaker opens
    - Attempt execution
    - Verify execution blocked

12. **test_circuit_breaker_recovery**
    - Open circuit breaker
    - Wait for recovery timeout
    - Verify circuit goes to half_open
    - Execute successfully
    - Verify circuit closes

13. **test_blackout_window_blocks_execution**
    - Create blackout window (now - 1 hour)
    - Attempt execution
    - Verify blocked with blackout error

---

#### Test Case Group: LLM Service

**Test File**: `tests/unit/test_services/test_llm_service.py`

**Test Cases**:

1. **test_analyze_alert_anthropic**
   - Mock Anthropic API response
   - Call analyze_alert() with Anthropic provider
   - Verify API called with correct prompt
   - Verify analysis parsed correctly

2. **test_analyze_alert_openai**
   - Mock OpenAI API response
   - Call analyze_alert() with OpenAI provider
   - Verify API called
   - Verify response structure

3. **test_analyze_alert_rate_limit**
   - Mock API rate limit error (429)
   - Call analyze_alert()
   - Verify retry logic triggered
   - Verify eventual success or graceful failure

4. **test_analyze_alert_timeout**
   - Mock API timeout
   - Call analyze_alert()
   - Verify timeout handled
   - Verify error logged

5. **test_chat_message_send**
   - Create chat session
   - Send message
   - Mock LLM response
   - Verify message stored
   - Verify response captured

6. **test_chat_context_retention**
   - Create chat session
   - Send 3 messages
   - Verify context includes all previous messages
   - Verify LLM receives full conversation

7. **test_llm_provider_selection**
   - Create multiple LLM providers
   - Set one as default
   - Call analyze without specifying provider
   - Verify default provider used

8. **test_token_counting**
   - Analyze alert
   - Verify token usage tracked
   - Verify stored in database

---

#### Test Case Group: Knowledge Service

**Test File**: `tests/unit/test_services/test_knowledge_service.py`

**Test Cases**:

1. **test_create_document_markdown**
   - Upload Markdown document
   - Verify document created
   - Verify content chunked
   - Verify embeddings generated

2. **test_create_document_pdf**
   - Upload PDF file
   - Verify text extracted
   - Verify chunks created
   - Verify searchable

3. **test_chunk_document_strategy**
   - Upload long document (5000 words)
   - Verify chunked appropriately (~500 words each)
   - Verify overlap between chunks

4. **test_generate_embeddings**
   - Create document chunk
   - Call generate_embeddings()
   - Verify embedding vector created
   - Verify vector dimension correct (e.g., 1536 for OpenAI)

5. **test_search_full_text**
   - Create 10 documents
   - Search for keyword "database"
   - Verify relevant documents returned
   - Verify ranked by relevance

6. **test_search_similarity**
   - Create documents
   - Search with natural language query
   - Verify semantically similar docs returned
   - Verify similarity scores included

7. **test_search_with_filters**
   - Create docs with various tags
   - Search with tag filter
   - Verify only matching tags returned

8. **test_image_upload**
   - Upload image (PNG)
   - Verify stored
   - Verify thumbnail generated

9. **test_image_ai_analysis**
   - Upload architecture diagram
   - Verify AI analyzes image
   - Verify components extracted

10. **test_delete_document_cascade**
    - Create document with chunks and images
    - Delete document
    - Verify chunks deleted
    - Verify images deleted
    - Verify embeddings removed

---

### 4.3 Utility Function Tests

#### Test Case Group: Validators

**Test File**: `tests/unit/test_utils/test_validators.py`

**Test Cases**:

1. **test_validate_email_valid**
   - Test valid email formats
   - Verify all pass validation

2. **test_validate_email_invalid**
   - Test invalid formats
   - Verify all fail validation

3. **test_validate_cron_expression_valid**
   - Test valid cron expressions
   - Verify all pass

4. **test_validate_cron_expression_invalid**
   - Test invalid expressions
   - Verify all fail

5. **test_validate_regex_pattern**
   - Test valid regex patterns
   - Verify compilation succeeds

6. **test_validate_regex_pattern_invalid**
   - Test invalid regex
   - Verify error raised

---

#### Test Case Group: Templating (Jinja2)

**Test File**: `tests/unit/test_utils/test_templating.py`

**Test Cases**:

1. **test_render_command_template_simple**
   - Template: "echo {{ alert.alertname }}"
   - Context: alertname="HighCPU"
   - Verify output: "echo HighCPU"

2. **test_render_command_template_complex**
   - Template with loops/conditionals
   - Verify correct rendering

3. **test_render_template_missing_variable**
   - Template references undefined variable
   - Verify graceful error or default

4. **test_render_template_escape_shell**
   - Template with shell special chars
   - Verify properly escaped

---

#### Test Case Group: Encryption

**Test File**: `tests/unit/test_utils/test_encryption.py`

**Test Cases**:

1. **test_encrypt_decrypt_api_key**
   - Encrypt API key
   - Decrypt API key
   - Verify matches original

2. **test_encrypt_decrypt_ssh_key**
   - Encrypt SSH private key
   - Decrypt
   - Verify matches

3. **test_password_hashing**
   - Hash password
   - Verify hash != plaintext
   - Verify bcrypt format

4. **test_password_verification**
   - Hash password
   - Verify correct password validates
   - Verify incorrect password fails

---

### 4.4 Schema Validation Tests

#### Test Case Group: Alert Schemas

**Test File**: `tests/unit/test_schemas/test_alert_schemas.py`

**Test Cases**:

1. **test_alertmanager_webhook_valid**
   - Valid Alertmanager payload
   - Parse with schema
   - Verify all fields present

2. **test_alertmanager_webhook_invalid**
   - Invalid payload (missing required fields)
   - Verify ValidationError raised

3. **test_alert_response_serialization**
   - Create AlertResponse object
   - Serialize to JSON
   - Verify all fields included

---

#### Test Case Group: Runbook Schemas

**Test File**: `tests/unit/test_schemas/test_runbook_schemas.py`

**Test Cases**:

1. **test_runbook_create_schema_valid**
   - Valid runbook creation payload
   - Verify validation passes

2. **test_runbook_create_schema_invalid_step_order**
   - Steps with duplicate order
   - Verify validation error

3. **test_runbook_step_command_validation**
   - Step without command
   - Verify error

4. **test_runbook_step_api_validation**
   - API step without URL
   - Verify error

---

## INTEGRATION TEST CASES

### 5.1 Alert Processing Flow

**Test File**: `tests/integration/test_alert_flow.py`

**Integration Test Cases**:

1. **test_alert_ingestion_to_analysis**
   - Send alert via webhook endpoint
   - Verify alert created in database
   - Verify rule matching executed
   - Verify auto-analysis triggered (if applicable)
   - Verify analysis result stored
   - **Components**: Webhook → Alert Service → Rules Service → LLM Service → Database

2. **test_alert_ingestion_to_clustering**
   - Send 5 related alerts
   - Verify all alerts created
   - Verify cluster created
   - Verify all alerts linked to cluster
   - **Components**: Webhook → Alert Service → Clustering Service → Database

3. **test_alert_ingestion_to_application_mapping**
   - Create application with matching rule
   - Send alert matching rule
   - Verify alert mapped to application
   - **Components**: Webhook → Alert Service → Application Service → Database

4. **test_alert_triggers_runbook**
   - Create runbook with trigger
   - Send matching alert
   - Verify runbook execution triggered
   - **Components**: Webhook → Alert Service → Trigger Matching → Remediation Service

---

### 5.2 Remediation Flow

**Test File**: `tests/integration/test_remediation_flow.py`

**Integration Test Cases**:

1. **test_runbook_creation_to_execution**
   - Create runbook via API
   - Execute runbook via API
   - Verify execution recorded
   - Verify steps executed in order
   - **Components**: API → Remediation Service → SSH/API Executor → Database

2. **test_runbook_execution_with_approval**
   - Create runbook requiring approval
   - Execute runbook
   - Verify pending approval status
   - Approve via API
   - Verify execution proceeds
   - **Components**: API → Remediation Service → Approval Workflow → Executor

3. **test_runbook_execution_rate_limit_to_circuit_breaker**
   - Execute runbook rapidly (trigger rate limit)
   - Execute multiple times and fail (trigger circuit breaker)
   - Verify circuit breaker opens
   - **Components**: Remediation Service → Rate Limiter → Circuit Breaker

4. **test_runbook_execution_with_blackout**
   - Create blackout window
   - Attempt execution during blackout
   - Verify blocked
   - Wait for blackout to end
   - Verify execution allowed
   - **Components**: Remediation Service → Blackout Window Service

5. **test_runbook_execution_failure_to_rollback**
   - Create runbook with rollback steps
   - Execute and simulate step failure
   - Verify rollback steps executed
   - **Components**: Executor → Rollback Handler → Database

---

### 5.3 Knowledge Base Flow

**Test File**: `tests/integration/test_knowledge_flow.py`

**Integration Test Cases**:

1. **test_document_upload_to_search**
   - Upload PDF document via API
   - Wait for processing (chunking, embedding)
   - Search for keywords
   - Verify document found
   - **Components**: API → Knowledge Service → Embedding Service → Vector DB → Search

2. **test_document_update_reindex**
   - Upload document
   - Update document content
   - Verify chunks regenerated
   - Verify embeddings updated
   - Search for old content → not found
   - Search for new content → found
   - **Components**: API → Knowledge Service → Reindexing → Database

3. **test_image_upload_to_ai_analysis**
   - Upload architecture diagram
   - Verify image stored
   - Verify AI analysis triggered
   - Verify components extracted
   - **Components**: API → File Storage → LLM Vision API → Database

4. **test_knowledge_base_in_alert_analysis**
   - Upload relevant documentation
   - Send alert
   - Trigger analysis
   - Verify knowledge base searched
   - Verify relevant docs used in analysis
   - **Components**: Alert → LLM Service → Knowledge Service → Analysis

---

### 5.4 Chat Flow

**Test File**: `tests/integration/test_chat_flow.py`

**Integration Test Cases**:

1. **test_chat_session_creation_to_message_exchange**
   - Create chat session via API
   - Send message via API
   - Verify LLM response received
   - Send follow-up message
   - Verify context retained
   - **Components**: API → Chat Service → LLM Service → Database

2. **test_chat_with_alert_context**
   - Create alert
   - Create chat session linked to alert
   - Send message about alert
   - Verify LLM has alert context
   - **Components**: Chat Service → Alert Service → LLM Service

3. **test_chat_session_deletion**
   - Create chat session with messages
   - Delete session via API
   - Verify session deleted
   - Verify messages cascade deleted
   - **Components**: API → Chat Service → Database

---

### 5.5 Scheduler Flow

**Test File**: `tests/integration/test_scheduler_flow.py`

**Integration Test Cases**:

1. **test_schedule_creation_to_execution**
   - Create runbook
   - Create schedule (interval: 1 minute)
   - Wait for execution
   - Verify runbook executed
   - Verify execution logged
   - **Components**: API → Scheduler → Remediation Service → Database

2. **test_schedule_pause_resume**
   - Create active schedule
   - Pause via API
   - Verify no executions while paused
   - Resume via API
   - Verify executions resume
   - **Components**: API → Scheduler → Database

3. **test_schedule_misfire_handling**
   - Create schedule with misfire grace time
   - Simulate missed execution
   - Restart within grace time
   - Verify execution runs (late)
   - **Components**: Scheduler → Misfire Handler → Remediation Service

---

### 5.6 ITSM Integration Flow

**Test File**: `tests/integration/test_itsm_flow.py`

**Integration Test Cases**:

1. **test_itsm_integration_sync**
   - Create ServiceNow integration
   - Trigger sync
   - Verify change events fetched
   - Verify stored in database
   - **Components**: API → ITSM Service → ServiceNow API → Database

2. **test_change_correlation_with_alert**
   - Sync change events
   - Send alert
   - Correlate changes with alert
   - Verify correlation score calculated
   - **Components**: ITSM Service → Alert Service → Correlation Engine

3. **test_itsm_integration_error_handling**
   - Create integration with invalid credentials
   - Trigger sync
   - Verify error captured
   - Verify retry scheduled
   - **Components**: ITSM Service → Error Handler → Retry Queue

---

## API TEST CASES

### 6.1 Authentication API Tests

**Test File**: `tests/api/test_auth_api.py`

**API Test Cases**:

1. **test_login_valid_credentials**
   - POST /api/auth/login
   - Body: valid username/password
   - Verify 200 OK
   - Verify JWT token returned
   - Verify user object returned

2. **test_login_invalid_credentials**
   - POST /api/auth/login
   - Body: invalid password
   - Verify 401 Unauthorized
   - Verify error message

3. **test_login_rate_limiting**
   - POST /api/auth/login 10 times rapidly
   - Verify 429 Too Many Requests

4. **test_logout**
   - Login to get token
   - POST /api/auth/logout
   - Verify 200 OK
   - Verify token invalidated

5. **test_refresh_token**
   - Login to get token
   - POST /api/auth/refresh
   - Verify new token issued
   - Verify extended expiry

6. **test_register_user**
   - POST /api/auth/register
   - Body: new user data
   - Verify 201 Created
   - Verify user in database

7. **test_register_duplicate_username**
   - Create user "test"
   - Attempt to register another "test"
   - Verify 409 Conflict

---

### 6.2 Alerts API Tests

**Test File**: `tests/api/test_alerts_api.py`

**API Test Cases**:

1. **test_webhook_ingest_firing_alert**
   - POST /webhook/alerts
   - Body: Alertmanager firing payload
   - Verify 200 OK
   - Verify alert created

2. **test_webhook_ingest_resolved_alert**
   - POST /webhook/alerts
   - Body: Alertmanager resolved payload
   - Verify 200 OK
   - Verify alert status updated

3. **test_webhook_invalid_payload**
   - POST /webhook/alerts
   - Body: malformed JSON
   - Verify 422 Unprocessable Entity

4. **test_get_alerts_list**
   - GET /api/alerts
   - Verify 200 OK
   - Verify pagination works
   - Verify total count returned

5. **test_get_alerts_filter_by_severity**
   - GET /api/alerts?severity=critical
   - Verify only critical alerts returned

6. **test_get_alerts_filter_by_status**
   - GET /api/alerts?status=firing
   - Verify only firing alerts returned

7. **test_get_alert_by_id**
   - GET /api/alerts/{alert_id}
   - Verify 200 OK
   - Verify correct alert returned

8. **test_get_alert_not_found**
   - GET /api/alerts/99999
   - Verify 404 Not Found

9. **test_get_alert_stats**
   - GET /api/alerts/stats
   - Verify 200 OK
   - Verify counts accurate

10. **test_analyze_alert**
    - POST /api/alerts/{alert_id}/analyze
    - Verify 200 OK
    - Verify analysis returned

11. **test_analyze_alert_unauthorized**
    - POST /api/alerts/{alert_id}/analyze
    - No auth token
    - Verify 401 Unauthorized

12. **test_update_alert**
    - PUT /api/alerts/{alert_id}
    - Update status or notes
    - Verify 200 OK
    - Verify updated

---

### 6.3 Remediation API Tests

**Test File**: `tests/api/test_remediation_api.py`

**API Test Cases**:

1. **test_create_runbook**
   - POST /api/remediation/runbooks
   - Valid runbook payload
   - Verify 201 Created
   - Verify runbook ID returned

2. **test_create_runbook_invalid_data**
   - POST /api/remediation/runbooks
   - Missing required fields
   - Verify 422 Unprocessable Entity

3. **test_get_runbooks_list**
   - GET /api/remediation/runbooks
   - Verify 200 OK
   - Verify list returned

4. **test_get_runbook_by_id**
   - GET /api/remediation/runbooks/{id}
   - Verify 200 OK
   - Verify steps included

5. **test_update_runbook**
   - PUT /api/remediation/runbooks/{id}
   - Update name
   - Verify 200 OK
   - Verify version incremented

6. **test_delete_runbook**
   - DELETE /api/remediation/runbooks/{id}
   - Verify 204 No Content
   - Verify deleted from database

7. **test_execute_runbook**
   - POST /api/remediation/runbooks/{id}/execute
   - Verify 200 OK
   - Verify execution ID returned

8. **test_execute_runbook_requires_approval**
   - POST execute for runbook with approval_required
   - Verify 200 OK
   - Verify status = "pending_approval"

9. **test_approve_execution**
   - POST /api/remediation/executions/{id}/approve
   - Verify 200 OK
   - Verify execution proceeds

10. **test_cancel_execution**
    - POST /api/remediation/executions/{id}/cancel
    - Verify 200 OK
    - Verify execution cancelled

11. **test_get_execution_history**
    - GET /api/remediation/runbooks/{id}/executions
    - Verify 200 OK
    - Verify executions listed

12. **test_get_execution_details**
    - GET /api/remediation/executions/{id}
    - Verify 200 OK
    - Verify step details included

13. **test_import_runbook_yaml**
    - POST /api/remediation/runbooks/import
    - Upload valid YAML
    - Verify 201 Created

14. **test_export_runbook_yaml**
    - GET /api/remediation/runbooks/{id}/export
    - Verify 200 OK
    - Verify YAML format

15. **test_circuit_breaker_status**
    - GET /api/remediation/circuit-breaker/{id}
    - Verify 200 OK
    - Verify state returned

16. **test_circuit_breaker_override**
    - POST /api/remediation/circuit-breaker/{id}/override
    - Verify 200 OK
    - Verify state reset

---

### 6.4 Knowledge Base API Tests

**Test File**: `tests/api/test_knowledge_api.py`

**API Test Cases**:

1. **test_create_document_markdown**
   - POST /api/knowledge/documents
   - Content-Type: application/json
   - Markdown content
   - Verify 201 Created

2. **test_create_document_pdf_upload**
   - POST /api/knowledge/documents
   - Content-Type: multipart/form-data
   - PDF file
   - Verify 201 Created

3. **test_get_documents_list**
   - GET /api/knowledge/documents
   - Verify 200 OK
   - Verify pagination

4. **test_get_document_by_id**
   - GET /api/knowledge/documents/{id}
   - Verify 200 OK
   - Verify content returned

5. **test_update_document**
   - PUT /api/knowledge/documents/{id}
   - Update content
   - Verify 200 OK

6. **test_delete_document**
   - DELETE /api/knowledge/documents/{id}
   - Verify 204 No Content

7. **test_search_documents_full_text**
   - POST /api/knowledge/search
   - search_type: "full_text"
   - Verify 200 OK
   - Verify results returned

8. **test_search_documents_similarity**
   - POST /api/knowledge/search
   - search_type: "similarity"
   - Verify 200 OK
   - Verify semantic results

9. **test_get_document_chunk**
   - GET /api/knowledge/chunks/{id}
   - Verify 200 OK

---

### 6.5 Chat API Tests

**Test File**: `tests/api/test_chat_api.py`

**API Test Cases**:

1. **test_create_chat_session**
   - POST /api/chat/sessions
   - Verify 201 Created
   - Verify session ID returned

2. **test_get_chat_sessions_list**
   - GET /api/chat/sessions
   - Verify 200 OK
   - Verify user's sessions only

3. **test_get_chat_session_details**
   - GET /api/chat/sessions/{id}
   - Verify 200 OK

4. **test_send_chat_message**
   - POST /api/chat/sessions/{id}/messages
   - Message content
   - Verify 200 OK
   - Verify response from LLM

5. **test_get_chat_messages**
   - GET /api/chat/sessions/{id}/messages
   - Verify 200 OK
   - Verify all messages returned

6. **test_delete_chat_session**
   - DELETE /api/chat/sessions/{id}
   - Verify 204 No Content

7. **test_chat_session_isolation**
   - Create session as user A
   - Try to access as user B
   - Verify 403 Forbidden

---

### 6.6 RBAC Authorization Tests

**Test File**: `tests/api/test_rbac_api.py`

**API Test Cases**:

1. **test_admin_can_create_user**
   - Login as admin
   - POST /api/users
   - Verify 201 Created

2. **test_engineer_cannot_create_user**
   - Login as engineer
   - POST /api/users
   - Verify 403 Forbidden

3. **test_operator_can_execute_runbook**
   - Login as operator
   - POST /api/remediation/runbooks/{id}/execute
   - Verify 200 OK

4. **test_operator_cannot_delete_runbook**
   - Login as operator
   - DELETE /api/remediation/runbooks/{id}
   - Verify 403 Forbidden

5. **test_admin_can_delete_any_runbook**
   - Login as admin
   - DELETE runbook created by engineer
   - Verify 204 No Content

6. **test_engineer_can_only_delete_own_runbook**
   - Login as engineer
   - DELETE own runbook → 204
   - DELETE other's runbook → 403

---

## DATABASE TEST CASES

### 7.1 Migration Tests

**Test File**: `tests/database/test_migrations.py`

**Test Cases**:

1. **test_migrations_run_successfully**
   - Apply all migrations to empty database
   - Verify no errors
   - Verify all tables created

2. **test_migrations_are_reversible**
   - Apply migration
   - Downgrade migration
   - Verify clean rollback

3. **test_migration_data_preservation**
   - Create data
   - Apply migration that alters table
   - Verify data still intact

---

### 7.2 Query Performance Tests

**Test File**: `tests/database/test_queries.py`

**Test Cases**:

1. **test_alert_list_query_performance**
   - Create 10,000 alerts
   - Query with filters and pagination
   - Verify query < 100ms

2. **test_knowledge_base_similarity_search_performance**
   - Create 1,000 documents
   - Perform vector similarity search
   - Verify query < 1 second

3. **test_runbook_execution_history_query**
   - Create 1,000 executions
   - Query with filters
   - Verify query < 100ms

---

### 7.3 Transaction Tests

**Test File**: `tests/database/test_transactions.py`

**Test Cases**:

1. **test_runbook_execution_transaction_rollback**
   - Start runbook execution
   - Simulate step failure
   - Verify transaction rolled back
   - Verify database state clean

2. **test_concurrent_alert_ingestion**
   - Ingest 10 alerts concurrently
   - Verify no deadlocks
   - Verify all alerts created

---

### 7.4 Constraint Tests

**Test File**: `tests/database/test_constraints.py`

**Test Cases**:

1. **test_unique_constraint_username**
   - Create user "test"
   - Attempt duplicate
   - Verify IntegrityError

2. **test_foreign_key_constraint**
   - Create alert with invalid rule_id
   - Verify ForeignKeyError

3. **test_cascade_delete**
   - Create runbook with steps
   - Delete runbook
   - Verify steps cascade deleted

---

## TEST EXECUTION STRATEGY

### 8.1 Test Organization

**Test Markers**:
```ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, multiple components)
    api: API endpoint tests
    database: Database-specific tests
    security: Security tests
    slow: Slow-running tests (>5 seconds)
    external: Tests requiring external services
```

**Run Specific Categories**:
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests
pytest -m integration

# API tests
pytest -m api

# Everything except slow tests
pytest -m "not slow"

# Parallel execution
pytest -n auto
```

---

### 8.2 Test Execution Order

**Priority 1 (Fast Feedback)**:
1. Unit tests (1-2 minutes)
2. Schema validation tests (30 seconds)

**Priority 2 (Core Functionality)**:
3. API tests (3-5 minutes)
4. Integration tests (5-10 minutes)

**Priority 3 (Comprehensive)**:
5. Database tests (2-3 minutes)
6. Security tests (3-5 minutes)
7. Performance tests (5-10 minutes)

**Total Estimated Time**: 20-30 minutes for full suite

---

### 8.3 Parallel Execution

**Configuration** (pytest.ini):
```ini
[pytest]
addopts =
    -n auto              # Auto-detect CPU count
    --dist loadscope     # Distribute by scope
    --maxfail=5          # Stop after 5 failures
```

**Expected Speedup**:
- 4 cores: 3-4x faster
- 8 cores: 6-7x faster

---

### 8.4 Coverage Requirements

**Minimum Coverage Targets**:
- Overall: 80%
- Critical paths (auth, remediation): 90%
- Models: 85%
- Services: 85%
- API endpoints: 75%

**Coverage Report**:
```bash
pytest --cov=app --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

---

## TEST DATA MANAGEMENT

### 9.1 Factory Boy Factories

**Purpose**: Generate test data dynamically

**Factories Needed**:

1. **UserFactory**
   - Generate users with random data
   - Override specific fields as needed
   - Example: `UserFactory.create(role="admin")`

2. **AlertFactory**
   - Generate alerts with realistic data
   - Random severities, instances
   - Example: `AlertFactory.create_batch(10, severity="critical")`

3. **RunbookFactory**
   - Generate runbooks with steps
   - Example: `RunbookFactory.create(steps__count=5)`

4. **DesignDocumentFactory**
   - Generate documents with embeddings
   - Example: `DesignDocumentFactory.create(content_type="markdown")`

---

### 9.2 Static Test Data

**Location**: `tests/test_data/`

**Files**:

1. **alerts/firing_alerts.json**
   - 10 sample firing alerts
   - Various severities and alertnames

2. **alerts/resolved_alerts.json**
   - 10 resolved alerts

3. **runbooks/linux_runbook.yaml**
   - Sample Linux runbook

4. **runbooks/windows_runbook.yaml**
   - Sample Windows runbook

5. **knowledge/sample_doc.md**
   - Sample Markdown document for testing

---

### 9.3 Database Seeding

**Seed Data Script**: `tests/fixtures/seed_database.py`

**Creates**:
- 3 test users (admin, engineer, operator)
- 1 default LLM provider
- 5 sample alerts
- 2 sample runbooks
- 1 sample application

**Usage**:
```bash
# Seed test database
python tests/fixtures/seed_database.py
```

---

## CI/CD INTEGRATION

### 10.1 GitHub Actions Workflow

**.github/workflows/pytest.yml**:

**Stages**:

1. **Lint & Format Check**
   - ruff check
   - black --check

2. **Unit Tests**
   - pytest -m unit
   - Fast feedback (<2 min)

3. **Integration Tests**
   - pytest -m integration
   - Requires database

4. **API Tests**
   - pytest -m api
   - Full API coverage

5. **Coverage Report**
   - Upload to Codecov
   - Fail if <80%

6. **Security Scan**
   - bandit -r app/
   - safety check

---

### 10.2 Test Environment in CI

**Services**:
```yaml
services:
  postgres:
    image: postgres:14
    env:
      POSTGRES_PASSWORD: test
      POSTGRES_DB: remediation_test
    options: >-
      --health-cmd pg_isready
      --health-interval 10s

  redis:
    image: redis:7
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
```

---

### 10.3 Pre-commit Hooks

**Install**:
```bash
pip install pre-commit
pre-commit install
```

**Hooks**:
- Run pytest -m "unit and not slow" (fast tests)
- Run ruff linting
- Run black formatting
- Check for merge conflicts
- Check for large files

---

## SUMMARY

### Test Coverage Overview

| Category | Test Files | Test Cases | Execution Time |
|----------|-----------|-----------|----------------|
| **Unit Tests** | 15 | 120+ | 2 min |
| **Integration Tests** | 6 | 25+ | 8 min |
| **API Tests** | 10 | 100+ | 5 min |
| **Database Tests** | 4 | 15+ | 3 min |
| **Security Tests** | 5 | 20+ | 3 min |
| **TOTAL** | **40+** | **280+** | **21 min** |

### Key Principles

1. ✅ **Fast Unit Tests**: Run in <2 minutes
2. ✅ **Isolated**: Each test independent
3. ✅ **Deterministic**: Same input = same output
4. ✅ **Comprehensive**: >80% code coverage
5. ✅ **Maintainable**: Clear, documented test cases

### Next Steps

1. **Week 1**: Set up test environment and fixtures
2. **Week 2**: Write unit tests for models and services
3. **Week 3**: Write API and integration tests
4. **Week 4**: Write database and security tests
5. **Week 5**: CI/CD integration and optimization

---

**END OF PYTEST TEST PLAN**