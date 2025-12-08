# AIOps Gaps Implementation Plan

**Created:** December 2024
**Status:** Planning
**Scope:** All 12 identified gaps from AIOPS_EVALUATION.md

---

## Overview

This plan addresses all gaps required to achieve full AIOps maturity. Organized into 4 phases with clear dependencies and deliverables.

```
Phase 1: Foundation (Weeks 1-3)     → 80% Maturity
Phase 2: Intelligence (Weeks 4-6)  → 85% Maturity
Phase 3: Automation (Weeks 7-9)    → 90% Maturity
Phase 4: Enterprise (Weeks 10-12)  → 95% Maturity
```

---

## Gap Inventory

| # | Gap | Priority | Phase | Dependencies |
|---|-----|----------|-------|--------------|
| 1 | Predictive Analytics / Anomaly Detection | HIGH | 2 | Gap 4 (Logs) |
| 2 | Event Correlation / Topology Awareness | HIGH | 2 | Gap 5 (Changes) |
| 3 | AI Feedback Loop | HIGH | 1 | None |
| 4 | Log Aggregation / Analysis | MEDIUM | 2 | None |
| 5 | Change Correlation | MEDIUM | 1 | None |
| 6 | Notification / Escalation | MEDIUM | 1 | None |
| 7 | Capacity Planning / Trend Analysis | MEDIUM | 3 | Gap 1, Gap 4 |
| 8 | Runbook Git Sync | LOW | 3 | None |
| 9 | Multi-Tenancy | LOW | 4 | All |
| 10 | SLA/SLO Tracking | LOW | 3 | Gap 2 |
| 11 | ChatOps Interface | LOW | 4 | Gap 6 |
| 12 | Incident Timeline Visualization | LOW | 2 | Gap 2 |

---

## Phase 1: Foundation Layer

**Goal:** Establish core feedback, notification, and change tracking infrastructure

### Gap 3: AI Feedback Loop

**Objective:** Enable AI to learn from remediation outcomes

#### Data Model
```python
# app/models_feedback.py

class RemediationFeedback(Base):
    __tablename__ = "remediation_feedback"

    id: int                          # Primary key
    alert_id: int                    # FK to Alert
    execution_id: Optional[int]      # FK to RunbookExecution (if applicable)
    feedback_type: str               # "helpful" | "not_helpful" | "incorrect" | "partially_helpful"
    rating: Optional[int]            # 1-5 star rating
    user_id: int                     # FK to User
    comment: Optional[str]           # Free-text feedback
    correct_action: Optional[str]    # What should have been done
    created_at: datetime

class AnalysisFeedback(Base):
    __tablename__ = "analysis_feedback"

    id: int
    alert_id: int
    analysis_section: str            # "root_cause" | "impact" | "remediation" | "prevention"
    is_accurate: bool
    user_correction: Optional[str]
    user_id: int
    created_at: datetime

class SuccessfulRemediation(Base):
    """Curated examples for few-shot learning"""
    __tablename__ = "successful_remediations"

    id: int
    alert_pattern: str               # Alert name pattern for matching
    alert_labels: dict               # Key labels for similarity
    problem_summary: str             # Condensed problem description
    solution_summary: str            # What worked
    runbook_id: Optional[int]        # If automated
    manual_steps: Optional[str]      # If manual
    verified_by: int                 # User who verified
    verified_at: datetime
    use_count: int                   # Times used as example
```

#### API Endpoints
```
POST /api/alerts/{id}/feedback              # Submit feedback on alert analysis
POST /api/executions/{id}/feedback          # Submit feedback on runbook execution
GET  /api/feedback/stats                    # Feedback analytics
POST /api/remediations/successful           # Mark as successful example
GET  /api/remediations/similar?alert_id=X   # Find similar past remediations
```

#### LLM Integration
```python
# Enhance prompt with successful examples
async def build_analysis_prompt(alert: Alert) -> str:
    # 1. Find similar successful remediations
    similar = await get_similar_remediations(alert, limit=3)

    # 2. Build few-shot examples section
    examples = format_examples(similar)

    # 3. Include in system prompt
    prompt = f"""
    You are an AIOps assistant. Here are similar past incidents that were successfully resolved:

    {examples}

    Now analyze this new alert:
    {format_alert(alert)}
    """
    return prompt
```

#### Files to Modify/Create
- `app/models_feedback.py` (new)
- `app/routers/feedback.py` (new)
- `app/services/feedback_service.py` (new)
- `app/services/llm_service.py` (modify - add few-shot)
- `templates/alert_detail.html` (modify - add feedback UI)

---

### Gap 5: Change Correlation

**Objective:** Track deployments and correlate with incidents

#### Data Model
```python
# app/models_changes.py

class ChangeEvent(Base):
    __tablename__ = "change_events"

    id: int
    event_type: str                  # "deployment" | "config_change" | "scaling" | "rollback" | "maintenance"
    source: str                      # "github" | "jenkins" | "argocd" | "manual" | "kubernetes"
    service: str                     # Affected service name
    environment: str                 # "production" | "staging" | "development"
    version: Optional[str]           # New version/tag
    previous_version: Optional[str]  # Previous version
    description: str
    user: Optional[str]              # Who made the change
    commit_sha: Optional[str]        # Git commit if applicable
    timestamp: datetime
    duration_seconds: Optional[int]  # How long the change took
    status: str                      # "started" | "completed" | "failed" | "rolled_back"
    metadata: dict                   # Additional context (labels, annotations)

    # Correlation fields
    related_alerts: List[int]        # Alerts that occurred during/after change
    correlation_score: Optional[float]  # 0-1 likelihood change caused issues

class ChangeCorrelation(Base):
    """Links changes to alerts"""
    __tablename__ = "change_correlations"

    id: int
    change_event_id: int
    alert_id: int
    correlation_type: str            # "temporal" | "service_match" | "user_confirmed"
    time_delta_seconds: int          # Alert time - Change time
    confidence: float                # 0-1
    confirmed_by: Optional[int]      # User who confirmed correlation
```

#### API Endpoints
```
POST /webhook/changes                        # Ingest change events
GET  /api/changes                            # List changes with filters
GET  /api/changes/{id}                       # Change details
GET  /api/alerts/{id}/related-changes        # Changes near alert time
POST /api/changes/{id}/correlate/{alert_id}  # Manually link change to alert
GET  /api/changes/stats                      # Change frequency metrics
```

