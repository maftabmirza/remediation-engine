# AIOps Remediation Engine - Feature & Usability Improvements

**Focus Areas:** Learning from Feedback, User Interaction, Design Docs, SOPs
**Out of Scope:** Security, Automated Testing, HA, Scaling (future plans)

---

## Executive Summary

This document outlines improvements to transform the platform from a **reactive tool** into an **intelligent learning system** that:
- Learns from every remediation outcome
- Captures and surfaces institutional knowledge
- Provides contextual guidance from past incidents
- Enables self-service SOP management

### Current State vs Target State

| Capability | Current | Target |
|------------|---------|--------|
| Feedback Collection | None | Multi-dimensional (ratings, comments, outcomes) |
| Learning from Outcomes | None | Automatic correlation & improvement |
| Knowledge Base | Runbook templates only | Full wiki + SOPs + design docs |
| Similar Incident Discovery | None | AI-powered similarity matching |
| Onboarding Experience | Manual | Guided workflows + tutorials |
| User Customization | Minimal | Personalized dashboards + preferences |

---

## 1. Learning from Feedback System

### 1.1 Feedback Collection Framework

**Problem:** No way to capture if AI recommendations or runbook executions actually helped.

**Solution:** Multi-layer feedback collection at key moments.

#### Database Models

```python
# New table: feedback on AI analysis quality
class AnalysisFeedback(Base):
    __tablename__ = "analysis_feedback"

    id = Column(UUID, primary_key=True, default=uuid4)
    alert_id = Column(UUID, ForeignKey("alerts.id"), nullable=False)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)

    # Quick feedback
    helpful = Column(Boolean)  # Thumbs up/down
    rating = Column(Integer)   # 1-5 stars (optional)

    # Detailed feedback
    accuracy = Column(String)  # "accurate", "partially_accurate", "inaccurate"
    actionability = Column(String)  # "actionable", "vague", "wrong_direction"

    # Free-form
    comments = Column(Text)
    what_was_missing = Column(Text)
    what_actually_worked = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)


# New table: execution outcome tracking
class ExecutionOutcome(Base):
    __tablename__ = "execution_outcomes"

    id = Column(UUID, primary_key=True, default=uuid4)
    execution_id = Column(UUID, ForeignKey("runbook_executions.id"), nullable=False)
    alert_id = Column(UUID, ForeignKey("alerts.id"))  # Optional link
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)

    # Did it work?
    resolved_issue = Column(Boolean)
    resolution_type = Column(String)  # "full", "partial", "no_effect", "made_worse"

    # Time tracking
    time_to_resolution_minutes = Column(Integer)

    # Learning
    recommendation_followed = Column(Boolean)
    manual_steps_taken = Column(Text)  # What did user do differently?
    improvement_suggestion = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)


# New table: chat session feedback
class ChatFeedback(Base):
    __tablename__ = "chat_feedback"

    id = Column(UUID, primary_key=True, default=uuid4)
    session_id = Column(UUID, ForeignKey("chat_sessions.id"), nullable=False)
    message_id = Column(UUID, ForeignKey("chat_messages.id"))  # Specific message
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)

    helpful = Column(Boolean)
    rating = Column(Integer)  # 1-5
    feedback_type = Column(String)  # "great", "wrong", "incomplete", "confusing"
    comments = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
```

#### UI Implementation

**Alert Detail Page - After AI Analysis:**
```html
<!-- Inline feedback widget -->
<div class="feedback-widget" data-alert-id="{{ alert.id }}">
    <span>Was this analysis helpful?</span>
    <button class="btn-feedback" data-value="up">👍</button>
    <button class="btn-feedback" data-value="down">👎</button>
    <a href="#" class="expand-feedback">More feedback...</a>

    <!-- Expanded feedback form (hidden by default) -->
    <div class="feedback-expanded hidden">
        <label>How accurate was the root cause analysis?</label>
        <select name="accuracy">
            <option value="accurate">Spot on</option>
            <option value="partial">Partially correct</option>
            <option value="wrong">Missed the mark</option>
        </select>

        <label>What actually fixed the issue?</label>
        <textarea name="what_worked" placeholder="Describe what you did..."></textarea>

        <button type="submit">Submit Feedback</button>
    </div>
</div>
```

**Post-Execution Prompt:**
```html
<!-- Modal after runbook execution completes -->
<div class="modal" id="execution-outcome-modal">
    <h3>How did the remediation go?</h3>

    <div class="outcome-buttons">
        <button data-outcome="resolved">✅ Issue Resolved</button>
        <button data-outcome="partial">⚠️ Partially Fixed</button>
        <button data-outcome="no_effect">❌ No Effect</button>
    </div>

    <div class="follow-up hidden">
        <label>What else did you need to do?</label>
        <textarea name="manual_steps"></textarea>

        <label>How could this runbook be improved?</label>
        <textarea name="improvement"></textarea>
    </div>
</div>
```

---

### 1.2 Learning Engine

**Problem:** Feedback is collected but never used to improve the system.

**Solution:** Background service that analyzes feedback and surfaces insights.

#### Learning Service Architecture

