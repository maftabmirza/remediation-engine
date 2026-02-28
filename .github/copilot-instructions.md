# GitHub Copilot Instructions

## Project Overview

This is the **Remediation Engine** — an automated incident response and remediation system built with FastAPI, PostgreSQL (pgvector), and a full observability stack.

---

## Server & Infrastructure

### Production / Development Server

| Property | Value |
|----------|-------|
| **Host** | `74.208.72.110` (p-ionos-02) |
| **OS** | Linux (Ubuntu) |
| **Runtime** | Docker + Docker Compose v2 |
| **App URL** | http://74.208.72.110:8080 |
| **Project root** | `/aiops` |

All development, building, and running happens directly on this Linux server via SSH. Docker Desktop / Windows is **not** used.

---

## Docker Services

All services are defined in `docker-compose.yml` and run in the `aiops-network` bridge network.

| Container | Image | External Port(s) | Purpose |
|-----------|-------|-----------------|---------|
| `remediation-engine` | `aiops-remediation-engine` (local build) | **8080** | Main FastAPI application |
| `aiops-postgres` | `pgvector/pgvector:pg16` | 5432 | PostgreSQL 16 with pgvector extension |
| `aiops-grafana` | `grafana/grafana-enterprise:latest` | 3000 | Dashboards & visualisation |
| `aiops-prometheus` | `prom/prometheus:latest` | 9090 | Metrics collection |
| `aiops-alertmanager` | `prom/alertmanager:latest` | 9093 | Alert routing |
| `aiops-loki` | `grafana/loki:latest` | 3100 | Log aggregation |
| `aiops-promtail` | `grafana/promtail:latest` | — | Log shipping to Loki |
| `aiops-tempo` | `grafana/tempo:2.6.1` | 3200, 4317, 4318, 9411 | Distributed tracing |
| `aiops-mimir` | `grafana/mimir:latest` | 9009 | Long-term metrics storage |
| `mcp-grafana` | `grafana/mcp-grafana:latest` | 8001→8000 | MCP server for AI agent Grafana access |

### Inter-container hostnames (internal DNS)

Inside the Docker network, containers reach each other by service name:

- `postgres:5432`
- `grafana:3000`
- `prometheus:9090`
- `loki:3100`
- `tempo:4317` (OTLP gRPC), `tempo:3200` (HTTP)
- `mcp-grafana:8000`

---

## Key Configuration Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | All service definitions |
| `docker-compose.test.yml` | Test environment |
| `Dockerfile` | Production app image |
| `Dockerfile.test` | Test image |
| `.env` | Secrets & env overrides (never commit) |
| `.env.example` | Template for `.env` |
| `app/models.py` | SQLAlchemy ORM models |
| `app/schemas.py` | Pydantic request/response schemas |
| `app/routers/` | FastAPI route handlers |
| `app/services/` | Business logic layer |
| `schema/schema.sql` | **Canonical DB schema** (pg_dump format — Atlas source of truth) |
| `atlas/migrations/` | Atlas migration SQL files |
| `atlas.hcl` | Atlas configuration |

---

## Common Commands

```bash
# Build & restart only the app (most common during development)
docker compose up -d --build remediation-engine

# Start entire stack
docker compose up -d

# Tail app logs
docker logs -f remediation-engine

# Open a shell in the app container
docker compose exec remediation-engine bash

# Open psql
docker compose exec -T postgres psql -U aiops -d aiops

# Check Atlas migration status
docker compose exec remediation-engine atlas migrate status \
  --dir "file:///app/atlas/migrations" \
  --url "$DATABASE_URL"
```

---

## Application Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI with Uvicorn
- **Database**: PostgreSQL 16 + pgvector (vector similarity search)
- **ORM**: SQLAlchemy
- **Schemas**: Pydantic v2
- **Auth**: JWT + role-based permissions
- **LLM integration**: LiteLLM (supports Anthropic, OpenAI, Google, Ollama, Azure)
- **Embeddings**: Configured via Settings → LLM Providers (`usage_type = 'embedding'`) — no `.env` fallback
- **Observability**: OpenTelemetry → Tempo, logs → Loki, metrics → Prometheus/Mimir

API docs (when running):
- Swagger UI: http://74.208.72.110:8080/docs
- ReDoc: http://74.208.72.110:8080/redoc

---

## Conventions & Notes