#### Webhook Payloads
```python
# GitHub Actions / Jenkins / ArgoCD webhook
{
    "event_type": "deployment",
    "source": "github",
    "service": "payment-service",
    "environment": "production",
    "version": "v2.3.1",
    "previous_version": "v2.3.0",
    "description": "Deploy payment service with new retry logic",
    "user": "developer@example.com",
    "commit_sha": "abc123",
    "timestamp": "2024-12-08T10:30:00Z",
    "status": "completed",
    "metadata": {
        "pr_number": 456,
        "jira_ticket": "PAY-789"
    }
}
```

#### Correlation Logic
```python
async def correlate_alert_with_changes(alert: Alert) -> List[ChangeCorrelation]:
    """Find changes that might have caused this alert"""

    correlations = []

    # 1. Temporal correlation: Changes in last 2 hours before alert
    recent_changes = await get_changes_before(alert.timestamp, hours=2)

    for change in recent_changes:
        score = 0.0

        # Time proximity (closer = higher score)
        delta = (alert.timestamp - change.timestamp).seconds
        time_score = max(0, 1 - (delta / 7200))  # 0-1 based on 2hr window
        score += time_score * 0.4

        # Service match
        if change.service in alert.labels.get("service", ""):
            score += 0.3

        # Environment match
        if change.environment == alert.labels.get("env", ""):
            score += 0.2

        # Change type (deployments more likely to cause issues)
        if change.event_type == "deployment":
            score += 0.1

        if score > 0.3:  # Threshold
            correlations.append(ChangeCorrelation(
                change_event_id=change.id,
                alert_id=alert.id,
                correlation_type="temporal",
                time_delta_seconds=delta,
                confidence=score
            ))

    return correlations
```

#### LLM Context Enhancement
```python
# Add to analysis prompt
async def get_change_context(alert: Alert) -> str:
    changes = await correlate_alert_with_changes(alert)
    if not changes:
        return "No recent changes detected in related services."

    context = "Recent changes that may be relevant:\n"
    for c in changes[:3]:
        change = await get_change(c.change_event_id)
        context += f"""
        - {change.event_type}: {change.service} @ {change.timestamp}
          Version: {change.previous_version} → {change.version}
          Description: {change.description}
          Correlation confidence: {c.confidence:.0%}
        """
    return context
```

#### Files to Modify/Create
- `app/models_changes.py` (new)
- `app/routers/changes.py` (new)
- `app/services/change_service.py` (new)
- `app/services/llm_service.py` (modify - add change context)
- `app/routers/webhook.py` (modify - add change webhook)

---

### Gap 6: Notification / Escalation

**Objective:** Multi-channel notifications with escalation policies

#### Data Model
```python
# app/models_notifications.py

class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: int
    name: str                        # "Production Slack", "PagerDuty On-Call"
    channel_type: str                # "slack" | "pagerduty" | "teams" | "email" | "webhook"
    config_encrypted: str            # Encrypted: webhook_url, api_key, routing_key, etc.
    is_enabled: bool
    created_by: int
    created_at: datetime

class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id: int
    name: str
    description: Optional[str]

    # Trigger conditions
    trigger_on: List[str]            # ["alert_received", "analysis_complete", "approval_needed",
                                     #  "execution_started", "execution_success", "execution_failed"]
    severity_filter: Optional[List[str]]  # ["critical", "warning"]
    alert_pattern: Optional[str]     # Alert name pattern

    # Actions
    channels: List[int]              # FK to NotificationChannel

    # Escalation
    escalation_enabled: bool
    escalation_delay_minutes: int    # Wait before escalating
    escalation_channels: List[int]   # Escalation targets

    # Rate limiting
    rate_limit_count: int            # Max notifications
    rate_limit_window_minutes: int   # Per time window

    is_enabled: bool
    priority: int
    created_at: datetime

class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: int
    rule_id: int
    channel_id: int
    trigger_event: str
    alert_id: Optional[int]
    execution_id: Optional[int]
    status: str                      # "sent" | "failed" | "rate_limited" | "escalated"
    response: Optional[str]          # Provider response
    sent_at: datetime

class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"

    id: int
    name: str
    levels: List[dict]               # [{delay_minutes, channels[], repeat_count}]
    is_default: bool
```

#### Channel Configurations
```python
# Slack
{
    "webhook_url": "https://hooks.slack.com/services/...",
    "channel": "#incidents",
    "username": "AIOps Bot",
    "icon_emoji": ":robot_face:"
}

# PagerDuty
{
    "routing_key": "your-integration-key",
    "api_url": "https://events.pagerduty.com/v2/enqueue"
}

# Microsoft Teams
{
    "webhook_url": "https://outlook.office.com/webhook/..."
}

# Email (SMTP)
{
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "username": "notifications@example.com",
    "password": "encrypted",
    "from_address": "aiops@example.com",
    "to_addresses": ["oncall@example.com"]
}

# Generic Webhook
{
    "url": "https://your-service.com/webhook",
    "method": "POST",
    "headers": {"Authorization": "Bearer token"},
    "template": "jinja2_template"
}
```

#### API Endpoints
```
# Channels
GET    /api/notifications/channels
POST   /api/notifications/channels
PATCH  /api/notifications/channels/{id}
DELETE /api/notifications/channels/{id}
POST   /api/notifications/channels/{id}/test    # Send test notification

# Rules
GET    /api/notifications/rules
POST   /api/notifications/rules
PATCH  /api/notifications/rules/{id}
DELETE /api/notifications/rules/{id}

# Logs
GET    /api/notifications/logs

# Escalation Policies
GET    /api/notifications/escalation-policies
POST   /api/notifications/escalation-policies
```

#### Notification Service
```python
# app/services/notification_service.py

class NotificationService:
    providers: Dict[str, NotificationProvider] = {
        "slack": SlackProvider(),
        "pagerduty": PagerDutyProvider(),
        "teams": TeamsProvider(),
        "email": EmailProvider(),
        "webhook": WebhookProvider(),
    }

    async def send_notification(
        self,
        event_type: str,
        alert: Optional[Alert] = None,
        execution: Optional[RunbookExecution] = None,
    ) -> List[NotificationLog]:
        """Send notifications based on matching rules"""

        # 1. Find matching rules
        rules = await self.get_matching_rules(event_type, alert)

        logs = []
        for rule in rules:
            # 2. Check rate limits
            if await self.is_rate_limited(rule):
                logs.append(NotificationLog(status="rate_limited", ...))
                continue

            # 3. Send to each channel
            for channel_id in rule.channels:
                channel = await self.get_channel(channel_id)
                provider = self.providers[channel.channel_type]

                message = self.format_message(event_type, alert, execution)
                result = await provider.send(channel.config, message)

                logs.append(NotificationLog(
                    status="sent" if result.success else "failed",
                    response=result.response,
                    ...
                ))

            # 4. Schedule escalation if enabled
            if rule.escalation_enabled:
                await self.schedule_escalation(rule, alert, execution)

        return logs
```

