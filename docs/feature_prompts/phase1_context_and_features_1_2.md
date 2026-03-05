# Implementation Plan — Phase 1 of 4
# Features: RAG-Enhanced Alert Diagnosis (B7) + Alert Suppression Rules (A6)

## HOW TO USE THIS PHASE
Input this file to Claude. Once complete, continue with phase2_features_3_4.md.

---

## Project Context

You are working on the **AIOps Remediation Engine** — a FastAPI + PostgreSQL (pgvector) automated incident response platform.

The platform has: 5 AI interaction points, multi-provider LLM (LiteLLM), runbook automation (SSH/WinRM/API), 3-layer alert clustering, circuit breakers/blackout windows, observability (Prometheus/Loki/Tempo/Grafana), ITSM connector, 4-provider notifications, PII detection, pgvector semantic search, agent orchestration with approval workflows, SAML SSO, and a learning feedback loop.

### Critical Files Reference
| Purpose | File Path |
|---------|-----------|
| Application/Component/Dependency models | app/models_application.py |
| Similarity search (pgvector) | app/services/similarity_service.py |
| Effectiveness scoring | app/services/effectiveness_service.py |
| Context enrichment pattern | app/services/agentic/context_enricher.py |
| Notification dispatcher | app/services/notification/dispatcher.py |
| Webhook alert ingestion | app/routers/webhook.py |
| LLM integration | app/services/llm_service.py |
| Prometheus queries | app/services/prometheus_service.py |
| Prompt management | app/services/prompt_service.py |
| Correlation service | app/services/correlation_service.py |
| Agent session/step models | app/models_agent.py |
| Learning feedback models | app/models_learning.py |
| Scheduler infrastructure | app/services/scheduler_service.py |
| Knowledge search | app/services/knowledge_search_service.py |
| Runbook/execution models | app/models_remediation.py |
| Change impact analysis | app/services/change_impact_service.py |
| Trigger matcher | app/services/trigger_matcher.py |
| Design doc/chunk models | app/models_knowledge.py |

### Coding Standards (always apply)
- PEP 8, type hints on ALL arguments and return values, async-first for I/O
- Import order: stdlib → third-party → local (`app.*`)
- `logger = logging.getLogger(__name__)` per module
- Google-style docstrings with Args/Returns/Raises
- `Depends(get_current_user)` on read endpoints, `Depends(require_admin)` or `Depends(require_role([...]))` on write
- `response_model`, `status.HTTP_201_CREATED` for POST
- Pagination: `page`/`page_size` (max 100) with `total` in response
- CSS: use CSS variables (`var(--bg-surface)` etc.), never hardcoded hex
- Modals: `.modal-overlay`/`.modal-container` — never `confirm()`/`alert()`/`prompt()`
- Notifications: `window.showToast(msg, type)` only

### Atlas Migration Rules (ALWAYS follow)
1. Update `schema/schema.sql` (source of truth)
2. Create `atlas/migrations/YYYYMMDDHHMMSS_description.sql`
3. Copy into container: `docker cp atlas/migrations/<file> remediation-engine:/app/atlas/migrations/`
4. Run: `docker compose exec remediation-engine atlas migrate hash --dir "file:///app/atlas/migrations"`
5. Run: `docker compose exec remediation-engine atlas migrate apply --dir "file:///app/atlas/migrations" --url "$DATABASE_URL"`
6. Copy atlas.sum back: `docker cp remediation-engine:/app/atlas/migrations/atlas.sum atlas/migrations/atlas.sum`
7. Update SQLAlchemy model + Pydantic schema
8. Rebuild: `docker compose up -d --build remediation-engine`
**NEVER run raw ALTER TABLE directly.**

### Test Requirements (always apply)
- Minimum 3 test cases per function: happy path, error case, edge case
- `@pytest.mark.asyncio` for async tests
- `AsyncMock` for async mocking, `MagicMock` for sync
- Use fixtures from `tests/conftest.py`
- Unit tests: `tests/unit/services/test_<name>.py` with `@pytest.mark.unit`
- Integration tests: `tests/integration/test_<name>.py` with `@pytest.mark.integration`

---

## Feature 1: RAG-Enhanced Alert Diagnosis (B7) — P0

