# AI Terminal Improvement Plan

## Implementation Plan for Achieving VS Code Copilot Parity

**Branch:** `claude/review-ai-terminal-gaps-86kqM`
**Date:** 2026-01-16
**Status:** Draft

---

## 1. Overview

### Summary

This plan addresses critical gaps between our `/ai` terminal features and VS Code Copilot Chat capabilities. The primary improvements focus on four areas: (1) File operations with diff preview UI for terminal-only environments, (2) Multi-agent orchestration with background execution, (3) Auto-iteration loop that monitors command output and self-corrects, and (4) Enhanced planning visibility with adaptive phase management.

Our current system has strong foundations (multi-provider LLM support, safety validation, phased workflow) but lacks autonomous operation capabilities, file editing UX, and multi-agent support that VS Code Copilot provides.

### High-Level Success Criteria

- Users can preview file changes with inline diff before execution
- AI agent can run in background and auto-iterate on failures
- Planning is visible, persistent, and user-editable
- Multiple agents can run concurrently with handoff capability
- Slash commands and chat participants provide quick actions
- All file operations have rollback capability

---

## 2. Scope

### In Scope

| Area | Items |
|------|-------|
| **File Operations** | File viewer panel, inline diff component, change set model, atomic operations, rollback |
| **Multi-Agent** | Background agent, agent session manager, agent handoff protocol |
| **Auto-Iteration** | Terminal output capture, error detection, auto-retry loop, test monitoring |
| **Planning** | Persistent markdown plans, phase revisit, sub-task decomposition, progress UI |
| **Chat UX** | Slash commands, chat participants, context variables |
| **Database** | New tables for change sets, agent orchestration, plans |
| **API** | New endpoints for file ops, multi-agent, planning |
| **Frontend** | File viewer, diff panel, plan editor, agent HQ view |

### Out of Scope

- Cloud agent (remote execution) - deferred to Phase 4
- IDE/editor integration - we remain terminal-focused
- Voice input/output
- Mobile UI optimization
- Multi-tenant isolation changes
- LLM fine-tuning or custom model training

---

## 3. Design

### 3.1 Architecture Diagram (Textual)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (ai_chat.js)                        │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────┤
│ Chat Panel  │ File Viewer │ Diff Panel  │ Plan Editor │ Agent HQ View  │
│             │ (new)       │ (new)       │ (new)       │ (new)          │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴───────┬────────┘
       │             │             │             │              │
       ▼             ▼             ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                   │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────┤
│ chat_api.py │file_ops_api │ plan_api.py │ agent_api.py│ changeset_api  │
│ (existing)  │ (new)       │ (new)       │ (enhanced)  │ (new)          │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴───────┬────────┘
       │             │             │             │              │
       ▼             ▼             ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER                                  │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────┤
│NativeAgent  │FileOps      │PlanService  │AgentOrch-   │ChangeSet      │
│(enhanced)   │Service(new) │(new)        │estrator(new)│Service(new)   │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴───────┬────────┘
       │             │             │             │              │
       ▼             ▼             ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                  │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────┤
│AISession    │FileVersion  │Plan         │AgentPool    │ChangeSet      │
│AIMessage    │FileBackup   │PlanStep     │AgentTask    │ChangeItem     │
│(existing)   │(new)        │(new)        │(new)        │(new)          │
└─────────────┴─────────────┴─────────────┴─────────────┴────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SSH/TERMINAL LAYER                               │
│              SSHClient (existing) + OutputCapture (new)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Model Changes

#### New Tables

```sql
-- Plan persistence and tracking
CREATE TABLE plans (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES ai_sessions(id),
    title VARCHAR(255),
    markdown_content TEXT,
    status VARCHAR(50),  -- 'draft', 'active', 'completed', 'abandoned'
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE plan_steps (
    id UUID PRIMARY KEY,
    plan_id UUID REFERENCES plans(id),
    step_number INTEGER,
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(50),  -- 'pending', 'in_progress', 'completed', 'skipped', 'failed'
    phase VARCHAR(50),   -- 'identify', 'verify', 'investigate', 'plan', 'act'
    parent_step_id UUID REFERENCES plan_steps(id),  -- for hierarchical steps
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- File operations and versioning
CREATE TABLE file_versions (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES ai_sessions(id),
    server_id UUID REFERENCES servers(id),
    file_path VARCHAR(1024),
    content TEXT,
    content_hash VARCHAR(64),
    version_number INTEGER,
    created_by VARCHAR(50),  -- 'user', 'agent', 'backup'
    created_at TIMESTAMP
);

CREATE TABLE file_backups (
    id UUID PRIMARY KEY,
    file_version_id UUID REFERENCES file_versions(id),
    backup_path VARCHAR(1024),  -- remote backup location
    created_at TIMESTAMP,
    expires_at TIMESTAMP
);

-- Change sets for atomic operations
CREATE TABLE change_sets (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES ai_sessions(id),
    agent_step_id UUID REFERENCES agent_steps(id),
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(50),  -- 'pending', 'previewing', 'applied', 'rolled_back'
    created_at TIMESTAMP,
    applied_at TIMESTAMP,
    rolled_back_at TIMESTAMP
);

CREATE TABLE change_items (
    id UUID PRIMARY KEY,
    change_set_id UUID REFERENCES change_sets(id),
    file_path VARCHAR(1024),
    operation VARCHAR(50),  -- 'create', 'modify', 'delete', 'rename'
    old_content TEXT,
    new_content TEXT,
    diff_hunks JSONB,
    status VARCHAR(50),  -- 'pending', 'accepted', 'rejected', 'applied'
    order_index INTEGER
);

-- Multi-agent orchestration
CREATE TABLE agent_pools (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    session_id UUID REFERENCES ai_sessions(id),
    max_concurrent_agents INTEGER DEFAULT 3,
    created_at TIMESTAMP
);

CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY,
    pool_id UUID REFERENCES agent_pools(id),
    agent_session_id UUID REFERENCES agent_sessions(id),
    agent_type VARCHAR(50),  -- 'local', 'background', 'cloud'
    goal TEXT,
    priority INTEGER,
    status VARCHAR(50),  -- 'queued', 'running', 'paused', 'completed', 'failed', 'handed_off'
    parent_task_id UUID REFERENCES agent_tasks(id),  -- for handoff tracking
    worktree_path VARCHAR(1024),  -- for background agents
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Auto-iteration tracking
CREATE TABLE iteration_loops (
    id UUID PRIMARY KEY,
    agent_step_id UUID REFERENCES agent_steps(id),
    command TEXT,
    iteration_number INTEGER,
    exit_code INTEGER,
    output TEXT,
    error_detected BOOLEAN,
    error_type VARCHAR(100),
    auto_fix_attempted BOOLEAN,
    created_at TIMESTAMP
);
```

