# AI Helper: Multiple Solutions & Runbook-First Integration Design (v2.0 - REVISED)

**Version:** 2.0
**Date:** 2026-01-06
**Status:** High-Level Design (Revised per Technical Review)
**Changes:** Aligned with project constraints (RBAC, markdown-only UI, minimal DB changes)

---

## Executive Summary

This document outlines the high-level design for enhancing the AI Helper to:
1. **Present multiple solution options** (2-3) in markdown format instead of suggesting a single command/action
2. **Recommend runbook execution** when automated runbooks exist (AI does NOT execute, only recommends)
3. **Let users choose** the most appropriate solution based on their context and preferences
4. **Integrate with existing runbook approval/execution flow** (respecting RBAC/ACL)

**Key Constraints Addressed:**
- `execute_runbook` is in `BLOCKED_ACTIONS` - AI Helper will RECOMMEND, not execute
- Response UI is markdown-only (rendered via `marked.parse()`) - no interactive buttons
- Prefer using existing tables (`ai_helper_audit_logs`) before creating new ones
- Orchestrator architecture changes must be minimal and backwards-compatible

---

## Problem Statement

### Current Limitations
- AI Helper currently suggests **single commands to execute** without presenting alternatives
- No integration with existing **runbook system** for automated remediation recommendations
- Users have no choice when **multiple valid solutions** exist for the same problem
- No consideration of **user preferences** (automated vs manual, quick fix vs thorough investigation)

### Requirements
- Present **2-3 solution options** when multiple approaches are available (markdown format)
- **Runbook-first approach**: Always check for existing runbooks before suggesting manual commands
- **RBAC/ACL awareness**: Show runbook recommendations with permission status
- **User choice tracking**: Learn which solutions users prefer over time (via existing audit log fields)
- **Context-aware ranking**: Match solutions to specific server types, applications, environments

### Non-Requirements (Out of Scope)
- AI Helper will NOT execute runbooks directly (security policy: `execute_runbook` in `BLOCKED_ACTIONS`)
- AI Helper will NOT bypass existing runbook approval workflows
- No new UI components (works within existing markdown-rendered chat interface)

---

## Design Overview

### Core Principles

1. **Runbook-First Strategy (Recommendation, Not Execution)**
   - Always search for matching runbooks in parallel with manual solutions
   - Prioritize automated solutions in recommendations
   - Provide runbook link with RBAC status (can user execute?)
   - **User must click through to runbook page to execute** (existing approval flow applies)

2. **Multiple Options Presentation (Markdown Format)**
   - Show 2-3 ranked options when confidence scores are similar
   - Present clear trade-offs (time, risk, automation level, success rate)
   - Use markdown formatting (headings, lists, links, code blocks)
   - No interactive buttons in AI chat (markdown links to runbook/docs pages)

3. **Smart Decision Matrix**
   - Auto-select when one solution is clearly superior (confidence > 0.9)
   - Present options when confidence differences are small (< 0.1)
   - Mark solutions as "experimental" when no high-confidence match exists

4. **User-Centric Feedback Loop (Use Existing Audit Tables)**
   - Store `solutions_presented` in `ai_helper_audit_logs.ai_action_details` (JSONB)
   - Track which solution user chose in `user_modifications` (JSONB)
   - Update confidence scores based on selection (async background job)
   - Learn user preferences over time (automated vs manual)

---

## Solution Architecture

### 1. Workflow Integration

```
User Query -> AI Helper Orchestrator
    |
    +--> Parallel Search (Deterministic):
    |    +-> Knowledge Base Search (Design docs, best practices)
    |    +-> Troubleshooting History Search (Past solutions)
    |    +-> Runbook Search (NEW: Automated remediation)
    |
    +--> Solution Ranker & Combiner (Deterministic):
    |    +-> Weighted scoring (semantic + context + success + automation)
    |    +-> Apply decision matrix
    |    +-> Return top 3 solutions with metadata
    |
    +--> LLM Response Formatter (LLM only formats, doesn't decide):
    |    +-> Take ranked solutions (already decided)
    |    +-> Format into markdown response
    |    +-> Include runbook links, commands, context
    |
    +--> Store in audit_logs.ai_action_details:
    |    +-> solutions_presented: [runbook, manual1, manual2]
    |    +-> decision_strategy: "multiple_options|single_recommendation"
    |
    V
User Clicks Runbook Link -> Existing Runbook Page (RBAC check, approval flow)
OR
User Copies Manual Command -> Executes manually
    |
    V
User Action Tracked in audit_logs.user_modifications
    |
    V
Feedback Loop -> Update Confidence Scores (Background Job)
```

**Key Change from v1.0:**
- LLM does NOT decide which solution to recommend (avoids fighting the ranker)
- Deterministic pipeline: Search -> Rank -> LLM formats the ranked results
- LLM only responsible for markdown formatting, not solution selection

### 2. Decision Matrix

```
IF confidence difference < 0.1 (solutions very similar):
   -> Show multiple options (2-3 max)
   -> Let user choose
   -> Track selection for learning

ELSE IF top result confidence > 0.9:
   -> Show top result as primary recommendation
   -> Provide "Other options" section with alternatives
   -> User can expand to see other options

ELSE IF no high-confidence result (all < 0.7):
   -> Show top 2-3 options
   -> Mark as "experimental" or "low confidence"
   -> Request user feedback after execution

ELSE (one clear winner, confidence 0.7-0.9):
   -> Show primary + one alternative
   -> Explain why primary is recommended
```

### 3. Runbook-First Logic (Recommendation Flow)

```
1. Query Received (e.g., "High CPU on Apache server")
   |
2. Parallel Search:
   - Runbook semantic search: "apache cpu high utilization"
   - Manual solution search: Past troubleshooting cases
   |
3. Context Filtering:
   - Server type: Apache web server
   - Application: PHP application
   - OS: Ubuntu 20.04
   - Environment: Production
   |
4. Runbook Match Found?
   YES -> Check RBAC/ACL (can user view/execute?)
   NO -> Show manual solutions only
   |
5. Runbook RBAC Check:
   - Check RunbookACL for user's permission (view vs execute)
   - If user can execute: Show as "Ready to execute"
   - If view-only: Show as "Requires approval from: [roles]"
   - If no access: Filter out from results
   |
6. Confidence Comparison:
   - Runbook confidence: 0.95 (high success rate, context match)
   - Top manual solution confidence: 0.85
   -> Recommend runbook as primary, manual as alternative
   |
7. Response Format (Markdown):
   - Runbook: [Link to runbook page] with permission status
   - Manual: Code blocks with copy-friendly commands
   - Knowledge: Links to related docs
```

**CRITICAL SECURITY NOTES:**
- AI Helper NEVER calls `execute_runbook` API directly (blocked by security policy)
- AI Helper only provides markdown link to runbook page: `/remediation/runbooks/{id}`
- User must click link, review runbook, and trigger execution manually
- Existing runbook approval workflow applies (RBAC, ACL, approval_required, etc.)

---

## Unified Response Structure (Markdown Format)

### Response Format (Markdown - No Interactive Buttons)

**High-Confidence Runbook Available:**