#### Message Templates
```python
# Slack message format
def format_slack_message(event_type: str, alert: Alert) -> dict:
    color_map = {"critical": "#ff0000", "warning": "#ffa500", "info": "#0000ff"}

    return {
        "attachments": [{
            "color": color_map.get(alert.severity, "#808080"),
            "title": f"🚨 {alert.alert_name}",
            "title_link": f"https://aiops.example.com/alerts/{alert.id}",
            "fields": [
                {"title": "Severity", "value": alert.severity, "short": True},
                {"title": "Instance", "value": alert.instance, "short": True},
                {"title": "Status", "value": alert.status, "short": True},
                {"title": "Time", "value": alert.timestamp.isoformat(), "short": True},
            ],
            "text": alert.annotations.get("description", ""),
            "footer": "AIOps Remediation Engine",
            "ts": int(alert.timestamp.timestamp())
        }],
        "blocks": [
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "View Alert"},
                     "url": f"https://aiops.example.com/alerts/{alert.id}"},
                    {"type": "button", "text": {"type": "plain_text", "text": "Acknowledge"},
                     "action_id": f"ack_{alert.id}"}
                ]
            }
        ]
    }
```

#### Files to Modify/Create
- `app/models_notifications.py` (new)
- `app/routers/notifications.py` (new)
- `app/services/notification_service.py` (new)
- `app/services/providers/slack.py` (new)
- `app/services/providers/pagerduty.py` (new)
- `app/services/providers/teams.py` (new)
- `app/services/providers/email.py` (new)
- `templates/settings/notifications.html` (new)

---

## Phase 2: Intelligence Layer

**Goal:** Add correlation, log analysis, anomaly detection, and timeline visualization

### Gap 2: Event Correlation / Topology Awareness

**Objective:** Group related alerts into incidents and understand service dependencies

#### Data Model
```python
# app/models_incidents.py

class Incident(Base):
    """Groups related alerts into a single incident"""
    __tablename__ = "incidents"

    id: int
    title: str                       # Auto-generated or manual
    description: Optional[str]
    status: str                      # "open" | "investigating" | "identified" | "mitigated" | "resolved"
    severity: str                    # Highest severity of member alerts

    # Correlation info
    correlation_method: str          # "temporal" | "topology" | "label" | "manual" | "ml"
    root_cause_alert_id: Optional[int]  # Primary alert

    # Impact
    affected_services: List[str]
    affected_environments: List[str]
    estimated_impact: Optional[str]  # "high" | "medium" | "low"
    customer_impact: bool

    # Timeline
    started_at: datetime             # First alert time
    detected_at: datetime            # When incident created
    acknowledged_at: Optional[datetime]
    mitigated_at: Optional[datetime]
    resolved_at: Optional[datetime]

    # Assignment
    assigned_to: Optional[int]       # User
    assigned_team: Optional[str]

    # Post-mortem
    postmortem_url: Optional[str]
    lessons_learned: Optional[str]

    created_by: int
    created_at: datetime
    updated_at: datetime

class IncidentAlert(Base):
    """Many-to-many: Incidents contain multiple alerts"""
    __tablename__ = "incident_alerts"

    id: int
    incident_id: int
    alert_id: int
    added_at: datetime
    added_by: Optional[int]          # Null if auto-correlated
    is_root_cause: bool

class ServiceDependency(Base):
    """Service topology for correlation"""
    __tablename__ = "service_dependencies"

    id: int
    source_service: str              # Service that depends on target
    target_service: str              # Service being depended upon
    dependency_type: str             # "sync" | "async" | "database" | "cache" | "external"
    criticality: str                 # "critical" | "degraded" | "optional"
    discovered_from: str             # "manual" | "kubernetes" | "consul" | "istio"
    metadata: dict
    created_at: datetime
    updated_at: datetime

class ServiceTopology(Base):
    """Service registry"""
    __tablename__ = "service_topology"

    id: int
    service_name: str
    service_type: str                # "api" | "worker" | "database" | "cache" | "queue"
    environment: str
    namespace: Optional[str]         # Kubernetes namespace
    owner_team: Optional[str]
    criticality: str                 # "tier1" | "tier2" | "tier3"
    health_check_url: Optional[str]
    documentation_url: Optional[str]
    labels: dict
    discovered_from: str
    last_seen: datetime
```

#### Correlation Engine
```python
# app/services/correlation_service.py

class CorrelationEngine:
    """Groups alerts into incidents using multiple strategies"""

    async def process_alert(self, alert: Alert) -> Optional[Incident]:
        """Determine if alert belongs to existing incident or creates new one"""

        # Strategy 1: Temporal clustering (alerts within 5 minutes)
        recent_incidents = await self.get_recent_open_incidents(minutes=30)
        for incident in recent_incidents:
            if await self.is_temporally_related(alert, incident):
                await self.add_alert_to_incident(alert, incident)
                return incident

        # Strategy 2: Topology-based (upstream/downstream services)
        related_services = await self.get_related_services(alert.service)
        for incident in recent_incidents:
            if await self.has_topology_overlap(incident, related_services):
                await self.add_alert_to_incident(alert, incident)
                return incident

        # Strategy 3: Label matching (same deployment, same host)
        for incident in recent_incidents:
            if await self.has_label_match(alert, incident, keys=["deployment", "host", "pod"]):
                await self.add_alert_to_incident(alert, incident)
                return incident

        # No match: Create new incident
        return await self.create_incident_from_alert(alert)

    async def is_temporally_related(self, alert: Alert, incident: Incident) -> bool:
        """Check if alert is within time window of incident"""
        window = timedelta(minutes=5)
        return abs(alert.timestamp - incident.started_at) < window

    async def get_related_services(self, service: str) -> List[str]:
        """Get upstream and downstream services"""
        deps = await self.db.query(ServiceDependency).filter(
            or_(
                ServiceDependency.source_service == service,
                ServiceDependency.target_service == service
            )
        ).all()
        return [d.source_service for d in deps] + [d.target_service for d in deps]

    async def identify_root_cause(self, incident: Incident) -> Optional[Alert]:
        """Use topology to identify root cause alert"""
        alerts = await self.get_incident_alerts(incident.id)

        # Build dependency graph
        graph = await self.build_service_graph([a.service for a in alerts])

        # Root cause is typically the most upstream failing service
        for alert in sorted(alerts, key=lambda a: a.timestamp):
            upstream_count = graph.get_upstream_count(alert.service)
            if upstream_count == 0:  # No dependencies = potential root cause
                return alert

        # Fallback: earliest alert
        return min(alerts, key=lambda a: a.timestamp)
```