#### Modified Tables

```sql
-- Add to agent_sessions
ALTER TABLE agent_sessions ADD COLUMN agent_type VARCHAR(50) DEFAULT 'local';
ALTER TABLE agent_sessions ADD COLUMN pool_id UUID REFERENCES agent_pools(id);
ALTER TABLE agent_sessions ADD COLUMN worktree_path VARCHAR(1024);
ALTER TABLE agent_sessions ADD COLUMN auto_iterate BOOLEAN DEFAULT false;
ALTER TABLE agent_sessions ADD COLUMN max_auto_iterations INTEGER DEFAULT 5;

-- Add to agent_steps
ALTER TABLE agent_steps ADD COLUMN iteration_count INTEGER DEFAULT 0;
ALTER TABLE agent_steps ADD COLUMN change_set_id UUID REFERENCES change_sets(id);
ALTER TABLE agent_steps ADD COLUMN plan_step_id UUID REFERENCES plan_steps(id);

-- Add to ai_sessions
ALTER TABLE ai_sessions ADD COLUMN active_plan_id UUID REFERENCES plans(id);
ALTER TABLE ai_sessions ADD COLUMN slash_command_context JSONB;
```

### 3.3 API Contract Changes

#### File Operations API

```
POST /api/files/read
Request:
{
    "server_id": "uuid",
    "file_path": "/etc/nginx/nginx.conf",
    "encoding": "utf-8",
    "line_start": 1,
    "line_end": 100
}
Response (200):
{
    "file_path": "/etc/nginx/nginx.conf",
    "content": "...",
    "total_lines": 250,
    "syntax": "nginx",
    "last_modified": "2026-01-15T10:30:00Z",
    "permissions": "644",
    "owner": "root"
}

POST /api/files/preview-edit
Request:
{
    "server_id": "uuid",
    "file_path": "/etc/nginx/nginx.conf",
    "changes": [
        {
            "type": "replace",
            "start_line": 10,
            "end_line": 12,
            "old_content": "worker_connections 1024;",
            "new_content": "worker_connections 2048;"
        }
    ]
}
Response (200):
{
    "change_set_id": "uuid",
    "diff_preview": {
        "hunks": [...],
        "additions": 1,
        "deletions": 1,
        "unified_diff": "..."
    },
    "validation": {
        "syntax_valid": true,
        "warnings": []
    }
}

POST /api/files/apply-changes
Request:
{
    "change_set_id": "uuid",
    "items_to_apply": ["uuid1", "uuid2"],  // or "all"
    "create_backup": true
}
Response (200):
{
    "applied": true,
    "backup_id": "uuid",
    "files_modified": ["/etc/nginx/nginx.conf"],
    "rollback_available": true
}

POST /api/files/rollback
Request:
{
    "change_set_id": "uuid"
}
Response (200):
{
    "rolled_back": true,
    "files_restored": ["/etc/nginx/nginx.conf"]
}
```

#### Plan API

```
POST /api/plans
Request:
{
    "session_id": "uuid",
    "title": "Fix high CPU on web-server-01",
    "initial_steps": [
        {"title": "Identify top processes", "phase": "investigate"},
        {"title": "Check for runaway queries", "phase": "investigate"}
    ]
}
Response (201):
{
    "id": "uuid",
    "title": "Fix high CPU on web-server-01",
    "markdown_content": "# Plan: Fix high CPU...",
    "steps": [...],
    "status": "draft"
}

GET /api/plans/{plan_id}
Response (200):
{
    "id": "uuid",
    "title": "...",
    "markdown_content": "...",
    "steps": [...],
    "progress": {
        "total": 5,
        "completed": 2,
        "in_progress": 1,
        "pending": 2
    }
}

PATCH /api/plans/{plan_id}/steps/{step_id}
Request:
{
    "status": "completed",
    "notes": "Found mysql query causing 90% CPU"
}
Response (200):
{
    "step": {...},
    "plan_progress": {...}
}

POST /api/plans/{plan_id}/revise
Request:
{
    "return_to_phase": "investigate",
    "reason": "Initial hypothesis incorrect",
    "new_steps": [...]
}
Response (200):
{
    "plan": {...},
    "revision_number": 2
}
```

#### Multi-Agent API