```markdown
## Recommended Solutions

### Option 1: Automated Runbook (Recommended)
**[Runbook #45: Apache High CPU - Graceful Restart](/remediation/runbooks/45)**
Confidence: ⭐⭐⭐ 95% | Success Rate: 100% (45/45) | Est. Time: 5 min
Permission: ✅ You can execute this runbook

**Description:** Gracefully restarts Apache with traffic drain and health check validation.

**Why recommended:** This runbook has a perfect success rate in similar contexts (Apache + Ubuntu + Production).

---

### Option 2: Manual Service Restart
Confidence: ⭐⭐ 85% | Success Rate: 90% (18/20) | Est. Time: 3 min

**Commands:**
```bash
sudo systemctl restart apache2
sudo systemctl status apache2
```

**Context:** Works well for Apache CPU issues on Ubuntu, but lacks health check validation.

---

### Option 3: Memory Configuration Tuning
Confidence: ⭐ 80% | Success Rate: 80% (12/15) | Est. Time: 15 min

**Approach:** Tune `MaxRequestWorkers` and memory limits in Apache config.
**See:** [Apache Performance Tuning Guide](/knowledge/docs/apache-tuning)

---

### Related Documentation
- [Apache Performance Tuning Guide](/knowledge/docs/apache-tuning)
- [Production Server Best Practices](/knowledge/docs/prod-best-practices)

---

**💡 Tip:** The automated runbook is the safest option with proven success. It handles traffic gracefully and validates health.

**⚠️ Note:** All manual commands require sudo privileges.
```

**Multiple Similar Solutions:**

```markdown
## Multiple Solutions Available

I found 3 solutions with similar confidence scores. Choose based on your timeline and risk tolerance:

### 1. Automated Runbook: MySQL Query Cache Tune
**[View Runbook #78](/remediation/runbooks/78)**
Confidence: ⭐⭐⭐ 88% | Success: 95% (20/21) | Time: 8 min
Permission: ✅ Ready to execute

### 2. Manual: Index Optimization
Confidence: ⭐⭐ 85% | Success: 85% (17/20) | Time: 10 min

**Commands:**
```sql
ANALYZE TABLE slow_table;
SHOW INDEX FROM slow_table;
-- Review and add missing indexes
```

### 3. Manual: Restart MySQL Service
Confidence: ⭐⭐ 82% | Success: 90% (18/20) | Time: 2 min

**Commands:**
```bash
sudo systemctl restart mysql
sudo systemctl status mysql
```

**Trade-offs:**
- Option 1: Automated, proven, but takes longer
- Option 2: Investigative, finds root cause, requires SQL knowledge
- Option 3: Quick fix, but doesn't address underlying issue
```

**No High-Confidence Match:**

```markdown
## Experimental Solutions

⚠️ No high-confidence match found. These solutions worked in loosely similar contexts:

### 1. Check Network Interface Stats
Confidence: ⭐ 65% | Limited history (2 similar cases)

**Commands:**
```bash
ip -s link show
netstat -i
dmesg | grep -i network
```

### 2. Review Recent Network Changes
Confidence: ⭐ 62% | Limited history (1 similar case)

**Approach:**
Check recent config changes, review network device logs, contact network team.

---

**📚 Related docs:** [Network Troubleshooting Guide](/knowledge/docs/network-debug)

**🙏 Please provide feedback after trying:** This helps the AI learn for future similar issues.
```

**Key Differences from v1.0:**
- No `[▶️ Execute]` buttons - just markdown links to runbook pages
- No `[📋 Copy]` buttons - users can select and copy from code blocks naturally
- No `[👁️ Show Details]` expanders - all details shown inline or via links
- Simple star ratings (⭐) instead of progress bars
- Permission status as text, not badges
- All navigation via standard markdown links

---

## Component Design

### 1. Runbook Search Service (NEW)

**Purpose:** Semantic search across existing runbooks to find automated solutions

**Implementation Location:** `app/services/runbook_search_service.py` (new file)

**Inputs:**
- User query (natural language)
- Context metadata (server_type, app, OS, environment) from `page_context`
- User permissions (RBAC roles) from current user session

**Outputs:**
- Ranked list of matching runbooks (max 3)
- Confidence scores (semantic similarity + context match)
- Execution metadata (success rate, duration, last run)
- RBAC eligibility (can user view/execute?)

**Search Strategy:**
```python
async def search_runbooks(
    query: str,
    context: Dict[str, Any],
    user: User,
    limit: int = 3
) -> List[RankedRunbook]:
    """
    Semantic search for runbooks matching query and context.

    1. Generate query embedding (same model as knowledge base)
    2. Vector similarity search against runbooks.embedding
    3. Apply context filters (server_type, app, OS, env)
    4. Apply RBAC filter (check RunbookACL)
    5. Rank by: similarity (50%) + success_rate (30%) + context_match (20%)
    6. Return top 3
    """
    # Generate embedding
    embedding = await generate_embedding(query)

    # Vector search with context filters
    results = db.query(Runbook).filter(
        Runbook.enabled == True,
        Runbook.embedding.cosine_distance(embedding) < 0.5,  # Similarity threshold
        Runbook.target_os_filter.contains([context.get('os', 'linux')])
    ).all()

    # Apply RBAC filter
    accessible_runbooks = [
        r for r in results
        if check_runbook_acl(user, r, permission='view')
    ]

    # Rank and score
    ranked = []
    for runbook in accessible_runbooks:
        score = calculate_runbook_score(
            runbook=runbook,
            embedding=embedding,
            context=context,
            user=user
        )
        ranked.append(RankedRunbook(runbook=runbook, score=score))

    # Sort by score and return top 3
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:limit]


def calculate_runbook_score(runbook, embedding, context, user):
    """Calculate weighted confidence score."""
    # Semantic similarity (0-1, 50% weight)
    semantic_sim = 1 - cosine_distance(runbook.embedding, embedding)

    # Success rate from runbook_executions (0-1, 30% weight)
    executions = db.query(RunbookExecution).filter(
        RunbookExecution.runbook_id == runbook.id,
        RunbookExecution.dry_run == False
    ).all()

    if executions:
        success_count = len([e for e in executions if e.status == 'success'])
        success_rate = success_count / len(executions)
    else:
        success_rate = 0.5  # Neutral for new runbooks

    # Context match (0-1, 20% weight)
    context_match = 0
    if context.get('server_type') in (runbook.tags or []):
        context_match += 0.5
    if context.get('application') in (runbook.tags or []):
        context_match += 0.3
    if context.get('environment', 'prod') in (runbook.tags or []):
        context_match += 0.2
    context_match = min(context_match, 1.0)

    # Weighted final score
    final_score = (
        semantic_sim * 0.5 +
        success_rate * 0.3 +
        context_match * 0.2
    )

    # Automation bonus (+0.15 for runbooks vs manual solutions)
    # Applied during ranking with manual solutions

    return final_score
```

### 2. Solution Ranker & Combiner (NEW)

**Purpose:** Combine runbook + manual solutions and rank by confidence, context, success rate

**Implementation Location:** `app/services/solution_ranker.py` (new file)

**Inputs:**
- Runbook search results (0-3 runbooks with scores)
- Manual solution search results (from troubleshooting history - future phase)
- Knowledge base references (from existing knowledge search)
- User context

