# Implementation Plan — Phase 2 of 4
# Features: Remediation Confidence Score (B6) + Post-Incident Postmortem Generation (A4)

## HOW TO USE THIS PHASE
Ensure Phase 1 (phase1_context_and_features_1_2.md) is complete first.
Input this file to Claude. Once complete, continue with phase3_features_5_6.md.

---

## Reminder: Project Standards
- PEP 8, type hints on ALL arguments/returns, async-first for I/O
- `@pytest.mark.unit` + `@pytest.mark.asyncio` for tests
- `Depends(get_current_user)` read / `Depends(require_admin)` or `require_role([...])` write
- Atlas migrations: NEVER raw DDL — always migration file + `atlas migrate hash` + `atlas migrate apply`
- Min 3 tests per function: happy path, error, edge case

### Key Files Already in Project
| Purpose | File |
|---------|------|
| pgvector similarity | app/services/similarity_service.py |
| Effectiveness/weighted scoring | app/services/effectiveness_service.py |
| LLM calls | app/services/llm_service.py |
| Runbook/execution models | app/models_remediation.py |
| Agent session/step models | app/models_agent.py |
| Learning feedback models | app/models_learning.py |
| Trigger matcher | app/services/trigger_matcher.py |
| Remediation router | app/routers/remediation.py |

---

## Feature 3: Remediation Confidence Score (B6) — P0

### Goal
Before executing a runbook, compute and display a confidence score (0-100%) based on how well that runbook has historically performed on similar alerts. Show plain-English reasoning.

### Files to Create
- `app/services/confidence_score_service.py` — Score computation
- `app/schemas_confidence.py` — Response schemas
- `tests/unit/services/test_confidence_score_service.py` — Tests

### Files to Modify
- `app/routers/remediation.py` — Add confidence score to execution trigger response
- `app/services/trigger_matcher.py` — Include confidence in trigger match result

### Schemas (app/schemas_confidence.py)
```python
class SampleOutcome(BaseModel):
    alert_id: UUID
    similarity: float
    outcome: str  # "success" | "failure" | "partial"
    resolution_time_minutes: Optional[float]

class ConfidenceScore(BaseModel):
    score: float                    # 0.0 - 100.0
    explanation: str                # Human-readable reason
    similar_count: int              # How many similar past alerts found
    success_rate: float             # 0.0 - 1.0
    avg_resolution_minutes: Optional[float]
    sample_outcomes: List[SampleOutcome]
    confidence_level: str           # "high" (≥70), "medium" (40-69), "low" (<40), "insufficient_data"
```

### Service: ConfidenceScoreService

**Method: `calculate(alert_id: UUID, runbook_id: UUID, db: AsyncSession) -> ConfidenceScore`**

Algorithm:
1. Load the alert; if it has no embedding, return `confidence_level = "insufficient_data"` with score = 50.0 (neutral)
2. Call `SimilarityService.find_similar_alerts(alert_id, limit=20, min_similarity=0.7)` to get similar historical alerts
3. For each similar alert, query `RunbookExecution` to find executions of `runbook_id` triggered by that alert
4. For matched executions, query `ExecutionOutcome` to get `outcome_type` and `resolution_time_minutes`
5. Compute weighted score:
   ```
   weighted_successes = Σ(similarity × (1.0 if outcome==success else 0.5 if partial else 0.0))
   weighted_total = Σ(similarity)
   raw_score = weighted_successes / weighted_total  # 0.0 - 1.0
   ```
6. If `similar_count < 3`: blend with `EffectivenessService.get_overall_score(runbook_id)` as a prior (60% prior, 40% computed)
7. Multiply by 100 for final score
8. Generate explanation as f-string (no LLM call):
   - `similar_count >= 3`: `"Based on {n} similar incidents: {pct}% success rate, avg resolution {t} min"`
   - `similar_count < 3` and prior available: `"Limited history ({n} similar incidents). Based mainly on overall runbook performance: {overall_pct}% success rate"`
   - No data at all: `"No historical data available for this runbook. Score based on runbook configuration only."`
9. Set `confidence_level`: `high` ≥70, `medium` 40-69, `low` <40, `insufficient_data` if no embedding

**Method: `bulk_calculate(alert_id: UUID, runbook_ids: List[UUID], db: AsyncSession) -> Dict[UUID, ConfidenceScore]`**
Calls `calculate()` for each runbook; used when trigger_matcher returns multiple candidate runbooks.

### Trigger Matcher Integration
In `app/services/trigger_matcher.py`, extend the `TriggerMatchResult` (or equivalent return type) to include an optional `confidence: Optional[ConfidenceScore]`. After finding matching rules, call `ConfidenceScoreService.calculate()` and attach the result.