```
POST /api/agents/pool
Request:
{
    "session_id": "uuid",
    "name": "Investigation Pool",
    "max_concurrent": 3
}
Response (201):
{
    "pool_id": "uuid",
    "name": "Investigation Pool",
    "agents": []
}

POST /api/agents/spawn
Request:
{
    "pool_id": "uuid",
    "agent_type": "background",
    "goal": "Run full test suite and fix failures",
    "auto_iterate": true,
    "max_iterations": 10
}
Response (202):
{
    "task_id": "uuid",
    "agent_session_id": "uuid",
    "agent_type": "background",
    "status": "queued",
    "worktree_path": "/tmp/agent-worktree-abc123"
}

POST /api/agents/handoff
Request:
{
    "from_task_id": "uuid",
    "to_agent_type": "local",
    "context_summary": "Background agent completed tests, needs user review",
    "transfer_plan": true
}
Response (200):
{
    "new_task_id": "uuid",
    "handoff_complete": true,
    "context_transferred": ["plan", "file_changes", "test_results"]
}

GET /api/agents/hq
Response (200):
{
    "pools": [...],
    "active_tasks": [
        {
            "task_id": "uuid",
            "agent_type": "background",
            "goal": "...",
            "status": "running",
            "progress": 45,
            "current_action": "Running pytest..."
        }
    ],
    "completed_tasks": [...],
    "pending_handoffs": [...]
}

WS /ws/agents/hq
Events:
{
    "type": "task_progress",
    "task_id": "uuid",
    "progress": 50,
    "current_action": "Fixing test_auth.py"
}
{
    "type": "task_completed",
    "task_id": "uuid",
    "result": "success",
    "summary": "All 45 tests passing"
}
{
    "type": "handoff_requested",
    "from_task_id": "uuid",
    "reason": "Needs user approval for production change"
}
```

#### Slash Commands API

```
POST /api/chat/command
Request:
{
    "session_id": "uuid",
    "command": "/diagnose",
    "args": "high memory usage on db-server-01",
    "context": {
        "server_id": "uuid",
        "selected_text": null
    }
}
Response (200):
{
    "command_executed": "/diagnose",
    "agent_triggered": true,
    "plan_created": true,
    "plan_id": "uuid"
}

GET /api/chat/commands
Response (200):
{
    "commands": [
        {
            "name": "/diagnose",
            "description": "Start diagnostic investigation",
            "args": "<issue description>",
            "example": "/diagnose high CPU on web-01"
        },
        {
            "name": "/fix",
            "description": "Apply a fix with confirmation",
            "args": "<what to fix>",
            "example": "/fix restart nginx service"
        },
        {
            "name": "/explain",
            "description": "Explain a command or concept",
            "args": "<command or topic>",
            "example": "/explain iptables -L"
        },
        {
            "name": "/plan",
            "description": "Create or show current plan",
            "args": "[show|create|edit]",
            "example": "/plan show"
        },
        {
            "name": "/rollback",
            "description": "Rollback last change set",
            "args": "[change_set_id]",
            "example": "/rollback"
        }
    ]
}
```

### 3.4 UI/UX Changes

#### 3.4.1 File Viewer Panel

```
┌─────────────────────────────────────────────────────────────────┐
│ File: /etc/nginx/nginx.conf                    [Edit] [History]│
├─────────────────────────────────────────────────────────────────┤
│  1 │ user nginx;                                                │
│  2 │ worker_processes auto;                                     │
│  3 │                                                            │
│  4 │ events {                                                   │
│  5 │     worker_connections 1024;   ← AI suggests: 2048         │
│  6 │ }                                                          │
│  7 │                                                            │
│  8 │ http {                                                     │
│    │ ... (syntax highlighted, line numbers)                     │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.4.2 Inline Diff Panel

```
┌─────────────────────────────────────────────────────────────────┐
│ Proposed Changes (3 files)              [Accept All] [Reject All]
├─────────────────────────────────────────────────────────────────┤
│ ▼ /etc/nginx/nginx.conf                    [Accept] [Reject]   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ @@ -5,1 +5,1 @@                                         │   │
│   │ -    worker_connections 1024;                           │   │
│   │ +    worker_connections 2048;                           │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ ▶ /etc/nginx/sites-enabled/default         [Accept] [Reject]   │
│ ▶ /var/log/nginx/error.log (view only)                         │
├─────────────────────────────────────────────────────────────────┤
│ Summary: +15 lines, -8 lines across 2 files                     │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.4.3 Plan Editor Panel

```
┌─────────────────────────────────────────────────────────────────┐
│ Plan: Fix High CPU on web-server-01          [Edit] [Abandon]  │
├─────────────────────────────────────────────────────────────────┤
│ Progress: ████████░░░░░░░░ 45%                                  │
│                                                                 │
│ ✓ Phase 1: Identify                                             │
│   ✓ Confirmed target: web-server-01 (Ubuntu 22.04)             │
│                                                                 │
│ ✓ Phase 2: Verify                                               │
│   ✓ SSH connection established                                  │
│                                                                 │
│ ● Phase 3: Investigate (in progress)                            │
│   ✓ Checked top processes - mysql at 89% CPU                   │
│   ○ Query slow log analysis                                     │
│   ○ Check for table locks                                       │
│                                                                 │
│ ○ Phase 4: Plan                                                 │
│   ○ Form hypothesis                                             │
│                                                                 │
│ ○ Phase 5: Act                                                  │
│   ○ Execute remediation                                         │
├─────────────────────────────────────────────────────────────────┤
│ [+ Add Step] [↩ Revise Plan] [→ Skip to Phase]                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.4.4 Agent HQ View

```
┌─────────────────────────────────────────────────────────────────┐
│ Agent HQ                                    [+ New Agent]       │
├─────────────────────────────────────────────────────────────────┤
│ Active Agents (2/3)                                             │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🔵 Local Agent                                    [Pause]   │ │
│ │    Goal: Investigate memory leak                            │ │
│ │    Status: Waiting for user input                           │ │
│ │    Current: Suggested command awaiting approval             │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🟢 Background Agent                               [Stop]    │ │
│ │    Goal: Run test suite and fix failures                    │ │
│ │    Status: Running (iteration 3/10)                         │ │
│ │    Current: Fixing test_auth.py:45                          │ │
│ │    Progress: ████████████░░░░░░ 67%                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ Completed (1)                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ✅ Background Agent                              [Details]  │ │
│ │    Goal: Analyze log patterns                               │ │
│ │    Result: Found 3 error patterns, report ready             │ │
│ │    Duration: 4m 32s                                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Pending Handoffs                                                │
│ • Background → Local: "Needs approval for schema migration"    │
│   [Accept Handoff] [View Context]                               │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.4.5 Chat with Slash Commands

