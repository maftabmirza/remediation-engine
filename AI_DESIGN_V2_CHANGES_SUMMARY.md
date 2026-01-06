# Design v2.0 Changes Summary

**Document:** AI_MULTIPLE_SOLUTIONS_RUNBOOK_DESIGN_V2.md
**Previous Version:** AI_MULTIPLE_SOLUTIONS_RUNBOOK_DESIGN.md
**Date:** 2026-01-06

---

## Overview

This document summarizes the key changes made to the Multiple Solutions & Runbook-First Integration design based on technical feedback from code review.

---

## Critical Changes

### 1. Security - AI Helper Does NOT Execute Runbooks

**v1.0 Issue:**
- Design suggested AI Helper could execute runbooks directly
- Showed `[▶️ Execute Runbook]` buttons in response
- Conflicted with security policy: `execute_runbook` is in `BLOCKED_ACTIONS`

**v2.0 Fix:**
- **AI Helper only RECOMMENDS runbooks, never executes**
- Markdown links to runbook detail pages: `[Runbook #45](/remediation/runbooks/45)`
- User must click through, review, and execute via existing runbook approval flow
- RBAC/ACL checks show permission status: "✅ You can execute" or "🔒 Requires: ops-team"
- Existing runbook system handles execution with full approval workflow

**Impact:**
- Maintains security policy compliance
- Respects RBAC/ACL enforcement
- Clear separation: AI advises, user executes
- Audit trail: recommendations logged separately from executions

---

### 2. Data Model Simplification

**v1.0 Issue:**
- Proposed new `runbook_embeddings` table (unnecessary duplication)
- Proposed new `troubleshooting_solution_feedback` table (premature)

**v2.0 Fix:**

#### Runbook Embeddings - Add Column, Not New Table
```sql
-- v1.0 (WRONG - new table)
CREATE TABLE runbook_embeddings (
  runbook_id UUID,
  embedding vector(1536),
  ...
);

-- v2.0 (CORRECT - add column)
ALTER TABLE runbooks ADD COLUMN embedding vector(1536);
CREATE INDEX runbooks_embedding_idx ON runbooks USING ivfflat (embedding vector_cosine_ops);
```

**Reasoning:** Embeddings are 1:1 with runbooks. No need for separate table unless we need multiple embeddings per runbook (versioning - future phase).

#### Feedback Tracking - Use Existing Audit Table
```json
// v1.0 (WRONG - new table)
CREATE TABLE troubleshooting_solution_feedback (...);

// v2.0 (CORRECT - use existing JSONB fields)
ai_helper_audit_logs.ai_action_details = {
  "solutions_presented": [
    {"solution_id": "...", "type": "runbook", "confidence": 0.95, "rank": 1},
    {"solution_id": "...", "type": "manual", "confidence": 0.85, "rank": 2}
  ]
}

ai_helper_audit_logs.user_modifications = {
  "solution_chosen_id": "...",
  "solution_chosen_rank": 1,
  "time_to_decision_seconds": 45
}
```

**Reasoning:** Existing table has all needed fields (timestamp, user_action, user_feedback, execution_result). Only create new table if we need complex analytics later.

**Impact:**
- Minimal DB migration (1 column + 1 index)
- No schema bloat
- Leverages existing audit infrastructure
- Easier to query and maintain

---

### 3. Response Format - Markdown Only

**v1.0 Issue:**
- Showed fancy UI mockups with interactive buttons
- `[▶️ Execute Runbook]`, `[📋 Copy Commands]`, `[👁️ Show Details]`
- Widget actually renders markdown via `marked.parse()` - no support for buttons

**v2.0 Fix:**

#### Markdown-Only Response Format
```markdown
## Recommended Solutions

### Option 1: Automated Runbook (Recommended)
**[Runbook #45: Apache High CPU Fix](/remediation/runbooks/45)**
Confidence: ⭐⭐⭐ 95% | Success: 100% | Time: 5 min
Permission: ✅ You can execute

**Description:** Gracefully restarts Apache with traffic drain...

---

### Option 2: Manual Service Restart
Confidence: ⭐⭐ 85% | Success: 90% | Time: 3 min

**Commands:**
```bash
sudo systemctl restart apache2
sudo systemctl status apache2
```

---

### Related Documentation
- [Apache Performance Guide](/knowledge/docs/apache-tuning)
```

**UI Elements Changed:**
| v1.0 (Wrong)                   | v2.0 (Correct)                     |
|--------------------------------|------------------------------------|
| `[▶️ Execute]` button          | `[Runbook #45](url)` markdown link |
| `[📋 Copy]` button             | Code blocks (users copy naturally) |
| `[👁️ Show Details]` expander  | All details inline or via links    |
| Progress bars for confidence   | Simple star ratings (⭐⭐⭐)        |
| Badge UI for permissions       | Text: "✅ You can execute"         |

**Impact:**
- Works with existing widget rendering (marked.parse())
- No frontend changes needed
- Clean, accessible markdown
- Users can copy commands naturally from code blocks

