# Implementation Plan — Phase 3 of 4
# Features: Runbook Auto-Generation (B2) + Service Health Score & Topology (A2)

## HOW TO USE THIS PHASE
Ensure Phase 1 & 2 are complete first.
Input this file to Claude. Once complete, continue with phase4_feature_7_oncall.md.

---

## Reminder: Project Standards
- PEP 8, type hints on ALL arguments/returns, async-first for I/O
- `@pytest.mark.unit` + `@pytest.mark.asyncio` for tests
- `Depends(get_current_user)` read / `Depends(require_admin)` or `require_role([...])` write
- Atlas migrations: NEVER raw DDL — always migration file + `atlas migrate hash` + `atlas migrate apply`
- Min 3 tests per function: happy path, error, edge case
- CSS: CSS variables only, `.modal-overlay` for modals, `window.showToast()` for notifications

### Key Files Already in Project
| Purpose | File |
|---------|------|
| Agent session/step models | app/models_agent.py |
| Runbook/execution models | app/models_remediation.py |
| Command safety (allow/block lists) | app/models_remediation.py (CommandBlocklist/CommandAllowlist) |
| Application/Component/Dependency models | app/models_application.py |
| Effectiveness/weighted scoring | app/services/effectiveness_service.py |
| Change impact analysis | app/services/change_impact_service.py |
| LLM integration | app/services/llm_service.py |

---

## Feature 5: AI-Powered Runbook Auto-Generation (B2) — P1

### Goal
Mine successful agent troubleshooting sessions (`AgentSession` + `AgentStep` + `SolutionOutcome`) to automatically generate reusable runbook drafts. No competitor does this end-to-end. Transforms tribal knowledge into codified automation.

### Files to Create
- `app/services/runbook_generation_service.py` — Core generation logic
- `app/schemas_runbook_generation.py` — Schemas
- `app/routers/runbook_generation_api.py` — API endpoints
- `tests/unit/services/test_runbook_generation_service.py` — Tests

### Files to Modify
- `app/main.py` — Register new router

### Schemas (app/schemas_runbook_generation.py)
```python
class GenerationCandidate(BaseModel):
    session_ids: List[UUID]          # Sessions in this cluster
    session_count: int
    goal_summary: str                # Inferred from session goals
    app_id: Optional[UUID]
    success_rate: float
    avg_resolution_minutes: Optional[float]
    representative_commands: List[str]  # Sample extracted commands

class GenerationCandidateListResponse(BaseModel):
    items: List[GenerationCandidate]
    total: int

class GenerateRunbookRequest(BaseModel):
    session_ids: List[UUID]          # Must be ≥ 1 session
    runbook_name: Optional[str]      # Override auto-generated name
    app_id: Optional[UUID]

class GeneratedStepPreview(BaseModel):
    step_number: int
    name: str
    step_type: str                   # "command", "api", "conditional", "rollback"
    command_template: str            # With Jinja2 {{ variable }} placeholders
    variables_required: List[str]    # Extracted variable names
    is_idempotent: Optional[bool]    # None = unknown, True/False from LLM analysis
    requires_human_review: bool      # True if non-idempotent pattern detected

class RunbookDraftResponse(BaseModel):
    runbook_id: UUID
    name: str
    description: str
    source: str                      # Always "auto_generated"
    auto_trigger_enabled: bool       # Always False until approved
    steps: List[GeneratedStepPreview]
    variables: List[str]             # All unique variables across steps
    requires_review_reasons: List[str]  # Why human review is needed
    session_count: int               # Sessions this was generated from
```

### Service: RunbookGenerationService

**Method: `find_generation_candidates(min_success_count: int = 3, db: AsyncSession) -> List[GenerationCandidate]`**

Algorithm:
1. Query `AgentSession` where `status = 'completed'` joined with `SolutionOutcome` where `outcome_type = 'resolved'`
2. Group sessions with similar goals using pgvector embedding similarity on `AgentSession.goal` field (cosine similarity ≥ 0.85)
3. Only include clusters with `>= min_success_count` sessions
4. For each cluster, extract a sample of commands from `AgentStep` where `step_type = 'command'` and `result_status = 'success'`
5. Return clusters sorted by session_count descending

**Method: `generate_runbook(session_ids: List[UUID], runbook_name: Optional[str], app_id: Optional[UUID], created_by: UUID, db: AsyncSession) -> Runbook`**

Algorithm:
1. Load `AgentStep` records for given sessions where `step_type = 'command'` and `result_status = 'success'`
2. Extract command sequences with their context (reasoning, inputs, outputs)
3. Run non-idempotent pattern scanner:
   - Flag commands containing: `rm`, `drop`, `delete`, `truncate`, `kill`, `format`, `mkfs`
   - Flag commands without `if ... then` guards for destructive operations
