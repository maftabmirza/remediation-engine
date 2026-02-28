# Implementation Plan: Three-Pillar LLM Integration with RBAC

## 1. Overview

### Summary
This plan implements a three-pillar LLM integration system for the Remediation-Engine platform: **AI Inquiry** (analytics/historical queries), **Troubleshooting** (interactive diagnostic assistance), and **RE-VIVE** (unified AI assistant for both Grafana stack control AND AIOps page interactions). The system integrates MCP Grafana for enhanced Grafana capabilities while maintaining custom tools for platform-specific operations. A comprehensive RBAC model ensures users can only access features and execute actions appropriate to their role.

### High-Level Success Criteria
- Users can ask historical questions about alerts, incidents, and metrics via AI Inquiry
- On-call engineers receive AI-assisted troubleshooting with real-time data gathering
- RE-VIVE provides unified AI control over Grafana stack (dashboards, alerts, queries) AND AIOps pages (runbooks, servers, settings)
- All AI features respect RBAC permissions - users cannot perform actions beyond their role
- MCP Grafana integration provides 20+ Grafana tools without custom implementation
- Audit trail captures all AI-initiated actions with user attribution

---

## 2. Scope

### Included
- MCP Grafana client library implementation
- AI Inquiry orchestrator and read-only tools
- Troubleshooting enhancement with MCP tools (Sift, OnCall, Traces)
- RE-VIVE unified orchestrator for Grafana + AIOps
- RBAC permission model for all AI features
- Tool registry extensions for each pillar
- API endpoints for all three pillars
- WebSocket streaming for real-time responses
- Action confirmation workflows for destructive operations
- Audit logging for AI-initiated actions

### Out of Scope
- Grafana LLM App integration (different paradigm, not needed)
- Custom MCP server development (using existing mcp-grafana)
- Mobile UI for AI features
- Voice interface
- Multi-tenant deployment (single organization assumed)
- Integration with external ITSM beyond existing connectors

---

## 3. Design

### 3.1 Architecture Diagram (Textual)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   AI Inquiry    │  │ Troubleshooting │  │         RE-VIVE             │  │
│  │   /inquiry      │  │ /alerts/{id}/   │  │    /revive (unified)        │  │
│  │                 │  │     chat        │  │  ┌─────────┬─────────────┐  │  │
│  │  [Analytics UI] │  │ [Chat UI]       │  │  │ Grafana │   AIOps     │  │  │
│  │                 │  │                 │  │  │  Mode   │   Mode      │  │  │
│  └────────┬────────┘  └────────┬────────┘  │  └────┬────┴──────┬──────┘  │  │
│           │                    │           └───────┼───────────┼─────────┘  │
└───────────┼────────────────────┼───────────────────┼───────────┼────────────┘
            │                    │                   │           │
            ▼                    ▼                   ▼           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER (FastAPI)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        RBAC MIDDLEWARE                               │   │
│  │  • Validates JWT token                                               │   │
│  │  • Extracts user role (admin, operator, engineer, viewer)            │   │
│  │  • Injects permissions into request context                          │   │
│  │  • Blocks unauthorized pillar/tool access                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│           ┌────────────────────────┼────────────────────────┐              │
│           ▼                        ▼                        ▼              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐    │
│  │    Inquiry      │    │ Troubleshooting │    │      RE-VIVE        │    │
│  │   Router        │    │    Router       │    │      Router         │    │
│  │ /api/v1/inquiry │    │ /api/v1/alerts/ │    │  /api/v1/revive     │    │
│  │                 │    │   {id}/chat     │    │                     │    │
│  └────────┬────────┘    └────────┬────────┘    └──────────┬──────────┘    │
│           │                      │                        │               │
└───────────┼──────────────────────┼────────────────────────┼───────────────┘
            │                      │                        │
            ▼                      ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR LAYER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐     │
│  │    Inquiry      │    │ Troubleshooting │    │      RE-VIVE        │     │
│  │  Orchestrator   │    │  Orchestrator   │    │    Orchestrator     │     │
│  │                 │    │   (existing +   │    │                     │     │
│  │  • Query        │    │    enhanced)    │    │  • Mode detection   │     │
│  │    classification│   │                 │    │    (grafana/aiops)  │     │
│  │  • Multi-step   │    │  • Alert context│    │  • Action confirm   │     │
│  │    reasoning    │    │  • Tool selection│   │  • Permission check │     │
│  │  • Response     │    │  • Command safety│   │  • Audit logging    │     │
│  │    formatting   │    │                 │    │                     │     │
│  └────────┬────────┘    └────────┬────────┘    └──────────┬──────────┘     │
│           │                      │                        │                │
└───────────┼──────────────────────┼────────────────────────┼────────────────┘
            │                      │                        │
            ▼                      ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TOOL REGISTRY LAYER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                    PERMISSION-AWARE TOOL REGISTRY                  │     │
│  │  • Each tool has required_permission attribute                     │     │
│  │  • Registry filters tools based on user role                       │     │
│  │  • Execution blocked if permission denied                          │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                    │                                        │
│  ┌─────────────────────────────────┼─────────────────────────────────┐     │
│  │                                 │                                  │     │
│  ▼                                 ▼                                  ▼     │
│  INQUIRY TOOLS          TROUBLESHOOTING TOOLS           RE-VIVE TOOLS       │
│  (read-only)            (read + suggest)                (read + write)      │
│  ├─query_alerts_history ├─get_alert_details            GRAFANA MODE:       │
│  ├─query_incidents      ├─get_similar_incidents        ├─search_dashboards │
│  ├─get_mttr_stats       ├─suggest_ssh_command          ├─create_dashboard  │
│  ├─get_alert_trends     ├─get_runbook                  ├─update_dashboard  │
│  ├─correlate_changes    ├─investigate_sift (MCP)       ├─delete_dashboard  │
│  └─get_timeline         ├─get_oncall (MCP)             ├─create_alert_rule │
│                         └─query_tempo (MCP)            ├─list_alert_rules  │
│                                                        ├─create_annotation │
│                                                        └─query_prometheus  │
│                                                        AIOPS MODE:         │
│                                                        ├─manage_runbooks   │
│                                                        ├─manage_servers    │
│                                                        ├─manage_credentials│
│                                                        ├─execute_runbook   │
│                                                        ├─manage_rules      │
│                                                        └─view_audit_logs   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
            │                      │                        │
            ▼                      ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND SERVICES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐     │
