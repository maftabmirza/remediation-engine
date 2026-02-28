# RE-VIVE User Guide

## What is RE-VIVE?

RE-VIVE (Remediation Engine - Virtual Intelligence Versatile Environment) is your unified AI assistant that seamlessly works across both Grafana observability and AIOps remediation platforms. It automatically detects your context and provides the right tools for the job.

## Access

Navigate to **`/revive`** in your browser.

## Two Modes

RE-VIVE operates in two distinct modes based on your current context:

### 🎨 Grafana Mode
**Triggered when**:
- Browsing Grafana pages (`/grafana/*`)
- Mentioning Grafana keywords (dashboard, prometheus, alert rule, etc.)

**Capabilities**:
- Search, create, update, delete dashboards
- Manage alert rules
- Query Prometheus metrics (PromQL)
- Query Loki logs (LogQL)
- Create annotations
- List datasources

### ⚙️ AIOps Mode
**Triggered when**:
- Browsing AIOps pages (`/remediation/*`, `/servers/*`)
- Mentioning AIOps keywords (runbook, server, execute, etc.)

**Capabilities**:
- List and search runbooks
- View server inventory
- Execute runbooks (with confirmation)
- Manage credentials
- View audit logs

### 🔮 Auto Mode
When context is ambiguous, RE-VIVE uses AI to detect the appropriate mode from your message.

---

## Getting Started

### Example Conversations

#### Grafana Mode

```
You: "show me all CPU dashboards"
RE-VIVE: [Switches to Grafana mode]
         🔧 Using tool: search_dashboards
         Found 3 dashboards:
         1. CPU Metrics - uid: cpu-001
         2. System CPU Usage - uid: sys-cpu
         3. Container CPU - uid: cont-cpu

You: "create a new dashboard for memory metrics"
RE-VIVE: 🔧 Using tool: create_dashboard
         ✅ Created dashboard: Memory Metrics
         URL: /d/mem-new-001

You: "query prometheus for node_cpu_seconds_total"
RE-VIVE: 🔧 Using tool: query_prometheus
         Results: [shows metric data]
```

#### AIOps Mode

```
You: "list runbooks for nginx"
RE-VIVE: [Switches to AIOps mode]
         🔧 Using tool: search_runbooks
         Found 2 runbooks:
         1. Restart Nginx Service
         2. Nginx Configuration Check

You: "show me all Linux servers"
RE-VIVE: 🔧 Using tool: list_servers
         Found 5 servers:
         - prod-web-01 (Ubuntu 22.04)
         - prod-web-02 (Ubuntu 22.04)
         ...

You: "execute restart nginx on prod-web-01"
RE-VIVE: ⚠️ Confirmation Required
         Risk Level: HIGH
         Action: Execute runbook "Restart Nginx"
         Target: prod-web-01
         
         [Approve] [Reject]
```

---

## UI Features

### Mode Indicator
Top-right badge shows current mode:
- 🟠 **Grafana Mode** - Orange badge
- 🟣 **AIOps Mode** - Purple badge
- 🔵 **Auto Mode** - Blue badge

### Session Management
- **Dropdown**: Select previous conversations
- **New Session**: Start fresh conversation
- Sessions persist across page refreshes

### Connection Status
- 🟢 **Connected** - Active WebSocket
- 🟡 **Connecting** - Reconnecting
- 🔴 **Disconnected** - Connection lost (auto-reconnects)

### Tool Visualization
See which tools are being used in real-time:
```
🔧 search_dashboards
🔧 query_prometheus  
✅ Done
```

### Stop Generation
Click the **Stop** button to cancel ongoing AI response.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift + Enter` | New line |
| `Ctrl + K` | Focus input |

---

## Permission Levels

Your available actions depend on your role:

| Action | Admin | Operator | Engineer | Viewer |
|--------|-------|----------|----------|--------|
| Search/View | ✅ | ✅ | ✅ | ✅ |
| Create | ✅ | ⚠️ Confirm | ❌ | ❌ |
| Update | ✅ | ⚠️ Confirm | ❌ | ❌ |
| Delete | ✅ | ❌ | ❌ | ❌ |
| Execute Runbook | ✅ | ⚠️ Confirm | ❌ | ❌ |

⚠️ = Requires confirmation

---

## Best Practices

### ✅ Do

1. **Be Specific**
   - ❌ "show dashboards"
   - ✅ "show CPU dashboards created this week"

2. **Provide Context**
   - ❌ "create a dashboard"
   - ✅ "create a dashboard for monitoring nginx on prod servers"

3. **Review Before Confirming**
   - Always read confirmation dialogs
   - Verify target servers/resources
   - Check risk level

4. **Use Natural Language**
   - "find alerts for the payment service"
   - "what runbooks do we have for MySQL?"

### ❌ Don't

1. **Don't Rush Confirmations**
   - High-risk actions are gated for a reason
   - Review before approving

2. **Don't Share Sessions**
   - Sessions are user-specific
   - Create separate sessions for different contexts

3. **Don't Assume Real-Time**
   - RE-VIVE queries on-demand
   - Data is fetched when you ask

---

## Confirmation Workflow

For high-risk actions (delete, execute), you'll see:

```
⚠️ Confirmation Required

