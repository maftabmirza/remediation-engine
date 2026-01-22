# AI Features Overview

## Introduction

The AIOps Platform includes a comprehensive Three-Pillar AI system that enhances incident management, provides analytics insights, and enables unified control over your observability and remediation infrastructure.

## Three Pillars

### 1. **AI Inquiry** - Historical Analytics 📊
Ask analytical questions about your infrastructure history.

**Access**: `/inquiry`

**Capabilities**:
- Query historical alerts and incidents
- Calculate MTTR statistics
- Analyze alert trends over time
- Correlate alerts with changes
- Search postmortems and runbooks

**Example Questions**:
- "Show me critical alerts from last week"
- "What's the MTTR for database incidents?"
- "Show alert trends for the payment service"

---

### 2. **Troubleshooting Assistant** - Live Diagnostics 🔍
AI-powered assistance for active incident troubleshooting.

**Access**: `/alerts/{id}/chat`

**Capabilities**:
- Alert context enrichment
- Similar incident detection
- Root cause suggestions
- Runbook recommendations
- Real-time data gathering (MCP-powered)

**Features**:
- Sift pattern analysis
- OnCall schedule integration
- Tempo trace correlation
- SSH command suggestions

---

### 3. **RE-VIVE** - Unified Assistant 🤖
Context-aware AI for both Grafana and AIOps operations.

**Access**: `/revive`

**Two Modes**:

**Grafana Mode** (`/grafana/*` pages):
- Search/create/update dashboards
- Manage alert rules
- Query Prometheus/Loki
- Create annotations

**AIOps Mode** (`/remediation/*` pages):
- List/search runbooks
- Manage servers
- Execute remediation workflows
- View audit logs

**Auto Mode Detection**: RE-VIVE automatically detects which mode to use based on your current page or message keywords.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Frontend Layer                     │
│  /inquiry  │  /alerts/{id}/chat  │  /revive    │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              API Layer (FastAPI)                │
│  • Authentication & RBAC                        │
│  • /api/revive/*  /api/v1/inquiry/*            │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│           Orchestrator Layer                    │
│  • Mode Detection  • Permission Checks          │
│  • Tool Selection  • Audit Logging              │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│            Tool Registry                        │
│  Inquiry Tools │ Troubleshooting │ RE-VIVE      │
│  (read-only)   │ (read+suggest)  │ (read+write) │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│          Backend Services                       │
│  PostgreSQL  │  MCP Grafana  │  Existing APIs   │
└─────────────────────────────────────────────────┘
```

---

## Role-Based Access Control

All AI features respect your role permissions:

| Role | Inquiry | Troubleshooting | RE-VIVE Grafana | RE-VIVE AIOps |
|------|---------|-----------------|-----------------|---------------|
| **Admin** | Full access | Full access | Full access | Full access |
| **Operator** | Full access | Full access | Read + Create* | Read + Execute* |
| **Engineer** | Full access | Own alerts only | Read only | Read only |
| **Viewer** | Aggregated only | View only | Search only | List only |

*Requires confirmation for destructive actions

---

## Getting Started

### Quick Start

1. **Try AI Inquiry**:
   - Navigate to `/inquiry`
   - Ask: "Show me alerts from yesterday"
   - Review the results and tool usage

2. **Use Troubleshooting**:
   - Open any alert detail page
   - Click "AI Assistant" tab
   - Ask: "What's causing this?"

3. **Explore RE-VIVE**:
   - Go to `/revive`
   - Try: "show me CPU dashboards" (Grafana mode)
   - Try: "list available runbooks" (AIOps mode)

### Best Practices

✅ **Do**:
- Be specific in your questions
- Provide context (time ranges, service names)
- Review tool executions before confirming
- Use natural language

❌ **Don't**:
- Request destructive actions without reviewing
- Share AI session links (they're user-specific)
- Assume AI has real-time data (it queries on demand)

---

## Key Features

### Real-Time Streaming
All AI responses stream in real-time via Server-Sent Events (SSE) or WebSocket for immediate feedback.

### Session Persistence
Conversations are saved and can be resumed. Each pillar maintains separate sessions.

### Tool Transparency
See exactly which tools the AI uses - every query, every API call is visible.

### Confirmation Workflows
High-risk actions (delete, execute) require explicit user confirmation with 5-minute expiry.

### Audit Trail
Complete audit log of all AI-initiated actions with user attribution and timing.

---

## MCP Integration

The platform uses the **Model Context Protocol (MCP)** to integrate with Grafana services:

- **20+ Grafana Tools**: Dashboards, alerts, queries, datasources
- **Standardized Protocol**: Consistent tool interface
- **No Custom Code**: Leverage existing MCP Grafana server
- **Real-Time Data**: Direct queries to Prometheus, Loki, Tempo

See [MCP Integration Guide](admin_guides/MCP_INTEGRATION.md) for details.

---

## Support & Troubleshooting

### Common Issues

**"Permission denied"**
- Check your role permissions with admin
- Some tools require specific role levels

**"Tool execution failed"**
- Verify Grafana/backend connectivity
- Check MCP server health: `curl http://localhost:8081/health`

**"Session not found"**
- Sessions expire after inactivity
- Start a new session by sending a message

### Getting Help

- **User Guides**: See `docs/user_guides/` for detailed pillar guides
- **Admin Guides**: See `docs/admin_guides/` for management docs
- **API Reference**: See `docs/API_REFERENCE.md` for programmatic access

---

## What's Next?

**Planned Enhancements**:
- Voice input for hands-free operation
- Export conversations as markdown/PDF
- Smart action suggestions
- Team collaboration on sessions
- Analytics dashboard for AI usage

---

## Technical Details

- **LLM Provider**: Configurable (OpenAI, Anthropic, Azure, etc.)
- **Database**: PostgreSQL for sessions/audit
- **Protocols**: SSE + WebSocket for streaming
- **Security**: JWT-based auth, RBAC, audit logging
- **Performance**: Average response time < 3s, 99th percentile < 10s

---

For detailed guides, see:
- [AI Inquiry User Guide](user_guides/AI_INQUIRY_USER_GUIDE.md)
- [Troubleshooting AI Guide](user_guides/TROUBLESHOOTING_AI_GUIDE.md)
- [RE-VIVE User Guide](user_guides/REVIVE_USER_GUIDE.md)
- [AI RBAC Admin Guide](admin_guides/AI_RBAC_ADMIN_GUIDE.md)