**Outputs:**
- Unified ranked list (max 3 solutions)
- Primary recommendation (if confidence > 0.9)
- Presentation strategy (single vs multiple options)

**Ranking Algorithm:**
```python
def rank_and_combine_solutions(
    runbooks: List[RankedRunbook],
    manual_solutions: List[RankedManualSolution],  # Future phase
    knowledge_refs: List[KnowledgeChunk],
    user_context: Dict[str, Any]
) -> RankedSolutionList:
    """
    Combine and rank all solution types.

    Returns structured data for LLM to format into markdown.
    """
    all_solutions = []

    # Add runbooks with automation bonus
    for ranked_runbook in runbooks:
        solution = Solution(
            type='runbook',
            id=ranked_runbook.runbook.id,
            title=ranked_runbook.runbook.name,
            description=ranked_runbook.runbook.description,
            confidence=ranked_runbook.score + 0.15,  # Automation bonus
            success_rate=get_success_rate(ranked_runbook.runbook),
            estimated_time_minutes=get_avg_duration(ranked_runbook.runbook),
            permission_status=get_permission_status(user, ranked_runbook.runbook),
            metadata={
                'runbook_id': str(ranked_runbook.runbook.id),
                'url': f'/remediation/runbooks/{ranked_runbook.runbook.id}',
                'automation_level': 'automated'
            }
        )
        all_solutions.append(solution)

    # Add manual solutions (future phase)
    for manual in manual_solutions:
        solution = Solution(
            type='manual',
            id=manual.id,
            title=manual.title,
            description=manual.description,
            confidence=manual.score,  # No automation bonus
            success_rate=manual.success_rate,
            estimated_time_minutes=manual.estimated_time,
            metadata={
                'commands': manual.commands,
                'approach': manual.approach
            }
        )
        all_solutions.append(solution)

    # Sort by confidence (descending)
    all_solutions.sort(key=lambda s: s.confidence, reverse=True)

    # Cap at 1.0
    for sol in all_solutions:
        sol.confidence = min(sol.confidence, 1.0)

    # Apply decision matrix
    strategy = determine_presentation_strategy(all_solutions)

    return RankedSolutionList(
        solutions=all_solutions[:3],  # Top 3
        presentation_strategy=strategy,
        knowledge_refs=knowledge_refs
    )


def determine_presentation_strategy(solutions: List[Solution]) -> str:
    """Apply decision matrix to determine how to present solutions."""
    if not solutions:
        return 'no_solutions'

    if len(solutions) == 1:
        return 'single_solution'

    top_confidence = solutions[0].confidence
    second_confidence = solutions[1].confidence if len(solutions) > 1 else 0

    confidence_diff = top_confidence - second_confidence

    if confidence_diff < 0.1:
        return 'multiple_options'  # Very similar, let user choose
    elif top_confidence > 0.9:
        return 'primary_with_alternatives'  # Clear winner
    elif top_confidence < 0.7:
        return 'experimental_options'  # Low confidence
    else:
        return 'primary_plus_one'  # One clear winner, one backup
```

### 3. Response Generator (UPDATED)

**Purpose:** Format ranked solutions into markdown response

**Implementation Location:** Enhanced LLM prompt in `app/services/ai_helper_orchestrator.py`

**Changes to Orchestrator:**
```python
# In ai_helper_orchestrator.py

async def _assemble_context(
    self,
    query: str,
    page_context: Optional[Dict[str, Any]],
    session_id: UUID
) -> Dict[str, Any]:
    """
    Enhanced context assembly with runbook search.
    """
    context = {
        'query': query,
        'page_context': page_context,
        'knowledge_sources_used': [],
        'knowledge_chunks_used': 0,
        'rag_search_time_ms': 0,
        'session_history': [],
        'runbook_results': [],  # NEW
        'ranked_solutions': None  # NEW
    }

    try:
        # Existing knowledge base search
        knowledge_results = self.knowledge_service.search_similar(...)
        context['knowledge_results'] = knowledge_results

        # NEW: Runbook search (parallel with knowledge search)
        if self._is_troubleshooting_query(query, page_context):
            runbook_search_service = RunbookSearchService(self.db)
            user = self.db.query(User).filter(User.id == user_id).first()

            runbook_results = await runbook_search_service.search_runbooks(
                query=query,
                context=page_context or {},
                user=user,
                limit=3
            )
            context['runbook_results'] = runbook_results

            # NEW: Rank and combine solutions
            solution_ranker = SolutionRanker(self.db)
            ranked_solutions = solution_ranker.rank_and_combine_solutions(
                runbooks=runbook_results,
                manual_solutions=[],  # Future phase
                knowledge_refs=knowledge_results,
                user_context=page_context or {}
            )
            context['ranked_solutions'] = ranked_solutions

        # Get session history
        session = self.db.query(AIHelperSession).filter(
            AIHelperSession.id == session_id
        ).first()

        if session and session.context:
            context['session_history'] = session.context.get('history', [])[-10:]

    except Exception as e:
        logger.warning(f"Error assembling context: {e}")

    return context


def _is_troubleshooting_query(self, query: str, page_context: Dict) -> bool:
    """Detect if this is a troubleshooting query that needs runbook search."""
    # Simple heuristics (can be enhanced)
    troubleshooting_keywords = [
        'high cpu', 'memory', 'disk', 'slow', 'error', 'fix', 'troubleshoot',
        'restart', 'down', 'failed', 'not working', 'issue', 'problem'
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in troubleshooting_keywords)
```

**Enhanced System Prompt:**
```python
# In _call_llm method, add to system prompt:

SOLUTION PRESENTATION (Runbook-First Troubleshooting):

When context includes 'ranked_solutions':
  - You have been provided with pre-ranked solutions (runbooks + manual)
  - DO NOT re-rank or re-decide - use the ranking provided
  - Your job is to FORMAT these solutions into markdown
  - Follow the presentation_strategy from ranked_solutions

Presentation Strategies:
  1. 'single_solution': Show one clear recommendation
  2. 'primary_with_alternatives': Lead with primary, mention alternatives exist
  3. 'multiple_options': Show 2-3 options, let user choose
  4. 'experimental_options': Show options but warn about low confidence
  5. 'primary_plus_one': Show primary + one backup option

Markdown Format Guidelines:
  - Use headings (## for sections, ### for options)
  - Use code blocks with language hints for commands
  - Use markdown links [text](url) for runbooks and docs
  - Use simple text ratings (⭐⭐⭐ for confidence)
  - Use emojis sparingly (✅ for permissions, ⚠️ for warnings, 💡 for tips)
  - NO HTML, NO interactive buttons, NO forms

For Runbooks:
  - Format as: **[Runbook #{id}: {name}]({url})**
  - Show permission status: "✅ You can execute" or "🔒 Requires: [roles]"
  - Show confidence, success rate, estimated time
  - Explain why recommended

For Manual Solutions:
  - Show commands in ```bash or ```sql code blocks
  - Explain context and trade-offs
  - Link to related documentation

Always include:
  - Clear recommendation or comparison of trade-offs
  - Related knowledge base links
  - Warnings about prerequisites (sudo, permissions, etc.)
```