```python
# app/services/learning_service.py

class LearningService:
    """Analyzes feedback to improve recommendations and runbooks."""

    async def analyze_runbook_effectiveness(self, runbook_id: UUID) -> RunbookInsights:
        """Calculate success metrics for a runbook."""
        executions = await self.get_executions(runbook_id, days=30)
        outcomes = await self.get_outcomes(runbook_id, days=30)

        return RunbookInsights(
            total_executions=len(executions),
            success_rate=self._calculate_success_rate(outcomes),
            avg_resolution_time=self._avg_resolution_time(outcomes),
            common_issues=self._extract_common_issues(outcomes),
            improvement_suggestions=self._aggregate_suggestions(outcomes),
            trending=self._calculate_trend(executions)
        )

    async def get_similar_past_incidents(
        self,
        alert: Alert,
        limit: int = 5
    ) -> list[SimilarIncident]:
        """Find similar alerts from history with their resolutions."""

        # Strategy 1: Exact fingerprint match (same alert, different times)
        fingerprint_matches = await self._find_by_fingerprint(
            alert.fingerprint,
            exclude_id=alert.id
        )

        # Strategy 2: Label similarity (same service, similar conditions)
        label_matches = await self._find_by_labels(
            alert.labels,
            similarity_threshold=0.7
        )

        # Strategy 3: Alert name pattern similarity
        name_matches = await self._find_by_name_similarity(alert.alert_name)

        # Combine and rank by relevance + recency
        combined = self._merge_and_rank(
            fingerprint_matches,
            label_matches,
            name_matches
        )

        # Enrich with outcome data
        return await self._enrich_with_outcomes(combined[:limit])

    async def generate_runbook_improvement_report(
        self,
        runbook_id: UUID
    ) -> ImprovementReport:
        """Generate actionable improvement recommendations."""

        outcomes = await self.get_outcomes(runbook_id, days=90)
        feedback = await self.get_feedback(runbook_id, days=90)

        # Analyze patterns
        failure_patterns = self._identify_failure_patterns(outcomes)
        missing_steps = self._extract_missing_steps(feedback)
        success_factors = self._identify_success_factors(outcomes)

        return ImprovementReport(
            runbook_id=runbook_id,
            recommendations=[
                f"Add step for: {step}" for step in missing_steps
            ],
            failure_patterns=failure_patterns,
            success_factors=success_factors,
            suggested_triggers=self._suggest_new_triggers(outcomes)
        )
```

#### Insights Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Learning Insights Dashboard                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TOP PERFORMING RUNBOOKS (Last 30 days)                         │
│  ┌──────────────────────────────┬────────┬─────────┬──────────┐ │
│  │ Runbook                      │ Runs   │ Success │ Avg Time │ │
│  ├──────────────────────────────┼────────┼─────────┼──────────┤ │
│  │ Restart Service              │ 145    │ 94%     │ 2.3 min  │ │
│  │ Clear Disk Space             │ 89     │ 87%     │ 4.1 min  │ │
│  │ Scale Pods                   │ 67     │ 91%     │ 1.8 min  │ │
│  └──────────────────────────────┴────────┴─────────┴──────────┘ │
│                                                                  │
│  ⚠️ RUNBOOKS NEEDING ATTENTION                                  │
│  • "Database Connection Fix" - 45% success rate, 12 failures    │
│    └─ Common issue: Missing step for connection pool reset      │
│  • "Memory Cleanup" - Users report "incomplete" 8 times         │
│    └─ Suggestion: Add swap clearing step                        │
│                                                                  │
│  📈 TRENDING ALERTS (Increasing frequency)                      │
│  • HighCPUUsage on prod-api-* (+34% this week)                  │
│  • DiskSpaceLow on logs-* (+22% this week)                      │
│                                                                  │
│  💡 AI ANALYSIS QUALITY                                         │
│  • Overall helpfulness: 78% positive                            │
│  • Most accurate for: Infrastructure alerts (89%)               │
│  • Needs improvement: Application errors (62%)                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 1.3 Contextual Recommendations

**Problem:** AI analysis doesn't leverage historical context.

**Solution:** Inject past incident data into LLM prompts.

#### Enhanced LLM Prompt Template

```python
# app/services/llm_service.py

async def build_analysis_prompt(self, alert: Alert) -> str:
    """Build prompt with historical context."""

    # Get similar past incidents
    learning = LearningService(self.db)
    similar_incidents = await learning.get_similar_past_incidents(alert, limit=3)

    # Get relevant runbook insights
    matching_runbooks = await self.get_matching_runbooks(alert)
    runbook_insights = [
        await learning.analyze_runbook_effectiveness(rb.id)
        for rb in matching_runbooks[:2]
    ]

    # Build context section
    historical_context = ""
    if similar_incidents:
        historical_context = """
## Historical Context

Similar incidents in the past:
"""
        for incident in similar_incidents:
            historical_context += f"""
### {incident.alert_name} ({incident.occurred_at.strftime('%Y-%m-%d')})
- **Resolution:** {incident.resolution_summary}
- **Time to resolve:** {incident.resolution_time_minutes} minutes
- **What worked:** {incident.what_worked}
"""

    # Build runbook effectiveness section
    runbook_context = ""
    if runbook_insights:
        runbook_context = """
## Available Runbooks Performance

"""
        for insight in runbook_insights:
            runbook_context += f"""
- **{insight.runbook_name}**: {insight.success_rate}% success rate
  - Common issues: {', '.join(insight.common_issues[:2])}
"""

    # Combine into full prompt
    return f"""
You are an expert SRE analyzing an alert. Provide actionable remediation guidance.

## Current Alert
- **Name:** {alert.alert_name}
- **Severity:** {alert.severity}
- **Instance:** {alert.instance}
- **Labels:** {json.dumps(alert.labels)}
- **Description:** {alert.annotations.get('description', 'N/A')}

{historical_context}

{runbook_context}

## Instructions
1. Analyze the root cause based on the alert details
2. Consider what worked in similar past incidents
3. Recommend specific remediation steps
4. If a runbook exists, mention it and any known issues
5. Provide commands that can be copy-pasted

Format your response with clear sections: Root Cause, Remediation Steps, Runbook Recommendation, Prevention.
"""
```