---

### 4. Architecture - Deterministic Pipeline

**v1.0 Issue:**
- LLM decides which solution to recommend
- Could fight the ranking algorithm
- Non-deterministic decision-making

**v2.0 Fix:**

#### Deterministic Pipeline
```
Search (deterministic):
  → Runbook Search (vector similarity)
  → Manual Search (future)
  → Knowledge Search

Rank (deterministic):
  → Weighted scoring algorithm
  → Context matching
  → Success rate integration
  → Decision matrix application

LLM Format (only formatting):
  → Take pre-ranked solutions
  → Format into markdown
  → NO re-ranking or decision-making
```

**Enhanced System Prompt:**
```
SOLUTION PRESENTATION:

When context includes 'ranked_solutions':
  - You have been provided with pre-ranked solutions
  - DO NOT re-rank or re-decide - use the ranking provided
  - Your job is to FORMAT these solutions into markdown
  - Follow the presentation_strategy from ranked_solutions
```

**Impact:**
- Consistent ranking (not LLM-dependent)
- Faster (LLM only formats, doesn't decide)
- Testable (deterministic ranking logic)
- Avoids LLM fighting the ranker

---

### 5. Concrete Integration Points

**v1.0 Issue:**
- Generic descriptions: "integrate with orchestrator"
- No specific function names or file paths

**v2.0 Fix:**

#### Function-Level Mapping

**File:** `app/services/ai_helper_orchestrator.py`
**Function:** `_assemble_context()` (Lines ~249-297)

```python
async def _assemble_context(self, query, page_context, session_id):
    # Existing knowledge search (lines 272-284)
    knowledge_results = self.knowledge_service.search_similar(...)

    # NEW: Add runbook search
    if self._is_troubleshooting_query(query, page_context):
        runbook_search_service = RunbookSearchService(self.db)
        runbook_results = await runbook_search_service.search_runbooks(...)

        # NEW: Rank and combine
        solution_ranker = SolutionRanker(self.db)
        ranked_solutions = solution_ranker.rank_and_combine_solutions(...)

        context['ranked_solutions'] = ranked_solutions

    return context
```

**New Files to Create:**
1. `app/services/runbook_search_service.py` (~200 lines)
   - `search_runbooks()` - semantic search
   - `calculate_runbook_score()` - weighted scoring
   - `get_success_rate()` - from runbook_executions

2. `app/services/solution_ranker.py` (~150 lines)
   - `rank_and_combine_solutions()` - merge runbook + manual
   - `determine_presentation_strategy()` - decision matrix
   - `apply_automation_bonus()` - +0.15 for runbooks

3. `alembic/versions/XXX_add_embedding_to_runbooks.py` (~30 lines)
   - Migration for embedding column + index

**Files to Modify:**
1. `app/services/ai_helper_orchestrator.py`:
   - `_assemble_context()` - add runbook search (~20 lines)
   - `_is_troubleshooting_query()` - new method (~15 lines)
   - `_call_llm()` - enhance system prompt (~30 lines)

2. `app/models_remediation.py`:
   - Add `embedding` column to `Runbook` model (~2 lines)

**Impact:**
- Clear implementation roadmap
- Minimal code changes
- Easy to review and estimate
- Backwards compatible

---

### 6. Minimal DB Migration

**v1.0 Issue:**
- Multiple new tables
- Complex schema changes

**v2.0 Fix:**

#### Single Migration for Phase 1
```sql
-- Add vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to runbooks
ALTER TABLE runbooks ADD COLUMN embedding vector(1536);

-- Create vector index
CREATE INDEX runbooks_embedding_idx
ON runbooks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Add index for enabled runbooks
CREATE INDEX idx_runbooks_enabled_embedding
ON runbooks (enabled)
WHERE embedding IS NOT NULL;
```

**That's it!** No new tables in Phase 1.

**Impact:**
- Minimal migration risk
- Fast to apply (adds column + indexes)
- Reversible (downgrade drops column)
- No data migration needed

---

### 7. Context Filtering Logic

**v1.0 Issue:**
- Generic "context-aware search" description
- No concrete filtering logic

**v2.0 Fix:**

#### Concrete Context Filters

**From Runbook Model:**
```python
class Runbook:
    target_os_filter = Column(ARRAY(String), default=["linux", "windows"])
    tags = Column(ARRAY(String), default=[])  # ["apache", "web-server", "production"]
```

**Search Query with Filters:**
```python
results = db.query(Runbook).filter(
    Runbook.enabled == True,
    Runbook.embedding.cosine_distance(embedding) < 0.5,  # Similarity threshold
    Runbook.target_os_filter.contains([context.get('os', 'linux')]),
    # Optional: filter by tags if available
).all()
```

**Context Match Scoring:**
```python
context_match = 0
if context.get('server_type') in (runbook.tags or []):
    context_match += 0.5  # Server type match
if context.get('application') in (runbook.tags or []):
    context_match += 0.3  # Application match
if context.get('environment') in (runbook.tags or []):
    context_match += 0.2  # Environment match
context_match = min(context_match, 1.0)  # Cap at 1.0
```

**Impact:**
- Uses existing runbook fields (target_os_filter, tags)
- No new columns needed
- Fast filtering (indexed fields)
- Clear scoring logic

---

## Summary of Key Improvements

| Aspect                    | v1.0 Issue                          | v2.0 Solution                        |
|---------------------------|-------------------------------------|--------------------------------------|
| **Security**              | AI executes runbooks                | AI recommends only, user executes    |
| **Data Model**            | 2 new tables                        | 1 column added to existing table     |
| **Response Format**       | Interactive buttons/cards           | Markdown links and code blocks       |
| **Architecture**          | LLM decides solutions               | Deterministic pipeline, LLM formats  |
| **Integration**           | Generic descriptions                | Function-level mapping               |
| **DB Migration**          | Complex multi-table schema          | Single migration (1 column + index)  |
| **Context Filtering**     | Vague "multi-dimensional"           | Concrete SQL filters + scoring       |
| **RBAC Integration**      | Unclear permission model            | Explicit view vs execute checks      |
| **Feedback Tracking**     | New table proposed                  | Use existing audit_logs JSONB fields |
| **Performance**           | Unclear optimization strategy       | Concrete query optimization + caching|

---

## What Stayed the Same

✅ **Core Concepts:**
- Runbook-first strategy (prioritize automated solutions)
- Multiple option presentation (2-3 ranked solutions)
- User choice tracking and learning
- Context-aware filtering
- Hybrid feedback model (explicit + implicit)

✅ **Goals:**
- Increase runbook utilization
- Improve user satisfaction
- Learn from user choices
- Reduce time to resolution

✅ **Success Metrics:**
- Solution acceptance rate > 70%
- Runbook utilization > 50%
- First-choice accuracy > 60%
- User satisfaction > 80%

---

## Migration Path from v1.0 to v2.0

If you started implementing v1.0, here's how to migrate to v2.0:

### 1. Data Model Changes

**If you created `runbook_embeddings` table:**
```sql
-- Copy embeddings back to runbooks table
ALTER TABLE runbooks ADD COLUMN embedding vector(1536);

UPDATE runbooks r
SET embedding = re.embedding
FROM runbook_embeddings re
WHERE r.id = re.runbook_id;

-- Drop the separate table
DROP TABLE runbook_embeddings;
```

**If you created `troubleshooting_solution_feedback` table:**
```sql
-- Migrate data to ai_helper_audit_logs JSONB fields
UPDATE ai_helper_audit_logs al
SET
    ai_action_details = jsonb_set(
        COALESCE(ai_action_details, '{}'::jsonb),
        '{solutions_presented}',
        tsf.solutions_presented
    ),
    user_modifications = jsonb_set(
        COALESCE(user_modifications, '{}'::jsonb),
        '{solution_chosen_id}',
        to_jsonb(tsf.solution_chosen_id::text)
    )
FROM troubleshooting_solution_feedback tsf
WHERE al.id = tsf.query_id;

-- Drop the separate table
DROP TABLE troubleshooting_solution_feedback;
```

### 2. Code Changes

**Update orchestrator to use deterministic pipeline:**
```python
# Remove LLM decision-making
- response = await llm_decide_best_solution(solutions)

# Add deterministic ranking
+ ranked_solutions = solution_ranker.rank_and_combine_solutions(...)
+ response = await llm_format_solutions(ranked_solutions)
```

**Update response formatter for markdown:**
```python
# Remove button generation
- return f"<button onclick='execute({id})'>Execute</button>"

# Add markdown links
+ return f"**[Runbook #{id}: {name}]({url})**"
```

### 3. Testing Changes

**Update tests to verify:**
- AI Helper does NOT call execute_runbook API
- Responses are valid markdown (no HTML buttons)
- JSONB fields are populated correctly in audit_logs
- Ranking is deterministic (same input = same output)
- RBAC permission status displayed correctly

---

## Next Steps

1. **Review v2.0 design document:** `AI_MULTIPLE_SOLUTIONS_RUNBOOK_DESIGN_V2.md`
2. **Approve changes:** Confirm alignment with project constraints
3. **Begin Phase 1 implementation:**
   - DB migration (add embedding column)
   - RunbookSearchService implementation
   - SolutionRanker implementation
   - Orchestrator integration
4. **Test with real data:**
   - Generate embeddings for existing runbooks
   - Test semantic search accuracy
   - Measure search latency
   - Validate RBAC filtering

---

**Document Status:** Ready for Review
**Related Documents:**
- `AI_MULTIPLE_SOLUTIONS_RUNBOOK_DESIGN_V2.md` (Full design)
- `AI_MULTIPLE_SOLUTIONS_RUNBOOK_DESIGN.md` (Original v1.0)
- `app/services/ai_helper_orchestrator.py` (Current implementation)
- `app/models_remediation.py` (Runbook models)
- `app/models_ai_helper.py` (Audit log models)