#### API Endpoints
```
# Incidents
GET    /api/incidents                        # List with filters
POST   /api/incidents                        # Create manually
GET    /api/incidents/{id}                   # Details with alerts
PATCH  /api/incidents/{id}                   # Update status, assign
POST   /api/incidents/{id}/alerts            # Add alert manually
DELETE /api/incidents/{id}/alerts/{alert_id} # Remove alert
POST   /api/incidents/{id}/merge/{other_id}  # Merge incidents

# Topology
GET    /api/topology/services                # Service registry
POST   /api/topology/services                # Register service
GET    /api/topology/dependencies            # All dependencies
POST   /api/topology/dependencies            # Add dependency
GET    /api/topology/graph                   # Full graph for visualization
POST   /api/topology/discover                # Trigger auto-discovery

# Correlation
GET    /api/correlation/config               # Correlation settings
PATCH  /api/correlation/config               # Update settings
```

#### Files to Modify/Create
- `app/models_incidents.py` (new)
- `app/routers/incidents.py` (new)
- `app/routers/topology.py` (new)
- `app/services/correlation_service.py` (new)
- `app/services/topology_service.py` (new)
- `templates/incidents.html` (new)
- `templates/topology.html` (new)

---

### Gap 4: Log Aggregation / Analysis

**Objective:** Query logs during AI analysis for deeper context

#### Data Model
```python
# app/models_logs.py

class LogSource(Base):
    """Log backend configuration"""
    __tablename__ = "log_sources"

    id: int
    name: str                        # "Production Loki", "ELK Cluster"
    source_type: str                 # "loki" | "elasticsearch" | "cloudwatch" | "splunk"
    config_encrypted: str            # Connection details
    is_enabled: bool
    is_default: bool

class LogQuery(Base):
    """Saved log queries"""
    __tablename__ = "log_queries"

    id: int
    name: str
    source_id: int
    query_template: str              # Jinja2 template with {{instance}}, {{service}}, etc.
    time_range_minutes: int
    description: Optional[str]

class AlertLogContext(Base):
    """Cached log context for alerts"""
    __tablename__ = "alert_log_contexts"

    id: int
    alert_id: int
    source_id: int
    query_used: str
    log_summary: str                 # LLM-generated summary
    log_snippet: str                 # Key log lines
    error_patterns: List[str]        # Extracted error patterns
    queried_at: datetime
```

#### Log Providers
```python
# app/services/log_providers/loki.py

class LokiProvider:
    async def query(self, config: dict, query: str, start: datetime, end: datetime) -> List[LogEntry]:
        """Query Loki for logs"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config['url']}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": int(start.timestamp() * 1e9),
                    "end": int(end.timestamp() * 1e9),
                    "limit": config.get("limit", 1000)
                },
                headers={"Authorization": f"Bearer {config.get('token', '')}"}
            )
            return self.parse_response(response.json())

# app/services/log_providers/elasticsearch.py

class ElasticsearchProvider:
    async def query(self, config: dict, query: str, start: datetime, end: datetime) -> List[LogEntry]:
        """Query Elasticsearch for logs"""
        # Build ES query DSL
        body = {
            "query": {
                "bool": {
                    "must": [{"query_string": {"query": query}}],
                    "filter": [{"range": {"@timestamp": {"gte": start.isoformat(), "lte": end.isoformat()}}}]
                }
            },
            "size": config.get("limit", 1000),
            "sort": [{"@timestamp": "desc"}]
        }
        # Execute query...
```

#### Log Analysis Service
```python
# app/services/log_analysis_service.py

class LogAnalysisService:
    async def get_log_context(self, alert: Alert) -> str:
        """Fetch and summarize relevant logs for an alert"""

        # 1. Determine time range (alert time ± 5 minutes)
        start = alert.timestamp - timedelta(minutes=5)
        end = alert.timestamp + timedelta(minutes=5)

        # 2. Build query from alert labels
        query = self.build_query(alert)  # e.g., {instance="web-1", level="error"}

        # 3. Query log source
        source = await self.get_default_source()
        provider = self.get_provider(source.source_type)
        logs = await provider.query(source.config, query, start, end)

        if not logs:
            return "No relevant logs found in the time window."

        # 4. Extract key patterns
        error_patterns = self.extract_error_patterns(logs)

        # 5. Summarize with LLM (if too many logs)
        if len(logs) > 50:
            summary = await self.summarize_logs(logs)
        else:
            summary = self.format_log_snippet(logs[:20])

        return f"""
        Log Analysis ({len(logs)} entries found):

        Error Patterns Detected:
        {chr(10).join(f'- {p}' for p in error_patterns[:5])}

        Key Log Entries:
        {summary}
        """

    def build_query(self, alert: Alert) -> str:
        """Build log query from alert labels"""
        # Loki example
        labels = []
        if alert.instance:
            labels.append(f'instance="{alert.instance}"')
        if alert.labels.get("pod"):
            labels.append(f'pod="{alert.labels["pod"]}"')
        if alert.labels.get("namespace"):
            labels.append(f'namespace="{alert.labels["namespace"]}"')

        return "{" + ", ".join(labels) + "} |= `error` or |= `exception` or |= `fatal`"
```

#### Integration with LLM
```python
# Modify app/services/llm_service.py

async def analyze_alert(self, alert: Alert, provider_id: Optional[int] = None) -> str:
    # ... existing code ...

    # NEW: Add log context
    log_context = await self.log_service.get_log_context(alert)

    prompt = f"""
    {self.base_prompt}

    Alert Details:
    {format_alert(alert)}

    Recent Log Activity:
    {log_context}

    Recent Changes:
    {change_context}

    Please analyze this alert...
    """
```