```
┌─────────────────────────────────────────────────────────────────┐
│ Chat                                           [@] [/] [#]      │
├─────────────────────────────────────────────────────────────────┤
│ User: /diagnose high cpu on web-server-01                       │
│                                                                 │
│ 🤖 Assistant:                                                   │
│ Starting diagnostic investigation for high CPU on web-server-01│
│                                                                 │
│ 📋 Plan created: "Diagnose High CPU"                            │
│ ┌─────────────────────────────────────┐                         │
│ │ ○ Check top processes               │                         │
│ │ ○ Analyze CPU metrics (Grafana)     │                         │
│ │ ○ Review recent deployments         │                         │
│ │ ○ Check for runaway queries         │                         │
│ └─────────────────────────────────────┘                         │
│                                                                 │
│ 🔍 Phase 1: Identifying target...                               │
│ ✅ Target confirmed: web-server-01 (Ubuntu 22.04)              │
│                                                                 │
│ 📊 Fetching CPU metrics from Grafana...                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ / ▌                                                             │
│ ┌─────────────────────────────────────┐                         │
│ │ /diagnose - Start investigation     │                         │
│ │ /fix - Apply a fix                  │                         │
│ │ /explain - Explain command          │                         │
│ │ /plan - Show/edit plan              │                         │
│ │ /rollback - Undo changes            │                         │
│ └─────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### 3.5 Security and Privacy Considerations

| Concern | Mitigation |
|---------|------------|
| **File content exposure** | All file reads go through SSH with existing auth; content not logged |
| **Backup storage** | Backups stored on remote server in temp directory with auto-expiry |
| **Change set persistence** | Diff content encrypted at rest; purged after 24 hours |
| **Background agent isolation** | Runs in separate worktree; no access to production without approval |
| **Credential handling** | No credentials stored in change sets or file versions |
| **Rollback authorization** | Rollback requires same auth level as original change |
| **Multi-agent access** | Each agent inherits session permissions; no escalation |
| **Command injection** | All file paths validated; no shell interpolation in file ops |

---

## 4. Implementation Plan

### Phase 1: File Operations Foundation

#### Task 1.1: File Operations Service

| Attribute | Value |
|-----------|-------|
| **Description** | Create service layer for reading, previewing edits, and managing file versions via SSH |
| **Files to create** | `app/services/file_ops_service.py` |
| **Files to modify** | `app/services/__init__.py` |
| **Interfaces** | SSH client integration |
| **Complexity** | Medium |
| **Dependencies** | Existing SSHClient |

**Key interfaces:**

```python
class FileOpsService:
    def __init__(self, db: Session, ssh_client: SSHClient): ...

    async def read_file(
        self, server_id: UUID, file_path: str,
        line_start: int = 1, line_end: int = None
    ) -> FileContent: ...

    async def preview_edit(
        self, server_id: UUID, file_path: str,
        changes: List[FileChange]
    ) -> DiffPreview: ...

    async def create_backup(
        self, server_id: UUID, file_path: str
    ) -> FileBackup: ...

    async def apply_changes(
        self, change_set_id: UUID,
        items: List[UUID] = None
    ) -> ApplyResult: ...

    async def rollback(
        self, change_set_id: UUID
    ) -> RollbackResult: ...
```

---

#### Task 1.2: Change Set Model and Service

| Attribute | Value |
|-----------|-------|
| **Description** | Database models and service for managing atomic change sets |
| **Files to create** | `app/models_changeset.py`, `app/services/changeset_service.py`, `app/schemas_changeset.py` |
| **Files to modify** | `app/models/__init__.py` |
| **Interfaces** | Database migrations |
| **Complexity** | Medium |
| **Dependencies** | Task 1.1 |

**Key interfaces:**

```python
# models_changeset.py
class ChangeSet(Base):
    __tablename__ = "change_sets"
    id: UUID
    session_id: UUID
    title: str
    status: ChangeSetStatus  # Enum
    items: List[ChangeItem]

class ChangeItem(Base):
    __tablename__ = "change_items"
    id: UUID
    change_set_id: UUID
    file_path: str
    operation: FileOperation  # Enum: create, modify, delete
    old_content: str
    new_content: str
    diff_hunks: dict
    status: ChangeItemStatus

# schemas_changeset.py
class ChangeSetCreate(BaseModel): ...
class ChangeSetResponse(BaseModel): ...
class DiffHunk(BaseModel):
    start_line: int
    end_line: int
    old_lines: List[str]
    new_lines: List[str]