### Goal
When any of the 5 AI interaction points processes an alert, automatically inject relevant knowledge base sections (design docs, architecture diagrams) as context.

### Files to Create
- `app/services/knowledge_enrichment_service.py` — Core service
- `tests/unit/services/test_knowledge_enrichment_service.py` — Tests

### Files to Modify
- `app/services/revive/revive_service.py` — Add knowledge context to RE-VIVE (App) prompt
- `app/services/revive/revive_grafana_service.py` — Add knowledge context to RE-VIVE (Grafana)
- `app/services/agentic/ai_troubleshoot_agent.py` — Extend with knowledge chunks (already uses context_enricher.py)
- `app/services/agentic/ai_inquiry_agent.py` — Add knowledge context
- `app/services/agentic/ai_alert_help_agent.py` — Add knowledge context

### Service: KnowledgeEnrichmentService
Create `app/services/knowledge_enrichment_service.py` that:

1. Takes an Alert (or alert_id) and a SQLAlchemy Session
2. Looks up alert's `app_id` (from `Alert.app_id` or label matching via `Application.alert_label_matchers`)
3. Queries `DesignChunk` table using pgvector cosine similarity against alert embedding
4. Also fetches `DesignImage.ai_description` for the matched application
5. Returns formatted context string (max 2000 tokens, ranked by relevance)
6. Also includes past postmortems and successfully resolved similar alerts as additional RAG sources

Additional RAG sources to include:
- Past `PostmortemReport` records for the same application (once Feature 4 is built — use try/import guard for now)
- Successfully resolved `Alert` records with high embedding similarity

### Context Enricher Integration
Add `knowledge_context: Optional[str]` field to the `EnrichedContext` dataclass in `app/services/agentic/context_enricher.py`. Populate it by calling `KnowledgeEnrichmentService`.

### Prompt Injection
Wire the returned context string into the system/user prompts of all 5 AI pillars:
1. RE-VIVE (App): `app/services/revive/revive_service.py`
2. RE-VIVE (Grafana): `app/services/revive/revive_grafana_service.py`
3. /troubleshoot: `app/services/agentic/ai_troubleshoot_agent.py`
4. /inquiry: `app/services/agentic/ai_inquiry_agent.py`
5. /alerts help: `app/services/agentic/ai_alert_help_agent.py`

### Reuse Pattern
Follow the `SimilarityService` pattern for pgvector queries. Follow the `TroubleshootingContextEnricher` pattern for async enrichment.

### Tests (test_knowledge_enrichment_service.py)
- Happy path: knowledge chunks found and formatted correctly
- No embedding on alert: graceful fallback (return empty string)
- No matching application: return empty string
- Empty knowledge base: return empty string
- Max token truncation: verify output stays within 2000 tokens
- Successfully resolved alerts included as RAG source

---

## Feature 2: Alert Suppression Rules (A6) — P0

### Goal
Suppress alert noise during maintenance windows. Alerts matching suppression rules are stored but marked suppressed — not clustered, not analyzed, not auto-remediated.

### Files to Create
- `app/models_suppression.py` — AlertSuppressionRule model
- `app/schemas_suppression.py` — Pydantic schemas
- `app/services/alert_suppression_service.py` — Suppression logic
- `app/routers/alert_suppression_api.py` — CRUD endpoints
- `atlas/migrations/20260304120000_add_alert_suppression.sql` — Migration
- `tests/unit/services/test_alert_suppression_service.py` — Tests

### Files to Modify
- `schema/schema.sql` — Add `alert_suppression_rules` table
- `app/routers/webhook.py` — Add suppression check before processing (after alert creation, before rule matching/analysis)
- `app/models_application.py` or `app/models.py` — Add `maintenance_mode: bool` column to `Application`
- `app/main.py` — Register new router

### Model: AlertSuppressionRule
```
id:           UUID, PK
name:         VARCHAR(200), NOT NULL
rule_type:    VARCHAR(20), NOT NULL  -- "time_based", "label_based", "service_based", "maintenance"
matchers:     JSONB  -- {"alertname": ".*CPU.*", "severity": "warning", "service": "app-*"}
app_id:       UUID, FK applications (nullable)
starts_at:    TIMESTAMPTZ, NOT NULL
ends_at:      TIMESTAMPTZ (nullable -- NULL = permanent rule)
grace_period_minutes: INTEGER DEFAULT 5  -- Silence clustering after window ends to prevent flapping storm
is_active:    BOOLEAN DEFAULT TRUE
created_by:   UUID, FK users
created_at:   TIMESTAMPTZ DEFAULT now()
updated_at:   TIMESTAMPTZ DEFAULT now()
```