### Remediation Router Integration
In `app/routers/remediation.py`, include the `confidence` field in the execution trigger response so the UI/caller can show it before confirming execution.

### Tests (test_confidence_score_service.py)
- High confidence: many similar alerts, high success rate → score ≥ 70
- Low confidence: many similar alerts, mostly failures → score < 40
- Insufficient data: fewer than 3 similar alerts → blends with prior, `confidence_level = "medium"` or reflects prior
- No embedding on alert: returns score = 50.0 with `confidence_level = "insufficient_data"`
- No execution history: returns score based purely on effectiveness prior
- Partial outcomes: `partial` outcomes count as 0.5 weight
- `bulk_calculate` returns dict keyed by runbook_id

---

## Feature 4: Post-Incident Review / Postmortem Generation (A4) — P1

### Goal
Auto-generate structured postmortem reports from incident data (alerts, executions, feedback, metrics) using LLM. Support manual editing and export.

### Files to Create
- `app/models_postmortem.py` — PostmortemReport model
- `app/schemas_postmortem.py` — Pydantic schemas
- `app/services/postmortem_service.py` — Generation + CRUD
- `app/routers/postmortem_api.py` — API endpoints
- `atlas/migrations/20260304130000_add_postmortem_reports.sql` — Migration
- `tests/unit/services/test_postmortem_service.py` — Tests

### Files to Modify
- `schema/schema.sql` — Add `postmortem_reports` table
- `app/main.py` — Register new router

### Model: PostmortemReport (app/models_postmortem.py)
```
id:                   UUID, PK, default gen_random_uuid()
title:                VARCHAR(500), NOT NULL
alert_id:             UUID, FK alerts (nullable)
app_id:               UUID, FK applications (nullable)
status:               VARCHAR(20), DEFAULT 'draft'  -- draft, in_review, published
incident_start:       TIMESTAMPTZ
incident_end:         TIMESTAMPTZ
severity:             VARCHAR(20)
timeline:             JSONB  -- [{timestamp, event, source, manual: bool}]
impact_summary:       TEXT
root_cause:           TEXT
contributing_factors: JSONB  -- [string]
remediation_actions:  JSONB  -- [{action, runbook_id, outcome, duration_minutes}]
action_items:         JSONB  -- [{description, owner, due_date, status}]
lessons_learned:      TEXT
metrics:              JSONB  -- {mttd_minutes, mtta_minutes, mtte_minutes, mttr_minutes}
generated_by:         VARCHAR(20) DEFAULT 'ai'  -- ai, manual
out_of_band_context:  JSONB  -- [{source, content, timestamp}] for Slack/vendor/customer notes
reviewed_by:          UUID, FK users (nullable)
created_by:           UUID, FK users
created_at:           TIMESTAMPTZ DEFAULT now()
updated_at:           TIMESTAMPTZ DEFAULT now()
```

### Migration SQL (20260304130000_add_postmortem_reports.sql)
```sql
CREATE TABLE public.postmortem_reports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title character varying(500) NOT NULL,
    alert_id uuid,
    app_id uuid,
    status character varying(20) DEFAULT 'draft' NOT NULL,
    incident_start timestamp with time zone,
    incident_end timestamp with time zone,
    severity character varying(20),
    timeline jsonb DEFAULT '[]'::jsonb,
    impact_summary text,
    root_cause text,
    contributing_factors jsonb DEFAULT '[]'::jsonb,
    remediation_actions jsonb DEFAULT '[]'::jsonb,
    action_items jsonb DEFAULT '[]'::jsonb,
    lessons_learned text,
    metrics jsonb DEFAULT '{}'::jsonb,
    generated_by character varying(20) DEFAULT 'ai',
    out_of_band_context jsonb DEFAULT '[]'::jsonb,
    reviewed_by uuid,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT postmortem_reports_pkey PRIMARY KEY (id),
    CONSTRAINT postmortem_reports_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id),
    CONSTRAINT postmortem_reports_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id),
    CONSTRAINT postmortem_reports_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id),
    CONSTRAINT postmortem_reports_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);

CREATE INDEX ix_postmortem_reports_alert_id ON public.postmortem_reports USING btree (alert_id);
CREATE INDEX ix_postmortem_reports_app_id ON public.postmortem_reports USING btree (app_id);
CREATE INDEX ix_postmortem_reports_status ON public.postmortem_reports USING btree (status);
```