#### API Endpoints
```
# Log Sources
GET    /api/logs/sources
POST   /api/logs/sources
PATCH  /api/logs/sources/{id}
DELETE /api/logs/sources/{id}
POST   /api/logs/sources/{id}/test         # Test connection

# Log Queries
GET    /api/logs/queries
POST   /api/logs/queries
GET    /api/logs/query                      # Execute ad-hoc query
GET    /api/alerts/{id}/logs               # Get logs for specific alert
```

#### Files to Modify/Create
- `app/models_logs.py` (new)
- `app/routers/logs.py` (new)
- `app/services/log_analysis_service.py` (new)
- `app/services/log_providers/loki.py` (new)
- `app/services/log_providers/elasticsearch.py` (new)
- `app/services/llm_service.py` (modify)
- `templates/settings/log_sources.html` (new)

---

### Gap 1: Predictive Analytics / Anomaly Detection

**Objective:** Predict incidents before they occur using historical patterns

#### Data Model
```python
# app/models_predictions.py

class MetricForecast(Base):
    """Predicted metric values"""
    __tablename__ = "metric_forecasts"

    id: int
    metric_name: str
    labels: dict                     # {instance, job, etc.}
    forecast_time: datetime          # When prediction was made
    predicted_values: List[dict]     # [{timestamp, value, lower, upper}]
    model_type: str                  # "prophet" | "arima" | "lstm"
    confidence_level: float

class AnomalyDetection(Base):
    """Detected anomalies"""
    __tablename__ = "anomaly_detections"

    id: int
    metric_name: str
    labels: dict
    detected_at: datetime
    anomaly_type: str                # "spike" | "drop" | "trend_change" | "pattern_break"
    severity: str                    # "low" | "medium" | "high"
    expected_value: float
    actual_value: float
    deviation_percent: float
    context: str                     # Description
    alert_generated: bool
    alert_id: Optional[int]

class PredictiveRule(Base):
    """Rules for predictive alerting"""
    __tablename__ = "predictive_rules"

    id: int
    name: str
    metric_pattern: str              # Metric name pattern
    label_filters: dict

    # Thresholds
    anomaly_sensitivity: float       # 0-1 (lower = more sensitive)
    forecast_horizon_hours: int      # How far ahead to predict
    threshold_breach_percent: float  # % deviation to trigger

    # Actions
    create_alert: bool
    notify_channels: List[int]
    suggested_runbook_id: Optional[int]

    is_enabled: bool
```

#### Prediction Service
```python
# app/services/prediction_service.py

class PredictionService:
    async def train_forecast_model(self, metric_name: str, labels: dict) -> ForecastModel:
        """Train time-series forecast model"""
        # 1. Fetch historical data from Prometheus
        history = await self.prometheus.query_range(
            metric_name, labels,
            start=datetime.now() - timedelta(days=30),
            end=datetime.now(),
            step="5m"
        )

        # 2. Prepare data for Prophet
        df = pd.DataFrame(history)
        df.columns = ["ds", "y"]

        # 3. Train model
        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=True
        )
        model.fit(df)

        return model

    async def detect_anomalies(self, metric_name: str, labels: dict, window_hours: int = 1) -> List[Anomaly]:
        """Detect anomalies in recent data"""
        # Use Isolation Forest or similar
        recent = await self.prometheus.query_range(...)

        # Statistical anomaly detection
        mean = np.mean(recent)
        std = np.std(recent)

        anomalies = []
        for point in recent:
            z_score = abs(point.value - mean) / std
            if z_score > 3:  # 3 sigma
                anomalies.append(Anomaly(
                    anomaly_type="spike" if point.value > mean else "drop",
                    expected_value=mean,
                    actual_value=point.value,
                    deviation_percent=((point.value - mean) / mean) * 100
                ))

        return anomalies

    async def predict_breach(self, metric_name: str, labels: dict, threshold: float) -> Optional[datetime]:
        """Predict when metric will breach threshold"""
        model = await self.get_or_train_model(metric_name, labels)

        future = model.make_future_dataframe(periods=24*12, freq="5min")  # 24 hours
        forecast = model.predict(future)

        # Find first breach
        for _, row in forecast.iterrows():
            if row["yhat"] > threshold:
                return row["ds"]

        return None  # No predicted breach
```

#### Alert Pattern Learning
```python
# app/services/pattern_learning_service.py

class PatternLearningService:
    """Learn from alert history to predict escalations"""

    async def predict_escalation(self, alert: Alert) -> dict:
        """Predict if alert will escalate to critical"""

        # 1. Find similar historical alerts
        similar = await self.find_similar_alerts(alert, limit=100)

        # 2. Calculate escalation rate
        escalated = [a for a in similar if a.severity == "critical"]
        escalation_rate = len(escalated) / len(similar) if similar else 0

        # 3. Analyze escalation patterns
        avg_time_to_escalate = self.calculate_avg_escalation_time(escalated)

        return {
            "escalation_probability": escalation_rate,
            "predicted_time_to_escalate": avg_time_to_escalate,
            "similar_incidents": len(similar),
            "recommendation": "Immediate attention needed" if escalation_rate > 0.5 else "Monitor"
        }

    async def get_trending_alerts(self) -> List[dict]:
        """Identify alert patterns that are increasing"""
        # Group alerts by name/pattern over time
        # Detect increasing frequency
        # Return alerts that are "trending up"
        pass
```

#### API Endpoints
```
# Predictions
GET  /api/predictions/forecasts              # Active forecasts
POST /api/predictions/forecast               # Create forecast for metric
GET  /api/predictions/anomalies              # Recent anomalies
GET  /api/predictions/escalation/{alert_id}  # Escalation prediction

# Rules
GET    /api/predictions/rules
POST   /api/predictions/rules
PATCH  /api/predictions/rules/{id}

# Patterns
GET  /api/predictions/trending               # Trending alert patterns
GET  /api/predictions/insights               # ML-generated insights
```

#### Files to Modify/Create
- `app/models_predictions.py` (new)
- `app/routers/predictions.py` (new)
- `app/services/prediction_service.py` (new)
- `app/services/pattern_learning_service.py` (new)
- `templates/predictions.html` (new)
- `requirements.txt` (add: prophet, scikit-learn)

---

### Gap 12: Incident Timeline Visualization

**Objective:** Visual timeline showing incident progression