### 4. Feedback Loop Integration (Use Existing Tables)

**Purpose:** Track which solutions users choose and learn preferences

**Implementation:** Use existing `ai_helper_audit_logs` table fields

**Data Structure in ai_action_details (JSONB):**
```json
{
  "solutions_presented": [
    {
      "solution_id": "uuid-of-runbook-or-manual",
      "solution_type": "runbook",
      "title": "Apache High CPU - Graceful Restart",
      "confidence": 0.95,
      "rank": 1,
      "permission_status": "can_execute",
      "url": "/remediation/runbooks/45"
    },
    {
      "solution_id": "manual-restart-apache",
      "solution_type": "manual",
      "title": "Manual Apache Restart",
      "confidence": 0.85,
      "rank": 2,
      "commands": ["sudo systemctl restart apache2"]
    },
    {
      "solution_id": "manual-tune-memory",
      "solution_type": "manual",
      "title": "Memory Configuration Tuning",
      "confidence": 0.80,
      "rank": 3
    }
  ],
  "presentation_strategy": "primary_with_alternatives",
  "decision_reason": "High confidence runbook available with perfect success rate"
}
```

**Data Structure in user_modifications (JSONB):**
```json
{
  "solution_chosen_id": "uuid-of-runbook-or-manual",
  "solution_chosen_type": "runbook",
  "solution_chosen_rank": 1,
  "time_to_decision_seconds": 45,
  "user_action": "clicked_runbook_link",
  "execution_attempted": true,
  "execution_result": "success",  # Updated later via webhook or poll
  "feedback_comment": "Worked perfectly, thanks!"
}
```

**Tracking Mechanism:**
```javascript
// In agent_widget.js - track link clicks

function addMessage(text, type, audit_log_id) {
    const div = document.createElement('div');
    div.className = `agent-message ${type}`;
    div.dataset.auditLogId = audit_log_id;  // Store audit log ID

    if (typeof marked !== 'undefined') {
        div.innerHTML = marked.parse(text);
    }

    // Track link clicks to runbooks or docs
    div.querySelectorAll('a[href*="/remediation/runbooks/"]').forEach(link => {
        link.addEventListener('click', (e) => {
            const runbook_id = link.href.split('/runbooks/')[1];
            trackSolutionChoice(audit_log_id, {
                solution_chosen_id: runbook_id,
                solution_chosen_type: 'runbook',
                user_action: 'clicked_runbook_link'
            });
        });
    });

    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function trackSolutionChoice(audit_log_id, choice_data) {
    fetch('/api/ai-helper/track-choice', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify({
            audit_log_id: audit_log_id,
            choice_data: choice_data,
            timestamp: new Date().toISOString()
        })
    });
}
```

**Backend Endpoint:**
```python
# New endpoint in ai_helper_routes.py

@router.post("/track-choice")
async def track_solution_choice(
    request: SolutionChoiceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track which solution the user chose.
    Updates ai_helper_audit_logs.user_modifications.
    """
    audit_log = db.query(AIHelperAuditLog).filter(
        AIHelperAuditLog.id == request.audit_log_id
    ).first()

    if not audit_log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    # Update user_modifications field
    if audit_log.user_modifications is None:
        audit_log.user_modifications = {}

    audit_log.user_modifications.update({
        'solution_chosen_id': request.choice_data.solution_chosen_id,
        'solution_chosen_type': request.choice_data.solution_chosen_type,
        'user_action': request.choice_data.user_action,
        'time_to_decision_seconds': (
            datetime.utcnow() - audit_log.timestamp
        ).total_seconds(),
        'chosen_at': datetime.utcnow().isoformat()
    })

    audit_log.user_action = request.choice_data.user_action
    audit_log.user_action_timestamp = datetime.utcnow()

    db.commit()

    # Trigger async confidence update (future phase)
    # await update_solution_confidence_scores(audit_log)

    return {"status": "tracked", "audit_log_id": str(audit_log.id)}
```

**Learning Loop (Future Phase - Background Job):**
```python
async def update_solution_confidence_scores(audit_log: AIHelperAuditLog):
    """
    Update confidence scores based on user choices.
    Runs as background job (Celery/async).
    """
    solutions_presented = audit_log.ai_action_details.get('solutions_presented', [])
    choice = audit_log.user_modifications.get('solution_chosen_id')

    if not choice:
        return

    for solution in solutions_presented:
        if solution['solution_id'] == choice:
            # User chose this solution - increase confidence
            # Store adjustment in a separate table (future: confidence_adjustments)
            logger.info(f"User chose solution {choice} (rank {solution['rank']})")
            # Increment counters for this solution type
        else:
            # User did not choose this solution - decrease slightly
            logger.info(f"User rejected solution {solution['solution_id']}")

    # Update per-user preference profile (future phase)
    # Does this user prefer automated vs manual?
    # Does this user prefer quick fixes vs thorough investigations?
```

---

## Data Model Extensions (MINIMAL CHANGES)

### Phase 1: Add Embedding to Runbooks (NOT a new table)

**Migration:** Add `embedding` column to existing `runbooks` table

```python
# alembic/versions/XXX_add_embedding_to_runbooks.py

def upgrade():
    # Add vector extension if not exists
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Add embedding column to runbooks
    op.add_column(
        'runbooks',
        sa.Column('embedding', Vector(1536), nullable=True)
    )

    # Create vector index for fast similarity search
    op.execute('''
        CREATE INDEX runbooks_embedding_idx
        ON runbooks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')

    # Add index for enabled runbooks (frequently filtered)
    op.create_index(
        'idx_runbooks_enabled_embedding',
        'runbooks',
        ['enabled'],
        postgresql_where=sa.text('embedding IS NOT NULL')
    )

def downgrade():
    op.drop_index('idx_runbooks_enabled_embedding', table_name='runbooks')
    op.execute('DROP INDEX runbooks_embedding_idx')
    op.drop_column('runbooks', 'embedding')
```

**Embedding Generation:**
```python
# In runbook_search_service.py or background job

async def generate_runbook_embeddings():
    """
    Generate embeddings for all runbooks.
    Runs as background job or migration script.
    """
    runbooks = db.query(Runbook).filter(
        Runbook.enabled == True,
        Runbook.embedding == None
    ).all()

    for runbook in runbooks:
        # Combine name + description + tags for embedding
        text = f"{runbook.name}. {runbook.description or ''}. Tags: {', '.join(runbook.tags or [])}"

        # Generate embedding (same model as knowledge base)
        embedding = await generate_embedding(text)

        runbook.embedding = embedding
        db.commit()

        logger.info(f"Generated embedding for runbook {runbook.id}: {runbook.name}")
```

**Regeneration Trigger:**
```python
# In models_remediation.py - add event listener

from sqlalchemy import event

@event.listens_for(Runbook, 'after_update')
def regenerate_embedding_on_update(mapper, connection, target):
    """
    Regenerate embedding when runbook name/description/tags change.
    """
    if target.name or target.description or target.tags:
        # Mark for regeneration (background job will pick up)
        target.embedding = None  # Force regeneration
        logger.info(f"Runbook {target.id} updated, will regenerate embedding")
```

### Phase 2: Use Existing Audit Log Fields (NO NEW TABLE)