│  │   PostgreSQL    │    │   MCP Grafana   │    │   Existing Services │     │
│  │   (alerts,      │    │     Client      │    │                     │     │
│  │    incidents,   │    │                 │    │  • PrometheusClient │     │
│  │    executions)  │    │  Connects to:   │    │  • LokiClient       │     │
│  │                 │    │  mcp-grafana    │    │  • ExecutionWorker  │     │
│  │                 │    │  server         │    │  • RunbookService   │     │
│  └─────────────────┘    └────────┬────────┘    └─────────────────────┘     │
│                                  │                                          │
│                                  ▼                                          │
│                         ┌─────────────────┐                                │
│                         │ Grafana Instance│                                │
│                         │ (Prometheus,    │                                │
│                         │  Loki, Tempo,   │                                │
│                         │  OnCall, Sift)  │                                │
│                         └─────────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Model Changes

#### New Tables

**Table: `ai_sessions`**
```sql
CREATE TABLE ai_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    pillar VARCHAR(20) NOT NULL CHECK (pillar IN ('inquiry', 'troubleshooting', 'revive')),
    revive_mode VARCHAR(20) CHECK (revive_mode IN ('grafana', 'aiops', NULL)),
    context_type VARCHAR(50),  -- 'alert', 'dashboard', 'runbook', etc.
    context_id UUID,           -- Reference to contextual entity
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ai_sessions_user ON ai_sessions(user_id);
CREATE INDEX idx_ai_sessions_pillar ON ai_sessions(pillar);
```

**Table: `ai_messages`**
```sql
CREATE TABLE ai_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES ai_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    tool_calls JSONB,          -- For assistant messages with tool calls
    tool_call_id VARCHAR(100), -- For tool response messages
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ai_messages_session ON ai_messages(session_id);
```

**Table: `ai_tool_executions`**
```sql
CREATE TABLE ai_tool_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES ai_sessions(id),
    message_id UUID REFERENCES ai_messages(id),
    user_id UUID NOT NULL REFERENCES users(id),
    tool_name VARCHAR(100) NOT NULL,
    tool_category VARCHAR(50) NOT NULL,  -- 'inquiry', 'troubleshooting', 'revive_grafana', 'revive_aiops'
    arguments JSONB NOT NULL,
    result TEXT,
    result_status VARCHAR(20) CHECK (result_status IN ('success', 'error', 'blocked', 'pending_approval')),
    permission_required VARCHAR(100),
    permission_granted BOOLEAN,
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ai_tool_executions_session ON ai_tool_executions(session_id);
CREATE INDEX idx_ai_tool_executions_user ON ai_tool_executions(user_id);
CREATE INDEX idx_ai_tool_executions_tool ON ai_tool_executions(tool_name);
```

**Table: `ai_action_confirmations`**
```sql
CREATE TABLE ai_action_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES ai_sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    action_type VARCHAR(100) NOT NULL,
    action_details JSONB NOT NULL,
    risk_level VARCHAR(20) CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    expires_at TIMESTAMP WITH TIME ZONE,
    confirmed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ai_confirmations_session ON ai_action_confirmations(session_id);
CREATE INDEX idx_ai_confirmations_status ON ai_action_confirmations(status);
```

**Table: `ai_permissions`** (extends existing RBAC)
```sql
CREATE TABLE ai_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id),
    pillar VARCHAR(20) NOT NULL,
    tool_category VARCHAR(50),  -- NULL means all tools in pillar
    tool_name VARCHAR(100),     -- NULL means all tools in category
    permission VARCHAR(20) NOT NULL CHECK (permission IN ('allow', 'deny', 'confirm')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(role_id, pillar, tool_category, tool_name)
);

CREATE INDEX idx_ai_permissions_role ON ai_permissions(role_id);
```

#### Schema Updates to Existing Tables

**Update `users` table:**
```sql
ALTER TABLE users ADD COLUMN ai_preferences JSONB DEFAULT '{}';
-- Stores: default_pillar, preferred_llm, confirmation_level, etc.
```

**Update `audit_logs` table:**
```sql
ALTER TABLE audit_logs ADD COLUMN ai_session_id UUID REFERENCES ai_sessions(id);
ALTER TABLE audit_logs ADD COLUMN ai_tool_name VARCHAR(100);
```

### 3.3 API Contract Changes

#### AI Inquiry Endpoints

**POST /api/v1/inquiry/query**
```json
// Request
{
    "query": "How many alerts fired on payment-service last week?",
    "context": {
        "time_range": {
            "start": "2024-01-08T00:00:00Z",
            "end": "2024-01-15T00:00:00Z"
        },
        "services": ["payment-service"]
    },
    "response_format": "detailed"
}

// Response 200 OK
{
    "session_id": "uuid",
    "answer": {
        "summary": "Payment-service had 47 alerts last week...",
        "data": {
            "total_alerts": 47,
            "by_severity": {"critical": 5, "warning": 32, "info": 10},
            "by_day": [{"date": "2024-01-08", "count": 12}]
        },
        "timeline": [],
        "sources": ["alerts_db", "prometheus"]
    },
    "tools_used": ["query_alerts_history", "get_alert_trends"],
    "tokens_used": 1250
}

// Response 403 Forbidden
{
    "error": "insufficient_permissions",
    "message": "Role 'viewer' cannot access AI Inquiry",
    "required_permission": "ai:inquiry:read"
}
```

**GET /api/v1/inquiry/sessions**
```json
// Response 200 OK
{
    "sessions": [
        {
            "id": "uuid",
            "started_at": "2024-01-15T10:30:00Z",
            "message_count": 5,
            "last_query": "What caused the outage on Jan 10?"
        }
    ],
    "pagination": {"page": 1, "per_page": 20, "total": 45}
}
```

**GET /api/v1/inquiry/sessions/{session_id}/messages**
```json
// Response 200 OK
{
    "session_id": "uuid",
    "messages": [
        {"role": "user", "content": "...", "created_at": "..."},
        {"role": "assistant", "content": "...", "tools_used": [], "created_at": "..."}
    ]
}
```

#### Troubleshooting Endpoints (Enhanced)

**POST /api/v1/alerts/{alert_id}/chat/message** (existing, enhanced)
```json
// Request
{
    "message": "What's causing this alert?",
    "include_sift": true,
    "include_oncall": true
}

// Response 200 OK (streaming via WebSocket or SSE)
{
    "session_id": "uuid",
    "response": {
        "content": "Based on my investigation...",
        "tools_used": [
            {"name": "investigate_sift", "source": "mcp"},
            {"name": "get_oncall_schedule", "source": "mcp"},
            {"name": "get_similar_incidents", "source": "native"}
        ],
        "suggestions": [
            {
                "type": "command",
                "server": "api-server-01",
                "command": "systemctl --no-pager status api-service",
                "explanation": "Check service status"
            }
        ],
        "runbook_match": {
            "id": "uuid",
            "name": "API Service Recovery",
            "confidence": 0.87
        }
    }
}
```

#### RE-VIVE Endpoints (New)