#### Frontend Component
```javascript
// static/js/incident-timeline.js

class IncidentTimeline {
    constructor(containerId, incident) {
        this.container = document.getElementById(containerId);
        this.incident = incident;
        this.events = [];
    }

    async loadEvents() {
        // Fetch all events for incident
        const [alerts, changes, executions, comments] = await Promise.all([
            fetch(`/api/incidents/${this.incident.id}/alerts`),
            fetch(`/api/incidents/${this.incident.id}/changes`),
            fetch(`/api/incidents/${this.incident.id}/executions`),
            fetch(`/api/incidents/${this.incident.id}/comments`)
        ]);

        this.events = this.mergeAndSort([
            ...alerts.map(a => ({type: 'alert', time: a.timestamp, data: a})),
            ...changes.map(c => ({type: 'change', time: c.timestamp, data: c})),
            ...executions.map(e => ({type: 'execution', time: e.started_at, data: e})),
            ...comments.map(c => ({type: 'comment', time: c.created_at, data: c}))
        ]);
    }

    render() {
        const html = `
            <div class="timeline">
                ${this.events.map(e => this.renderEvent(e)).join('')}
            </div>
        `;
        this.container.innerHTML = html;
    }

    renderEvent(event) {
        const icons = {
            alert: '🚨',
            change: '🔄',
            execution: '⚡',
            comment: '💬'
        };

        return `
            <div class="timeline-event timeline-event-${event.type}">
                <div class="timeline-icon">${icons[event.type]}</div>
                <div class="timeline-content">
                    <div class="timeline-time">${this.formatTime(event.time)}</div>
                    <div class="timeline-title">${this.getTitle(event)}</div>
                    <div class="timeline-details">${this.getDetails(event)}</div>
                </div>
            </div>
        `;
    }
}
```

#### API Enhancement
```python
# Add to app/routers/incidents.py

@router.get("/{incident_id}/timeline")
async def get_incident_timeline(incident_id: int, db: Session = Depends(get_db)):
    """Get unified timeline of all incident events"""

    events = []

    # Alerts
    alerts = await get_incident_alerts(db, incident_id)
    events.extend([{
        "type": "alert",
        "timestamp": a.timestamp.isoformat(),
        "title": f"Alert: {a.alert_name}",
        "severity": a.severity,
        "details": a.annotations.get("description", "")
    } for a in alerts])

    # Changes (correlated)
    changes = await get_correlated_changes(db, incident_id)
    events.extend([{
        "type": "change",
        "timestamp": c.timestamp.isoformat(),
        "title": f"{c.event_type}: {c.service}",
        "details": c.description
    } for c in changes])

    # Executions
    executions = await get_incident_executions(db, incident_id)
    events.extend([{
        "type": "execution",
        "timestamp": e.started_at.isoformat(),
        "title": f"Runbook: {e.runbook.name}",
        "status": e.status,
        "details": e.output_summary
    } for e in executions])

    # Sort by timestamp
    events.sort(key=lambda x: x["timestamp"])

    return {"events": events}
```

#### Files to Modify/Create
- `static/js/incident-timeline.js` (new)
- `static/css/timeline.css` (new)
- `templates/incident_detail.html` (new)
- `app/routers/incidents.py` (modify)

---

## Phase 3: Advanced Automation

**Goal:** Enhance runbook capabilities and add capacity planning

### Gap 7: Capacity Planning / Trend Analysis

**Objective:** Predict resource exhaustion and generate capacity reports

#### Data Model
```python
# app/models_capacity.py

class CapacityMetric(Base):
    __tablename__ = "capacity_metrics"

    id: int
    resource_type: str               # "cpu" | "memory" | "disk" | "network" | "custom"
    resource_name: str               # "web-cluster", "postgres-primary"
    current_usage: float
    current_capacity: float
    usage_trend: str                 # "increasing" | "stable" | "decreasing"
    predicted_exhaustion: Optional[datetime]
    last_updated: datetime

class CapacityReport(Base):
    __tablename__ = "capacity_reports"

    id: int
    report_type: str                 # "weekly" | "monthly" | "on_demand"
    generated_at: datetime
    report_data: dict                # Full report JSON
    recommendations: List[str]
    generated_by: int

class CapacityThreshold(Base):
    __tablename__ = "capacity_thresholds"

    id: int
    resource_type: str
    resource_pattern: str
    warning_threshold: float         # e.g., 0.7 (70%)
    critical_threshold: float        # e.g., 0.9 (90%)
    forecast_days: int               # Alert if predicted breach within N days
    notify_channels: List[int]
```

#### Capacity Service
```python
# app/services/capacity_service.py

class CapacityService:
    async def analyze_capacity(self, resource_type: str) -> List[CapacityMetric]:
        """Analyze current and projected capacity"""

        metrics = []

        # Query Prometheus for resource usage
        queries = {
            "cpu": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            "memory": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
            "disk": '(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100'
        }

        results = await self.prometheus.query(queries[resource_type])

        for result in results:
            # Get historical data for trend
            history = await self.prometheus.query_range(...)
            trend = self.calculate_trend(history)

            # Predict exhaustion
            if trend == "increasing":
                exhaustion = await self.predict_exhaustion(history, threshold=0.9)
            else:
                exhaustion = None

            metrics.append(CapacityMetric(
                resource_type=resource_type,
                resource_name=result.labels["instance"],
                current_usage=result.value,
                current_capacity=100,  # Percentage-based
                usage_trend=trend,
                predicted_exhaustion=exhaustion
            ))

        return metrics

    async def generate_report(self, report_type: str) -> CapacityReport:
        """Generate capacity planning report"""

        # Collect all metrics
        cpu = await self.analyze_capacity("cpu")
        memory = await self.analyze_capacity("memory")
        disk = await self.analyze_capacity("disk")

        # Generate recommendations
        recommendations = []

        for metric in cpu + memory + disk:
            if metric.predicted_exhaustion:
                days_until = (metric.predicted_exhaustion - datetime.now()).days
                if days_until < 7:
                    recommendations.append(
                        f"CRITICAL: {metric.resource_name} {metric.resource_type} "
                        f"predicted to exhaust in {days_until} days"
                    )
                elif days_until < 30:
                    recommendations.append(
                        f"WARNING: {metric.resource_name} {metric.resource_type} "
                        f"predicted to exhaust in {days_until} days"
                    )

        return CapacityReport(
            report_type=report_type,
            report_data={
                "cpu": [m.dict() for m in cpu],
                "memory": [m.dict() for m in memory],
                "disk": [m.dict() for m in disk],
                "summary": self.generate_summary(cpu, memory, disk)
            },
            recommendations=recommendations
        )
```