**No migration needed** - use existing JSONB fields:

- `ai_helper_audit_logs.ai_action_details` → Store `solutions_presented`
- `ai_helper_audit_logs.user_modifications` → Store `solution_chosen`
- `ai_helper_audit_logs.user_action` → Store action type ("clicked_runbook_link", "copied_command")
- `ai_helper_audit_logs.user_action_timestamp` → Track when user acted
- `ai_helper_audit_logs.user_feedback` → Store thumbs up/down
- `ai_helper_audit_logs.user_feedback_comment` → Store optional feedback text

**Existing fields cover all our needs:**
- ✅ Solutions presented (ai_action_details JSONB)
- ✅ Solution chosen (user_modifications JSONB)
- ✅ Execution tracking (executed, execution_result, execution_details)
- ✅ User feedback (user_feedback, user_feedback_comment)
- ✅ Time to decision (timestamp vs user_action_timestamp)

**Only create a new table if:**
- We need per-solution historical stats (future phase 3+)
- We need per-user preference profiles (future phase 4+)
- We need solution A/B testing framework (future phase 4+)

---

## Integration Points (Function-Level Mapping)

### 1. With Existing Knowledge Base

**File:** `app/services/ai_helper_orchestrator.py`
**Function:** `_assemble_context()`
**Lines:** ~249-297

**Integration:**
```python
async def _assemble_context(self, query, page_context, session_id):
    # Existing knowledge search (lines 272-284)
    knowledge_results = self.knowledge_service.search_similar(...)

    # NEW: Add runbook search in parallel
    if self._is_troubleshooting_query(query, page_context):
        runbook_search_service = RunbookSearchService(self.db)
        runbook_results = await runbook_search_service.search_runbooks(...)

        # NEW: Rank and combine
        solution_ranker = SolutionRanker(self.db)
        ranked_solutions = solution_ranker.rank_and_combine_solutions(
            runbooks=runbook_results,
            manual_solutions=[],
            knowledge_refs=knowledge_results,
            user_context=page_context or {}
        )

        context['ranked_solutions'] = ranked_solutions

    return context
```

### 2. With Existing Runbook System

**File:** `app/models_remediation.py`
**Model:** `Runbook`, `RunbookExecution`, `RunbookACL`
**Lines:** Runbook (44-104), RunbookExecution (233-295)

**Integration:**
- Runbook search queries `Runbook` table with vector similarity
- Success rate computed from `RunbookExecution` table (status='success')
- RBAC checked via `RunbookACL` table (existing permissions logic)
- AI Helper links to `/remediation/runbooks/{id}` (existing UI)
- Execution flow uses existing runbook approval/execution system

**No changes to runbook execution flow** - AI Helper only recommends, doesn't execute.

### 3. With AI Helper Orchestrator

**File:** `app/services/ai_helper_orchestrator.py`
**Function:** `_call_llm()`
**Lines:** ~299-450

**Integration:**
```python
async def _call_llm(self, query, context, user_context):
    # Existing system prompt (lines 326-435)
    system_prompt = """
    ... existing prompt ...

    SOLUTION PRESENTATION (Runbook-First Troubleshooting):

    When context includes 'ranked_solutions':
      - Use the pre-ranked solutions provided
      - DO NOT re-rank or re-decide
      - Format into markdown using presentation_strategy
      - Follow markdown guidelines (no buttons, no HTML)

    ... (see "Enhanced System Prompt" section above) ...
    """

    # Build user message with ranked solutions
    user_message = f"User query: {query}\n\n"

    if context.get('ranked_solutions'):
        user_message += "Ranked Solutions:\n"
        user_message += json.dumps(
            context['ranked_solutions'].to_dict(),
            indent=2
        )
        user_message += "\n\nFormat these solutions into markdown response."

    # Call LLM (existing logic)
    response = await self.llm_service.chat_completion(...)

    return response
```

### 4. With RBAC System

**File:** `app/services/rbac.py` (if exists) or inline in runbook routes
**Function:** `check_runbook_acl()`

**Integration:**
```python
def check_runbook_acl(user: User, runbook: Runbook, permission: str = 'view') -> bool:
    """
    Check if user has permission to view/execute runbook.

    Permissions hierarchy:
    - 'view': Can see runbook exists (for AI recommendations)
    - 'execute': Can trigger runbook execution

    Uses existing RunbookACL table and approval_roles logic.
    """
    # Check if runbook is enabled
    if not runbook.enabled:
        return False

    # Check RunbookACL for explicit permissions
    acl_entry = db.query(RunbookACL).filter(
        RunbookACL.runbook_id == runbook.id,
        RunbookACL.user_id == user.id
    ).first()

    if acl_entry:
        if permission == 'view':
            return acl_entry.can_view or acl_entry.can_execute
        elif permission == 'execute':
            return acl_entry.can_execute

    # Check approval_roles (default permissions)
    if permission == 'execute' and runbook.approval_required:
        user_roles = [r.name for r in user.roles]
        return any(role in runbook.approval_roles for role in user_roles)

    # Default: everyone can view, execution requires roles
    if permission == 'view':
        return True
    else:
        return False


def get_permission_status(user: User, runbook: Runbook) -> str:
    """
    Get human-readable permission status for display.
    """
    if check_runbook_acl(user, runbook, permission='execute'):
        return "can_execute"
    elif check_runbook_acl(user, runbook, permission='view'):
        return "view_only"
    else:
        return "no_access"
```

---

## User Experience Flow (Updated for Markdown)

### Scenario 1: High-Confidence Runbook Available

```
User: "High CPU on Apache server prod-web-01"

AI Response (Markdown):
┌──────────────────────────────────────┐
│ ## Recommended Solution               │
│                                       │
│ ### Automated Runbook (Recommended)   │
│ [Runbook #45: Apache CPU Fix](/...)   │
│ ⭐⭐⭐ 95% | Success: 100% | 5 min   │
│ ✅ You can execute                    │
│                                       │
│ Description: Gracefully restarts...   │
│                                       │
│ [See 2 alternatives below]            │
└──────────────────────────────────────┘

User clicks: [Runbook #45] link
  → Navigates to /remediation/runbooks/45
  → Existing runbook page loads
  → User reviews runbook details
  → User clicks "Execute" (existing UI button)
  → Existing RBAC check
  → Existing approval workflow (if required)
  → Runbook executes
  → Success/failure logged in runbook_executions

AI Helper tracks:
  → user_action = "clicked_runbook_link"
  → solution_chosen_id = runbook.id
  → solution_chosen_rank = 1
  → Time to decision recorded
```

### Scenario 2: Multiple Similar Solutions