---

## 2. User Interaction Improvements

### 2.1 Guided Workflows

**Problem:** New users don't know the optimal path from alert to resolution.

**Solution:** Step-by-step guided workflows with progress tracking.

#### Workflow Definition

```python
# app/models_workflow.py

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id = Column(UUID, primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    trigger_type = Column(String)  # "alert", "manual", "scheduled"
    trigger_conditions = Column(JSONB)  # When to suggest this workflow

    # Steps defined as JSONB for flexibility
    steps = Column(JSONB)  # List of WorkflowStep objects

    # Metadata
    category = Column(String)
    estimated_duration_minutes = Column(Integer)
    skill_level = Column(String)  # "beginner", "intermediate", "expert"

    created_by = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id = Column(UUID, primary_key=True, default=uuid4)
    template_id = Column(UUID, ForeignKey("workflow_templates.id"))
    user_id = Column(UUID, ForeignKey("users.id"))
    alert_id = Column(UUID, ForeignKey("alerts.id"))  # Optional

    current_step = Column(Integer, default=0)
    status = Column(String)  # "in_progress", "completed", "abandoned"

    # Track time per step
    step_timestamps = Column(JSONB)  # {step_index: {"started": ..., "completed": ...}}

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
```

#### Example Workflow: Critical Alert Response

```yaml
name: Critical Alert Response
description: Standard procedure for handling critical severity alerts
trigger_type: alert
trigger_conditions:
  severity: critical

estimated_duration_minutes: 15
skill_level: beginner

steps:
  - id: acknowledge
    title: "Acknowledge the Alert"
    description: "Let the team know you're handling this"
    type: action
    action:
      type: api_call
      endpoint: /api/alerts/{alert_id}/acknowledge
    tips:
      - "Check if anyone else is already working on this in Slack"
      - "Update the incident channel if one exists"

  - id: review_analysis
    title: "Review AI Analysis"
    description: "Read the AI-generated analysis for context"
    type: review
    component: ai_analysis_panel
    tips:
      - "Pay attention to the root cause section"
      - "Check if similar incidents are mentioned"

  - id: connect_server
    title: "Connect to Affected Server"
    description: "Open a terminal session to investigate"
    type: action
    component: quick_connect
    context:
      server_from: alert.labels.instance
    tips:
      - "Use 'top' or 'htop' to check resource usage"
      - "Check logs with 'journalctl -u {service} -n 100'"

  - id: investigate
    title: "Investigate the Issue"
    description: "Run diagnostic commands to understand the problem"
    type: checklist
    items:
      - "Check service status"
      - "Review recent logs"
      - "Check resource usage (CPU, memory, disk)"
      - "Verify network connectivity"
    suggested_commands:
      - "systemctl status {service}"
      - "df -h"
      - "free -m"
      - "netstat -tlnp"

  - id: remediate
    title: "Apply Remediation"
    description: "Execute the fix"
    type: choice
    options:
      - label: "Run Recommended Runbook"
        action: execute_runbook
        component: runbook_selector
      - label: "Manual Fix"
        action: manual
        component: terminal
      - label: "Escalate"
        action: escalate
        component: escalation_form

  - id: verify
    title: "Verify Resolution"
    description: "Confirm the issue is fixed"
    type: checklist
    items:
      - "Service is running normally"
      - "Alert has resolved (or will resolve soon)"
      - "No related alerts firing"
      - "User/customer impact mitigated"

  - id: document
    title: "Document the Incident"
    description: "Record what happened and what you did"
    type: form
    fields:
      - name: root_cause
        label: "Root Cause"
        type: textarea
      - name: resolution
        label: "Resolution Steps"
        type: textarea
      - name: prevention
        label: "Prevention Ideas"
        type: textarea

  - id: feedback
    title: "Provide Feedback"
    description: "Help us improve"
    type: feedback
    component: execution_feedback
```

#### Workflow UI Component

```html
<!-- Workflow progress sidebar -->
<div class="workflow-sidebar">
    <div class="workflow-header">
        <h3>🔧 Critical Alert Response</h3>
        <span class="progress">Step 3 of 8</span>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 37.5%"></div>
        </div>
    </div>

    <div class="workflow-steps">
        <div class="step completed">
            <span class="step-icon">✓</span>
            <span class="step-title">Acknowledge Alert</span>
            <span class="step-time">2m ago</span>
        </div>

        <div class="step completed">
            <span class="step-icon">✓</span>
            <span class="step-title">Review AI Analysis</span>
        </div>

        <div class="step current">
            <span class="step-icon">→</span>
            <span class="step-title">Connect to Server</span>
            <div class="step-content">
                <p>Open a terminal to investigate</p>
                <button class="btn-primary" onclick="quickConnect()">
                    Quick Connect to prod-api-01
                </button>
                <div class="tips">
                    💡 Tip: Use 'top' to check CPU usage
                </div>
            </div>
        </div>

        <div class="step pending">
            <span class="step-icon">○</span>
            <span class="step-title">Investigate</span>
        </div>

        <!-- More steps... -->
    </div>

    <div class="workflow-actions">
        <button class="btn-secondary">Skip Step</button>
        <button class="btn-secondary">Pause Workflow</button>
        <button class="btn-link">Need Help?</button>
    </div>
</div>
```