```

---

#### Task 1.3: File Operations API Router

| Attribute | Value |
|-----------|-------|
| **Description** | REST API endpoints for file operations |
| **Files to create** | `app/routers/file_ops_api.py` |
| **Files to modify** | `app/main.py` (register router) |
| **Interfaces** | REST API |
| **Complexity** | Medium |
| **Dependencies** | Task 1.1, 1.2 |

**Endpoints:**
- `POST /api/files/read`
- `POST /api/files/preview-edit`
- `POST /api/files/apply-changes`
- `POST /api/files/rollback`
- `GET /api/files/versions/{file_path}`
- `GET /api/changesets/{change_set_id}`

---

#### Task 1.4: Database Migration for File Operations

| Attribute | Value |
|-----------|-------|
| **Description** | Alembic migration for file_versions, file_backups, change_sets, change_items tables |
| **Files to create** | `alembic/versions/xxx_add_file_operations_tables.py` |
| **Interfaces** | Database schema |
| **Complexity** | Low |
| **Dependencies** | None |

---

#### Task 1.5: Frontend File Viewer Component

| Attribute | Value |
|-----------|-------|
| **Description** | JavaScript component for displaying file content with syntax highlighting |
| **Files to create** | `static/js/components/file_viewer.js`, `static/css/file_viewer.css` |
| **Files to modify** | `static/js/ai_chat.js`, `templates/ai_chat.html` |
| **Interfaces** | DOM, File Ops API |
| **Complexity** | High |
| **Dependencies** | Task 1.3, highlight.js library |

**Key functions:**

```javascript
class FileViewer {
    constructor(containerId, options = {}) {}

    async loadFile(serverId, filePath, options = {}) {}
    renderContent(content, syntax) {}
    highlightLines(startLine, endLine, className) {}
    showLineAnnotation(line, message, type) {}
    getSelectedLines() {}
    dispose() {}
}
```

---

#### Task 1.6: Frontend Diff Panel Component

| Attribute | Value |
|-----------|-------|
| **Description** | Component for showing proposed changes with accept/reject per hunk |
| **Files to create** | `static/js/components/diff_panel.js`, `static/css/diff_panel.css` |
| **Files to modify** | `static/js/ai_chat.js` |
| **Interfaces** | DOM, Change Set API |
| **Complexity** | High |
| **Dependencies** | Task 1.3, diff2html library |

**Key functions:**

```javascript
class DiffPanel {
    constructor(containerId) {}

    async loadChangeSet(changeSetId) {}
    renderDiff(changeItems) {}
    acceptItem(itemId) {}
    rejectItem(itemId) {}
    acceptAll() {}
    rejectAll() {}
    async applyAccepted() {}

    onAccept(callback) {}
    onReject(callback) {}
    onApply(callback) {}
}
```

---

### Phase 2: Planning System

#### Task 2.1: Plan Models and Service

| Attribute | Value |
|-----------|-------|
| **Description** | Database models and service for persistent, hierarchical plans |
| **Files to create** | `app/models_plan.py`, `app/services/plan_service.py`, `app/schemas_plan.py` |
| **Files to modify** | `app/models/__init__.py` |
| **Complexity** | Medium |
| **Dependencies** | None |

**Key interfaces:**

```python
class PlanService:
    def __init__(self, db: Session): ...

    def create_plan(
        self, session_id: UUID, title: str,
        initial_steps: List[PlanStepCreate] = None
    ) -> Plan: ...

    def add_step(
        self, plan_id: UUID, step: PlanStepCreate,
        parent_step_id: UUID = None
    ) -> PlanStep: ...

    def update_step_status(
        self, step_id: UUID, status: StepStatus,
        notes: str = None
    ) -> PlanStep: ...

    def revise_plan(
        self, plan_id: UUID, return_to_phase: str,
        new_steps: List[PlanStepCreate]
    ) -> Plan: ...

    def to_markdown(self, plan_id: UUID) -> str: ...

    def get_progress(self, plan_id: UUID) -> PlanProgress: ...
```

---

#### Task 2.2: Plan API Router

| Attribute | Value |
|-----------|-------|
| **Description** | REST API for plan CRUD and progression |
| **Files to create** | `app/routers/plan_api.py` |
| **Files to modify** | `app/main.py` |
| **Complexity** | Low |
| **Dependencies** | Task 2.1 |

---

#### Task 2.3: Database Migration for Plans

| Attribute | Value |
|-----------|-------|
| **Description** | Alembic migration for plans and plan_steps tables |
| **Files to create** | `alembic/versions/xxx_add_plan_tables.py` |
| **Complexity** | Low |
| **Dependencies** | None |

---

#### Task 2.4: Integrate Plans with Agent

| Attribute | Value |
|-----------|-------|
| **Description** | Modify NativeToolAgent to create and update plans during execution |
| **Files to modify** | `app/services/agentic/native_agent.py`, `app/services/agentic/prompts.py` |
| **Complexity** | Medium |
| **Dependencies** | Task 2.1 |

**Changes:**
- Agent creates plan at start of troubleshooting
- Each phase transition updates plan
- Tool calls create plan steps
- Plan revised on hypothesis change

---

#### Task 2.5: Allow Phase Revisit in Workflow

| Attribute | Value |
|-----------|-------|
| **Description** | Modify phase enforcement to allow backward transitions with reason |
| **Files to modify** | `app/services/agentic/native_agent.py`, `app/schemas_ai.py` |
| **Complexity** | Medium |
| **Dependencies** | Task 2.4 |

**Changes:**
- Add `can_return_to_phase()` method
- Track phase history
- Require reason for phase revisit
- Update plan on revisit

---

#### Task 2.6: Frontend Plan Editor Component

| Attribute | Value |
|-----------|-------|
| **Description** | Interactive plan display with progress, editing, and phase navigation |
| **Files to create** | `static/js/components/plan_editor.js`, `static/css/plan_editor.css` |
| **Files to modify** | `static/js/ai_chat.js`, `templates/ai_chat.html` |
| **Complexity** | High |
| **Dependencies** | Task 2.2 |

---

### Phase 3: Auto-Iteration Loop

#### Task 3.1: Terminal Output Capture Service

| Attribute | Value |
|-----------|-------|
| **Description** | Service to capture and analyze terminal output automatically |
| **Files to create** | `app/services/output_capture_service.py` |
| **Files to modify** | `app/services/ssh_service.py` |
| **Complexity** | Medium |
| **Dependencies** | Existing SSH service |

**Key interfaces:**

```python
class OutputCaptureService:
    def __init__(self, ssh_client: SSHClient): ...

    async def execute_and_capture(
        self, command: str, timeout: int = 60
    ) -> CommandResult: ...

    def analyze_output(
        self, output: str, exit_code: int
    ) -> OutputAnalysis: ...

    def detect_errors(
        self, output: str
    ) -> List[DetectedError]: ...

    def suggest_fix(
        self, error: DetectedError
    ) -> Optional[str]: ...