```
User: "MySQL slow queries on db-master"

AI Response (Markdown):
┌──────────────────────────────────────┐
│ ## Multiple Solutions Available       │
│                                       │
│ ### 1. Runbook: MySQL Cache Tune      │
│ [View Runbook #78](/...)              │
│ ⭐⭐⭐ 88% | 8 min | ✅ Ready         │
│                                       │
│ ### 2. Manual: Index Optimization     │
│ ⭐⭐ 85% | 10 min                     │
│ ```sql                                │
│ ANALYZE TABLE slow_table;             │
│ ```                                   │
│                                       │
│ ### 3. Manual: Restart MySQL          │
│ ⭐⭐ 82% | 2 min                      │
│ ```bash                               │
│ sudo systemctl restart mysql          │
│ ```                                   │
└──────────────────────────────────────┘

User chooses Option 2 (Manual Index):
  → Selects SQL commands from code block
  → Copies to clipboard
  → Executes in MySQL client
  → Returns to AI chat
  → Provides feedback: 👍 "Worked well"

AI Helper tracks:
  → user_action = "copied_manual_command"
  → solution_chosen_id = "manual-index-optimization"
  → solution_chosen_rank = 2
  → user_feedback = "helpful"
  → Learn: User prefers investigative approach
```

### Scenario 3: No High-Confidence Match

```
User: "Strange network latency spikes"

AI Response (Markdown):
┌──────────────────────────────────────┐
│ ## Experimental Solutions             │
│ ⚠️ Low confidence - limited history   │
│                                       │
│ ### 1. Check Network Interface Stats  │
│ ⭐ 65% confidence                     │
│ ```bash                               │
│ ip -s link show                       │
│ netstat -i                            │
│ ```                                   │
│                                       │
│ ### 2. Review Network Changes         │
│ ⭐ 62% confidence                     │
│                                       │
│ [Network Troubleshooting Guide](/...) │
│                                       │
│ 🙏 Feedback appreciated!              │
└──────────────────────────────────────┘

User tries Option 1:
  → Copies commands
  → Executes, finds issue
  → Provides feedback: 👍 "Found the problem, thanks!"
  → Optional comment: "NIC errors were the issue"

AI Helper tracks:
  → user_action = "copied_manual_command"
  → solution_chosen_id = "manual-network-stats"
  → solution_chosen_rank = 1
  → execution_result = "success" (from feedback)
  → user_feedback = "helpful"
  → user_feedback_comment = "NIC errors..."

Background job:
  → Increase confidence for this solution
  → Associate "network latency" with "NIC stats check"
  → Next time: higher confidence for similar queries
```

---

## RBAC and Security Considerations (CRITICAL)

### Runbook Recommendation Permissions (NOT Execution)

**AI Helper Permission Model:**
- AI Helper shows runbook recommendations if user has `view` permission
- AI Helper does NOT execute runbooks (security policy: `execute_runbook` in `BLOCKED_ACTIONS`)
- User must navigate to runbook page and trigger execution manually
- Existing runbook approval workflow applies

**Permission Checks:**
```
AI Helper checks:
1. Can user VIEW runbook? (RunbookACL.can_view OR in approval_roles)
   YES → Show runbook in recommendations
   NO → Filter out, only show manual alternatives

2. Can user EXECUTE runbook? (RunbookACL.can_execute OR in approval_roles)
   YES → Show "✅ You can execute"
   NO → Show "🔒 Requires approval from: [roles]"
```

**Runbook Page checks (existing flow):**
1. User navigates to `/remediation/runbooks/{id}`
2. Runbook detail page loads (existing RBAC check)
3. User reviews runbook steps and configuration
4. User clicks "Execute" button (existing UI)
5. Backend checks:
   - User has `runbook.execute` permission (RBAC)
   - User is in `runbook.approval_roles` (if approval_required)
   - Runbook is `enabled`
   - Server is accessible
6. If approval required:
   - Create pending execution
   - Send approval request (Slack/Email)
   - Wait for approval
7. If approved or no approval needed:
   - Execute runbook via existing executor
   - Log to `runbook_executions`

**Audit Logging:**

**What AI Helper Logs:**
- Runbook recommendations shown to user
- User's permission status (can_execute, view_only, no_access)
- Which runbook user clicked (if any)
- Timestamp of recommendation

**What Runbook System Logs (existing):**
- Execution attempts (success/failure)
- Approval workflow (requested, approved, rejected)
- RBAC checks (permission granted/denied)
- Step-by-step execution details

**Security Events to Monitor:**
- User with no permission tries to access runbook page (403 error)
- User attempts to modify runbook they don't own
- Unusual pattern: Many runbook views but no executions (reconnaissance?)
- Failed executions after AI recommendations (potential RBAC bypass attempt)

---

## Performance Considerations

### Search Latency

**Target:** < 500ms for parallel search (runbooks + knowledge)

**Optimization Strategies:**
1. **Vector Index:** Use `ivfflat` or `hnsw` index on `runbooks.embedding`
2. **Pre-filtering:** Apply context filters (enabled=true, OS match) before vector search
3. **Limit candidates:** Only search top 10 semantic matches, then rank by context
4. **Cache embeddings:** Cache query embeddings for common phrases (5-minute TTL)
5. **Async/parallel:** Run runbook search + knowledge search in parallel

**Query Performance:**
```sql
-- Optimized runbook search query
SELECT r.*,
       1 - (r.embedding <=> query_embedding) AS similarity
FROM runbooks r
WHERE r.enabled = true
  AND r.target_os_filter @> ARRAY['linux']::text[]
  AND (r.embedding <=> query_embedding) < 0.5  -- Similarity threshold
ORDER BY r.embedding <=> query_embedding
LIMIT 10;

-- Uses index: runbooks_embedding_idx (ivfflat)
-- Estimated time: 50-150ms for 1000 runbooks
```

### Ranking Latency

**Target:** < 100ms for ranking and combining

**Optimization:**
- Pre-compute success rates (cache in Redis, refresh hourly)
- Avoid complex joins - fetch related data in separate queries
- Use simple weighted scoring (no ML inference)
- Limit to top 3 solutions (avoid ranking hundreds)

### Total Response Time

**Target:** < 1 second end-to-end

**Breakdown:**
- Parallel search (runbooks + knowledge): 500ms
- Ranking and combining: 100ms
- LLM formatting: 300ms (depends on model)
- DB write (audit log): 50ms
- Network/overhead: 50ms

**Total:** ~1000ms

**Monitoring:**
```python
# In ai_helper_orchestrator.py

start_time = datetime.utcnow()

# Search phase
search_start = datetime.utcnow()
runbook_results = await search_runbooks(...)
search_duration = (datetime.utcnow() - search_start).total_seconds() * 1000

# Ranking phase
rank_start = datetime.utcnow()
ranked_solutions = rank_and_combine_solutions(...)
rank_duration = (datetime.utcnow() - rank_start).total_seconds() * 1000

# LLM phase
llm_start = datetime.utcnow()
response = await call_llm(...)
llm_duration = (datetime.utcnow() - llm_start).total_seconds() * 1000

# Log performance metrics
logger.info(f"Search: {search_duration}ms | Rank: {rank_duration}ms | LLM: {llm_duration}ms")

# Store in audit log for analysis
audit_log.runbook_search_time_ms = search_duration
audit_log.ranking_time_ms = rank_duration
audit_log.llm_latency_ms = llm_duration
audit_log.total_duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
```

---

## Metrics and Monitoring

### Success Metrics

1. **Solution Acceptance Rate**
   - % of presented solutions that users choose to execute/copy
   - Target: > 70%
   - Measure: `COUNT(user_modifications IS NOT NULL) / COUNT(*)`