---

### 2.2 Command Palette & Quick Actions

**Problem:** Users must navigate through menus to perform common actions.

**Solution:** Global command palette (Cmd+K / Ctrl+K) for instant access.

#### Implementation

```javascript
// static/js/command-palette.js

class CommandPalette {
    constructor() {
        this.commands = [];
        this.recentCommands = this.loadRecent();
        this.init();
    }

    init() {
        // Register default commands
        this.register({
            id: 'goto-alerts',
            title: 'Go to Alerts',
            keywords: ['alerts', 'incidents', 'list'],
            icon: '🚨',
            action: () => window.location.href = '/alerts'
        });

        this.register({
            id: 'goto-runbooks',
            title: 'Go to Runbooks',
            keywords: ['runbooks', 'playbooks', 'automation'],
            icon: '📋',
            action: () => window.location.href = '/runbooks'
        });

        this.register({
            id: 'new-runbook',
            title: 'Create New Runbook',
            keywords: ['new', 'create', 'runbook'],
            icon: '➕',
            action: () => openNewRunbookModal()
        });

        this.register({
            id: 'quick-ssh',
            title: 'Quick SSH Connect...',
            keywords: ['ssh', 'terminal', 'connect', 'server'],
            icon: '💻',
            action: () => openQuickConnectModal(),
            hasSubmenu: true
        });

        this.register({
            id: 'search-alerts',
            title: 'Search Alerts...',
            keywords: ['search', 'find', 'alerts'],
            icon: '🔍',
            action: (query) => searchAlerts(query),
            takesInput: true,
            placeholder: 'Search alerts by name, severity, or labels...'
        });

        this.register({
            id: 'analyze-alert',
            title: 'Analyze Current Alert',
            keywords: ['analyze', 'ai', 'llm'],
            icon: '🤖',
            context: 'alert-detail',  // Only show on alert detail page
            action: () => triggerAnalysis()
        });

        this.register({
            id: 'start-workflow',
            title: 'Start Guided Workflow...',
            keywords: ['workflow', 'guide', 'wizard'],
            icon: '🧭',
            action: () => openWorkflowSelector()
        });

        // Keyboard shortcut
        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                this.open();
            }
        });
    }

    register(command) {
        this.commands.push(command);
    }

    search(query) {
        if (!query) {
            return [...this.recentCommands, ...this.commands.slice(0, 5)];
        }

        const lowerQuery = query.toLowerCase();
        return this.commands
            .filter(cmd => {
                const matchesTitle = cmd.title.toLowerCase().includes(lowerQuery);
                const matchesKeyword = cmd.keywords.some(k =>
                    k.toLowerCase().includes(lowerQuery)
                );
                return matchesTitle || matchesKeyword;
            })
            .slice(0, 10);
    }

    open() {
        // Show palette modal
        document.getElementById('command-palette').classList.add('open');
        document.getElementById('command-input').focus();
    }
}
```

#### Command Palette UI

```html
<!-- Command palette overlay -->
<div id="command-palette" class="command-palette">
    <div class="palette-container">
        <div class="palette-input-wrapper">
            <span class="palette-icon">⌘</span>
            <input type="text"
                   id="command-input"
                   placeholder="Type a command or search..."
                   autocomplete="off">
            <kbd>ESC</kbd>
        </div>

        <div class="palette-results">
            <div class="result-section">
                <div class="section-title">Recent</div>
                <div class="result-item selected">
                    <span class="item-icon">🚨</span>
                    <span class="item-title">Go to Alerts</span>
                    <span class="item-shortcut">G A</span>
                </div>
            </div>

            <div class="result-section">
                <div class="section-title">Commands</div>
                <div class="result-item">
                    <span class="item-icon">💻</span>
                    <span class="item-title">Quick SSH Connect</span>
                    <span class="item-hint">→</span>
                </div>
                <div class="result-item">
                    <span class="item-icon">🤖</span>
                    <span class="item-title">Analyze Current Alert</span>
                </div>
            </div>
        </div>

        <div class="palette-footer">
            <span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span>
            <span><kbd>↵</kbd> Select</span>
            <span><kbd>ESC</kbd> Close</span>
        </div>
    </div>
</div>
```

---

### 2.3 Personalized Dashboard

**Problem:** One-size-fits-all dashboard doesn't match individual workflows.

**Solution:** Customizable dashboard with drag-and-drop widgets.

#### User Preferences Model