#### API Endpoints
```
GET  /api/capacity/metrics                   # Current capacity metrics
GET  /api/capacity/metrics/{type}            # By resource type
GET  /api/capacity/forecast/{resource}       # Forecast for resource
GET  /api/capacity/reports                   # List reports
POST /api/capacity/reports                   # Generate report
GET  /api/capacity/reports/{id}              # Get report
GET  /api/capacity/recommendations           # Active recommendations
```

---

### Gap 8: Runbook Git Sync

**Objective:** Sync runbook definitions from Git repositories

#### Data Model
```python
# Extend app/models_remediation.py

class RunbookRepository(Base):
    __tablename__ = "runbook_repositories"

    id: int
    name: str
    repo_url: str                    # git@github.com:org/runbooks.git
    branch: str                      # "main"
    path: str                        # "runbooks/" (directory within repo)
    auth_type: str                   # "ssh_key" | "token" | "none"
    auth_encrypted: Optional[str]
    sync_enabled: bool
    sync_interval_minutes: int
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_commit: Optional[str]
```

#### Git Sync Service
```python
# app/services/git_sync_service.py

class GitSyncService:
    async def sync_repository(self, repo: RunbookRepository) -> SyncResult:
        """Sync runbooks from Git repository"""

        # 1. Clone/pull repository
        repo_path = await self.ensure_repo(repo)

        # 2. Find runbook files (YAML)
        runbook_files = list(Path(repo_path / repo.path).glob("**/*.yaml"))

        results = {"created": 0, "updated": 0, "unchanged": 0, "errors": []}

        for file in runbook_files:
            try:
                # 3. Parse YAML
                definition = yaml.safe_load(file.read_text())

                # 4. Validate schema
                validated = RunbookSchema(**definition)

                # 5. Check if exists
                existing = await self.get_runbook_by_source(repo.id, str(file))

                if existing:
                    if existing.checksum != self.compute_checksum(definition):
                        await self.update_runbook(existing, validated)
                        results["updated"] += 1
                    else:
                        results["unchanged"] += 1
                else:
                    await self.create_runbook(repo, file, validated)
                    results["created"] += 1

            except Exception as e:
                results["errors"].append({"file": str(file), "error": str(e)})

        return SyncResult(**results)
```

#### Runbook YAML Schema
```yaml
# Example runbook definition: runbooks/restart-service.yaml
name: Restart Service
description: Safely restart a failing service
category: infrastructure
tags: [restart, service, recovery]

execution:
  mode: semi_auto
  approval_required: true
  approval_timeout_minutes: 30
  max_executions_per_hour: 5
  cooldown_minutes: 15

triggers:
  - alert_pattern: "ServiceDown*"
    severity: [critical, warning]
    min_duration_seconds: 300

steps:
  - name: Check current status
    type: command
    command_linux: systemctl status {{service_name}}
    timeout_seconds: 30
    continue_on_fail: true

  - name: Graceful restart
    type: command
    command_linux: systemctl restart {{service_name}}
    requires_elevation: true
    timeout_seconds: 60
    rollback_command_linux: systemctl start {{service_name}}

  - name: Verify service health
    type: api
    method: GET
    endpoint: "{{health_check_url}}"
    expected_status_codes: [200]
    retry_count: 3
    retry_delay_seconds: 10

notifications:
  on_success:
    - channel: slack
      message: "Service {{service_name}} restarted successfully"
  on_failure:
    - channel: pagerduty
      severity: critical
```

---

### Gap 10: SLA/SLO Tracking

**Objective:** Define SLA targets and track compliance

#### Data Model
```python
# app/models_sla.py

class SLADefinition(Base):
    __tablename__ = "sla_definitions"

    id: int
    name: str                        # "Critical Alert Response"
    description: str

    # Targets
    target_mtta_minutes: float       # Mean Time to Acknowledge
    target_mttr_minutes: float       # Mean Time to Resolve
    target_availability: float       # 99.9%
    target_success_rate: float       # Remediation success rate

    # Scope
    applies_to_severity: List[str]   # ["critical", "warning"]
    applies_to_services: List[str]   # ["payment-*", "auth-*"]

    # Alerting
    breach_notify_channels: List[int]
    warning_threshold_percent: float  # Alert at 80% of SLA

    is_active: bool
    created_at: datetime

class SLAReport(Base):
    __tablename__ = "sla_reports"

    id: int
    sla_id: int
    period_start: datetime
    period_end: datetime

    # Actuals
    actual_mtta_minutes: float
    actual_mttr_minutes: float
    actual_availability: float
    actual_success_rate: float

    # Compliance
    mtta_compliant: bool
    mttr_compliant: bool
    availability_compliant: bool
    success_rate_compliant: bool
    overall_compliant: bool

    # Details
    total_incidents: int
    breached_incidents: int
    breach_details: List[dict]

class SLABreach(Base):
    __tablename__ = "sla_breaches"

    id: int
    sla_id: int
    alert_id: int
    incident_id: Optional[int]
    breach_type: str                 # "mtta" | "mttr" | "availability"
    target_value: float
    actual_value: float
    breached_at: datetime
    notified: bool
```

#### SLA Service
```python
# app/services/sla_service.py

class SLAService:
    async def check_compliance(self, sla: SLADefinition, period: str = "current_month") -> SLAReport:
        """Check SLA compliance for a period"""

        start, end = self.get_period_bounds(period)

        # Get relevant alerts
        alerts = await self.get_alerts_in_scope(sla, start, end)

        # Calculate metrics
        mtta = self.calculate_mtta(alerts)
        mttr = self.calculate_mttr(alerts)
        availability = await self.calculate_availability(sla.applies_to_services, start, end)
        success_rate = await self.calculate_success_rate(alerts)

        # Check compliance
        report = SLAReport(
            sla_id=sla.id,
            period_start=start,
            period_end=end,
            actual_mtta_minutes=mtta,
            actual_mttr_minutes=mttr,
            actual_availability=availability,
            actual_success_rate=success_rate,
            mtta_compliant=mtta <= sla.target_mtta_minutes,
            mttr_compliant=mttr <= sla.target_mttr_minutes,
            availability_compliant=availability >= sla.target_availability,
            success_rate_compliant=success_rate >= sla.target_success_rate,
        )
        report.overall_compliant = all([
            report.mtta_compliant,
            report.mttr_compliant,
            report.availability_compliant,
            report.success_rate_compliant
        ])

        return report

    async def record_breach(self, sla: SLADefinition, alert: Alert, breach_type: str):
        """Record an SLA breach"""
        breach = SLABreach(
            sla_id=sla.id,
            alert_id=alert.id,
            breach_type=breach_type,
            target_value=getattr(sla, f"target_{breach_type}"),
            actual_value=self.get_actual_value(alert, breach_type),
            breached_at=datetime.now()
        )

        # Notify
        await self.notification_service.send(
            event_type="sla_breach",
            channels=sla.breach_notify_channels,
            context={"breach": breach, "alert": alert}
        )
```