### Schemas (app/schemas_postmortem.py)
- `TimelineEntry`: `{timestamp: datetime, event: str, source: str, manual: bool}`
- `ActionItem`: `{description: str, owner: Optional[str], due_date: Optional[date], status: str}`
- `PostmortemReportCreate`: `{alert_id: Optional[UUID], app_id: Optional[UUID]}`
- `PostmortemReportUpdate`: all editable fields optional (title, timeline, impact_summary, root_cause, contributing_factors, remediation_actions, action_items, lessons_learned, out_of_band_context, action_items status)
- `PostmortemReportResponse`: all fields including computed metrics
- `PostmortemListResponse`: `{items: List[PostmortemReportResponse], total: int, page: int, page_size: int}`
- `OutOfBandContextAdd`: `{source: str, content: str, timestamp: Optional[datetime]}`

### Service: PostmortemService

**Method: `generate(alert_id: UUID, created_by: UUID, db: AsyncSession) -> PostmortemReport`**

Data gathering:
1. Load Alert + all correlated alerts (via `AlertCorrelation`)
2. Load `RunbookExecution` records linked to the alert + `StepExecution` details
3. Load `IncidentMetrics` (MTTD, MTTA, MTTE, MTTR if available)
4. Load `AnalysisFeedback` for the alert
5. Load `SolutionOutcome` for resolved cases

Build timeline (sorted by timestamp):
- Alert `fired_at`
- Each correlated alert `timestamp`
- Each `RunbookExecution.started_at` and `completed_at`
- Each `StepExecution.started_at` with step name/output summary
- Resolution timestamp from `IncidentMetrics.resolved_at`

LLM call via `LLMService`:
```
System: "You are an SRE expert generating a structured post-incident review."
User: "Given the following incident data, generate:
1. A concise impact summary (2-3 sentences, include affected services and user impact)
2. Root cause analysis (what actually failed and why)
3. Contributing factors (list of 3-5 items)
4. Lessons learned (what should change)
5. 3-5 concrete action items with suggested owners

Incident data:
{json.dumps(gathered_data, indent=2, default=str)}"
```

Parse LLM response and populate model fields. Set `status = "draft"`, `generated_by = "ai"`.
Compute metrics from timestamps.

**Method: `regenerate(postmortem_id: UUID, db: AsyncSession) -> PostmortemReport`**
Re-runs generation preserving manual `out_of_band_context` entries. Merges existing manual timeline entries back in.

**Method: `add_out_of_band_context(postmortem_id: UUID, entry: OutOfBandContextAdd, db: AsyncSession) -> PostmortemReport`**
Appends a manual context entry (e.g., customer report, vendor status, Slack thread summary) to `out_of_band_context`.

**Method: `publish(postmortem_id: UUID, reviewed_by: UUID, db: AsyncSession) -> PostmortemReport`**
Sets `status = "published"`, sets `reviewed_by`.

### Router: /api/postmortems/ (app/routers/postmortem_api.py)
- `POST /api/postmortems/generate` — Generate from alert_id, auth: `get_current_user`, returns draft
- `GET /api/postmortems/` — List (paginated, filter by app_id/status), auth: `get_current_user`
- `GET /api/postmortems/{id}` — Get single, auth: `get_current_user`
- `PUT /api/postmortems/{id}` — Update (editing), auth: `get_current_user`
- `POST /api/postmortems/{id}/regenerate` — Re-generate preserving manual edits, auth: `get_current_user`
- `POST /api/postmortems/{id}/out-of-band` — Add manual context entry, auth: `get_current_user`
- `POST /api/postmortems/{id}/publish` — Publish, auth: `require_role(["admin", "engineer"])`
- `DELETE /api/postmortems/{id}` — Delete draft, auth: `require_admin`

### Tests (test_postmortem_service.py)
- Generation with full data: all sections populated, timeline sorted correctly
- Generation with partial data: only alert, no executions → graceful, filled with available data
- Alert not found: raises `HTTPException 404`
- LLM failure: raises appropriate error, does not save partial record
- `add_out_of_band_context`: entry appended, existing entries preserved
- `regenerate`: manual out_of_band_context entries preserved, AI sections refreshed
- `publish`: status changes to "published", reviewed_by set
- MTTD/MTTR calculation: values computed correctly from timestamps
- Timeline ordering: events sorted chronologically regardless of source

---

## Deliverables for Phase 2
After implementing both features, verify:
- [ ] `pytest tests/unit/services/test_confidence_score_service.py -v` passes
- [ ] `pytest tests/unit/services/test_postmortem_service.py -v` passes
- [ ] Atlas migration `20260304130000_add_postmortem_reports.sql` applied successfully
- [ ] `schema/schema.sql` updated with `postmortem_reports` table
- [ ] Confidence score appears in remediation trigger/match responses
- [ ] Postmortem router registered in `app/main.py`

**When Phase 2 is complete, proceed to: `docs/feature_prompts/phase3_features_5_6.md`**