**POST /api/v1/revive/message**
```json
// Request
{
    "message": "Create a dashboard for the checkout service",
    "mode": "grafana",
    "context": {
        "current_page": "/dashboards",
        "selected_items": []
    }
}

// Response 200 OK
{
    "session_id": "uuid",
    "response": {
        "content": "I'll create a dashboard for checkout service...",
        "mode_detected": "grafana",
        "action_required": {
            "type": "create_dashboard",
            "details": {
                "title": "Checkout Service Overview",
                "panels": ["request_rate", "error_rate", "latency_p99"],
                "folder": "Services"
            },
            "risk_level": "medium",
            "confirmation_id": "uuid"
        }
    }
}

// Response 403 Forbidden
{
    "error": "permission_denied",
    "message": "Role 'engineer' cannot create dashboards",
    "required_permission": "ai:revive:grafana:dashboard:create",
    "alternative": "You can request dashboard creation from an admin"
}
```

**POST /api/v1/revive/confirm/{confirmation_id}**
```json
// Request
{
    "action": "approve"
}

// Response 200 OK
{
    "confirmation_id": "uuid",
    "status": "approved",
    "result": {
        "action": "create_dashboard",
        "success": true,
        "resource": {
            "type": "dashboard",
            "uid": "checkout-overview",
            "url": "https://grafana.example.com/d/checkout-overview"
        }
    }
}
```

**GET /api/v1/revive/capabilities**
```json
// Response 200 OK (filtered by user role)
{
    "user_role": "operator",
    "modes": {
        "grafana": {
            "enabled": true,
            "capabilities": [
                {"name": "search_dashboards", "permission": "allow"},
                {"name": "create_dashboard", "permission": "confirm"},
                {"name": "delete_dashboard", "permission": "deny"}
            ]
        },
        "aiops": {
            "enabled": true,
            "capabilities": [
                {"name": "list_runbooks", "permission": "allow"},
                {"name": "execute_runbook", "permission": "confirm"},
                {"name": "manage_servers", "permission": "deny"}
            ]
        }
    }
}
```

**WebSocket /api/v1/revive/ws**
```json
// Client -> Server
{
    "type": "message",
    "content": "Show me all alerts for api-gateway",
    "mode": "auto"
}

// Server -> Client (streaming)
{"type": "chunk", "content": "I found "}
{"type": "chunk", "content": "15 alerts for api-gateway..."}
{"type": "tool_use", "tool": "list_alert_rules", "status": "executing"}
{"type": "complete", "tools_used": ["list_alert_rules"], "tokens_used": 890}
```

#### RBAC Management Endpoints

**GET /api/v1/admin/ai-permissions**
```json
// Response 200 OK
{
    "permissions": [
        {
            "role": "admin",
            "pillar": "revive",
            "tool_category": "grafana",
            "tool_name": null,
            "permission": "allow"
        },
        {
            "role": "operator",
            "pillar": "revive",
            "tool_category": "grafana",
            "tool_name": "delete_dashboard",
            "permission": "deny"
        }
    ]
}
```

**PUT /api/v1/admin/ai-permissions**
```json
// Request
{
    "role_id": "uuid",
    "pillar": "revive",
    "tool_category": "aiops",
    "tool_name": "execute_runbook",
    "permission": "confirm"
}

// Response 200 OK
{
    "id": "uuid",
    "message": "Permission updated successfully"
}
```

### 3.4 UI/UX Changes

#### Navigation Updates
```
┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR NAVIGATION (Updated)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dashboard                                                      │
│  Alerts                                                         │
│  Runbooks                                                       │
│  Servers                                                        │
│  ─────────────────                                              │
│  AI FEATURES (NEW SECTION)                                      │
│     ├─ AI Inquiry         [Analytics & Questions]               │
│     └─ RE-VIVE            [AI Assistant]                        │
│  ─────────────────                                              │
│  Settings                                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### AI Inquiry Page (`/inquiry`)
```
┌─────────────────────────────────────────────────────────────────┐
│  AI Inquiry - Analytics & Historical Questions                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Ask a question about your systems...                    │   │
│  │                                                         │   │
│  │ [How many alerts fired on payment-service last week?]   │   │
│  │                                                    [Ask]│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  SUGGESTED QUESTIONS:                                           │
│  • What caused the most incidents this month?                   │
│  • Compare MTTR between Q3 and Q4                               │
│  • Which service has the highest alert frequency?               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ANSWER                                                  │   │
│  │                                                         │   │
│  │ Payment-service had **47 alerts** last week:            │   │
│  │                                                         │   │
│  │ | Severity | Count | % of Total |                       │   │
│  │ |----------|-------|------------|                       │   │
│  │ | Critical |   5   |    11%     |                       │   │
│  │ | Warning  |  32   |    68%     |                       │   │
│  │ | Info     |  10   |    21%     |                       │   │
│  │                                                         │   │
│  │ [Timeline View] [Export CSV] [Save Query]               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  RECENT QUERIES:                                                │
│  • Why did checkout have issues on Jan 10? (2h ago)             │
│  • What's the MTTR trend for API services? (yesterday)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### RE-VIVE Page (`/revive`)
```
┌─────────────────────────────────────────────────────────────────┐
│  RE-VIVE - AI Assistant                              [Grafana]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MODE: [Grafana Stack] [AIOps Platform]                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  You: Create a dashboard for the checkout service       │   │
│  │       with CPU, memory, and request rate panels         │   │
│  │                                                         │   │
│  │  RE-VIVE: I'll create a dashboard for checkout          │   │
│  │           service with the following panels:            │   │
│  │                                                         │   │
│  │           1. CPU Usage (node_cpu_seconds_total)         │   │
│  │           2. Memory Usage (node_memory_*)               │   │
│  │           3. Request Rate (http_requests_total)         │   │
│  │                                                         │   │
│  │           ┌──────────────────────────────────────┐      │   │
│  │           │ ACTION REQUIRED                      │      │   │
│  │           │                                      │      │   │
│  │           │ Create Dashboard: Checkout Service   │      │   │
│  │           │ Folder: Services                     │      │   │
│  │           │ Panels: 3                            │      │   │
│  │           │                                      │      │   │
│  │           │ [Approve]  [Reject]  [Edit]          │      │   │
│  │           └──────────────────────────────────────┘      │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Ask RE-VIVE anything...                            [->] │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  QUICK ACTIONS (based on mode):                                 │
│  Grafana: [Create Dashboard] [List Alerts] [Query Metrics]      │
│  AIOps:   [List Runbooks] [Execute Runbook] [Manage Servers]    │
│                                                                 │
│  YOUR PERMISSIONS: Can create dashboards, cannot delete         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Troubleshooting Chat (Enhanced)
```
┌─────────────────────────────────────────────────────────────────┐
│  Alert: HighLatency on api-gateway              [Critical]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ CONTEXT (auto-gathered)                                 │   │
│  │ • Sift: 45 similar errors detected (NEW via MCP)        │   │
│  │ • OnCall: Sarah Chen (primary), Mike Liu (secondary)    │   │
│  │ • Similar Incidents: 3 found, last resolved by restart  │   │
│  │ • Runbook: "API Gateway Recovery" available             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  CHAT:                                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  You: What's causing this?                              │   │
│  │                                                         │   │
│  │  AI: Based on Sift analysis, I found a pattern of       │   │
│  │      connection timeout errors starting at 14:32.       │   │
│  │                                                         │   │
│  │      This correlates with a config deployment at        │   │
│  │      14:30. Similar incident INC-2024-001 was           │   │
│  │      resolved by rolling back the config.               │   │
│  │                                                         │   │
│  │      Suggested command:                                 │   │
│  │      ┌────────────────────────────────────────┐         │   │
│  │      │ $ kubectl rollout undo deployment/api  │         │   │
│  │      │   --to-revision=previous               │         │   │
│  │      │                      [Copy] [Execute]  │         │   │
│  │      └────────────────────────────────────────┘         │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.5 Security and Privacy Considerations

