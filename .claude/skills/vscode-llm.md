# VS Code LLM Skill — Remediation Engine

## Purpose

This skill ensures **consistent, complete results** when using any LLM assistant (Copilot, Claude, etc.) inside VS Code for the Remediation Engine project. It enforces mandatory steps that are easy to forget: **writing tests**, **creating Atlas migration files**, and following **project coding standards** for every change.

---

## Project Overview

- **Name**: AIOps Remediation Engine
- **Stack**: Python 3.11+ / FastAPI / PostgreSQL 16 (pgvector) / SQLAlchemy / Docker
- **LLM Framework**: LiteLLM (Anthropic, OpenAI, Google, Ollama)
- **Auth**: JWT + RBAC (role-based access control)
- **Migrations**: Atlas (declarative SQL migrations — NOT Alembic)
- **Tests**: pytest + pytest-asyncio + Playwright (E2E)
- **Linting**: black (formatter), ruff (linter), mypy (type checker)

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

**Unit test (sync) — group related tests in a class:**
```python
"""
Unit tests for the <service> service.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.my_service import my_function


class TestMyFunction:
    """Test my_function behavior."""

    def test_happy_path(self):
        """Test the expected behavior with valid input."""
        result = my_function("valid_input")
        assert result == "expected_output"

    def test_error_case(self):
        """Test error handling with invalid input."""
        with pytest.raises(ValueError, match="Invalid input"):
            my_function(None)

    def test_edge_case_empty_string(self):
        """Test edge case with empty string."""
        result = my_function("")
        assert result is None
```

**Unit test (async) — use `@pytest.mark.asyncio` and `AsyncMock`:**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.my_async_service import process_data