---

## Phase 4: Enterprise Features

**Goal:** Multi-tenancy and ChatOps for enterprise deployment

### Gap 9: Multi-Tenancy

**Objective:** Support multiple teams/organizations with data isolation

#### Data Model
```python
# app/models_tenancy.py

class Organization(Base):
    __tablename__ = "organizations"

    id: int
    name: str
    slug: str                        # URL-safe identifier
    settings: dict                   # Org-level settings
    created_at: datetime

class Team(Base):
    __tablename__ = "teams"

    id: int
    organization_id: int
    name: str
    slug: str
    settings: dict
    created_at: datetime

class TeamMembership(Base):
    __tablename__ = "team_memberships"

    id: int
    team_id: int
    user_id: int
    role: str                        # "owner" | "admin" | "member" | "viewer"
    joined_at: datetime

# Add to existing models
class Alert(Base):
    # ... existing fields ...
    organization_id: int             # NEW: Tenant isolation
    team_id: Optional[int]           # NEW: Team scoping

class Runbook(Base):
    # ... existing fields ...
    organization_id: int
    team_id: Optional[int]
    visibility: str                  # "team" | "organization" | "private"
```

#### Tenant Context
```python
# app/middleware/tenant.py

class TenantMiddleware:
    async def __call__(self, request: Request, call_next):
        # Extract tenant from JWT or subdomain
        tenant_id = self.extract_tenant(request)

        # Set in request state
        request.state.organization_id = tenant_id

        response = await call_next(request)
        return response

# Use in queries
def get_alerts(db: Session, org_id: int, filters: AlertFilters):
    query = db.query(Alert).filter(Alert.organization_id == org_id)
    # ... apply filters ...
    return query.all()
```

---

### Gap 11: ChatOps Interface

**Objective:** Slack/Teams bot for incident management

#### Bot Commands
```
/aiops incidents                    - List active incidents
/aiops incident <id>                - Get incident details
/aiops ack <alert_id>               - Acknowledge alert
/aiops analyze <alert_id>           - Trigger AI analysis
/aiops run <runbook> [target]       - Execute runbook
/aiops approve <execution_id>       - Approve pending execution
/aiops status                       - System health overview
/aiops oncall                       - Show on-call schedule
```

#### Slack App Service
```python
# app/services/chatops/slack_bot.py

from slack_bolt.async_app import AsyncApp

class SlackBotService:
    def __init__(self):
        self.app = AsyncApp(token=settings.SLACK_BOT_TOKEN)
        self.register_handlers()

    def register_handlers(self):
        @self.app.command("/aiops")
        async def handle_command(ack, command, respond):
            await ack()

            args = command["text"].split()
            action = args[0] if args else "help"

            handlers = {
                "incidents": self.list_incidents,
                "incident": self.get_incident,
                "ack": self.acknowledge_alert,
                "analyze": self.trigger_analysis,
                "run": self.execute_runbook,
                "approve": self.approve_execution,
                "status": self.system_status,
                "help": self.show_help
            }

            handler = handlers.get(action, self.show_help)
            response = await handler(args[1:], command["user_id"])
            await respond(response)

        @self.app.action("approve_execution")
        async def handle_approval(ack, body, respond):
            await ack()
            execution_id = body["actions"][0]["value"]
            user = body["user"]["id"]

            result = await self.approve_execution_action(execution_id, user)
            await respond(result)

    async def list_incidents(self, args, user_id) -> dict:
        incidents = await self.incident_service.get_open_incidents(limit=5)

        blocks = [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Active Incidents*"}
        }]

        for inc in incidents:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{inc.title}*\n{inc.severity} | {inc.status} | {len(inc.alerts)} alerts"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View"},
                    "url": f"{settings.BASE_URL}/incidents/{inc.id}"
                }
            })

        return {"blocks": blocks}
```

---

## Dependency Graph

```
                    ┌─────────────────────┐
                    │    Gap 3: Feedback  │
                    │    (No deps)        │
                    └─────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ Gap 5: Change │   │ Gap 6: Notify   │   │ Gap 8: Git Sync │
│ Correlation   │   │                 │   │ (No deps)       │
└───────┬───────┘   └────────┬────────┘   └─────────────────┘
        │                    │
        ▼                    │
┌───────────────┐            │
│ Gap 2: Event  │◄───────────┘
│ Correlation   │
└───────┬───────┘
        │
        ├──────────────────────┐
        │                      │
        ▼                      ▼
┌───────────────┐    ┌─────────────────┐
│ Gap 4: Logs   │    │ Gap 12: Timeline│
└───────┬───────┘    └─────────────────┘
        │
        ▼
┌───────────────┐    ┌─────────────────┐
│ Gap 1: Predict│    │ Gap 10: SLA     │
│               │    │                 │
└───────┬───────┘    └────────┬────────┘
        │                     │
        ▼                     │
┌───────────────┐             │
│ Gap 7: Capac- │◄────────────┘
│ ity Planning  │
└───────────────┘

┌─────────────────────────────────────────────┐
│              Phase 4 (Independent)          │
│  Gap 9: Multi-Tenancy  ←  All other gaps    │
│  Gap 11: ChatOps       ←  Gap 6 (Notify)    │
└─────────────────────────────────────────────┘
```

---

## Summary

| Phase | Gaps | Key Deliverables |
|-------|------|------------------|
| **Phase 1** | 3, 5, 6 | Feedback loop, change tracking, Slack/PagerDuty |
| **Phase 2** | 1, 2, 4, 12 | Correlation engine, log context, predictions, timeline |
| **Phase 3** | 7, 8, 10 | Capacity reports, GitOps runbooks, SLA tracking |
| **Phase 4** | 9, 11 | Multi-tenancy, Slack bot |

**Total New Files:** ~40
**Total Modified Files:** ~15
**New Database Tables:** ~25
**New API Endpoints:** ~60