#### RBAC Permission Matrix

| Role | AI Inquiry | Troubleshooting | RE-VIVE Grafana | RE-VIVE AIOps |
|------|------------|-----------------|-----------------|---------------|
| **admin** | Full access | Full access | Full access | Full access |
| **operator** | Full access | Full access | Read + Create (confirm) | Read + Execute (confirm) |
| **engineer** | Full access | Own alerts only | Read only | Read + View runbooks |
| **viewer** | Read summaries | View only | Search only | View only |

#### Tool Permission Categories

```
PERMISSION LEVELS:
├── allow      - Execute without confirmation
├── confirm    - Requires user confirmation before execution
├── deny       - Blocked, shows alternative or escalation path
└── audit_only - Allowed but logged with extra detail

RISK CLASSIFICATION:
├── read       - Query/search operations (low risk)
├── create     - Create new resources (medium risk)
├── update     - Modify existing resources (medium-high risk)
├── delete     - Remove resources (high risk)
└── execute    - Run commands/runbooks (high risk)
```

#### Security Controls

1. **Authentication**: All AI endpoints require valid JWT token
2. **Authorization**: RBAC checked at orchestrator level before tool selection
3. **Tool-level Permissions**: Each tool execution validates user permission
4. **Audit Logging**: All AI tool executions logged with user, input, output
5. **Rate Limiting**: Per-user rate limits on AI endpoints
6. **Input Validation**: Sanitize all user inputs before LLM processing
7. **Output Filtering**: Prevent credential/secret exposure in responses
8. **Confirmation Expiry**: Action confirmations expire after 5 minutes
9. **Sensitive Data Masking**: Mask credentials in tool results before returning

#### Data Privacy

1. **Session Isolation**: Users can only view their own AI sessions
2. **Message Retention**: Configurable retention period for AI messages
3. **No PII in Prompts**: System prompts don't include user PII
4. **Grafana Token Scope**: MCP uses service account with minimal required permissions
5. **Local LLM Option**: Support for Ollama to keep data on-premise

---

## 4. Implementation Plan

### Phase 1: Foundation - MCP Client & RBAC

#### Task 1.1: MCP Client Library
**Description**: Create a Python client library for communicating with MCP Grafana server using the MCP protocol over SSE transport.

**Files to create**:
- `app/services/mcp/__init__.py`
- `app/services/mcp/client.py`
- `app/services/mcp/transport.py`
- `app/services/mcp/types.py`
- `app/services/mcp/exceptions.py`
- `tests/unit/test_mcp_client.py`

**Interfaces**:
```python
# app/services/mcp/client.py
class MCPClient:
    def __init__(self, server_url: str, api_token: str): ...
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def list_tools(self) -> List[MCPTool]: ...
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolResult: ...
    async def health_check(self) -> bool: ...

# app/services/mcp/types.py
@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any]

@dataclass
class MCPToolResult:
    content: List[MCPContent]
    is_error: bool
```

**Configuration keys**:
- `MCP_GRAFANA_URL`: URL of MCP Grafana server
- `MCP_GRAFANA_TOKEN`: Service account token for Grafana
- `MCP_CONNECTION_TIMEOUT`: Connection timeout in seconds
- `MCP_REQUEST_TIMEOUT`: Request timeout in seconds

**Complexity**: Medium
**Dependencies**: None

---

#### Task 1.2: AI Permission Models
**Description**: Create database models for AI-specific RBAC permissions.

**Files to create**:
- `app/models_ai.py`
- `alembic/versions/xxx_add_ai_permission_tables.py`

**Files to update**:
- `app/models.py` (add `ai_preferences` to User)

**Interfaces**:
```python
# app/models_ai.py
class AISession(Base):
    __tablename__ = "ai_sessions"
    id: UUID
    user_id: UUID
    pillar: str  # 'inquiry', 'troubleshooting', 'revive'
    revive_mode: Optional[str]  # 'grafana', 'aiops'
    context_type: Optional[str]
    context_id: Optional[UUID]
    started_at: datetime
    ended_at: Optional[datetime]
    message_count: int

class AIMessage(Base):
    __tablename__ = "ai_messages"
    id: UUID
    session_id: UUID
    role: str
    content: str
    tool_calls: Optional[Dict]
    tool_call_id: Optional[str]
    tokens_used: Optional[int]

class AIToolExecution(Base):
    __tablename__ = "ai_tool_executions"
    id: UUID
    session_id: UUID
    user_id: UUID
    tool_name: str
    tool_category: str
    arguments: Dict
    result: Optional[str]
    result_status: str
    permission_required: Optional[str]
    permission_granted: bool
    execution_time_ms: Optional[int]

class AIPermission(Base):
    __tablename__ = "ai_permissions"
    id: UUID
    role_id: UUID
    pillar: str
    tool_category: Optional[str]
    tool_name: Optional[str]
    permission: str  # 'allow', 'deny', 'confirm'

class AIActionConfirmation(Base):
    __tablename__ = "ai_action_confirmations"
    id: UUID
    session_id: UUID
    user_id: UUID
    action_type: str
    action_details: Dict
    risk_level: str
    status: str
    expires_at: datetime
```

**Complexity**: Low
**Dependencies**: None

---

#### Task 1.3: AI Permission Service
**Description**: Create service for checking and managing AI permissions based on user role.

**Files to create**:
- `app/services/ai_permission_service.py`
- `tests/unit/test_ai_permission_service.py`