@dataclass
class OutputAnalysis:
    success: bool
    error_type: Optional[str]  # 'syntax', 'permission', 'not_found', 'timeout', etc.
    error_message: Optional[str]
    suggested_fix: Optional[str]
    requires_user_input: bool
```

---

#### Task 3.2: Iteration Loop Model and Service

| Attribute | Value |
|-----------|-------|
| **Description** | Track iteration attempts and auto-fix history |
| **Files to create** | `app/models_iteration.py`, `app/services/iteration_service.py` |
| **Complexity** | Medium |
| **Dependencies** | Task 3.1 |

**Key interfaces:**

```python
class IterationService:
    def __init__(self, db: Session, capture_service: OutputCaptureService): ...

    async def execute_with_retry(
        self, agent_step_id: UUID,
        command: str,
        max_iterations: int = 5,
        auto_fix: bool = True
    ) -> IterationResult: ...

    async def should_retry(
        self, iteration: IterationLoop
    ) -> Tuple[bool, Optional[str]]: ...

    def get_iteration_history(
        self, agent_step_id: UUID
    ) -> List[IterationLoop]: ...
```

---

#### Task 3.3: Database Migration for Iteration Tracking

| Attribute | Value |
|-----------|-------|
| **Description** | Alembic migration for iteration_loops table |
| **Files to create** | `alembic/versions/xxx_add_iteration_loops.py` |
| **Complexity** | Low |
| **Dependencies** | None |

---

#### Task 3.4: Integrate Auto-Iteration with Agent

| Attribute | Value |
|-----------|-------|
| **Description** | Modify agent to use auto-iteration when enabled |
| **Files to modify** | `app/services/agentic/native_agent.py`, `app/routers/agent_api.py` |
| **Complexity** | High |
| **Dependencies** | Task 3.1, 3.2 |

**Changes:**
- Add `auto_iterate` flag to agent session
- After command execution, check for errors
- Auto-retry with LLM-suggested fixes
- Cap iterations at `max_auto_iterations`
- Handoff to user on persistent failures

---

#### Task 3.5: Frontend Iteration Progress Display

| Attribute | Value |
|-----------|-------|
| **Description** | Show iteration progress and auto-fix attempts in UI |
| **Files to modify** | `static/js/ai_chat.js`, `static/css/ai_chat.css` |
| **Complexity** | Medium |
| **Dependencies** | Task 3.4 |

---

### Phase 4: Multi-Agent Orchestration

#### Task 4.1: Agent Pool and Task Models

| Attribute | Value |
|-----------|-------|
| **Description** | Database models for agent pools and task management |
| **Files to create** | `app/models_agent_pool.py` |
| **Files to modify** | `app/models_agent.py` |
| **Complexity** | Medium |
| **Dependencies** | None |

---

#### Task 4.2: Agent Orchestrator Service

| Attribute | Value |
|-----------|-------|
| **Description** | Service to manage multiple agents, spawn background agents, handle handoffs |
| **Files to create** | `app/services/agent_orchestrator.py` |
| **Complexity** | High |
| **Dependencies** | Task 4.1, existing agent services |

**Key interfaces:**

```python
class AgentOrchestrator:
    def __init__(self, db: Session): ...

    async def create_pool(
        self, session_id: UUID, name: str,
        max_concurrent: int = 3
    ) -> AgentPool: ...

    async def spawn_agent(
        self, pool_id: UUID,
        agent_type: AgentType,  # Enum: local, background
        goal: str,
        **config
    ) -> AgentTask: ...

    async def handoff(
        self, from_task_id: UUID,
        to_agent_type: AgentType,
        context_summary: str
    ) -> AgentTask: ...

    async def get_hq_status(
        self, session_id: UUID
    ) -> HQStatus: ...

    async def stop_agent(
        self, task_id: UUID
    ) -> bool: ...
```

---

#### Task 4.3: Background Agent Worker

| Attribute | Value |
|-----------|-------|
| **Description** | Background worker that runs agents in isolated context |
| **Files to create** | `app/workers/background_agent_worker.py` |
| **Complexity** | High |
| **Dependencies** | Task 4.1, 4.2 |

**Key features:**
- Runs in separate process/thread
- Creates worktree for isolation
- Reports progress via WebSocket
- Handles graceful shutdown

---

#### Task 4.4: Database Migration for Multi-Agent

| Attribute | Value |
|-----------|-------|
| **Description** | Alembic migration for agent_pools, agent_tasks tables and agent_sessions modifications |
| **Files to create** | `alembic/versions/xxx_add_multi_agent_tables.py` |
| **Complexity** | Low |
| **Dependencies** | None |

---

#### Task 4.5: Multi-Agent API Router

| Attribute | Value |
|-----------|-------|
| **Description** | REST and WebSocket API for multi-agent operations |
| **Files to create** | `app/routers/agent_hq_api.py` |
| **Files to modify** | `app/main.py` |
| **Complexity** | Medium |
| **Dependencies** | Task 4.2 |

---

#### Task 4.6: Frontend Agent HQ View

| Attribute | Value |
|-----------|-------|
| **Description** | Dashboard for viewing and managing multiple agents |
| **Files to create** | `static/js/components/agent_hq.js`, `static/css/agent_hq.css` |
| **Files to modify** | `static/js/ai_chat.js`, `templates/ai_chat.html` |
| **Complexity** | High |
| **Dependencies** | Task 4.5 |

---

### Phase 5: Chat UX Enhancements

#### Task 5.1: Slash Command Registry and Parser

| Attribute | Value |
|-----------|-------|
| **Description** | System for registering and parsing slash commands |
| **Files to create** | `app/services/slash_commands.py` |
| **Complexity** | Medium |
| **Dependencies** | None |

**Key interfaces:**

```python
class SlashCommandRegistry:
    commands: Dict[str, SlashCommand]

    def register(self, command: SlashCommand): ...
    def parse(self, input_text: str) -> Optional[ParsedCommand]: ...
    def get_completions(self, prefix: str) -> List[str]: ...