4. Call `LLMService` with prompt:
   ```
   System: "You are an SRE expert creating reusable runbooks from successful troubleshooting sessions."
   User: "Given these successful command sequences from {n} real incidents, generate a generalized runbook:

   REQUIREMENTS:
   - Replace hardcoded values (hostnames, IPs, service names, thresholds) with Jinja2 {{ variable_name }} placeholders
   - Add conditional steps using if/else logic where appropriate
   - Include rollback steps for any destructive or state-changing operations
   - Wrap non-idempotent operations with idempotency guards (check before apply)
   - Name each step clearly

   OUTPUT FORMAT: JSON with fields: name, description, steps (array of {step_number, name, step_type, command_template, variables_required, rollback_command, is_idempotent})

   Command sequences:
   {json.dumps(command_sequences, indent=2)}"
   ```
5. Parse LLM JSON response
6. Validate each generated command against `CommandBlocklist`:
   - If any command matches blocklist: raise `ValueError` with details, do NOT create runbook
7. Create `Runbook` record with:
   - `source = "auto_generated"`
   - `auto_trigger_enabled = False` (requires human approval before use)
   - `is_active = False`
   - `description` includes "Auto-generated from {n} sessions. Requires human review before activation."
8. Create `RunbookStep` records for each generated step
9. Return the created `Runbook`

**Method: `approve_draft(runbook_id: UUID, approved_by: UUID, db: AsyncSession) -> Runbook`**
Sets `is_active = True`, logs approval in `AuditLog` (if available), optionally sets `auto_trigger_enabled = True` based on caller preference.

### Router: /api/runbook-generation/ (app/routers/runbook_generation_api.py)
- `GET /api/runbook-generation/candidates` — List generation opportunities, auth: `get_current_user`
- `POST /api/runbook-generation/generate` — Generate runbook from sessions, auth: `require_role(["admin", "engineer"])`
- `POST /api/runbook-generation/approve/{runbook_id}` — Approve draft for use, auth: `require_admin`
- `GET /api/runbook-generation/drafts` — List auto-generated drafts pending review, auth: `get_current_user`

### Tests (test_runbook_generation_service.py)
- Successful generation: 3 similar sessions → runbook draft created with Jinja2 variables
- Blocklist violation: command containing blocked pattern → `ValueError` raised, no runbook created
- Insufficient sessions: 1 session → returns empty candidates (below `min_success_count`)
- LLM failure: LLM raises exception → error propagated, no partial runbook saved
- Variable extraction: `"systemctl restart nginx"` → template `"systemctl restart {{ service_name }}"` with `variables_required = ["service_name"]`
- Non-idempotent detection: `rm -rf /tmp/cache` flagged with `requires_human_review = True`
- `approve_draft`: `is_active` set to True, `auto_trigger_enabled` follows input
- `find_generation_candidates`: only clusters with ≥ min_success_count returned

---

## Feature 6: Service Health Score & Topology (A2) — P1

### Goal
Compute composite health scores per application/component and expose topology data for D3.js visualization. Gives operators an instant "is my service healthy?" view with dependency-aware degradation.

### Files to Create
- `app/services/service_health_service.py` — Health score computation
- `app/schemas_health.py` — Schemas
- `app/routers/service_health_api.py` — API endpoints
- `tests/unit/services/test_service_health_service.py` — Tests

### Files to Modify
- `app/main.py` — Register new router

### Schemas (app/schemas_health.py)
```python
class HealthFactor(BaseModel):
    name: str               # "active_alerts", "execution_success", "dependency_health", "change_risk"
    weight: float           # Actual weight used (redistributed if no data)
    score: float            # 0-100 for this factor
    detail: str             # Human-readable explanation

class ServiceHealthScore(BaseModel):
    app_id: UUID
    app_name: str
    score: float                        # 0-100
    status: str                         # "healthy", "degraded", "critical", "unknown"
    factors: List[HealthFactor]
    active_alerts: int
    critical_alerts: int
    computed_at: datetime

class TopologyNode(BaseModel):
    id: str                 # Component UUID as string
    name: str
    type: str               # Component type (web, database, cache, queue, etc.)
    app_id: str
    app_name: str
    health_score: Optional[float]
    health_status: str
    is_hard_dependency: Optional[bool]  # Null for root nodes

class TopologyEdge(BaseModel):
    source: str             # Component UUID
    target: str             # Component UUID
    type: str               # Dependency type
    failure_impact: str     # "hard" (propagates failure) or "soft" (degrades gracefully)

class TopologyGraph(BaseModel):
    nodes: List[TopologyNode]
    edges: List[TopologyEdge]
    computed_at: datetime

class ApplicationHealthListResponse(BaseModel):
    items: List[ServiceHealthScore]
    total: int
```