Action: Delete Dashboard
Resource: "Old CPU Dashboard" (uid: old-cpu-001)
Risk Level: MEDIUM

This action cannot be undone. Are you sure?

Expires in: 4:32

[✅ Approve]  [❌ Reject]
```

**What Happens**:
1. Confirmation created with 5-minute expiry
2. Action is paused waiting for your decision
3. Click Approve → Action executes
4. Click Reject → Action cancelled
5. Timeout → Action expires (auto-reject)

---

## Troubleshooting

### Connection Issues

**Problem**: "Disconnected" status

**Solutions**:
1. Check internet connection
2. Wait for auto-reconnect (happens automatically)
3. Refresh page if persistent

---

### Mode Not Switching

**Problem**: RE-VIVE stays in wrong mode

**Solutions**:
1. Be explicit: "switch to grafana mode"
2. Use mode-specific keywords
3. Navigate to relevant page before asking

---

### Tool Execution Errors

**Problem**: "Tool execution failed"

**Possible Causes**:
- Permission denied (check with admin)
- Grafana/backend unavailable
- Invalid parameters

**Solution**:
- Check error message for details
- Verify permissions with `GET /api/v1/admin/ai/permissions`
- Contact admin if persistent

---

### Session Lost

**Problem**: "Session not found"

**Solution**:
- Sessions expire after 24 hours of inactivity
- Start new session by sending a message
- Previous sessions available in dropdown

---

## Advanced Usage

### Multi-Step Workflows

RE-VIVE remembers conversation context:

```
You: "search for CPU dashboards"
RE-VIVE: [shows 3 dashboards]

You: "show me the first one"  # References previous results
RE-VIVE: [loads dashboard details]

You: "create a copy of it"  # References loaded dashboard
RE-VIVE: [creates copy]
```

### Page Context Integration

RE-VIVE knows your current page:

```
[On /grafana/d/cpu-001]
You: "what alerts are configured for this dashboard?"
RE-VIVE: [Queries alerts for dashboard uid: cpu-001]
```

### Combining Modes

Switch modes mid-conversation:

```
You: "show grafana dashboards for nginx"  # Grafana mode
RE-VIVE: [shows dashboards]

You: "now show me the runbooks for nginx"  # Switches to AIOps
RE-VIVE: [shows runbooks]
```

---

## Tips & Tricks

💡 **Tip**: Use "explain" to understand results
```
You: "explain this PromQL query: rate(http_requests_total[5m])"
RE-VIVE: This calculates the per-second rate of HTTP requests...
```

💡 **Tip**: Ask for examples
```
You: "show me an example runbook for restarting a service"
RE-VIVE: [providestemplate and explanation]
```

💡 **Tip**: Get help anytime
```
You: "what can you help me with?"
RE-VIVE: I can help with:
         Grafana: dashboards, alerts, queries...
         AIOps: runbooks, servers, execution...
```

---

## Privacy & Security

- ✅ Conversations are private and user-specific
- ✅ All actions are audited with user attribution
- ✅ Permissions enforced by RBAC
- ✅ Sensitive data not logged
- ✅ WebSocket connections are authenticated

---

## Feedback

Help improve RE-VIVE:
- Report issues to your admin
- Suggest new features
- Share successful use cases

---

## What's Next?

Explore more AI features:
- [AI Inquiry](AI_INQUIRY_USER_GUIDE.md) - Historical analytics
- [Troubleshooting AI](TROUBLESHOOTING_AI_GUIDE.md) - Live diagnostics
- [AI Features Overview](../AI_FEATURES_OVERVIEW.md) - Complete guide