2. **Runbook Utilization**
   - % of troubleshooting queries where runbook was available and chosen
   - Target: > 50% when runbook matches exist
   - Measure: Filter by `solution_chosen_type='runbook'`

3. **First-Choice Accuracy**
   - % of times user chooses top-ranked solution (rank 1)
   - Target: > 60%
   - Measure: `COUNT(solution_chosen_rank=1) / COUNT(*)`

4. **User Satisfaction**
   - Thumbs up rate after solution execution
   - Target: > 80%
   - Measure: `COUNT(user_feedback='helpful') / COUNT(user_feedback IS NOT NULL)`

5. **Execution Success Rate**
   - % of chosen runbooks that complete successfully
   - Target: > 85%
   - Measure: Join with `runbook_executions` table, check `status='success'`

### Monitoring Dashboards

**Dashboard 1: Solution Quality**
```sql
-- Average confidence of presented solutions
SELECT
    DATE(timestamp) as date,
    AVG((ai_action_details->'solutions_presented'->0->>'confidence')::numeric) as avg_top_confidence,
    COUNT(*) as total_queries
FROM ai_helper_audit_logs
WHERE ai_action_details->'solutions_presented' IS NOT NULL
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

**Dashboard 2: Runbook vs Manual**
```sql
-- Runbook choice rate
SELECT
    user_modifications->>'solution_chosen_type' as solution_type,
    COUNT(*) as choices,
    AVG((user_modifications->>'time_to_decision_seconds')::numeric) as avg_decision_time_sec
FROM ai_helper_audit_logs
WHERE user_modifications->>'solution_chosen_type' IS NOT NULL
GROUP BY solution_type;
```

**Dashboard 3: User Behavior**
```sql
-- Rank distribution (do users choose top option?)
SELECT
    (user_modifications->>'solution_chosen_rank')::int as rank_chosen,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM ai_helper_audit_logs
WHERE user_modifications->>'solution_chosen_rank' IS NOT NULL
GROUP BY rank_chosen
ORDER BY rank_chosen;
```

**Dashboard 4: Learning Effectiveness**
```sql
-- Confidence improvement over time for specific solutions
SELECT
    ai_action_details->'solutions_presented'->0->>'solution_id' as solution_id,
    ai_action_details->'solutions_presented'->0->>'title' as solution_title,
    DATE(timestamp) as date,
    AVG((ai_action_details->'solutions_presented'->0->>'confidence')::numeric) as avg_confidence,
    COUNT(CASE WHEN user_modifications->>'solution_chosen_rank' = '1' THEN 1 END) as times_chosen