### Service: ServiceHealthService

**Method: `calculate_health(app_id: UUID, db: AsyncSession) -> ServiceHealthScore`**

Factor computation (default weights, redistributed when data unavailable):

**Factor 1 — Active Alerts (default weight 40%)**
- Query `Alert` where `app_id = app_id` and `status = 'firing'`
- Severity penalties: critical → -40 pts, warning → -15 pts, info → -5 pts
- Score = max(0, 100 + Σ penalties)
- If no alerts ever exist for this app: weight = 0, redistribute to other factors

**Factor 2 — Execution Success (default weight 25%)**
- Call `EffectivenessService.get_app_success_rate(app_id)` for recent executions
- Score = success_rate × 100
- If no executions exist: weight = 0, redistribute

**Factor 3 — Dependency Health (default weight 20%)**
- Query `ComponentDependency` for all components of `app_id`
- BFS traversal of dependency graph with cycle detection (track visited set)
- Classify each dependency edge: `failure_impact = "hard"` or `"soft"` from `ComponentDependency.failure_impact` field
- Hard dependency: if dependency score < 30 → force parent score to critical (≤20)
- Soft dependency: if dependency score < 50 → reduce parent score by 15%
- Average dependent health scores (weighted by failure_impact)
- If no dependencies exist: weight = 0, redistribute

**Factor 4 — Change Risk (default weight 15%)**
- Query recent `ChangeImpactAnalysis` records via `ChangeImpactService`
- Score = 100 - (avg_correlation_score × 100) — higher change correlation = higher risk = lower score
- If no recent changes: weight = 0, redistribute

**Weight redistribution when factors have no data:**
```python
available_factors = [f for f in factors if f.has_data]
total_available_weight = sum(f.default_weight for f in available_factors)
for f in available_factors:
    f.actual_weight = f.default_weight / total_available_weight
```

**Status thresholds:**
- 80-100: `"healthy"`
- 50-79: `"degraded"`
- 0-49: `"critical"`
- No data at all: `"unknown"`

**Method: `get_topology(app_id: Optional[UUID], db: AsyncSession) -> TopologyGraph`**

1. Query `ApplicationComponent` (optionally filtered by `app_id`)
2. Query `ComponentDependency` for all components
3. For each component node, call `calculate_health()` for its parent app (cache results by app_id to avoid repeated computation)
4. Return D3.js-compatible `TopologyGraph`:
   - Nodes: one per `ApplicationComponent`
   - Edges: one per `ComponentDependency` with `failure_impact` type

### Router: /api/health/ (app/routers/service_health_api.py)
- `GET /api/health/applications` — All apps with health scores (paginated), auth: `get_current_user`
- `GET /api/health/applications/{id}` — Detailed health breakdown with per-factor scores, auth: `get_current_user`
- `GET /api/health/topology` — Full topology graph, auth: `get_current_user`
- `GET /api/health/topology/{app_id}` — App-specific topology (includes dependencies), auth: `get_current_user`

### Tests (test_service_health_service.py)
- Healthy app: no firing alerts, recent successful executions → score ≥ 80, status "healthy"
- Degraded app: some warning alerts → score 50-79, status "degraded"
- Critical app: critical alert firing → score < 50, status "critical"
- Hard dependency cascade: dependency with score < 30 → parent forced to critical
- Soft dependency cascade: dependency with score < 50 → parent score reduced by 15%
- Circular dependencies: BFS cycle detection prevents infinite loop
- Weight redistribution: when 2 factors have no data, remaining 2 factors share 100% of weight
- Isolated component: no dependencies → factor 3 weight = 0, redistributed
- Unknown status: app exists but no data of any kind → status = "unknown"
- Topology: nodes and edges returned in D3.js format with correct health colors

---

## Deliverables for Phase 3
After implementing both features, verify:
- [ ] `pytest tests/unit/services/test_runbook_generation_service.py -v` passes
- [ ] `pytest tests/unit/services/test_service_health_service.py -v` passes
- [ ] `app/services/runbook_generation_service.py` created with CommandBlocklist validation
- [ ] `app/services/service_health_service.py` created with cycle detection
- [ ] Topology endpoint returns D3.js-compatible JSON
- [ ] Both new routers registered in `app/main.py`
- [ ] Auto-generated runbooks have `is_active = False` until approved

**When Phase 3 is complete, proceed to: `docs/feature_prompts/phase4_feature_7_oncall.md`**