@dataclass
class SlashCommand:
    name: str  # e.g., "/diagnose"
    description: str
    args_pattern: str
    handler: Callable
    requires_server: bool = True

# Built-in commands
DIAGNOSE_COMMAND = SlashCommand(
    name="/diagnose",
    description="Start diagnostic investigation",
    args_pattern="<issue description>",
    handler=handle_diagnose
)
```

---

#### Task 5.2: Chat Participant System

| Attribute | Value |
|-----------|-------|
| **Description** | System for @-mentionable context providers |
| **Files to create** | `app/services/chat_participants.py` |
| **Complexity** | Medium |
| **Dependencies** | Existing tool registry |

**Key interfaces:**

```python
class ChatParticipant:
    name: str  # e.g., "@server"
    description: str
    context_provider: Callable[[str], str]

class ParticipantRegistry:
    participants: Dict[str, ChatParticipant]

    def get_context(
        self, mentions: List[str], args: Dict
    ) -> str: ...

# Built-in participants
SERVER_PARTICIPANT = ChatParticipant(
    name="@server",
    description="Current server context",
    context_provider=get_server_context
)

LOGS_PARTICIPANT = ChatParticipant(
    name="@logs",
    description="Recent log entries",
    context_provider=get_recent_logs
)
```

---

#### Task 5.3: Context Variable System

| Attribute | Value |
|-----------|-------|
| **Description** | #file, #output, #error variable references |
| **Files to create** | `app/services/context_variables.py` |
| **Files to modify** | `app/services/agentic/native_agent.py` |
| **Complexity** | Low |
| **Dependencies** | None |

---

#### Task 5.4: Slash Command API

| Attribute | Value |
|-----------|-------|
| **Description** | API endpoint for executing slash commands |
| **Files to create** | None |
| **Files to modify** | `app/routers/chat_api.py` |
| **Complexity** | Low |
| **Dependencies** | Task 5.1 |

---

#### Task 5.5: Frontend Command Autocomplete

| Attribute | Value |
|-----------|-------|
| **Description** | Autocomplete dropdown for slash commands and participants |
| **Files to modify** | `static/js/ai_chat.js`, `static/css/ai_chat.css` |
| **Complexity** | Medium |
| **Dependencies** | Task 5.1, 5.2 |

---

## 5. Testing

### Unit Tests

| Test File | Test Name | Asserts |
|-----------|-----------|---------|
| `tests/test_file_ops_service.py` | `test_read_file_success` | Returns content with line numbers |
| | `test_read_file_not_found` | Raises FileNotFoundError |
| | `test_preview_edit_generates_diff` | Diff hunks match expected |
| | `test_create_backup` | Backup file created on remote |
| | `test_apply_changes_modifies_file` | File content updated |
| | `test_rollback_restores_backup` | Original content restored |
| `tests/test_changeset_service.py` | `test_create_changeset` | ChangeSet persisted with items |
| | `test_accept_item` | Item status updated |
| | `test_reject_item` | Item excluded from apply |
| | `test_apply_partial` | Only accepted items applied |
| `tests/test_plan_service.py` | `test_create_plan` | Plan with steps persisted |
| | `test_add_hierarchical_step` | Parent-child relationship correct |
| | `test_update_step_status` | Status and timestamp updated |
| | `test_revise_plan` | New steps added, phase reset |
| | `test_to_markdown` | Valid markdown output |
| `tests/test_iteration_service.py` | `test_execute_success` | Single iteration, success |
| | `test_execute_retry_on_error` | Retries up to max |
| | `test_detect_syntax_error` | Error type identified |
| | `test_detect_permission_error` | Suggests sudo fix |
| `tests/test_agent_orchestrator.py` | `test_create_pool` | Pool persisted with limits |
| | `test_spawn_local_agent` | Agent session created |
| | `test_spawn_background_agent` | Worker process started |
| | `test_handoff_transfers_context` | New task has parent context |
| | `test_pool_respects_max_concurrent` | Queues when at limit |
| `tests/test_slash_commands.py` | `test_parse_diagnose` | Command and args extracted |
| | `test_parse_with_quotes` | Quoted args preserved |
| | `test_unknown_command` | Returns None |
| | `test_get_completions` | Matching commands returned |

### Integration Tests

| Test File | Scenario | Expected Outcome |
|-----------|----------|------------------|
| `tests/integration/test_file_ops_flow.py` | User previews edit, accepts, applies | File modified on remote server |
| | User previews edit, rejects, no change | File unchanged |
| | User applies, then rolls back | File restored to original |
| `tests/integration/test_plan_flow.py` | Agent creates plan during troubleshooting | Plan visible with steps |
| | Agent revises plan on failure | New steps added, phase returns |
| `tests/integration/test_auto_iteration.py` | Command fails, auto-fix succeeds | Iteration count = 2, success |
| | Command fails 5 times | Handoff to user |
| `tests/integration/test_multi_agent.py` | Spawn background agent | Agent runs in background |
| | Background agent completes | Result available in HQ |
| | Handoff background to local | Context transferred |

### End-to-End Tests

| Test File | Scenario | Expected Outcome |
|-----------|----------|------------------|
| `tests/e2e/test_full_troubleshooting.py` | User types "/diagnose high cpu" | Plan created, investigation runs, commands suggested |
| `tests/e2e/test_file_edit_flow.py` | AI suggests config change | Diff shown, user accepts, file modified |
| `tests/e2e/test_background_agent.py` | User spawns background test runner | Tests run, failures fixed, report shown |

### Test Fixtures

```python
# tests/fixtures/ssh_mock.py
class MockSSHClient:
    """Mock SSH client for testing without real servers"""
    files: Dict[str, str]  # Simulated file system

    async def execute(self, command: str) -> Tuple[str, int]: ...
    async def read_file(self, path: str) -> str: ...
    async def write_file(self, path: str, content: str): ...

