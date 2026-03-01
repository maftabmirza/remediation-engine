# CLAUDE.md — Remediation Engine

This file provides context to Claude (in VS Code, CLI, or web) for consistent code generation.

## Project

AIOps Remediation Engine — an AI-powered incident response platform.
- **Stack**: Python 3.11+ / FastAPI / PostgreSQL 16 (pgvector) / SQLAlchemy / Docker
- **Migrations**: Atlas (declarative SQL — not Alembic)
- **Tests**: pytest / pytest-asyncio / Playwright
- **LLM**: LiteLLM (multi-provider: Anthropic, OpenAI, Google, Ollama)

## Critical Rules

### 1. ALWAYS write tests

Every code change must include tests. No exceptions.

- **Service changes** (`app/services/`) → unit test in `tests/unit/services/test_<name>.py`
- **Router changes** (`app/routers/`) → integration test in `tests/integration/test_<name>.py`
- **Model changes** (`app/models*.py`) → unit test + Atlas migration
- **Agentic changes** (`app/services/agentic/`) → test in `tests/unit/services/agentic/`
- **E2E/UI changes** → test in `tests/e2e/`
- Use fixtures from `tests/conftest.py` (see `.claude/skills/vscode-llm.md` for full list)
- Minimum 3 test cases per function: happy path, error case, edge case
- Use `@pytest.mark.asyncio` for async tests
- Mock external deps: `AsyncMock` for async, `MagicMock` for sync

### 2. ALWAYS create Atlas migrations for schema changes

If you add/remove/modify any database column, table, index, or constraint:

1. Update `schema/schema.sql` (source of truth)
2. Create `atlas/migrations/YYYYMMDDHHMMSS_description.sql` with the migration SQL
3. Update the SQLAlchemy model in `app/models*.py`
4. Update the Pydantic schema in `app/schemas*.py` if API-visible
5. Never run raw DDL against the database — always use Atlas migrations

### 3. Review LLM interaction impact

There are 5 independent LLM interaction points. When modifying shared LLM code, check impact on all:

1. **RE-VIVE (App)** — `app/services/revive/`, `app/routers/revive.py`
2. **RE-VIVE (Grafana)** — `app/routers/revive_grafana.py`, `app/services/mcp/`
3. **/troubleshoot** — `app/services/agentic/ai_troubleshoot_agent.py`
4. **/inquiry** — `app/services/agentic/ai_inquiry_agent.py`
5. **/alerts help** — `app/services/agentic/ai_alert_help_agent.py`

RE-VIVE files must have the `revive` prefix in their filename.

### 4. Coding standards

- **PEP 8** compliance, `black` formatter, `ruff` linter
- **Type hints** on ALL function arguments AND return values — no exceptions
- **Async-first** for I/O operations (`async def` + `await`)
- **Import order**: stdlib → third-party → local (`app.*`), separated by blank lines
- **Logging**: `logger = logging.getLogger(__name__)` per module, f-strings, appropriate levels
- **Docstrings**: Google-style with `Args:`, `Returns:`, `Raises:` sections
- **Error handling**: Specific exceptions first, log with `exc_info=True`, never bare `except:`
- **No secrets in code** — use `app/config.py` (`get_settings()`)
- **SQL safety**: Always use `like_escape()` for LIKE queries, parameter binding for raw SQL
- **Router pattern**: `/api/<feature>` prefix, `response_model`, `status.HTTP_201_CREATED` for POST
- **Pagination**: `page`/`page_size` (max 100) with `total` in response
- **Auth on every endpoint**: `Depends(get_current_user)` for read, `Depends(require_admin)` or `Depends(require_role([...]))` for write

For comprehensive coding standards, patterns, examples, and best practices, see: **`.claude/skills/vscode-llm.md`**

## Test Commands

```bash
pytest tests/unit -v                    # Unit tests (fast)
pytest tests/integration -v             # Integration tests (need DB)
pytest tests/unit --cov=app             # With coverage
pytest tests/unit -k "test_name"        # Specific test
```

## Schema Change Commands

```bash
# Inside the container:
atlas migrate hash --dir "file:///app/atlas/migrations"
atlas migrate apply --dir "file:///app/atlas/migrations" --url "$DATABASE_URL"
```

## Key Directories

- `app/services/` — business logic
- `app/routers/` — API endpoints
- `app/models*.py` — SQLAlchemy models (by domain)
- `app/schemas*.py` — Pydantic schemas (by domain)
- `tests/` — all tests (unit, integration, e2e, security, performance)
- `schema/schema.sql` — canonical DB schema
- `atlas/migrations/` — Atlas migration files
- `config/` — application configuration (revive.yaml, etc.)
