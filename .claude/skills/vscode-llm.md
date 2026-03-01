# VS Code LLM Skill — Remediation Engine

## Purpose

This skill ensures **consistent, complete results** when using any LLM assistant (Copilot, Claude, etc.) inside VS Code for the Remediation Engine project. It enforces mandatory steps that are easy to forget: **writing tests** and **creating Atlas migration files** for every change.

---

## Project Overview

- **Name**: AIOps Remediation Engine
- **Stack**: Python 3.11+ / FastAPI / PostgreSQL 16 (pgvector) / SQLAlchemy / Docker
- **LLM Framework**: LiteLLM (Anthropic, OpenAI, Google, Ollama)
- **Auth**: JWT + RBAC
- **Migrations**: Atlas (declarative SQL migrations — NOT Alembic)
- **Tests**: pytest + pytest-asyncio + Playwright (E2E)

---

## Mandatory Checklist — Every Code Change

When writing or modifying code, you **MUST** complete ALL applicable items below. Do not skip any step.

### 1. Test Cases (ALWAYS REQUIRED)

Every code change **must** include corresponding test cases. Never submit code without tests.

#### Where to place tests

| Change type | Test location | Marker |
|---|---|---|
| Service / business logic (`app/services/`) | `tests/unit/services/test_<service_name>.py` | `@pytest.mark.unit` |
| Agentic service (`app/services/agentic/`) | `tests/unit/services/agentic/test_<name>.py` | `@pytest.mark.unit` |
| Router / API endpoint (`app/routers/`) | `tests/integration/test_<router_name>.py` | `@pytest.mark.integration` |
| Model changes (`app/models*.py`) | `tests/unit/models/test_<model_name>.py` | `@pytest.mark.unit` |
| Utility (`app/utils/`) | `tests/unit/utils/test_<util_name>.py` | `@pytest.mark.unit` |
| UI / full workflow | `tests/e2e/test_<feature>_ui.py` | `@pytest.mark.e2e` |

#### Test patterns to follow

**Unit test (sync)**:
```python
import pytest
from unittest.mock import MagicMock, patch

class TestMyService:
    def test_basic_case(self):
        """Test the expected behavior."""
        result = my_function("input")
        assert result == "expected_output"

    def test_edge_case(self):
        """Test edge case handling."""
        result = my_function("")
        assert result is None
```

**Unit test (async)**:
```python
import pytest
from unittest.mock import AsyncMock, patch

class TestMyAsyncService:
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async service method."""
        mock_dep = AsyncMock(return_value={"key": "value"})
        result = await my_async_function(mock_dep)
        assert result["key"] == "value"
```

**Integration test (API endpoint)**:
```python
import pytest

class TestMyEndpoint:
    @pytest.mark.asyncio
    async def test_create_resource(self, async_client, admin_auth_headers):
        """Test creating a resource via API."""
        response = await async_client.post(
            "/api/resource",
            json={"name": "test"},
            headers=admin_auth_headers,
        )
        assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, async_client):
        """Test that unauthenticated requests are rejected."""
        response = await async_client.get("/api/resource")
        assert response.status_code == 401
```

#### Test requirements

- **Minimum 3 test cases per function/endpoint**: happy path, error case, edge case
- **Mock external dependencies**: LLM calls, SSH connections, database in unit tests
- **Use existing fixtures** from `tests/conftest.py` (see available fixtures below)
- **Use `@pytest.mark.asyncio`** for all async test functions
- **Follow naming convention**: `test_<what_is_being_tested>` for functions, `Test<Component>` for classes

#### Available fixtures (from `tests/conftest.py`)

| Fixture | Description |
|---|---|
| `test_db_session` / `db` | SQLAlchemy session for DB tests |
| `test_client` | Sync FastAPI TestClient |
| `async_client` | Async httpx.AsyncClient |
| `authenticated_client` | Pre-authenticated async client |
| `test_admin_user` | Admin user in test DB |
| `test_operator_user` | Operator user in test DB |
| `admin_auth_headers` | JWT admin token headers |
| `operator_auth_headers` | JWT operator token headers |
| `sample_alert_payload` | Alertmanager webhook JSON |
| `sample_alert_data` | Alert model data |
| `sample_rule_data` | Auto-analyze rule config |
| `sample_llm_provider` | LLM provider config (Claude) |
| `mock_llm_service` | Mocked LLM service |
| `mock_ssh_service` | Mocked SSH service |
| `sample_runbook_data` | Runbook with steps |
| `sample_server_credentials` | SSH server config |

---

### 2. Atlas Database Migrations (REQUIRED for schema changes)

If your change modifies **any database table** (add/remove/rename columns, add tables, change constraints, add indexes), you **MUST** create an Atlas migration.

**NEVER** run raw `ALTER TABLE` or `CREATE TABLE` directly against the database.

#### Step-by-step

1. **Update `schema/schema.sql`** — this is the canonical schema (source of truth)

2. **Create a migration file** in `atlas/migrations/` with this naming:
   ```
   atlas/migrations/YYYYMMDDHHMMSS_description.sql
   ```
   Use current date/time (e.g., `20260301120000_add_my_column.sql`).

3. **Write the SQL** in the migration file:
   ```sql
   -- Add column example
   ALTER TABLE public.my_table ADD COLUMN new_field VARCHAR(100) NOT NULL DEFAULT '';

   -- Add index example
   CREATE INDEX ix_my_table_new_field ON public.my_table USING btree (new_field);
   ```

4. **Update the SQLAlchemy model** in the corresponding `app/models*.py` file to match.

5. **Update the Pydantic schema** in the corresponding `app/schemas*.py` file if the field is API-visible.