- Follow PEP 8; use type hints everywhere.
- Tests use `test_*.py` naming; run via `docker-compose.test.yml`.
- Never commit `.env` — use `.env.example` as template.
- `app/`, `static/`, `templates/` are **bind-mounted** into the container — code changes are live without rebuild. Dependency or config changes require `--build`.
- Volumes `postgres_data`, `grafana-data`, `loki-data`, `prometheus-data` persist across restarts.

---

## Database Schema Changes — Atlas Workflow

**ALWAYS use Atlas for schema changes. Never run raw `ALTER TABLE` or `CREATE TABLE` directly.**

### Source of truth

`schema/schema.sql` is the canonical schema definition. All changes start here.

### Atlas lives inside the container

Atlas CLI is installed inside the `remediation-engine` container at `/usr/local/bin/atlas`. It is **not** installed on the host.

```bash
docker compose exec remediation-engine atlas version
```

### Step-by-step: adding a column (or any schema change)

**1. Update `schema/schema.sql`** — add the new column, index, constraint, etc.

**2. Copy the updated schema into the running container:**

```bash
docker cp schema/schema.sql remediation-engine:/app/schema/schema.sql
```

**3. Write the migration SQL file** in `atlas/migrations/` using the naming convention:

```
atlas/migrations/YYYYMMDDHHMMSS_description.sql
```

Example — `atlas/migrations/20260228000000_add_llm_provider_usage_type.sql`:

```sql
ALTER TABLE public.llm_providers ADD COLUMN usage_type character varying(20) NOT NULL DEFAULT 'llm';
CREATE INDEX ix_llm_providers_usage_type ON public.llm_providers USING btree (usage_type);
```

**4. Copy the migration file into the container:**

```bash
docker cp atlas/migrations/20260228000000_add_llm_provider_usage_type.sql \
  remediation-engine:/app/atlas/migrations/
```

**5. Update `atlas.sum`** (Atlas integrity hash — must always be in sync):

```bash
docker compose exec remediation-engine atlas migrate hash \
  --dir "file:///app/atlas/migrations"
```

**6. Baseline the DB if `atlas_schema_revisions` does not yet exist**

Check whether Atlas has ever managed this DB:

```bash
docker compose exec -T postgres psql -U aiops -d aiops \
  -c "SELECT version FROM atlas_schema_revisions ORDER BY applied_at DESC LIMIT 1;"
```

If the table doesn't exist, set the revision pointer to the last known-good migration **before** your new one:

```bash
docker compose exec remediation-engine atlas migrate set 20260226000001 \
  --dir "file:///app/atlas/migrations" \
  --url "$DATABASE_URL"
```

This creates `atlas_schema_revisions` and marks all previous migrations as applied without re-running them.

**7. Apply the new migration:**

```bash
docker compose exec remediation-engine atlas migrate apply \
  --dir "file:///app/atlas/migrations" \
  --url "$DATABASE_URL"
```

Expected output:
```
Migrating to version 20260228000000 from 20260226000001 (1 migrations in total):
  -- migrating version 20260228000000
    -> ALTER TABLE ...
  -- ok (4ms)
```

**8. Sync `atlas.sum` back to the host:**

```bash
docker cp remediation-engine:/app/atlas/migrations/atlas.sum atlas/migrations/atlas.sum
```

**9. Update the SQLAlchemy model** in `app/models.py` and Pydantic schemas in `app/schemas.py` to match.

**10. Rebuild the container:**

```bash
docker compose up -d --build remediation-engine
```

---

### Why not `atlas migrate diff`?

`schema/schema.sql` is a raw `pg_dump` output (starts with a BOM and uses dump-format comments). Atlas cannot parse it as an HCL/SQL schema source — `atlas migrate diff` will error. **Always write migration files by hand**, matching exactly what the schema change requires, then use `atlas migrate hash` + `atlas migrate apply`.

### Key rules

| Rule | Reason |
|------|--------|
| Never `ALTER TABLE` directly in psql or Python | Bypasses Atlas tracking; future `migrate apply` will fail with "already exists" |
| Never edit `atlas.sum` by hand | Always regenerate via `atlas migrate hash` |
| One logical change per migration file | Easier rollback and review |
| `schema/schema.sql` must stay in sync | It is the reference for human review; keep it updated alongside each migration |
| `DATABASE_URL` env var is set inside the container | Use it directly: `--url "$DATABASE_URL"` when exec-ing into the container |