FROM ai_helper_audit_logs
WHERE ai_action_details->'solutions_presented' IS NOT NULL
GROUP BY solution_id, solution_title, DATE(timestamp)
ORDER BY date DESC;
```

---

## Implementation Phases (High-Level - Detailed for Phase 1)

### Phase 1: Foundation (Runbook Search)

**Goal:** Enable runbook discovery via semantic search and recommendation

**Timeline:** ~2-3 weeks

**Components:**

1. **Database Migration** (1 day)
   - Add `embedding` column to `runbooks` table (Vector(1536))
   - Create ivfflat index on `embedding`
   - Generate embeddings for existing runbooks (background job)

2. **Runbook Search Service** (3-4 days)
   - Implement `RunbookSearchService` class
   - Semantic search using pgvector
   - Context filtering (server_type, OS, environment)
   - RBAC integration (check permissions)
   - Success rate calculation from `runbook_executions`

3. **Solution Ranker** (2-3 days)
   - Implement `SolutionRanker` class
   - Weighted scoring algorithm
   - Decision matrix logic
   - Output structured data for LLM formatting

4. **Orchestrator Integration** (2-3 days)
   - Modify `_assemble_context()` to include runbook search
   - Add `_is_troubleshooting_query()` detection
   - Enhance system prompt with markdown formatting guidelines
   - Store `solutions_presented` in `ai_action_details`

5. **Response Formatting** (1-2 days)
   - Update LLM prompt templates
   - Test markdown rendering in widget
   - Ensure runbook links work correctly

6. **Testing** (2-3 days)
   - Unit tests for search, ranking, scoring
   - Integration tests with real runbooks
   - Performance testing (search latency < 500ms)
   - RBAC edge cases

**Success Criteria:**
- ✅ Runbooks searchable via natural language queries
- ✅ RBAC-filtered results (only shows what user can view)
- ✅ < 500ms search latency (avg)
- ✅ Markdown links to runbooks render correctly
- ✅ Top 3 ranked runbooks match user's context

**Minimal DB Migration:**
```sql
-- Phase 1 Migration
ALTER TABLE runbooks ADD COLUMN embedding vector(1536);
CREATE INDEX runbooks_embedding_idx ON runbooks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- No new tables created in Phase 1
-- Use existing ai_helper_audit_logs.ai_action_details for tracking
```

**Concrete Files to Create:**
1. `app/services/runbook_search_service.py` (~200 lines)
2. `app/services/solution_ranker.py` (~150 lines)
3. `alembic/versions/XXX_add_embedding_to_runbooks.py` (~30 lines)
4. `scripts/generate_runbook_embeddings.py` (background job, ~50 lines)

**Concrete Files to Modify:**
1. `app/services/ai_helper_orchestrator.py`:
   - `_assemble_context()` - add runbook search (~20 lines)
   - `_is_troubleshooting_query()` - new method (~15 lines)
   - `_call_llm()` - enhance system prompt (~30 lines)

2. `app/models_remediation.py`:
   - Add `embedding` column to `Runbook` model (~2 lines)
   - Add event listener for embedding regeneration (~10 lines)

### Phase 2: User Feedback Tracking

**Goal:** Track which solutions users choose and store in audit logs

**Components:**
- Frontend click tracking (agent_widget.js)
- Backend API endpoint (`/api/ai-helper/track-choice`)
- Update `user_modifications` field in audit logs
- Dashboard queries for analysis

**Success Criteria:**
- ✅ Capture which solution user chose (> 80% of interactions)
- ✅ Time to decision recorded
- ✅ No new tables created (use existing audit_logs)

### Phase 3: Confidence Score Updates

**Goal:** Learn from user choices to improve recommendations

**Components:**
- Background job to analyze user choices
- Confidence score adjustments (stored in JSONB or new stats table)
- Use historical choice data to re-rank future solutions

**Success Criteria:**
- ✅ Confidence scores improve over 30 days
- ✅ First-choice accuracy increases by 10%
- ✅ User satisfaction > 80%

### Phase 4: Manual Solution Integration (Future)

**Goal:** Add manual troubleshooting solutions from history

**Components:**
- Troubleshooting case storage (plain text + embeddings)
- Manual solution search and ranking
- Combined runbook + manual recommendations

**Success Criteria:**
- ✅ Manual solutions searchable via semantic search
- ✅ Runbook vs manual choice rate balanced
- ✅ Coverage for queries without matching runbooks

---

## Open Questions and Design Decisions

### Resolved Questions

1. **Q: Should AI Helper execute runbooks directly?**
   - **A: NO.** `execute_runbook` is in `BLOCKED_ACTIONS` for security. AI Helper only recommends, user must click through to runbook page and execute via existing flow.

2. **Q: Do we need a new `runbook_embeddings` table?**
   - **A: NO.** Add `embedding` column directly to `runbooks` table. Only create separate table if we need multiple embeddings per runbook (e.g., for versioning).

3. **Q: Do we need a new `troubleshooting_solution_feedback` table?**
   - **A: NOT YET.** Use existing `ai_helper_audit_logs.ai_action_details` and `user_modifications` (JSONB) first. Only create new table if we need complex queries or per-solution stats later.

4. **Q: Can we use interactive buttons in the UI?**
   - **A: NO.** Widget renders markdown via `marked.parse()`. Use markdown links `[text](url)` and code blocks for commands. Users can select/copy naturally.

5. **Q: Should LLM decide which solution to recommend?**
   - **A: NO.** Use deterministic pipeline: Search → Rank (by algorithm) → LLM formats. LLM only does markdown formatting, not decision-making. This avoids LLM fighting the ranker.

### Open Questions (Future Phases)

1. **Runbook suggestion frequency:** How often should we suggest creating a runbook from frequently-used manual solutions?
   - **Proposal:** If manual solution chosen 5+ times with 80%+ success rate, show "💡 This could be automated as a runbook" message

2. **Cross-solution learning:** If a manual solution works well, should we suggest automating it as a runbook?
   - **Proposal:** Track manual solutions with high success rate, surface to runbook creators

3. **Fallback strategy:** What if neither runbooks nor manual solutions have high confidence? Should we engage expert humans?
   - **Proposal:** If all confidence < 0.6, suggest "Contact on-call engineer" or "Create new runbook"

4. **Multi-step solutions:** How to handle solutions that require multiple stages (diagnostic → action)?
   - **Proposal:** Phase 4 - allow chaining runbooks or multi-step manual procedures

5. **Confidence explanation:** Should we show users why AI is confident in a solution?
   - **Proposal:** Add optional "Why this solution?" section with breakdown (similarity: 0.8, success rate: 0.9, context match: 0.7)

---

## Risk and Mitigation

### Risk 1: Security - Accidental Runbook Execution

**Risk:** User might think AI executes runbooks automatically, leading to confusion or security concerns

**Mitigation:**
- ✅ Clear messaging: "Click to review and execute" (not "Click to execute")
- ✅ Runbook link goes to detail page, not direct execution endpoint
- ✅ Existing approval workflow prevents accidental execution
- ✅ Audit log tracks recommendations vs actual executions separately
- ✅ Documentation: AI Helper is advisory only, never executes commands

### Risk 2: RBAC Complexity

**Risk:** Permission checking might slow down response or create false negatives

**Mitigation:**
- ✅ Cache user permissions (refresh every 5 minutes via Redis)
- ✅ Pre-filter runbooks by `enabled=true` before expensive RBAC checks
- ✅ Log RBAC denials for security team review
- ✅ Provide clear messaging: "🔒 Requires approval from: ops-team" (not just hidden)

### Risk 3: Poor Ranking Quality

**Risk:** Users might frequently choose lower-ranked options, indicating bad ranking

**Mitigation:**
- ✅ Track "rank inversion rate" (user chooses #3 when #1 was available)
- ✅ A/B test ranking algorithms (future phase)
- ✅ Manual review of low-confidence cases (Grafana dashboard)
- ✅ Incorporate human expert feedback: "Was this helpful?" thumbs up/down

### Risk 4: Context Mismatch

**Risk:** Solutions might be recommended for wrong context (wrong OS, app version, etc.)

**Mitigation:**
- ✅ Strict context filtering before search (target_os_filter, tags)
- ✅ Require minimum context match threshold (> 70%)
- ✅ Show context details in solution presentation: "For: Ubuntu 20.04, Apache 2.4"
- ✅ Allow users to report "wrong context" as feedback
- ✅ Tag runbooks with required context attributes (OS, app, version)

### Risk 5: Embedding Regeneration Cost

**Risk:** Regenerating embeddings for all runbooks after model change could be expensive

**Mitigation:**
- ✅ Use same embedding model as knowledge base (already paid for)
- ✅ Generate embeddings asynchronously (background job)
- ✅ Mark stale embeddings (`updated_at` tracking) and regenerate incrementally
- ✅ Cache embeddings in table, not regenerate per query
- ✅ Estimate: ~1000 runbooks × $0.0001 per embedding = $0.10 per full regeneration

---

## Success Criteria

### Must Have (P0)

- ✅ Present multiple solutions when confidence scores are similar (< 0.1 difference)
- ✅ Runbook-first search and prioritization
- ✅ RBAC/ACL awareness (show permission status, don't execute)
- ✅ Track which solution users choose (via existing audit log fields)
- ✅ Context-aware filtering (server type, app, OS, environment)
- ✅ Markdown-only response format (no interactive buttons)
- ✅ Response latency < 1 second end-to-end (P90)

### Should Have (P1)

- Confidence score improvements over time (30-day measurement)
- User satisfaction > 80% (thumbs up rate)
- First-choice accuracy > 60% (users choose top option)
- Runbook utilization > 50% (when runbook matches exist)
- Solution acceptance rate > 70% (users act on recommendations)

### Nice to Have (P2)

- User preference personalization (future phase 4)
- Proactive runbook creation suggestions
- Cross-team learning (organization-wide patterns)
- Confidence explanation ("Why am I seeing this solution?")
- Manual solution integration (troubleshooting history)

---

## Conclusion

This revised design transforms AI Helper from a single-suggestion system to an intelligent, multi-option recommender that:

1. **Prioritizes automation** via runbook-first search (without executing)
2. **Respects user choice** by presenting multiple ranked options in markdown
3. **Learns continuously** from user selections (via existing audit log fields)
4. **Enforces security** through RBAC/ACL awareness and read-only recommendations
5. **Adapts to context** using multi-dimensional filtering and semantic search

**Key Improvements from v1.0:**
- ✅ Clarified AI Helper does NOT execute runbooks (security policy)
- ✅ Simplified data model (use existing tables, add embedding column to runbooks)
- ✅ Changed response format to markdown-only (no interactive buttons)
- ✅ Deterministic pipeline (LLM only formats, doesn't decide)
- ✅ Concrete integration points mapped to function-level
- ✅ Minimal DB migration (just add embedding column)
- ✅ Aligned with project constraints (RBAC, audit logs, markdown UI)

**Next Steps:**
1. Review and approve this revised high-level design
2. Implement Phase 1: Runbook Search Foundation
   - DB migration (add embedding column)
   - RunbookSearchService implementation
   - SolutionRanker implementation
   - Orchestrator integration
3. Test with real runbooks and troubleshooting queries
4. Measure success metrics and iterate

---

**Document Status:** Ready for Review (v2.0 - Revised)
**Approvers:** Product Owner, Engineering Lead, Security Team
**Related Documents:**
- AI_LEARNING_PLAN.md (Overall AI learning strategy)
- AI_AGENT_GRAFANA_BUILDER_MODE_FIX.md (Grafana integration)
- Existing runbook system documentation
- RBAC/ACL system documentation
- ai_helper_orchestrator.py (current implementation)
- models_remediation.py (runbook models)
- models_ai_helper.py (audit log models)
