# Troubleshooting Session Learning for Future Reference - High-Level Plan

**Date:** 2026-01-06
**Status:** High-Level Planning (No Implementation)
**Context:** Question from user about learning from troubleshooting sessions

---

## Question

> Are we considering troubleshooting session learning for future reference? If yes, how? If no, why not?

## Answer: YES - Phase 4 Integration

**We ARE considering troubleshooting session learning**, but it's designed as **Phase 4** (after runbook-first integration is complete).

---

## Why Phase 4 (Not Phase 1-2)?

### Strategic Sequencing

**Phase 1-2:** Runbook-first (automated solutions)
- Runbooks have: Known success rates, structured steps, version control
- Easier to search, rank, and recommend
- Lower risk (approved by ops team)
- Immediate ROI (automate common incidents)

**Phase 3:** Feedback loop
- Learn which runbooks users prefer
- Track runbook effectiveness
- Build confidence in AI recommendations

**Phase 4:** Troubleshooting history (manual solutions)
- Manual solutions are: Ad-hoc commands, contextual, less structured
- Harder to generalize (works for one server, may not work for another)
- Higher risk (unvalidated by ops team)
- Requires Phase 1-3 infrastructure (semantic search, ranking, feedback)

**Why this order makes sense:**
1. Build trust with AI (start with safe, known solutions)
2. Establish search and ranking infrastructure (reusable for manual solutions)
3. Collect feedback data (learn what works before suggesting experimental solutions)
4. Then add manual solutions (with confidence scoring based on historical success)

---

## What is Troubleshooting Session Learning?

### Definition

**Troubleshooting Session Learning** means:
- Capturing manual troubleshooting sessions (commands, analysis, resolution)
- Storing them in a searchable knowledge base
- Recommending past solutions for similar future incidents
- Learning which manual approaches work best over time

### Example Scenario

**Incident 1:** User investigates "MySQL slow queries on db-prod-01"
```bash
# Commands user ran:
SHOW PROCESSLIST;
SHOW ENGINE INNODB STATUS;
ANALYZE TABLE orders;
ALTER TABLE orders ADD INDEX idx_created_at (created_at);

# Resolution: Adding index fixed slow queries
# Success: ✅ Query time reduced from 5s to 50ms
```

**Incident 2 (3 months later):** New user sees "MySQL slow queries on db-prod-02"