```python
# app/models.py - extend User model

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id = Column(UUID, ForeignKey("users.id"), primary_key=True)

    # Dashboard layout (JSON describing widget positions)
    dashboard_layout = Column(JSONB, default=lambda: {
        "widgets": [
            {"id": "active-alerts", "x": 0, "y": 0, "w": 2, "h": 2},
            {"id": "recent-executions", "x": 2, "y": 0, "w": 2, "h": 2},
            {"id": "my-servers", "x": 0, "y": 2, "w": 2, "h": 1},
            {"id": "quick-actions", "x": 2, "y": 2, "w": 2, "h": 1},
        ]
    })

    # Quick access items
    pinned_servers = Column(ARRAY(UUID))  # Favorite servers
    pinned_runbooks = Column(ARRAY(UUID))  # Favorite runbooks

    # Alert preferences
    default_alert_filters = Column(JSONB)  # {severity: [], status: []}
    alert_sound_enabled = Column(Boolean, default=True)

    # Terminal preferences
    terminal_font_size = Column(Integer, default=14)
    terminal_theme = Column(String, default="dark")

    # Notification preferences
    email_on_execution_complete = Column(Boolean, default=True)
    browser_notifications = Column(Boolean, default=True)

    # Theme
    ui_theme = Column(String, default="system")  # "light", "dark", "system"

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### Available Dashboard Widgets

```python
DASHBOARD_WIDGETS = {
    "active-alerts": {
        "title": "Active Alerts",
        "description": "Firing alerts by severity",
        "min_width": 1,
        "min_height": 1,
        "component": "ActiveAlertsWidget"
    },
    "recent-executions": {
        "title": "Recent Executions",
        "description": "Latest runbook executions",
        "min_width": 2,
        "min_height": 1,
        "component": "RecentExecutionsWidget"
    },
    "my-servers": {
        "title": "My Servers",
        "description": "Quick connect to pinned servers",
        "min_width": 1,
        "min_height": 1,
        "component": "PinnedServersWidget"
    },
    "quick-actions": {
        "title": "Quick Actions",
        "description": "Frequently used actions",
        "min_width": 1,
        "min_height": 1,
        "component": "QuickActionsWidget"
    },
    "system-health": {
        "title": "System Health",
        "description": "Overall platform health metrics",
        "min_width": 2,
        "min_height": 1,
        "component": "SystemHealthWidget"
    },
    "alert-trends": {
        "title": "Alert Trends",
        "description": "Alert frequency over time",
        "min_width": 2,
        "min_height": 2,
        "component": "AlertTrendsWidget"
    },
    "team-activity": {
        "title": "Team Activity",
        "description": "Recent actions by team members",
        "min_width": 2,
        "min_height": 1,
        "component": "TeamActivityWidget"
    },
    "learning-insights": {
        "title": "Learning Insights",
        "description": "Runbook effectiveness and suggestions",
        "min_width": 2,
        "min_height": 2,
        "component": "LearningInsightsWidget"
    },
    "on-call-status": {
        "title": "On-Call Status",
        "description": "Current on-call rotation",
        "min_width": 1,
        "min_height": 1,
        "component": "OnCallWidget"
    }
}
```

---

### 2.4 Contextual Help & Tooltips

**Problem:** Users need to learn the system through documentation.

**Solution:** In-context help that appears where needed.

#### Contextual Tips System

```python
# app/services/contextual_help.py

CONTEXTUAL_TIPS = {
    "alert_detail_page": [
        {
            "element": "#ai-analysis-section",
            "title": "AI Analysis",
            "content": "Click 'Analyze' to get AI-powered root cause analysis. "
                      "The AI considers alert labels, similar past incidents, "
                      "and known runbook effectiveness.",
            "show_once": True
        },
        {
            "element": "#quick-connect-btn",
            "title": "Quick Connect",
            "content": "Jump directly into a terminal session on the affected server. "
                      "The server is auto-detected from the alert's 'instance' label.",
            "show_once": True
        }
    ],
    "runbook_editor": [
        {
            "element": "#step-command-input",
            "title": "Using Variables",
            "content": "Use {{variable_name}} syntax to insert dynamic values. "
                      "Available: {{alert.name}}, {{alert.labels.instance}}, etc.",
            "show_once": False
        }
    ],
    "terminal": [
        {
            "element": ".terminal-container",
            "title": "Terminal Session",
            "content": "Commands you run here are logged for audit. "
                      "Use Ctrl+D or type 'exit' to close the session.",
            "show_once": True
        }
    ]
}
```

---

## 3. Knowledge Base & Documentation Hub

### 3.1 Integrated Wiki/Documentation System

**Problem:** SOPs, design docs, and tribal knowledge are scattered or missing.

**Solution:** Built-in wiki with categories and linking.

#### Knowledge Base Models

```python
# app/models_knowledge.py

class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(UUID, primary_key=True, default=uuid4)

    # Content
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)  # URL-friendly
    content = Column(Text)  # Markdown
    excerpt = Column(String)  # Short summary

    # Organization
    category = Column(String)  # "sop", "design_doc", "runbook_guide", "troubleshooting"
    tags = Column(ARRAY(String))
    parent_id = Column(UUID, ForeignKey("knowledge_articles.id"))  # For hierarchy

    # Visibility
    visibility = Column(String, default="team")  # "public", "team", "private"

    # Linking
    related_runbooks = Column(ARRAY(UUID))  # Link to runbooks
    related_alerts = Column(ARRAY(String))  # Alert name patterns

    # Versioning
    version = Column(Integer, default=1)

    # Metadata
    author_id = Column(UUID, ForeignKey("users.id"))
    last_editor_id = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Stats
    view_count = Column(Integer, default=0)
    helpful_count = Column(Integer, default=0)