**Interfaces**:
```python
# app/services/ai_permission_service.py
class AIPermissionService:
    def __init__(self, db: Session): ...

    def can_access_pillar(self, user: User, pillar: str) -> bool: ...

    def get_tool_permission(
        self, user: User, pillar: str, tool_category: str, tool_name: str
    ) -> ToolPermission: ...

    def filter_tools_by_permission(
        self, user: User, pillar: str, tools: List[Tool]
    ) -> List[Tool]: ...

    def create_confirmation(
        self, session_id: UUID, user: User, action_type: str,
        action_details: Dict, risk_level: str
    ) -> AIActionConfirmation: ...

    def process_confirmation(
        self, confirmation_id: UUID, user: User, action: str
    ) -> ConfirmationResult: ...

    def get_user_capabilities(self, user: User) -> Dict[str, Any]: ...

@dataclass
class ToolPermission:
    permission: str  # 'allow', 'deny', 'confirm'
    reason: Optional[str]
    alternative: Optional[str]
```

**Complexity**: Medium
**Dependencies**: Task 1.2

---

#### Task 1.4: Default AI Permissions Seed
**Description**: Create default AI permissions for each role.

**Files to create**:
- `app/seeds/ai_permissions.py`
- `alembic/versions/xxx_seed_default_ai_permissions.py`

**Default permissions**:
```python
DEFAULT_AI_PERMISSIONS = {
    "admin": {
        "inquiry": {"*": "allow"},
        "troubleshooting": {"*": "allow"},
        "revive": {"grafana": {"*": "allow"}, "aiops": {"*": "allow"}}
    },
    "operator": {
        "inquiry": {"*": "allow"},
        "troubleshooting": {"*": "allow"},
        "revive": {
            "grafana": {
                "search_*": "allow",
                "get_*": "allow",
                "query_*": "allow",
                "create_*": "confirm",
                "update_*": "confirm",
                "delete_*": "deny"
            },
            "aiops": {
                "list_*": "allow",
                "get_*": "allow",
                "execute_runbook": "confirm",
                "manage_*": "deny"
            }
        }
    },
    "engineer": {
        "inquiry": {"*": "allow"},
        "troubleshooting": {"own_alerts": "allow"},
        "revive": {
            "grafana": {"search_*": "allow", "get_*": "allow", "query_*": "allow"},
            "aiops": {"list_*": "allow", "get_*": "allow"}
        }
    },
    "viewer": {
        "inquiry": {"aggregated_only": "allow"},
        "troubleshooting": {"view_only": "allow"},
        "revive": {
            "grafana": {"search_*": "allow"},
            "aiops": {"list_*": "allow"}
        }
    }
}
```

**Complexity**: Low
**Dependencies**: Task 1.2, Task 1.3

---

### Phase 2: AI Inquiry Pillar

#### Task 2.1: Inquiry Tool Definitions
**Description**: Define read-only tools for AI Inquiry pillar.

**Files to create**:
- `app/services/agentic/tools/inquiry_tools.py`
- `tests/unit/test_inquiry_tools.py`

**Interfaces**:
```python
# app/services/agentic/tools/inquiry_tools.py

INQUIRY_TOOLS = [
    Tool(
        name="query_alerts_history",
        description="Query historical alerts with filters",
        category="inquiry",
        risk_level="read",
        parameters=[
            ToolParameter("service", "string", "Service name filter"),
            ToolParameter("severity", "string", "Severity filter", enum=["critical", "warning", "info"]),
            ToolParameter("time_range", "object", "Time range with start/end"),
            ToolParameter("status", "string", "Alert status", enum=["firing", "resolved"]),
            ToolParameter("limit", "integer", "Max results", default=100)
        ]
    ),
    Tool(name="query_incidents", ...),
    Tool(name="get_mttr_statistics", ...),
    Tool(name="get_alert_trends", ...),
    Tool(name="correlate_alerts_changes", ...),
    Tool(name="get_incident_timeline", ...),
    Tool(name="search_postmortems", ...)
]

class InquiryToolHandlers:
    def __init__(self, db: Session): ...

    async def query_alerts_history(self, args: Dict) -> str: ...
    async def query_incidents(self, args: Dict) -> str: ...
    async def get_mttr_statistics(self, args: Dict) -> str: ...
    async def get_alert_trends(self, args: Dict) -> str: ...
    async def correlate_alerts_changes(self, args: Dict) -> str: ...
    async def get_incident_timeline(self, args: Dict) -> str: ...
    async def search_postmortems(self, args: Dict) -> str: ...
```

**Complexity**: Medium
**Dependencies**: Task 1.2

---

#### Task 2.2: Inquiry Orchestrator
**Description**: Create orchestrator for AI Inquiry that handles query classification and multi-step reasoning.

**Files to create**:
- `app/services/agentic/inquiry_orchestrator.py`
- `tests/unit/test_inquiry_orchestrator.py`

**Interfaces**:
```python
# app/services/agentic/inquiry_orchestrator.py

class InquiryOrchestrator:
    def __init__(
        self,
        db: Session,
        user: User,
        llm_service: LLMService,
        permission_service: AIPermissionService
    ): ...

    async def process_query(
        self,
        query: str,
        context: Optional[InquiryContext] = None,
        response_format: str = "detailed"
    ) -> InquiryResponse: ...

    def classify_query(self, query: str) -> QueryClassification: ...

    async def execute_multi_step(
        self,
        plan: List[InquiryStep]
    ) -> List[StepResult]: ...

    def format_response(
        self,
        results: List[StepResult],
        format_type: str
    ) -> FormattedResponse: ...

@dataclass
class InquiryContext:
    time_range: Optional[TimeRange]
    services: Optional[List[str]]
    severity_filter: Optional[List[str]]

@dataclass
class InquiryResponse:
    session_id: UUID
    answer: AnswerContent
    tools_used: List[str]
    tokens_used: int
```

**Complexity**: High
**Dependencies**: Task 1.3, Task 2.1

---

#### Task 2.3: Inquiry API Router
**Description**: Create FastAPI router for AI Inquiry endpoints.

**Files to create**:
- `app/routers/inquiry.py`
- `tests/integration/test_inquiry_api.py`

**Interfaces**:
```python
# app/routers/inquiry.py

router = APIRouter(prefix="/api/v1/inquiry", tags=["AI Inquiry"])

@router.post("/query", response_model=InquiryResponseSchema)
async def query(
    request: InquiryQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> InquiryResponseSchema: ...

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(...) -> SessionListResponse: ...

@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_session_messages(...) -> MessageListResponse: ...

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_query_suggestions(...) -> SuggestionsResponse: ...
```

**Complexity**: Medium
**Dependencies**: Task 2.2

---

#### Task 2.4: Inquiry UI Components
**Description**: Create frontend components for AI Inquiry page.

**Files to create**:
- `app/templates/inquiry/index.html`
- `app/static/js/inquiry.js`
- `app/static/css/inquiry.css`

**UI Components**:
- Query input with suggestions
- Answer display (text, table, timeline views)
- Recent queries sidebar
- Export functionality (CSV, PDF)
- Session history