Also add to `applications` table:
```
maintenance_mode: BOOLEAN DEFAULT FALSE
```

### Migration SQL (20260304120000_add_alert_suppression.sql)
```sql
CREATE TABLE public.alert_suppression_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(200) NOT NULL,
    rule_type character varying(20) NOT NULL,
    matchers jsonb,
    app_id uuid,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone,
    grace_period_minutes integer DEFAULT 5,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT alert_suppression_rules_pkey PRIMARY KEY (id),
    CONSTRAINT alert_suppression_rules_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id),
    CONSTRAINT alert_suppression_rules_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);

CREATE INDEX ix_alert_suppression_rules_app_id ON public.alert_suppression_rules USING btree (app_id);
CREATE INDEX ix_alert_suppression_rules_is_active ON public.alert_suppression_rules USING btree (is_active);

ALTER TABLE public.applications ADD COLUMN IF NOT EXISTS maintenance_mode boolean DEFAULT false;
```

### Service: AlertSuppressionService
Method: `check_suppression(alert_labels: dict, app_id: Optional[UUID], db: AsyncSession) -> Optional[AlertSuppressionRule]`

Logic:
1. Fetch all active rules where `is_active = True` and (`ends_at IS NULL OR ends_at > now()`)
2. For each rule, check:
   - If `app_id` matches (or rule has no app constraint)
   - If app's `maintenance_mode = True` → immediate suppression
   - Match `matchers` dict using regex pattern matching against alert labels
3. Return first matching rule (or None)
4. For SLO exemption: when suppressed, record suppression in a structured way so SLO evaluation can exclude this window for accurate reporting

### Webhook Integration
In `app/routers/webhook.py`, after alert is created in DB but before rule matching/clustering/analysis:
```python
suppression = await suppression_service.check_suppression(alert.labels, alert.app_id, db)
if suppression:
    alert.status = "suppressed"
    await db.commit()
    logger.info(f"Alert {alert.id} suppressed by rule {suppression.id} ({suppression.name})")
    return  # Skip all downstream processing
```

### CRUD Router (/api/alert-suppression/)
- `GET /api/alert-suppression/` — List rules (paginated), auth: `get_current_user`
- `POST /api/alert-suppression/` — Create rule, auth: `require_admin`
- `GET /api/alert-suppression/{id}` — Get rule, auth: `get_current_user`
- `PUT /api/alert-suppression/{id}` — Update rule, auth: `require_admin`
- `DELETE /api/alert-suppression/{id}` — Delete rule, auth: `require_admin`
- `POST /api/alert-suppression/check` — Test if labels would be suppressed (dry-run), auth: `get_current_user`

### Tests (test_alert_suppression_service.py)
- Time-based match: rule active within window suppresses alert
- Time-based no match: rule outside window does not suppress
- Label regex match: `".*CPU.*"` matches `"HighCPULoad"`
- Label regex no match: pattern does not match label
- Maintenance mode: `application.maintenance_mode = True` suppresses all alerts for that app
- Expired rule: `ends_at < now()` does not suppress
- Overlapping rules: first matching rule returned
- No active rules: returns None
- Grace period: alert within grace period after window end is still suppressed
- SLO exemption recording: suppressed alert is excluded from SLO calculation window

---

## Deliverables for Phase 1
After implementing both features, verify:
- [ ] `pytest tests/unit/services/test_knowledge_enrichment_service.py -v` passes
- [ ] `pytest tests/unit/services/test_alert_suppression_service.py -v` passes
- [ ] Atlas migration applied successfully
- [ ] `schema/schema.sql` updated with `alert_suppression_rules` table and `maintenance_mode` column
- [ ] All 5 AI interaction points receive knowledge context
- [ ] Webhook suppression check in place
- [ ] New routers registered in `app/main.py`

**When Phase 1 is complete, proceed to: `docs/feature_prompts/phase2_features_3_4.md`**