#### Key rules

| Rule | Reason |
|---|---|
| One logical change per migration file | Easier rollback and review |
| `schema/schema.sql` must stay in sync | It is the human-readable reference |
| Update both the model AND migration | They must match or deployment breaks |
| Never edit `atlas.sum` by hand | Regenerated via `atlas migrate hash` |
| Use `YYYYMMDDHHMMSS` timestamp naming | Maintains migration ordering |

#### Model file mapping

| Domain | Model file | Schema file |
|---|---|---|
| Core (alerts, rules, users) | `app/models.py` | `app/schemas.py` |
| Remediation (runbooks, executions) | `app/models_remediation.py` | `app/schemas_remediation.py` |
| AI / LLM | `app/models_ai.py` | `app/schemas_ai.py` |
| Agent / HQ | `app/models_agent.py` | — |
| Application profiles | `app/models_application.py` | `app/schemas_application.py` |
| Knowledge base | `app/models_knowledge.py` | `app/schemas_knowledge.py` |
| ITSM | `app/models_itsm.py` | `app/schemas_itsm.py` |
| Dashboards | `app/models_dashboards.py` | — |
| Changesets | `app/models_changeset.py` | — |
| Learning | `app/models_learning.py` | `app/schemas_learning.py` |
| Scheduler | `app/models_scheduler.py` | `app/schemas_scheduler.py` |
| PII | `app/models/pii_models.py` | — |

---

### 3. LLM Interaction Points (REVIEW IMPACT)

This project has **5 independent LLM interaction points**. When modifying any LLM-related code, check if your change impacts other interaction points.

| # | Name | Key files | Purpose |
|---|---|---|---|
| 1 | RE-VIVE (App) | `app/services/revive/`, `app/routers/revive.py`, `app/routers/revive_app.py` | AI helper for the application UI |
| 2 | RE-VIVE (Grafana) | `app/routers/revive_grafana.py`, `app/services/mcp/` | AI helper on Grafana stack, calls MCP |
| 3 | /troubleshoot | `app/services/agentic/ai_troubleshoot_agent.py`, `app/services/agentic/troubleshooting_orchestrator.py`, `app/routers/troubleshoot_api.py` | Independent troubleshooting agent |
| 4 | /inquiry | `app/services/agentic/ai_inquiry_agent.py`, `app/services/agentic/inquiry_orchestrator.py`, `app/routers/inquiry.py` | Data reading and Q&A |
| 5 | /alerts help | `app/services/agentic/ai_alert_help_agent.py`, `app/routers/alerts_chat_api.py` | Alert troubleshooting with extra detail |

**Rules**:
- Files dedicated to RE-VIVE **must** have the `revive` prefix in their filename
- Always review cross-impact when modifying shared services like `llm_service.py`, `prompt_service.py`, or `context_variables.py`
- Each LLM interaction point should be developed and tested **independently**

---

### 4. Coding Standards

- **PEP 8** compliance
- **Type hints** on all function arguments and return values
- **Async-first**: Use `async def` for I/O-bound operations
- **Import order**: stdlib → third-party → local (`app.*`)
- **Error handling**: Use specific exceptions, not bare `except:`
- **No secrets in code**: Use environment variables via `app/config.py` (`get_settings()`)

---

### 5. File Organization

```
app/
├── routers/         # API endpoints — one file per feature
├── services/        # Business logic
│   ├── agentic/     # AI agent system (tools, orchestrators)
│   ├── revive/      # RE-VIVE AI helper
│   └── mcp/         # Model Context Protocol clients
├── models*.py       # SQLAlchemy ORM models (by domain)
├── schemas*.py      # Pydantic schemas (by domain)
├── middleware/       # Request middleware
├── utils/           # Shared utilities
└── llm_core/        # LLM client abstractions

tests/
├── conftest.py      # Shared fixtures
├── unit/            # Isolated tests (no DB, no network)
│   ├── services/    # Service layer tests
│   │   └── agentic/ # Agent system tests
│   ├── models/      # Model tests
│   └── utils/       # Utility tests
├── integration/     # API + DB tests
│   └── routers/     # Router-specific integration tests
├── e2e/             # Playwright browser tests
├── security/        # Security tests
├── performance/     # Benchmark tests
└── fixtures/        # Shared test data
```

---

### 6. Running Tests Locally

```bash
# All unit tests (fast, no DB needed)
pytest tests/unit -v

# Specific test file
pytest tests/unit/services/test_rules_engine.py -v

# Integration tests (need PostgreSQL running)
pytest tests/integration -v

# With coverage report
pytest tests/unit --cov=app --cov-report=term

# Parallel execution
pytest tests/unit -n auto
```

---

### 7. Pre-Commit Verification

Before committing, verify:

1. **Tests pass**: `pytest tests/unit -v`
2. **No import errors**: `python -c "from app.main import app"`
3. **Formatting**: `black --check app/ tests/`
4. **Schema in sync** (if DB changed): verify `schema/schema.sql` matches your migration

---

## Quick Reference — What to Generate

| You changed... | You MUST also create/update... |
|---|---|
| A service in `app/services/` | Unit test in `tests/unit/services/test_<name>.py` |
| A router in `app/routers/` | Integration test in `tests/integration/test_<name>.py` |
| A model in `app/models*.py` | Atlas migration + update `schema/schema.sql` + unit test |
| A schema in `app/schemas*.py` | Unit test for validation logic |
| An agentic tool | Unit test in `tests/unit/services/agentic/` |
| Shared LLM code | Tests for ALL 5 LLM interaction points that use it |
| A template in `templates/` | E2E test in `tests/e2e/` |
| `config.py` | Verify `.env.example` is updated |