# tests/fixtures/sample_files.py
NGINX_CONF = """
user nginx;
worker_processes auto;
...
"""

NGINX_CONF_MODIFIED = """
user nginx;
worker_processes 4;
...
"""
```

---

## 6. Acceptance Criteria

### Feature: File Operations

- [ ] User can view file contents with syntax highlighting in File Viewer panel
- [ ] AI can propose file changes that appear in Diff Panel
- [ ] User can accept/reject individual change items
- [ ] Accepted changes are applied atomically to remote server
- [ ] User can rollback applied changes within 24 hours
- [ ] File versions are tracked and viewable

### Feature: Planning System

- [ ] Plan is automatically created at start of troubleshooting
- [ ] Plan steps are visible in Plan Editor panel
- [ ] Plan progress updates in real-time as agent works
- [ ] User can manually add/remove plan steps
- [ ] Agent can revise plan and return to earlier phase
- [ ] Plan exports to valid markdown

### Feature: Auto-Iteration

- [ ] Agent automatically captures command output
- [ ] Failed commands trigger auto-retry with fix
- [ ] Iteration history visible in UI
- [ ] Max iterations respected (default 5)
- [ ] Handoff to user on persistent failure

### Feature: Multi-Agent

- [ ] User can spawn background agent from Agent HQ
- [ ] Multiple agents run concurrently (up to pool limit)
- [ ] Background agent progress visible in real-time
- [ ] Handoff transfers context between agents
- [ ] User can stop any agent

### Feature: Chat UX

- [ ] Slash commands show autocomplete on `/` key
- [ ] `/diagnose`, `/fix`, `/explain`, `/plan`, `/rollback` work
- [ ] Chat participants `@server`, `@logs` inject context
- [ ] Context variables `#file`, `#output` resolve correctly

### Manual Test Checklist

1. [ ] Start new session, type `/diagnose high cpu`
2. [ ] Verify plan appears in Plan Editor
3. [ ] Wait for AI to suggest a command
4. [ ] Verify command card appears with safety indicator
5. [ ] Execute command, verify output captured automatically
6. [ ] Verify AI continues without prompting for output
7. [ ] When AI suggests file edit, verify Diff Panel shows changes
8. [ ] Accept one change, reject another
9. [ ] Apply changes, verify file modified on server
10. [ ] Click rollback, verify file restored
11. [ ] Spawn background agent with goal "run all tests"
12. [ ] Verify Agent HQ shows progress
13. [ ] Wait for completion, verify results in HQ
14. [ ] Test handoff from background to local agent

---

## 7. Developer Notes

### Known Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **SSH connection limits** | Background agents may exhaust connections | Pool connections; limit concurrent agents |
| **Large file handling** | Memory issues with big files | Stream file reads; paginate content |
| **Diff generation performance** | Slow for large changes | Use efficient diff library (difflib); cache results |
| **Background agent runaway** | Resource exhaustion | Strict timeouts; max iterations; auto-kill |
| **WebSocket disconnection** | Lost progress updates | Reconnection logic; persist state to DB |
| **Concurrent change conflicts** | Race conditions on same file | Locking mechanism; version checks before apply |
| **Breaking existing API** | Client compatibility issues | Version API; maintain backward compat |

### Performance Considerations

- File content should be fetched on-demand, not preloaded
- Diff computation should happen server-side
- WebSocket messages should be throttled (max 10/sec)
- Background agents should yield CPU periodically
- Database queries should use connection pooling

### Configuration Keys

```python
# config.py additions
FILE_OPS_BACKUP_RETENTION_HOURS = 24
FILE_OPS_MAX_FILE_SIZE_MB = 10
PLAN_AUTO_CREATE = True
PLAN_MAX_STEPS = 50
ITERATION_MAX_RETRIES = 5
ITERATION_RETRY_DELAY_SEC = 2
AGENT_POOL_MAX_CONCURRENT = 3
AGENT_BACKGROUND_TIMEOUT_SEC = 600
SLASH_COMMAND_PREFIX = "/"
CHAT_PARTICIPANT_PREFIX = "@"
```

### Dependencies to Add

```
# requirements.txt additions
diff-match-patch>=20230430  # For diff generation
Pygments>=2.17.0            # For syntax highlighting
```

---

## DONE - Immediate Next Steps

1. [ ] **Create database migrations** - Run Task 1.4, 2.3, 3.3, 4.4 to set up all new tables
2. [ ] **Implement FileOpsService** - Task 1.1 is foundational; blocks all file operation features
3. [ ] **Implement ChangeSetService** - Task 1.2 enables atomic operations and diff tracking
4. [ ] **Build File Viewer component** - Task 1.5 provides UI for file content display
5. [ ] **Build Diff Panel component** - Task 1.6 enables accept/reject workflow for changes