class KnowledgeArticleVersion(Base):
    """Track article history for rollback."""
    __tablename__ = "knowledge_article_versions"

    id = Column(UUID, primary_key=True, default=uuid4)
    article_id = Column(UUID, ForeignKey("knowledge_articles.id"))
    version = Column(Integer)
    content = Column(Text)
    editor_id = Column(UUID, ForeignKey("users.id"))
    edit_summary = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### Knowledge Base Categories

```yaml
categories:
  sop:
    name: "Standard Operating Procedures"
    icon: "📋"
    description: "Step-by-step procedures for common operations"
    templates:
      - sop-template.md

  design_doc:
    name: "Design Documents"
    icon: "📐"
    description: "Architecture and design decisions"
    templates:
      - design-doc-template.md
      - adr-template.md  # Architecture Decision Record

  troubleshooting:
    name: "Troubleshooting Guides"
    icon: "🔧"
    description: "How to diagnose and fix common issues"
    templates:
      - troubleshooting-template.md

  service_docs:
    name: "Service Documentation"
    icon: "📚"
    description: "Documentation for each service/component"
    templates:
      - service-doc-template.md

  onboarding:
    name: "Onboarding"
    icon: "🎓"
    description: "Guides for new team members"
    templates:
      - onboarding-checklist.md

  postmortem:
    name: "Post-Incident Reviews"
    icon: "📊"
    description: "Learnings from past incidents"
    templates:
      - postmortem-template.md
```

#### SOP Template Example

```markdown
# SOP: [Title]

**Version:** 1.0
**Last Updated:** {{date}}
**Author:** {{author}}
**Approver:** {{approver}}

## Purpose
[Why does this procedure exist?]

## Scope
[When should this SOP be used?]

## Prerequisites
- [ ] Access to system X
- [ ] Permission level Y

## Procedure

### Step 1: [Action]
**Expected Time:** X minutes

[Detailed instructions]

```bash
# Example command
systemctl status myservice
```

**Expected Output:**
```
Active: active (running)
```

**If it fails:** Go to [Troubleshooting section](#troubleshooting)

### Step 2: [Action]
...

## Rollback Procedure
[How to undo if something goes wrong]

## Troubleshooting
### Common Issue 1
**Symptom:** [What you see]
**Cause:** [Why it happens]
**Solution:** [How to fix]

## Related Documents
- [[Runbook: Service Restart]]
- [[Design Doc: Service Architecture]]

## Change History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | {{date}} | {{author}} | Initial version |
```

---

### 3.2 Contextual Knowledge Surfacing

**Problem:** Relevant documentation isn't shown when needed.

**Solution:** Auto-surface related articles in context.

#### Knowledge Service

```python
# app/services/knowledge_service.py

class KnowledgeService:
    """Surface relevant knowledge articles contextually."""

    async def get_articles_for_alert(
        self,
        alert: Alert
    ) -> list[KnowledgeArticle]:
        """Find relevant articles for an alert."""

        articles = []

        # Match by alert name pattern
        pattern_matches = await self.db.execute(
            select(KnowledgeArticle)
            .where(
                KnowledgeArticle.related_alerts.any(alert.alert_name)
            )
        )
        articles.extend(pattern_matches.scalars().all())

        # Match by tags from alert labels
        service = alert.labels.get("service")
        if service:
            tag_matches = await self.db.execute(
                select(KnowledgeArticle)
                .where(KnowledgeArticle.tags.contains([service]))
            )
            articles.extend(tag_matches.scalars().all())

        # Full-text search on title/content
        search_matches = await self.search_articles(
            query=alert.alert_name,
            limit=3
        )
        articles.extend(search_matches)

        return self._dedupe_and_rank(articles)

    async def get_articles_for_runbook(
        self,
        runbook: Runbook
    ) -> list[KnowledgeArticle]:
        """Find documentation related to a runbook."""

        return await self.db.execute(
            select(KnowledgeArticle)
            .where(
                KnowledgeArticle.related_runbooks.contains([runbook.id])
            )
            .order_by(KnowledgeArticle.helpful_count.desc())
        ).scalars().all()

    async def suggest_articles_for_search(
        self,
        query: str
    ) -> list[KnowledgeArticle]:
        """Full-text search with ranking."""

        # Use PostgreSQL full-text search
        return await self.db.execute(
            select(KnowledgeArticle)
            .where(
                func.to_tsvector('english', KnowledgeArticle.title + ' ' + KnowledgeArticle.content)
                .match(query)
            )
            .order_by(KnowledgeArticle.view_count.desc())
            .limit(10)
        ).scalars().all()
```

#### Alert Detail Page - Knowledge Panel

```html
<!-- Related documentation sidebar -->
<div class="knowledge-panel">
    <h4>📚 Related Documentation</h4>

    {% if knowledge_articles %}
    <div class="article-list">
        {% for article in knowledge_articles %}
        <a href="/knowledge/{{ article.slug }}" class="article-card">
            <span class="article-icon">
                {{ category_icons[article.category] }}
            </span>
            <div class="article-info">
                <span class="article-title">{{ article.title }}</span>
                <span class="article-category">{{ article.category }}</span>
            </div>
            <span class="article-helpful">
                👍 {{ article.helpful_count }}
            </span>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <div class="no-articles">
        <p>No related documentation found.</p>
        <a href="/knowledge/new?alert={{ alert.id }}">
            Create documentation for this alert type
        </a>
    </div>
    {% endif %}

    <a href="/knowledge?q={{ alert.alert_name }}" class="see-all">
        Search knowledge base →
    </a>
</div>
```