**AI Helper suggests:**
> "I found a similar incident from 3 months ago where adding an index resolved slow queries on the `orders` table.
>
> **Past solution (90% confidence):**
> 1. Check current query performance: `SHOW PROCESSLIST`
> 2. Analyze table: `ANALYZE TABLE orders`
> 3. Add missing index: `ALTER TABLE orders ADD INDEX idx_created_at (created_at)`
>
> **Context match:** Same database (MySQL), same table (orders), same symptom (slow queries)
> **Success rate:** Worked in 9/10 similar cases
>
> **Alternative:** [Runbook #34: MySQL Query Optimization](/runbooks/34)"

---

## High-Level Design (Phase 4)

### 1. Data Capture Strategy

**What to Capture:**
- Troubleshooting session metadata:
  - Alert/incident that triggered session
  - User who resolved it
  - Timestamp (start → resolution)
  - Server/application context
  - Final outcome (success, partial, failed)

- Commands executed:
  - Full command text
  - Command output (truncated to 1000 chars)
  - Exit code
  - Execution order (step 1, step 2, ...)

- Resolution summary:
  - Root cause identified
  - Solution applied (commands or config changes)
  - Validation steps (how to confirm fix)
  - Lessons learned (optional user input)

**Where to Store:**
```
troubleshooting_sessions (table):
  - id (UUID)
  - alert_id (FK to alerts)
  - user_id (FK to users)
  - server_id (FK to servers)
  - started_at, resolved_at
  - outcome (success, partial_success, failed, abandoned)
  - root_cause (text)
  - resolution_summary (text)
  - tags (ARRAY: ['mysql', 'slow-query', 'indexing'])
  - embedding (vector 1536) -- for semantic search
  - created_at, updated_at

troubleshooting_steps (table):
  - id (UUID)
  - session_id (FK to troubleshooting_sessions)
  - step_order (integer)
  - command_text (text)
  - command_output (text, truncated)
  - exit_code (integer)
  - step_type (diagnostic, remediation, validation)
  - notes (text, optional user annotation)
  - executed_at (timestamp)
```

**How to Capture:**
Two approaches:

**Option A: Manual Entry (Phase 4a - simpler)**
- After resolving incident, user clicks "Save as troubleshooting case"
- Form pre-filled with AI chat history (commands + outputs)
- User edits/annotates, adds resolution summary
- Saved to database with embeddings

**Option B: Automatic Capture (Phase 4b - advanced)**
- AI Helper tracks all commands executed in chat session
- Detects resolution (user says "fixed", alert clears, user gives thumbs up)
- Auto-creates troubleshooting case draft
- User reviews and approves (or discards)

---

### 2. Semantic Search Integration

**Same Infrastructure as Runbooks:**

```
User Query: "MySQL slow queries on db-prod-02"
    ↓
Parallel Search:
    ├─→ Runbook Search (existing, Phase 1)
    ├─→ Troubleshooting Session Search (NEW, Phase 4)
    └─→ Knowledge Base Search (existing)
    ↓
Unified Ranking:
    1. Runbook #34: MySQL Query Optimization (confidence: 0.95, automated)
    2. Session #456: Similar slow query fix (confidence: 0.85, manual)
    3. Session #789: Index tuning approach (confidence: 0.78, manual)
    ↓
Present to User (markdown):
    ## Recommended Solutions

    ### Option 1: Automated Runbook ⭐⭐⭐
    [Runbook #34: MySQL Optimization](/runbooks/34)
    Success: 100% | Time: 10 min | Automated

    ### Option 2: Past Manual Solution ⭐⭐
    **Similar Incident (3 months ago):**
    User @alice resolved "slow queries on orders table" by adding index.

    **Commands used:**
    ```sql
    ANALYZE TABLE orders;
    ALTER TABLE orders ADD INDEX idx_created_at (created_at);
    ```

    **Success rate:** 90% (9/10 similar cases)
    **Context:** MySQL 8.0, orders table, missing index
    [View full session](/troubleshooting/sessions/456)
```

**Ranking Logic:**
```python
# In solution_ranker.py (Phase 4 enhancement)

for session in troubleshooting_sessions:
    score = (
        semantic_similarity * 0.5 +      # How similar is the query?
        success_rate * 0.3 +             # How often does this solution work?
        context_match * 0.2              # Same DB, OS, app?
    )

    # Automation penalty (manual < automated)
    # Runbooks get +0.15, manual solutions get +0.00
    # This ensures runbooks rank higher by default

    confidence = score  # No bonus for manual solutions
```

**Key Difference from Runbooks:**
- Runbooks: +0.15 automation bonus (preferred)
- Manual solutions: +0.00 bonus (fallback when no runbook exists)

---

### 3. Learning from Success/Failure

**Feedback Loop:**

After user tries a manual solution:
1. Track execution result (success/failed)
2. Update `success_rate` for that troubleshooting session
3. Adjust confidence scores for future recommendations

```
Example:
- Session #456 recommended 10 times
- Successful resolution: 9 times
- Failed resolution: 1 time
- Success rate: 90%

Next time:
- Confidence starts at: base_semantic_similarity * 0.5 + 0.9 * 0.3 + context * 0.2
- If success rate drops to 70%, confidence decreases proportionally
- If success rate climbs to 95%, confidence increases
```

**Feedback Collection:**
```markdown
## Did this solution work?

👍 Yes, problem resolved
👎 No, tried different approach
🤔 Partially worked
💬 Add comment (optional)
```

**Feedback Storage:**
```
troubleshooting_feedback (table):
  - id (UUID)
  - session_id (FK to troubleshooting_sessions - the original session)
  - recommended_to_user_id (FK to users - who got the recommendation)
  - recommended_at (timestamp)
  - user_tried (boolean - did they try it?)
  - outcome (success, failed, partial, abandoned)
  - user_comment (text, optional)
  - created_at (timestamp)
```

**Learning Algorithm (Background Job):**
```python
# Runs daily to update success rates

def update_session_success_rates():
    for session in troubleshooting_sessions:
        feedback = get_feedback_for_session(session.id)

        if len(feedback) >= 3:  # Minimum 3 data points
            success_count = len([f for f in feedback if f.outcome == 'success'])
            total_count = len(feedback)
            session.success_rate = success_count / total_count

            # If success rate < 50%, mark as deprecated
            if session.success_rate < 0.5:
                session.deprecated = True
                session.deprecated_reason = "Low success rate in recent usage"

        db.commit()
```

---

### 4. Context-Aware Matching

**Problem:** Manual solutions are highly contextual.
- "Restart Apache" works on Ubuntu, not Docker containers
- "Add index to orders table" assumes orders table exists
- "Increase max_connections" may not apply to RDS (different config)

**Solution:** Strict context filtering

```python
def search_troubleshooting_sessions(query, context):
    # Base semantic search
    results = vector_search(query)

    # Apply strict context filters
    filtered = []
    for session in results:
        # Must match OS (if known)
        if context.get('os') and session.server_os != context['os']:
            continue

        # Must match application (if known)
        if context.get('application') and session.application != context['application']:
            continue

        # Must match environment type (prod, staging, dev)
        # Don't recommend prod solutions for dev environments (may be too aggressive)
        if context.get('environment') and session.environment != context['environment']:
            continue

        # Semantic similarity threshold (higher than runbooks)
        if session.similarity_score < 0.7:  # Runbooks use 0.5, manual uses 0.7
            continue

        filtered.append(session)

    return filtered[:5]  # Top 5 matches
```

**Why stricter filtering?**
- Runbooks are tested and approved → safe to recommend with lower similarity
- Manual solutions are ad-hoc → only recommend if very similar context

---

### 5. Runbook Suggestion from Manual Solutions

**Cross-Learning:** If a manual solution is used frequently, suggest creating a runbook.

**Logic:**
```python
# Background job: Identify manual solutions worthy of automation

def suggest_runbook_creation():
    # Find frequently-used manual solutions
    popular_sessions = db.query(TroubleshootingSession).filter(
        TroubleshootingSession.recommended_count >= 5,    # Recommended 5+ times
        TroubleshootingSession.success_rate >= 0.8,      # 80%+ success rate
        TroubleshootingSession.runbook_created == False  # No runbook yet
    ).all()

    for session in popular_sessions:
        # Create notification for ops team
        create_notification(
            type='runbook_suggestion',
            title=f'Consider automating: {session.resolution_summary}',
            message=f'''
            This manual solution has been used {session.recommended_count} times
            with {session.success_rate*100}% success rate.

            Consider creating a runbook to automate this common task.

            [View session](/troubleshooting/sessions/{session.id})
            [Create runbook](/runbooks/new?from_session={session.id})
            ''',
            severity='info'
        )
```

**Runbook Creation Wizard:**
```
User clicks "Create runbook" from troubleshooting session
    ↓
Wizard pre-fills:
    - Name: "Fix slow queries on orders table (indexing)"
    - Description: From session.resolution_summary
    - Steps: Auto-generated from session.steps (commands + validation)
    - Target OS: From session.server_os
    - Tags: From session.tags
    ↓
User reviews, edits, adds approval settings
    ↓
Runbook created and linked to original session
    ↓
Future recommendations: Runbook replaces manual session
```

**Lifecycle:**
```
Manual Solution (Phase 4)
    ↓ (used 10+ times successfully)
Suggested for Automation
    ↓ (ops team creates runbook)
Automated Runbook (Phase 1)
    ↓ (replaces manual solution in rankings)
Future Recommendations: Runbook-first
```

---

### 6. Privacy and Compliance

**Considerations:**

1. **Command Sanitization:**
   - Strip sensitive data from commands (passwords, tokens, API keys)
   - Regex patterns: `password=\S+`, `token=\S+`, `--key \S+`
   - Store sanitized versions only

2. **Output Truncation:**
   - Limit command output to 1000 characters
   - Avoid capturing sensitive data (customer PII, secrets)
   - Allow users to redact before saving

3. **User Consent:**
   - Opt-in for session tracking: "Save this session for future reference?"
   - Default: OFF (manual save only)
   - Org-wide setting: Enable automatic capture (with admin approval)

4. **Access Control:**
   - Troubleshooting sessions inherit permissions from alert/server
   - If user can't access alert, can't see troubleshooting session
   - Filter search results by user permissions

---

## Implementation Roadmap

### Phase 4a: Manual Session Capture (Weeks 1-3)

**Goal:** Allow users to manually save successful troubleshooting sessions

**Tasks:**
1. Create database schema (troubleshooting_sessions, troubleshooting_steps)
2. Add "Save as troubleshooting case" button to AI chat
3. Build session capture form (pre-fill from chat history)
4. Generate embeddings for saved sessions
5. Test semantic search with manual sessions

**Success Criteria:**
- Users can save troubleshooting sessions
- Sessions are searchable via semantic search
- Basic ranking works (semantic similarity + context match)

---

### Phase 4b: Automated Search Integration (Weeks 4-6)

**Goal:** Recommend manual solutions alongside runbooks

**Tasks:**
1. Integrate session search into `ai_helper_orchestrator`
2. Update `solution_ranker` to include manual solutions
3. Format manual solutions in markdown responses
4. Add context filtering (OS, app, environment)
5. Test end-to-end recommendation flow

**Success Criteria:**
- AI Helper recommends manual solutions when no runbook exists
- Runbooks still rank higher (automation bonus)
- Context filtering prevents mismatched recommendations

---

### Phase 4c: Feedback Loop (Weeks 7-9)

**Goal:** Learn which manual solutions work over time

**Tasks:**
1. Add feedback UI ("Did this work?")
2. Track solution execution results
3. Calculate success rates from feedback
4. Update confidence scores based on success rates
5. Deprecate low-performing solutions

**Success Criteria:**
- Success rates update based on user feedback
- Confidence scores reflect real-world performance
- Low-performing solutions hidden from recommendations

---

### Phase 4d: Runbook Suggestion (Weeks 10-12)

**Goal:** Suggest creating runbooks from popular manual solutions

**Tasks:**
1. Background job to identify automation candidates
2. Notification system for ops team
3. Runbook creation wizard (pre-fill from session)
4. Link runbooks to source sessions
5. Measure runbook creation rate

**Success Criteria:**
- Ops team receives automation suggestions
- 20%+ of suggestions convert to runbooks
- Manual solutions gradually replaced by runbooks

---

## Why This Approach Works

### 1. Runbook-First Maintains Safety
- Start with known, approved solutions (runbooks)
- Add manual solutions as fallback (when no runbook exists)
- Gradually automate popular manual solutions
- **Result:** Safety + completeness

### 2. Reuses Existing Infrastructure
- Same semantic search (pgvector)
- Same ranking algorithm (weighted scoring)
- Same feedback loop (user choice tracking)
- **Result:** Minimal new code

### 3. Enables Continuous Improvement
- Manual solutions → Feedback → Runbooks → More automation
- Confidence scores improve over time
- Knowledge base grows organically
- **Result:** Self-improving system

### 4. Respects Context
- Strict filtering prevents mismatched solutions
- Context-aware ranking (OS, app, environment)
- Success rate reflects real-world applicability
- **Result:** High-quality recommendations

---

## Metrics to Track (Phase 4)

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Sessions Captured** | 10+ per week | `COUNT(*) FROM troubleshooting_sessions WHERE created_at > NOW() - INTERVAL '7 days'` |
| **Manual Solution Usage** | 30% of recommendations | `COUNT(*) WHERE solution_type='manual' / COUNT(*)` |
| **Manual Solution Success Rate** | > 70% | `AVG(success_rate) FROM troubleshooting_sessions WHERE recommended_count > 0` |
| **Runbook Creation from Sessions** | 5+ per month | `COUNT(*) FROM runbooks WHERE source='session' AND created_at > NOW() - INTERVAL '30 days'` |
| **Context Match Accuracy** | > 80% | `COUNT(*) WHERE context_matched=true / COUNT(*)` |

---

## Risks and Mitigation

### Risk 1: Manual Solutions Don't Work in Different Contexts

**Mitigation:**
- Strict context filtering (OS, app, environment must match)
- Higher similarity threshold (0.7 vs 0.5 for runbooks)
- Clear context display: "This worked on Ubuntu 20.04 + MySQL 8.0"
- User feedback deprecates low-performing solutions

---

### Risk 2: Sensitive Data Leakage (Commands/Outputs)

**Mitigation:**
- Sanitize commands before storing (regex for passwords, tokens)
- Truncate outputs to 1000 chars
- Opt-in for session capture (not automatic by default)
- User review before saving (can redact sensitive parts)

---

### Risk 3: Manual Solutions Become Stale (Software Updates)

**Mitigation:**
- Track last_used_at timestamp
- Deprecate sessions not used in 6+ months
- Show age in recommendations: "This solution is 8 months old"
- Success rate naturally drops if solution no longer works

---

### Risk 4: Users Create Runbooks Manually (Don't Use System)

**Mitigation:**
- Make session capture easy (1-click from chat)
- Show value: "This session has helped 5 other users"
- Gamification: Badge for "Most helpful troubleshooting cases"
- Integrate with runbook wizard (pre-fill from session)

---

## Comparison: Runbooks vs Manual Solutions

| Aspect | Runbooks (Phase 1) | Manual Solutions (Phase 4) |
|--------|-------------------|---------------------------|
| **Structure** | Formal steps, approval required | Ad-hoc commands, user-contributed |
| **Quality** | High (reviewed by ops team) | Variable (depends on contributor) |
| **Automation** | Fully automated execution | Manual copy-paste |
| **Search Confidence** | Higher (automation bonus +0.15) | Lower (no bonus) |
| **Context Sensitivity** | Moderate (designed for common cases) | High (specific to exact context) |
| **Maintenance** | Versioned, updated centrally | Feedback-driven deprecation |
| **Risk** | Low (tested and approved) | Medium (user-contributed) |
| **Coverage** | Narrow (only common incidents) | Broad (includes edge cases) |

**Best Strategy:** Runbook-first, manual solutions as fallback.

---

## Conclusion

### Summary

**YES, we are considering troubleshooting session learning** as **Phase 4** of the AI Helper evolution.

**Why Phase 4?**
1. Build runbook infrastructure first (Phase 1-2)
2. Establish feedback loop (Phase 3)
3. Then add manual solutions (Phase 4) using same infrastructure

**How will it work?**
1. Capture troubleshooting sessions (manual or automatic)
2. Store with embeddings for semantic search
3. Recommend manual solutions when no runbook exists
4. Learn from user feedback (success rates)
5. Suggest automating popular manual solutions as runbooks

**Benefits:**
- Comprehensive coverage (runbooks + manual solutions)
- Continuous improvement (manual → automated)
- Context-aware matching (strict filtering)
- Reuses existing infrastructure (minimal new code)

**Timeline:**
- Phase 1-2: Runbook-first (4-6 weeks) ← Current focus
- Phase 3: Feedback loop (2-3 weeks)
- Phase 4: Manual solutions (12 weeks)
- **Total:** ~6 months to full troubleshooting session learning

---

**Document Status:** High-Level Planning (No Implementation)
**Next Steps:** Complete Phase 1-2 first, then revisit this plan for Phase 4 kickoff
**Related:** AI_MULTIPLE_SOLUTIONS_RUNBOOK_DESIGN_V2.md (Phase 1-3 design)