**Complexity**: Medium
**Dependencies**: Task 2.3

---

### Phase 3: Troubleshooting Enhancement

#### Task 3.1: MCP Tool Adapters for Troubleshooting
**Description**: Create adapters to use MCP Grafana tools within existing troubleshooting system.

**Files to create**:
- `app/services/agentic/tools/mcp_adapters.py`
- `tests/unit/test_mcp_adapters.py`

**Interfaces**:
```python
# app/services/agentic/tools/mcp_adapters.py

class MCPToolAdapter:
    def __init__(self, mcp_client: MCPClient): ...

    def get_adapted_tools(self) -> List[Tool]: ...

    async def execute(self, tool_name: str, arguments: Dict) -> str: ...

MCP_TROUBLESHOOTING_TOOLS = [
    "investigate_sift",
    "get_oncall_schedule",
    "query_tempo",
    "create_annotation",
    "query_prometheus",
    "query_loki"
]

class SiftAdapter:
    async def investigate(
        self,
        app_name: str,
        time_range: TimeRange,
        investigation_type: str = "errors"
    ) -> SiftResult: ...

class OnCallAdapter:
    async def get_schedule(
        self,
        team: Optional[str] = None
    ) -> OnCallSchedule: ...
```

**Complexity**: Medium
**Dependencies**: Task 1.1

---

#### Task 3.2: Enhanced Troubleshooting Tool Registry
**Description**: Update existing ToolRegistry to include MCP tools for troubleshooting.

**Files to update**:
- `app/services/agentic/tool_registry.py`

**Files to create**:
- `app/services/agentic/enhanced_tool_registry.py`

**Interfaces**:
```python
# app/services/agentic/enhanced_tool_registry.py

class EnhancedToolRegistry(ToolRegistry):
    def __init__(
        self,
        db: Session,
        alert_id: Optional[UUID] = None,
        mcp_client: Optional[MCPClient] = None,
        user: Optional[User] = None,
        permission_service: Optional[AIPermissionService] = None
    ): ...

    def _register_mcp_tools(self) -> None: ...

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> str: ...
```

**Complexity**: Medium
**Dependencies**: Task 1.3, Task 3.1

---

#### Task 3.3: Troubleshooting Context Enrichment
**Description**: Add automatic context gathering using MCP tools when troubleshooting session starts.

**Files to create**:
- `app/services/agentic/context_enricher.py`
- `tests/unit/test_context_enricher.py`

**Interfaces**:
```python
# app/services/agentic/context_enricher.py

class TroubleshootingContextEnricher:
    def __init__(
        self,
        db: Session,
        mcp_client: MCPClient,
        alert_id: UUID
    ): ...

    async def enrich(self) -> EnrichedContext: ...

    async def _get_sift_analysis(self) -> Optional[SiftAnalysis]: ...
    async def _get_oncall_info(self) -> Optional[OnCallInfo]: ...

@dataclass
class EnrichedContext:
    sift_analysis: Optional[SiftAnalysis]
    oncall_info: Optional[OnCallInfo]
    similar_incidents: List[SimilarIncident]
    recent_changes: List[ChangeEvent]
    matching_runbooks: List[Runbook]
    gathered_at: datetime
```

**Complexity**: Medium
**Dependencies**: Task 3.1

---

#### Task 3.4: Update Troubleshooting Chat API
**Description**: Enhance existing chat API to use enriched context and MCP tools.

**Files to update**:
- `app/routers/chat.py`
- `app/services/agentic/orchestrator.py`

**Interface changes**:
```python
# app/routers/chat.py

@router.post("/alerts/{alert_id}/chat/message")
async def send_message(
    alert_id: UUID,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ChatMessageResponse: ...

class ChatMessageRequest(BaseModel):
    message: str
    include_sift: bool = True
    include_oncall: bool = True
```

**Complexity**: Medium
**Dependencies**: Task 3.2, Task 3.3

---

### Phase 4: RE-VIVE Unified Assistant

#### Task 4.1: RE-VIVE Mode Detector
**Description**: Create service to detect whether user intent is for Grafana or AIOps mode.

**Files to create**:
- `app/services/revive/mode_detector.py`
- `tests/unit/test_mode_detector.py`

**Interfaces**:
```python
# app/services/revive/mode_detector.py

class ReviveModeDetector:
    GRAFANA_KEYWORDS = [
        "dashboard", "panel", "query", "promql", "logql", "alert rule",
        "datasource", "annotation", "grafana", "prometheus", "loki",
        "tempo", "oncall", "sift", "visualization"
    ]

    AIOPS_KEYWORDS = [
        "runbook", "server", "credential", "execute", "ssh", "terminal",
        "remediation", "auto-analyze", "rule", "setting", "configuration"
    ]

    def __init__(self, llm_service: Optional[LLMService] = None): ...

    def detect(
        self,
        message: str,
        current_page: Optional[str] = None,
        explicit_mode: Optional[str] = None
    ) -> ModeDetectionResult: ...

    def detect_with_llm(self, message: str) -> ModeDetectionResult: ...

@dataclass
class ModeDetectionResult:
    mode: str
    confidence: float
    detected_intent: str
    suggested_tools: List[str]
```

**Complexity**: Low
**Dependencies**: None

---

#### Task 4.2: RE-VIVE Grafana Tools
**Description**: Define all Grafana-related tools for RE-VIVE using MCP.

**Files to create**:
- `app/services/revive/tools/grafana_tools.py`
- `tests/unit/test_revive_grafana_tools.py`

**Interfaces**:
```python
# app/services/revive/tools/grafana_tools.py

REVIVE_GRAFANA_TOOLS = [
    # Dashboard tools (MCP)
    Tool(name="search_dashboards", ...),
    Tool(name="get_dashboard_by_uid", ...),
    Tool(name="create_dashboard", requires_confirmation=True, ...),
    Tool(name="update_dashboard", requires_confirmation=True, ...),
    Tool(name="delete_dashboard", requires_confirmation=True, ...),

    # Alert rule tools (MCP)
    Tool(name="list_alert_rules", ...),
    Tool(name="get_alert_rule_by_uid", ...),
    Tool(name="create_alert_rule", ...),
    Tool(name="update_alert_rule", ...),
    Tool(name="delete_alert_rule", ...),

    # Query tools (MCP)
    Tool(name="query_prometheus", ...),
    Tool(name="query_loki", ...),
    Tool(name="query_tempo", ...),

    # OnCall tools (MCP)
    Tool(name="get_oncall_schedule", ...),
    Tool(name="list_oncall_teams", ...),

    # Incident tools (MCP)
    Tool(name="list_incidents", ...),
    Tool(name="create_incident", ...),
    Tool(name="update_incident", ...),

    # Annotation tools (MCP)
    Tool(name="create_annotation", ...),
    Tool(name="list_annotations", ...),

    # Sift tools (MCP)
    Tool(name="list_sift_investigations", ...),
    Tool(name="get_sift_analysis", ...)
]

class GrafanaToolHandlers:
    def __init__(self, mcp_client: MCPClient, db: Session): ...

    async def execute(self, tool_name: str, arguments: Dict) -> ToolResult: ...
```