---

### 3.3 Post-Incident Review (PIR) System

**Problem:** Learnings from incidents aren't captured systematically.

**Solution:** Structured PIR workflow with templates.

#### PIR Model

```python
# app/models_pir.py

class PostIncidentReview(Base):
    __tablename__ = "post_incident_reviews"

    id = Column(UUID, primary_key=True, default=uuid4)

    # Incident details
    title = Column(String, nullable=False)
    incident_date = Column(DateTime, nullable=False)
    severity = Column(String)  # P1, P2, P3, P4
    duration_minutes = Column(Integer)

    # Related items
    alert_ids = Column(ARRAY(UUID))
    execution_ids = Column(ARRAY(UUID))

    # Structured content
    summary = Column(Text)
    impact = Column(Text)  # What was affected

    timeline = Column(JSONB)  # [{"time": "10:00", "event": "Alert fired"}]

    root_cause = Column(Text)
    contributing_factors = Column(ARRAY(String))

    what_went_well = Column(ARRAY(String))
    what_went_poorly = Column(ARRAY(String))

    action_items = Column(JSONB)  # [{"title": "", "owner": "", "due_date": ""}]

    # Workflow
    status = Column(String, default="draft")  # draft, review, published
    author_id = Column(UUID, ForeignKey("users.id"))
    reviewers = Column(ARRAY(UUID))

    # Knowledge base link (auto-create article from PIR)
    knowledge_article_id = Column(UUID, ForeignKey("knowledge_articles.id"))

    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime)
```

#### PIR Template

```
┌─────────────────────────────────────────────────────────────────┐
│  📋 Post-Incident Review                                        │
│                                                                  │
│  Title: [Database Connection Failures - 2024-12-13]             │
│  Severity: P2            Duration: 45 minutes                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SUMMARY                                                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Brief description of what happened                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  IMPACT                                                          │
│  • Users affected: ~500                                          │
│  • Revenue impact: $X,XXX                                        │
│  • SLA breach: Yes / No                                          │
│                                                                  │
│  TIMELINE                                                        │
│  ┌──────────┬──────────────────────────────────────────────────┐ │
│  │ 10:00    │ Alert fired: DatabaseConnectionHigh              │ │
│  │ 10:05    │ On-call acknowledged                             │ │
│  │ 10:15    │ Root cause identified: connection pool exhausted │ │
│  │ 10:30    │ Fix deployed: increased pool size                │ │
│  │ 10:45    │ Alert resolved                                   │ │
│  └──────────┴──────────────────────────────────────────────────┘ │
│  [ + Add Event ]                                                 │
│                                                                  │
│  ROOT CAUSE                                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Connection pool was sized for normal load. Traffic spike   │ │
│  │ from marketing campaign exhausted available connections.   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  CONTRIBUTING FACTORS                                            │
│  ☑ No alerting on connection pool utilization                   │
│  ☑ Traffic spike was not communicated to ops team               │
│  ☐ Add more...                                                   │
│                                                                  │
│  WHAT WENT WELL                                                  │
│  + Quick identification of root cause                            │
│  + Runbook for connection issues was accurate                    │
│  [ + Add ]                                                       │
│                                                                  │
│  WHAT COULD BE IMPROVED                                          │
│  - No proactive monitoring of connection pool                    │
│  - Communication gap with marketing                              │
│  [ + Add ]                                                       │
│                                                                  │
│  ACTION ITEMS                                                    │
│  ┌────────────────────────────────┬──────────┬─────────────────┐ │
│  │ Action                         │ Owner    │ Due Date        │ │
│  ├────────────────────────────────┼──────────┼─────────────────┤ │
│  │ Add connection pool alerting   │ @alice   │ 2024-12-20      │ │
│  │ Create runbook for scaling     │ @bob     │ 2024-12-25      │ │
│  │ Set up marketing → ops channel │ @carol   │ 2024-12-18      │ │
│  └────────────────────────────────┴──────────┴─────────────────┘ │
│  [ + Add Action Item ]                                           │
│                                                                  │
│  ─────────────────────────────────────────────────────────────── │
│  [ Save Draft ]  [ Submit for Review ]  [ Publish ]              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. SOP Management System

### 4.1 SOP Lifecycle Management

**Problem:** SOPs become outdated and aren't regularly reviewed.

**Solution:** Built-in SOP lifecycle with review reminders.

#### SOP Model Extension

```python
# Extend KnowledgeArticle for SOP-specific features

class SOPMetadata(Base):
    __tablename__ = "sop_metadata"

    article_id = Column(UUID, ForeignKey("knowledge_articles.id"), primary_key=True)

    # Lifecycle
    status = Column(String, default="draft")  # draft, pending_review, approved, deprecated

    # Review cycle
    review_frequency_days = Column(Integer, default=90)
    last_reviewed_at = Column(DateTime)
    next_review_at = Column(DateTime)
    reviewer_id = Column(UUID, ForeignKey("users.id"))

    # Approval
    approved_by = Column(UUID, ForeignKey("users.id"))
    approved_at = Column(DateTime)

    # Ownership
    owner_id = Column(UUID, ForeignKey("users.id"))  # Primary owner
    stakeholders = Column(ARRAY(UUID))  # People to notify on changes

    # Training
    requires_training = Column(Boolean, default=False)
    training_completed_by = Column(ARRAY(UUID))  # Users who completed training

    # Usage tracking
    last_used_at = Column(DateTime)  # Last time someone followed this SOP
    use_count = Column(Integer, default=0)