class TestProcessData:
    """Test async process_data function."""

    @pytest.mark.asyncio
    async def test_successful_processing(self):
        """Test successful async data processing."""
        mock_db = MagicMock()
        mock_provider = AsyncMock(return_value={"result": "ok"})

        with patch("app.services.my_async_service.call_provider", mock_provider):
            result = await process_data(mock_db, "input")

        assert result["result"] == "ok"
        mock_provider.assert_called_once()

    @pytest.mark.asyncio
    async def test_provider_failure(self):
        """Test handling when provider raises an error."""
        mock_db = MagicMock()
        mock_provider = AsyncMock(side_effect=RuntimeError("API down"))

        with patch("app.services.my_async_service.call_provider", mock_provider):
            with pytest.raises(RuntimeError, match="API down"):
                await process_data(mock_db, "input")

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Test edge case with empty input."""
        mock_db = MagicMock()
        result = await process_data(mock_db, "")
        assert result is None
```

**Integration test (API endpoint) — use fixtures from conftest.py:**
```python
import pytest


class TestMyEndpoint:
    """Integration tests for /api/my-resource endpoint."""

    @pytest.mark.asyncio
    async def test_create_resource(self, async_client, admin_auth_headers):
        """Test creating a resource via API."""
        response = await async_client.post(
            "/api/my-resource",
            json={"name": "test-resource"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-resource"

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, async_client):
        """Test that unauthenticated requests are rejected."""
        response = await async_client.get("/api/my-resource")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_forbidden_for_operator(self, async_client, operator_auth_headers):
        """Test that operators cannot access admin-only endpoint."""
        response = await async_client.delete(
            "/api/my-resource/123",
            headers=operator_auth_headers,
        )
        assert response.status_code == 403
```

#### Test requirements

- **Minimum 3 test cases per function/endpoint**: happy path, error case, edge case
- **Mock external dependencies**: LLM calls, SSH connections, database in unit tests
- **Use existing fixtures** from `tests/conftest.py` (see available fixtures below)
- **Use `@pytest.mark.asyncio`** for all async test functions
- **Follow naming convention**: `test_<what_is_being_tested>` for functions, `Test<Component>` for classes
- **Docstrings on every test**: each test function must have a docstring explaining what it tests
- **Module docstring**: each test file must start with `"""Unit tests for the <name>."""`

#### Available fixtures (from `tests/conftest.py`)

| Fixture | Description |
|---|---|
| `test_db_session` / `db` | SQLAlchemy session for DB tests |
| `test_client` | Sync FastAPI TestClient |
| `async_client` | Async httpx.AsyncClient (preferred for integration tests) |
| `authenticated_client` | Pre-authenticated async client (admin) |
| `test_admin_user` | Admin user created in test DB |
| `test_operator_user` | Operator user created in test DB |
| `admin_auth_headers` | `{"Authorization": "Bearer <admin-jwt>"}` |
| `operator_auth_headers` | `{"Authorization": "Bearer <operator-jwt>"}` |
| `sample_alert_payload` | Alertmanager webhook JSON payload |
| `sample_alert_data` | Alert model data dict |
| `sample_rule_data` | Auto-analyze rule config dict |
| `sample_llm_provider` | LLM provider config (Claude) |
| `mock_llm_service` | MagicMock with `analyze_alert` as AsyncMock |
| `mock_ssh_service` | MagicMock with `connect`/`execute_command`/`disconnect` |
| `mock_rules_engine` | MagicMock with `match_rule`/`evaluate_alert` |
| `sample_runbook_data` | Runbook with 3 steps |
| `sample_server_credentials` | SSH server config dict |
| `test_runbook` | Runbook ORM object in test DB |
| `test_runbook_with_steps` | Runbook + 2 RunbookStep objects in test DB |
| `mock_env_vars` | Sets DATABASE_URL, JWT_SECRET_KEY, etc. |

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

## Coding Standards

These standards are derived from the actual project codebase. All generated code **must** follow them.

### 4.1 Type Hints — All Functions Must Be Typed

Every function **must** have type hints on all parameters and the return type.

```python
# CORRECT — fully typed
async def generate_completion(
    db: Session,
    prompt: str,
    provider: Optional[LLMProvider] = None,
    json_mode: bool = False,
) -> Tuple[str, LLMProvider]:

def search_similar(
    self,
    query: str,
    app_id: Optional[UUID] = None,
    limit: int = 10,
    min_similarity: float = 0.3,
) -> List[Dict[str, Any]]:

# WRONG — missing types
def search_similar(self, query, app_id=None, limit=10):
```

**Type hint rules:**
- Use `Optional[X]` for nullable parameters, not `X | None`
- Use `UUID` for all ID fields, never raw strings
- Use `List`, `Dict`, `Set`, `Tuple` from `typing` module
- Use `AsyncIterator[X]` for streaming/generator return types
- Use `TYPE_CHECKING` guard for circular import resolution:
  ```python
  from __future__ import annotations
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from sqlalchemy.orm import Session
  ```

### 4.2 Logging — Module-Level Logger with Structured Messages

```python
import logging

logger = logging.getLogger(__name__)

# Log levels — use appropriately:
logger.debug(f"Processing item {item_id}")           # Verbose internal state
logger.info(f"Calling LLM provider: {provider.name}") # Normal operations
logger.warning("No embedding provider configured")     # Recoverable issues
logger.error(f"SSH auth failed: {e}", exc_info=True)   # Failures (include stack trace)
```

**Logging rules:**
- One `logger = logging.getLogger(__name__)` per module, at module top level
- Use f-strings for message formatting
- Include contextual information (IDs, names, counts)
- Use `exc_info=True` in `logger.error()` when catching exceptions
- Never use `print()` for logging

### 4.3 Docstrings — Google-Style

```python
class ApplicationService:
    """Service layer for application registry operations."""

    def match_alert_to_application(
        self, alert: Alert
    ) -> Optional[Application]:
        """
        Match an alert to an application based on label matchers.

        Args:
            alert: Alert object with labels_json.

        Returns:
            Matched Application or None if no match found.
        """
```

**Docstring rules:**
- **Classes**: one-line summary describing the class purpose
- **Methods/functions**: description + Args + Returns (+ Raises when applicable)
- **Google-style format** with `Args:`, `Returns:`, `Raises:` sections
- **Module-level docstring** at top of every file
- Complex classes may include multi-paragraph description with implementation notes

### 4.4 Error Handling — Three-Tier Strategy

**Tier 1: Specific exceptions with context** (preferred)
```python
try:
    self._conn = await asyncio.wait_for(
        asyncssh.connect(**connect_options),
        timeout=self.CONNECT_TIMEOUT,
    )
except asyncio.TimeoutError:
    logger.error(f"SSH connect timed out for {self.hostname}:{self.port}")
    raise ConnectionError(
        f"SSH connection timed out after {self.CONNECT_TIMEOUT}s — "
        f"host unreachable or firewall blocking port {self.port}"
    )
except asyncssh.PermissionDenied as e:
    logger.error(f"SSH auth failed: {e}")
    raise ConnectionError(f"SSH authentication failed: {e}")
```

**Tier 2: Graceful degradation with fallback** (for non-critical paths)
```python
try:
    embedding = client.embeddings.create(input=[text], model=self.model_id)
    return embedding
except Exception as e:
    logger.error(f"Failed to generate embedding: {e}")
    return None  # Caller handles None gracefully
```

**Tier 3: Log + re-raise with metrics** (for monitored operations)
```python
try:
    response = await acompletion(**kwargs)
    LLM_REQUESTS.labels(provider=name, status="success").inc()
except Exception as e:
    LLM_REQUESTS.labels(provider=name, status="error").inc()
    raise RuntimeError(f"LLM API call failed: {str(e)}")
```

**Error handling rules:**
- **Never** use bare `except:` — always specify an exception type
- Catch specific exceptions first, then broader `Exception` as fallback
- Always log errors with context before re-raising
- Use `exc_info=True` for unexpected errors to capture stack traces
- Provide user-friendly error messages with actionable context

### 4.5 Async/Await — Async-First for I/O

```python
# All I/O operations must be async
async def process_alert(db: Session, alert_id: UUID) -> Dict[str, Any]:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()

    # Await all async calls
    analysis, provider = await generate_completion(db, prompt)

    # Use asyncio.wait_for() for timeout management
    result = await asyncio.wait_for(
        ssh_executor.execute(command),
        timeout=300,
    )
    return {"analysis": analysis, "result": result}

# Implement __aenter__/__aexit__ for resource cleanup
class MyService:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
```

**Async rules:**
- `async def` for all functions performing I/O (API, DB, file, network)
- `await` on every async function call — never forget it
- Use `asyncio.wait_for()` for timeout management
- Implement async context managers (`__aenter__`/`__aexit__`) for resource cleanup
- Sync functions are fine for pure computation (matching, parsing, formatting)

### 4.6 Import Order

Always follow this order, separated by blank lines:

```python
# 1. Standard library
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

# 2. Third-party
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# 3. Local application
from app.config import get_settings
from app.database import get_db
from app.models import Alert, User
from app.schemas import AlertResponse
from app.services.auth_service import get_current_user
```

### 4.7 Dependency Injection Patterns

Use the established patterns in order of preference:

```python
# Pattern 1: Constructor injection (class-based services)
class ApplicationService:
    def __init__(self, db: Session):
        self.db = db

# Pattern 2: Function parameter injection (standalone functions)
async def generate_completion(
    db: Session,
    prompt: str,
    provider: Optional[LLMProvider] = None,
) -> Tuple[str, LLMProvider]:

# Pattern 3: FastAPI Depends (routers only)
@router.get("/items")
async def list_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

# Pattern 4: Module-level singleton with getter
_orchestrator = ReviveOrchestrator()

def get_revive_orchestrator() -> ReviveOrchestrator:
    return _orchestrator
```

### 4.8 Router / API Endpoint Standards

```python
# Router initialization — always include prefix and tags
router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

# GET endpoint with pagination and filtering
@router.get("", response_model=MyListResponse)
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List items with pagination and optional filtering."""
    query = db.query(MyModel)

    if search:
        query = query.filter(
            MyModel.name.ilike(f"%{like_escape(search)}%", escape="\\")
        )

    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(MyModel.created_at.desc()).offset(offset).limit(page_size).all()

    return MyListResponse(
        items=[MyResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )

# POST endpoint with proper status code
@router.post("", response_model=MyResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_data: MyCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new item."""
    existing = db.query(MyModel).filter(MyModel.name == item_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item with name '{item_data.name}' already exists",
        )

    item = MyModel(**item_data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

# Error responses — always use HTTPException with status module constants
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
```

**Router rules:**
- Prefix: always `/api/<feature>`
- Tags: always include for OpenAPI grouping
- Use `response_model` for typed responses
- Use `status.HTTP_201_CREATED` for POST that creates resources
- Use `Query(default, ge=, le=)` for validated query parameters
- Page size capped at 100 for security/performance
- Always escape search strings with `like_escape()` for SQL injection prevention
- Pagination: use `page`/`page_size` pattern with `total` and `total_pages` in response
- Auth: `Depends(get_current_user)` for read, `Depends(require_admin)` or `Depends(require_role([...]))` for write

### 4.9 Database Access Patterns

```python
# ORM query builder (preferred)
alert = db.query(Alert).filter(Alert.id == alert_id).first()
if not alert:
    raise HTTPException(status_code=404, detail="Alert not found")

# Filtered query with joins
components = (
    db.query(ApplicationComponent)
    .join(ComponentDependency, ComponentDependency.to_component_id == ApplicationComponent.id)
    .filter(ComponentDependency.from_component_id == component_id)
    .all()
)

# Multiple filter conditions
provider = (
    db.query(LLMProvider)
    .filter(
        LLMProvider.usage_type == "embedding",
        LLMProvider.is_enabled == True,
        LLMProvider.is_default == True,
    )
    .first()
)

# Async session (for routers using get_async_db)
query = select(Runbook).options(selectinload(Runbook.steps))
if conditions:
    query = query.where(and_(*conditions))
query = query.order_by(Runbook.name).offset(skip).limit(limit)
result = await db.execute(query)
runbooks = result.scalars().all()

# Raw SQL only for complex queries (pgvector similarity)
sql = text("""
    SELECT c.id, c.content,
           1 - (c.embedding <=> CAST(:query_embedding AS vector)) as similarity
    FROM design_chunks c
    WHERE c.embedding IS NOT NULL
      AND 1 - (c.embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
    ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
    LIMIT :limit
""")
result = self.db.execute(sql, {"query_embedding": emb, "min_similarity": 0.3, "limit": 10})

# Create pattern: add → commit → refresh
item = MyModel(name=data.name, value=data.value)
db.add(item)
db.commit()
db.refresh(item)
```

**Database rules:**
- Use ORM `.query()` builder for standard CRUD
- Use `text()` for complex queries only (vector search, aggregations)
- Always use parameter binding (`:param_name`) — never f-strings in SQL
- Use `.first()` for single, `.all()` for multiple results
- Always check `if not result:` and raise 404

### 4.10 Pydantic Schema Standards

```python
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class MyItemBase(BaseModel):
    """Base schema with shared fields."""
    name: str
    description: Optional[str] = None
    is_active: bool = True


class MyItemCreate(MyItemBase):
    """Schema for creating an item (no id, no timestamps)."""
    pass


class MyItemUpdate(BaseModel):
    """Schema for partial updates (all fields optional)."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class MyItemResponse(MyItemBase):
    """Schema for API responses (includes id + timestamps)."""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MyItemListResponse(BaseModel):
    """Paginated list response."""
    items: List[MyItemResponse]
    total: int
    page: int
    page_size: int
```

**Schema rules:**
- Inherit from `BaseModel`, use `ConfigDict(from_attributes=True)` on response models
- Naming: `<Name>Create`, `<Name>Update`, `<Name>Response`, `<Name>ListResponse`
- Create schemas: no `id`, no timestamps
- Update schemas: all fields `Optional` for partial updates
- Response schemas: include `id`, `created_at`, `updated_at`
- List responses: include `total`, `page`, `page_size` for pagination

### 4.11 Configuration — Never Hardcode Secrets

```python
# CORRECT — use get_settings()
from app.config import get_settings

settings = get_settings()
api_key = settings.anthropic_api_key

# WRONG — hardcoded secret
api_key = "sk-ant-api03-..."

# WRONG — direct os.environ without defaults
api_key = os.environ["ANTHROPIC_API_KEY"]
```

**Rules:**
- All secrets come from `app/config.py` via `get_settings()`
- New settings → add to `Settings` class in `config.py` AND to `.env.example`
- Never commit `.env` files — only `.env.example`

---

## Best Practices

### BP-1: Prefer Existing Patterns Over New Abstractions

Before creating a new utility or abstraction, check if the pattern already exists:
- **Search reuse**: use `like_escape()` from `app/utils/` instead of writing your own
- **Auth patterns**: use `require_admin` / `require_role([...])` from `auth_service`
- **Pagination**: follow the `page`/`page_size`/`total` pattern used everywhere
- **Singleton services**: follow the `_instance` + `get_<service>()` getter pattern

### BP-2: Keep Services Stateless

Services should not hold mutable state between requests. Use constructor injection for the `db` session and avoid module-level mutable globals.

```python
# CORRECT — stateless with injected dependencies
class AlertService:
    def __init__(self, db: Session):
        self.db = db

    def get_alert(self, alert_id: UUID) -> Optional[Alert]:
        return self.db.query(Alert).filter(Alert.id == alert_id).first()

# WRONG — shared mutable state
_cached_alerts = {}  # Danger: shared across requests

class AlertService:
    def get_alert(self, alert_id):
        if alert_id in _cached_alerts:
            return _cached_alerts[alert_id]
```

### BP-3: Fail Fast, Fail Loud

Validate inputs at the boundary (router/API layer) and raise specific errors immediately.

```python
# CORRECT — validate early, raise specific error
@router.post("/runbooks/{runbook_id}/execute")
async def execute_runbook(
    runbook_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
):
    runbook = db.query(Runbook).filter(Runbook.id == runbook_id).first()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    if not runbook.enabled:
        raise HTTPException(status_code=400, detail="Runbook is disabled")
```

### BP-4: Idempotent Migrations

Write migrations that can be re-run safely (use `IF NOT EXISTS`, `IF EXISTS`):

```sql
-- CORRECT — safe to re-run
ALTER TABLE public.alerts ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'normal';
CREATE INDEX IF NOT EXISTS ix_alerts_priority ON public.alerts (priority);

-- WRONG — will fail if run twice
ALTER TABLE public.alerts ADD COLUMN priority VARCHAR(20);
```

### BP-5: Metrics for Observable Operations

When adding new service operations that interact with external systems, include Prometheus metrics:

```python
from prometheus_client import Counter, Histogram

MY_REQUESTS = Counter("my_requests_total", "Total requests", ["status"])
MY_LATENCY = Histogram("my_request_duration_seconds", "Request latency")

async def call_external_service():
    start = time.time()
    try:
        result = await external_call()
        MY_REQUESTS.labels(status="success").inc()
        return result
    except Exception as e:
        MY_REQUESTS.labels(status="error").inc()
        raise
    finally:
        MY_LATENCY.observe(time.time() - start)
```

### BP-6: WebSocket Conventions

```python
# Custom close codes — use 4000+ range
WS_CLOSE_AUTH_FAILED = 4001
WS_CLOSE_NOT_FOUND = 4004
WS_CLOSE_SSH_FAILED = 4010
WS_CLOSE_INTERNAL = 4500

# Always authenticate before accepting
@router.websocket("/ws/my-feature")
async def my_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    await websocket.accept()
    # ... handle messages ...
```

### BP-7: Streaming Responses (SSE)

For long-running AI operations, use Server-Sent Events:

```python
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def chat_stream(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

            async for chunk in orchestrator.run_turn(query):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0.01)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
```

### BP-8: Security Checklist

- Use `like_escape()` for all SQL LIKE/ILIKE queries
- Never build SQL with f-strings — always use parameter binding
- Always validate file paths to prevent directory traversal
- Rate-limit authentication endpoints with `slowapi`:
  ```python
  limiter = Limiter(key_func=get_remote_address, enabled=not settings.testing)

  @router.post("/login")
  @limiter.limit("5/minute")
  async def login(request: Request, ...):
  ```
- Use `HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})` for auth errors
- Never log secrets, API keys, or passwords

---

## File Organization

```
app/
├── routers/         # API endpoints — one file per feature
├── services/        # Business logic
│   ├── agentic/     # AI agent system (tools, orchestrators)
│   ├── revive/      # RE-VIVE AI helper
│   └── mcp/         # Model Context Protocol clients
├── models*.py       # SQLAlchemy ORM models (by domain)
├── schemas*.py      # Pydantic schemas (by domain)
├── middleware/       # Request middleware (BaseHTTPMiddleware subclasses)
├── utils/           # Shared utilities
├── llm_core/        # LLM client abstractions
└── config.py        # Settings via pydantic-settings

tests/
├── conftest.py      # Shared fixtures (DO NOT DUPLICATE — reuse these)
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

schema/
└── schema.sql       # Canonical DB schema (source of truth)

atlas/
└── migrations/      # Versioned SQL migrations (YYYYMMDDHHMMSS_name.sql)
```

---

## Running Tests Locally

```bash
# All unit tests (fast, no DB needed)
pytest tests/unit -v

# Specific test file
pytest tests/unit/services/test_rules_engine.py -v

# Integration tests (need PostgreSQL running)
pytest tests/integration -v

# With coverage report
pytest tests/unit --cov=app --cov-report=term

# Specific test by name
pytest tests/unit -k "test_wildcard_matches" -v
```

---

## Pre-Commit Verification

Before committing, verify:

1. **Tests pass**: `pytest tests/unit -v`
2. **No import errors**: `python -c "from app.main import app"`
3. **Formatting**: `black --check app/ tests/`
4. **Linting**: `ruff check app/ tests/`
5. **Schema in sync** (if DB changed): verify `schema/schema.sql` matches your migration

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
| Middleware in `app/middleware/` | Unit test + verify middleware registration order in `main.py` |
| A new API endpoint | Auth (get_current_user/require_admin) + pagination + tests |