**Complexity**: Medium
**Dependencies**: Task 1.1

---

#### Task 4.3: RE-VIVE AIOps Tools
**Description**: Define AIOps-related tools for RE-VIVE (platform management).

**Files to create**:
- `app/services/revive/tools/aiops_tools.py`
- `tests/unit/test_revive_aiops_tools.py`

**Interfaces**:
```python
# app/services/revive/tools/aiops_tools.py

REVIVE_AIOPS_TOOLS = [
    # Runbook tools
    Tool(name="list_runbooks", ...),
    Tool(name="get_runbook_details", ...),
    Tool(name="execute_runbook", requires_confirmation=True, ...),
    Tool(name="create_runbook", requires_confirmation=True, ...),

    # Server tools
    Tool(name="list_servers", ...),
    Tool(name="get_server_details", ...),
    Tool(name="add_server", requires_confirmation=True, ...),

    # Credential tools
    Tool(name="list_credentials", ...),
    Tool(name="create_credential", requires_confirmation=True, ...),

    # Rule tools
    Tool(name="list_auto_analyze_rules", ...),
    Tool(name="create_auto_analyze_rule", requires_confirmation=True, ...),

    # Audit tools
    Tool(name="query_audit_logs", ...),

    # Execution history
    Tool(name="list_executions", ...),
    Tool(name="get_execution_details", ...)
]

class AIOpsToolHandlers:
    def __init__(self, db: Session, user: User): ...

    async def execute(self, tool_name: str, arguments: Dict) -> ToolResult: ...
```

**Complexity**: Medium
**Dependencies**: None (uses existing services)

---

#### Task 4.4: RE-VIVE Orchestrator
**Description**: Create unified orchestrator for RE-VIVE that handles both Grafana and AIOps modes.

**Files to create**:
- `app/services/revive/orchestrator.py`
- `tests/unit/test_revive_orchestrator.py`

**Interfaces**:
```python
# app/services/revive/orchestrator.py

class ReviveOrchestrator:
    def __init__(
        self,
        db: Session,
        user: User,
        llm_service: LLMService,
        mcp_client: MCPClient,
        permission_service: AIPermissionService
    ): ...

    async def process_message(
        self,
        message: str,
        session_id: Optional[UUID] = None,
        mode: Optional[str] = None,
        context: Optional[ReviveContext] = None
    ) -> ReviveResponse: ...

    async def _handle_grafana_mode(
        self,
        message: str,
        session: AISession
    ) -> ReviveResponse: ...

    async def _handle_aiops_mode(
        self,
        message: str,
        session: AISession
    ) -> ReviveResponse: ...

    async def _execute_with_confirmation(
        self,
        tool: Tool,
        arguments: Dict,
        session: AISession
    ) -> Union[ToolResult, ConfirmationRequest]: ...

    def _build_tool_list(self, mode: str) -> List[Tool]: ...

    async def confirm_action(
        self,
        confirmation_id: UUID,
        action: str
    ) -> ConfirmationResult: ...

@dataclass
class ReviveContext:
    current_page: Optional[str]
    selected_items: Optional[List[str]]
    recent_actions: Optional[List[str]]

@dataclass
class ReviveResponse:
    session_id: UUID
    content: str
    mode_detected: str
    tools_used: List[ToolUsage]
    action_required: Optional[ActionConfirmation]
    resources_created: Optional[List[ResourceReference]]
```

**Complexity**: High
**Dependencies**: Task 4.1, Task 4.2, Task 4.3, Task 1.3

---

#### Task 4.5: RE-VIVE API Router
**Description**: Create FastAPI router for RE-VIVE endpoints.

**Files to create**:
- `app/routers/revive.py`
- `tests/integration/test_revive_api.py`

**Interfaces**:
```python
# app/routers/revive.py

router = APIRouter(prefix="/api/v1/revive", tags=["RE-VIVE"])

@router.post("/message", response_model=ReviveResponseSchema)
async def send_message(...) -> ReviveResponseSchema: ...

@router.post("/confirm/{confirmation_id}", response_model=ConfirmationResultSchema)
async def confirm_action(...) -> ConfirmationResultSchema: ...

@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(...) -> CapabilitiesResponse: ...

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(...) -> SessionListResponse: ...

@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(...) -> SessionDetailResponse: ...

@router.websocket("/ws")
async def websocket_endpoint(...): ...
```

**Complexity**: Medium
**Dependencies**: Task 4.4

---

#### Task 4.6: RE-VIVE WebSocket Handler
**Description**: Create WebSocket handler for streaming RE-VIVE responses.

**Files to create**:
- `app/services/revive/websocket_handler.py`
- `tests/unit/test_revive_websocket.py`

**Interfaces**:
```python
# app/services/revive/websocket_handler.py

class ReviveWebSocketHandler:
    def __init__(
        self,
        websocket: WebSocket,
        user: User,
        db: Session,
        orchestrator: ReviveOrchestrator
    ): ...

    async def handle_connection(self) -> None: ...

    async def _handle_message(self, data: Dict) -> None: ...

    async def _stream_response(self, data: Dict) -> None: ...
```

**Complexity**: Medium
**Dependencies**: Task 4.4

---

#### Task 4.7: RE-VIVE UI Page
**Description**: Create frontend page for RE-VIVE unified assistant.

**Files to create**:
- `app/templates/revive/index.html`
- `app/static/js/revive.js`
- `app/static/css/revive.css`

**UI Components**:
- Mode toggle (Grafana / AIOps)
- Chat interface with streaming
- Action confirmation modal
- Capabilities sidebar (shows what user can do)
- Quick action buttons (mode-specific)
- Resource links panel (shows created resources)
- Session history

**Complexity**: Medium
**Dependencies**: Task 4.5, Task 4.6

---

### Phase 5: Integration & Testing

#### Task 5.1: MCP Grafana Deployment Configuration
**Description**: Create deployment configuration for MCP Grafana server.

**Files to create**:
- `docker/mcp-grafana/docker-compose.yml`
- `docker/mcp-grafana/Dockerfile` (if custom build needed)
- `docs/MCP_GRAFANA_SETUP.md`