---

## Where to find more details

- Developer guide: `DEVELOPER_GUIDE.md`
- Deployment checklist: `DEPLOYMENT_CHECKLIST.md`
- Atlas migration guide: `ATLAS_MIGRATION_GUIDE.md`
- Docs folder: `docs/`


---

## Database Schema Changes — Atlas Workflow

**ALWAYS use Atlas for schema changes. Never run raw `ALTER TABLE` or `CREATE TABLE` directly.**

### Source of truth

`schema/schema.sql` is the canonical schema definition. All changes start here.

### Atlas lives inside the container

Atlas CLI is installed inside the `remediation-engine` container at `/usr/local/bin/atlas`. It is **not** installed on the host.

```bash
docker compose exec remediation-engine atlas version
```

### Step-by-step: adding a column (or any schema change)

**1. Update `schema/schema.sql`** — add the new column, index, constraint, etc.

**2. Copy the updated schema into the running container:**

```bash
docker cp schema/schema.sql remediation-engine:/app/schema/schema.sql
```

**3. Write the migration SQL file** in `atlas/migrations/` using the naming convention:

```
atlas/migrations/YYYYMMDDHHMMSS_description.sql
```

Example — `atlas/migrations/20260228000000_add_llm_provider_usage_type.sql`:

```sql
ALTER TABLE public.llm_providers ADD COLUMN usage_type character varying(20) NOT NULL DEFAULT 'llm';
CREATE INDEX ix_llm_providers_usage_type ON public.llm_providers USING btree (usage_type);
```

**4. Copy the migration file into the container:**

```bash
docker cp atlas/migrations/20260228000000_add_llm_provider_usage_type.sql \
  remediation-engine:/app/atlas/migrations/
```

**5. Update `atlas.sum`** (Atlas integrity hash — must always be in sync):

```bash
docker compose exec remediation-engine atlas migrate hash \
  --dir "file:///app/atlas/migrations"
```

**6. Baseline the DB if `atlas_schema_revisions` does not yet exist**

Check whether Atlas has ever managed this DB:

```bash
docker compose exec -T postgres psql -U aiops -d aiops \
  -c "SELECT version FROM atlas_schema_revisions ORDER BY applied_at DESC LIMIT 1;"
```

If the table doesn't exist, set the revision pointer to the last known-good migration **before** your new one:

```bash
docker compose exec remediation-engine atlas migrate set 20260226000001 \
  --dir "file:///app/atlas/migrations" \
  --url "$DATABASE_URL"
```

This creates `atlas_schema_revisions` and marks all previous migrations as applied without re-running them.

**7. Apply the new migration:**

```bash
docker compose exec remediation-engine atlas migrate apply \
  --dir "file:///app/atlas/migrations" \
  --url "$DATABASE_URL"
```

Expected output:
```
Migrating to version 20260228000000 from 20260226000001 (1 migrations in total):
  -- migrating version 20260228000000
    -> ALTER TABLE ...
  -- ok (4ms)
```

**8. Sync `atlas.sum` back to the host:**

```bash
docker cp remediation-engine:/app/atlas/migrations/atlas.sum atlas/migrations/atlas.sum
```

**9. Update the SQLAlchemy model** in `app/models.py` and Pydantic schemas in `app/schemas.py` to match.

**10. Rebuild the container:**

```bash
docker compose up -d --build remediation-engine
```

---

### Why not `atlas migrate diff`?

`schema/schema.sql` is a raw `pg_dump` output (starts with a BOM and uses dump-format comments). Atlas cannot parse it as an HCL/SQL schema source — `atlas migrate diff` will error. **Always write migration files by hand**, matching exactly what the schema change requires, then use `atlas migrate hash` + `atlas migrate apply`.

### Key rules

| Rule | Reason |
|------|--------|
| Never `ALTER TABLE` directly in psql or Python | Bypasses Atlas tracking; future `migrate apply` will fail with "already exists" |
| Never edit `atlas.sum` by hand | Always regenerate via `atlas migrate hash` |
| One logical change per migration file | Easier rollback and review |
| `schema/schema.sql` must stay in sync | It is the reference for human review; keep it updated alongside each migration |
| `DATABASE_URL` env var is set inside the container | Use it directly: `--url "$DATABASE_URL"` when exec-ing into the container |