```

#### SOP Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  📋 SOP Management                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ⚠️ NEEDS ATTENTION                                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ⏰ 3 SOPs due for review                                    │ │
│  │   • Database Backup Procedure (overdue by 15 days)         │ │
│  │   • Incident Response (due in 5 days)                      │ │
│  │   • Deployment Checklist (due in 12 days)                  │ │
│  │                                                             │ │
│  │ 📝 2 SOPs pending approval                                  │ │
│  │   • New: API Rate Limiting Procedure                       │ │
│  │   • Updated: Server Provisioning                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  RECENTLY USED (Last 7 days)                                    │
│  ┌────────────────────────────┬───────┬───────────────────────┐ │
│  │ SOP                        │ Uses  │ Last Used             │ │
│  ├────────────────────────────┼───────┼───────────────────────┤ │
│  │ Service Restart            │ 12    │ 2 hours ago           │ │
│  │ Disk Cleanup               │ 8     │ 5 hours ago           │ │
│  │ Database Failover          │ 3     │ 1 day ago             │ │
│  └────────────────────────────┴───────┴───────────────────────┘ │
│                                                                  │
│  BY CATEGORY                                                     │
│  ┌──────────────────┬─────────┬──────────┬────────────────────┐ │
│  │ Category         │ Total   │ Approved │ Needs Review       │ │
│  ├──────────────────┼─────────┼──────────┼────────────────────┤ │
│  │ Infrastructure   │ 15      │ 12       │ 3                  │ │
│  │ Application      │ 8       │ 7        │ 1                  │ │
│  │ Database         │ 6       │ 5        │ 1                  │ │
│  │ Security         │ 4       │ 4        │ 0                  │ │
│  └──────────────────┴─────────┴──────────┴────────────────────┘ │
│                                                                  │
│  [ + Create New SOP ]  [ Import from YAML ]  [ Export All ]     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.2 SOP Training & Compliance

**Problem:** Team members don't always know or follow SOPs.

**Solution:** Training tracking and compliance features.

```python
# app/models_training.py

class SOPTraining(Base):
    __tablename__ = "sop_training"

    id = Column(UUID, primary_key=True, default=uuid4)
    sop_id = Column(UUID, ForeignKey("knowledge_articles.id"))
    user_id = Column(UUID, ForeignKey("users.id"))

    status = Column(String)  # "not_started", "in_progress", "completed"

    # Quiz/acknowledgment
    quiz_score = Column(Integer)  # If quiz is required
    acknowledged_at = Column(DateTime)  # "I have read and understood"

    # Expiry (for periodic retraining)
    expires_at = Column(DateTime)

    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class SOPComplianceReport(Base):
    """Track SOP adherence during incident response."""
    __tablename__ = "sop_compliance_reports"

    id = Column(UUID, primary_key=True, default=uuid4)
    execution_id = Column(UUID, ForeignKey("runbook_executions.id"))
    sop_id = Column(UUID, ForeignKey("knowledge_articles.id"))

    followed_sop = Column(Boolean)
    deviations = Column(JSONB)  # What was done differently
    deviation_reason = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 5. Implementation Roadmap

### Phase 1: Feedback Foundation (2-3 weeks)
- [ ] Create feedback database models
- [ ] Add feedback widgets to alert detail page
- [ ] Add post-execution outcome modal
- [ ] Build feedback collection API endpoints
- [ ] Create basic insights dashboard

### Phase 2: Learning Engine (3-4 weeks)
- [ ] Implement similar incident matching
- [ ] Add historical context to LLM prompts
- [ ] Build runbook effectiveness tracking
- [ ] Create improvement suggestion system
- [ ] Add trending alerts detection

### Phase 3: Knowledge Base (3-4 weeks)
- [ ] Create knowledge article models
- [ ] Build article editor (Markdown)
- [ ] Implement full-text search
- [ ] Add contextual surfacing in UI
- [ ] Create SOP templates

### Phase 4: UX Improvements (2-3 weeks)
- [ ] Implement command palette
- [ ] Add customizable dashboard
- [ ] Create guided workflow system
- [ ] Add contextual help tooltips
- [ ] Implement keyboard shortcuts

### Phase 5: SOP & PIR System (2-3 weeks)
- [ ] Build SOP lifecycle management
- [ ] Create PIR workflow
- [ ] Add review reminders
- [ ] Implement training tracking
- [ ] Create compliance reporting

---

## Summary

These improvements will transform the platform from a **reactive remediation tool** to a **learning operations platform** that:

1. **Gets smarter over time** - learns from every incident and remediation
2. **Surfaces institutional knowledge** - documentation appears when needed
3. **Guides users effectively** - workflows prevent mistakes
4. **Captures learnings systematically** - PIRs create organizational memory
5. **Maintains SOP quality** - lifecycle management keeps docs current

The phased approach allows incremental value delivery while building toward a comprehensive solution.