**Configuration**:
```yaml
# docker/mcp-grafana/docker-compose.yml
services:
  mcp-grafana:
    image: ghcr.io/grafana/mcp-grafana:latest
    environment:
      - GRAFANA_URL=${GRAFANA_URL}
      - GRAFANA_API_KEY=${GRAFANA_SERVICE_ACCOUNT_TOKEN}
    ports:
      - "8081:8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Complexity**: Low
**Dependencies**: None

---

#### Task 5.2: AI Audit Logging Enhancement
**Description**: Enhance audit logging to capture all AI-initiated actions.

**Files to update**:
- `app/services/audit_service.py`

**Files to create**:
- `app/services/ai_audit_service.py`
- `tests/unit/test_ai_audit_service.py`

**Interfaces**:
```python
# app/services/ai_audit_service.py

class AIAuditService:
    def __init__(self, db: Session): ...

    def log_session_start(
        self,
        user: User,
        pillar: str,
        context: Optional[Dict] = None
    ) -> AISession: ...

    def log_tool_execution(
        self,
        session: AISession,
        tool_name: str,
        arguments: Dict,
        result: str,
        status: str,
        execution_time_ms: int
    ) -> AIToolExecution: ...

    def log_action_confirmation(
        self,
        session: AISession,
        action_type: str,
        details: Dict,
        status: str,
        user_decision: str
    ) -> None: ...

    def get_user_ai_activity(
        self,
        user_id: UUID,
        time_range: Optional[TimeRange] = None
    ) -> List[AIActivitySummary]: ...

    def get_tool_usage_stats(
        self,
        time_range: Optional[TimeRange] = None
    ) -> ToolUsageStats: ...
```

**Complexity**: Low
**Dependencies**: Task 1.2

---

#### Task 5.3: Integration Tests
**Description**: Create comprehensive integration tests for all three pillars.

**Files to create**:
- `tests/integration/test_inquiry_integration.py`
- `tests/integration/test_troubleshooting_integration.py`
- `tests/integration/test_revive_integration.py`
- `tests/integration/test_rbac_integration.py`
- `tests/integration/test_mcp_integration.py`

**Test scenarios**:
```python
# tests/integration/test_rbac_integration.py

class TestAIRBAC:
    def test_admin_full_access(self): ...
    def test_operator_limited_delete(self): ...
    def test_engineer_own_alerts_only(self): ...
    def test_viewer_read_only(self): ...
    def test_permission_inheritance(self): ...
    def test_tool_filtering_by_role(self): ...
    def test_confirmation_required_for_create(self): ...
    def test_blocked_action_shows_alternative(self): ...

# tests/integration/test_revive_integration.py

class TestReviveIntegration:
    def test_grafana_mode_create_dashboard(self): ...
    def test_grafana_mode_query_metrics(self): ...
    def test_aiops_mode_execute_runbook(self): ...
    def test_aiops_mode_list_servers(self): ...
    def test_auto_mode_detection(self): ...
    def test_confirmation_workflow(self): ...
    def test_confirmation_expiry(self): ...
    def test_websocket_streaming(self): ...
```

**Complexity**: Medium
**Dependencies**: All previous tasks

---

#### Task 5.4: Admin UI for AI Permissions
**Description**: Create admin interface for managing AI permissions.

**Files to create**:
- `app/templates/admin/ai_permissions.html`
- `app/static/js/admin_ai_permissions.js`
- `app/routers/admin_ai.py`

**Interfaces**:
```python
# app/routers/admin_ai.py

router = APIRouter(prefix="/api/v1/admin/ai", tags=["Admin - AI"])

@router.get("/permissions", response_model=AIPermissionListResponse)
async def list_permissions(...) -> AIPermissionListResponse: ...

@router.put("/permissions", response_model=AIPermissionResponse)
async def update_permission(...) -> AIPermissionResponse: ...

@router.get("/usage", response_model=AIUsageStatsResponse)
async def get_usage_stats(...) -> AIUsageStatsResponse: ...

@router.get("/audit", response_model=AIAuditLogResponse)
async def get_audit_logs(...) -> AIAuditLogResponse: ...
```

**Complexity**: Medium
**Dependencies**: Task 1.3, Task 5.2

---

#### Task 5.5: Documentation
**Description**: Create comprehensive documentation for all AI features.

**Files to create**:
- `docs/AI_FEATURES.md`
- `docs/AI_INQUIRY_GUIDE.md`
- `docs/TROUBLESHOOTING_AI_GUIDE.md`
- `docs/REVIVE_USER_GUIDE.md`
- `docs/AI_RBAC_ADMIN_GUIDE.md`
- `docs/MCP_INTEGRATION.md`

**Documentation sections**:
- Feature overview and capabilities
- User guides for each pillar
- Admin guide for RBAC configuration
- API reference
- Troubleshooting common issues
- Architecture diagrams

**Complexity**: Low
**Dependencies**: All previous tasks

---

## 5. Summary

### Task Dependencies Graph

```
Phase 1: Foundation
├── Task 1.1: MCP Client Library
├── Task 1.2: AI Permission Models
├── Task 1.3: AI Permission Service (depends: 1.2)
└── Task 1.4: Default Permissions Seed (depends: 1.2, 1.3)

Phase 2: AI Inquiry
├── Task 2.1: Inquiry Tools (depends: 1.2)
├── Task 2.2: Inquiry Orchestrator (depends: 1.3, 2.1)
├── Task 2.3: Inquiry API Router (depends: 2.2)
└── Task 2.4: Inquiry UI (depends: 2.3)

Phase 3: Troubleshooting Enhancement
├── Task 3.1: MCP Tool Adapters (depends: 1.1)
├── Task 3.2: Enhanced Tool Registry (depends: 1.3, 3.1)
├── Task 3.3: Context Enricher (depends: 3.1)
└── Task 3.4: Update Chat API (depends: 3.2, 3.3)

Phase 4: RE-VIVE
├── Task 4.1: Mode Detector
├── Task 4.2: Grafana Tools (depends: 1.1)
├── Task 4.3: AIOps Tools
├── Task 4.4: RE-VIVE Orchestrator (depends: 4.1, 4.2, 4.3, 1.3)
├── Task 4.5: RE-VIVE API Router (depends: 4.4)
├── Task 4.6: WebSocket Handler (depends: 4.4)
└── Task 4.7: RE-VIVE UI (depends: 4.5, 4.6)

Phase 5: Integration
├── Task 5.1: MCP Deployment Config
├── Task 5.2: AI Audit Enhancement (depends: 1.2)
├── Task 5.3: Integration Tests (depends: all)
├── Task 5.4: Admin UI (depends: 1.3, 5.2)
└── Task 5.5: Documentation (depends: all)
```

### Complexity Summary

| Complexity | Tasks |
|------------|-------|
| **Low** | 1.2, 1.4, 4.1, 5.1, 5.2, 5.5 |
| **Medium** | 1.1, 1.3, 2.1, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.2, 4.3, 4.5, 4.6, 4.7, 5.3, 5.4 |
| **High** | 2.2, 4.4 |

**Total Tasks**: 23
**Estimated PRs**: 23 (one per task, keeping PRs focused)
