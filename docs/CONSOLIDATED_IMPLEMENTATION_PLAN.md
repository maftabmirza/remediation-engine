# AIOps Platform - Consolidated Implementation Plan
## AI Chat Integration with Grafana Observability Stack

**Document Version:** 2.0
**Date:** 2025-12-26
**Branch:** `copilot/add-grafana-theming-branding`
**Status:** Phase 1-2 Complete | Phase 3-5 Pending

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Architecture Overview](#architecture-overview)
4. [Implementation Roadmap](#implementation-roadmap)
5. [Detailed Feature Specifications](#detailed-feature-specifications)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Plan](#deployment-plan)
8. [Success Metrics](#success-metrics)

---

## Executive Summary

### What We're Building

Enable users to ask natural language questions about their applications and infrastructure, with AI providing data-driven answers by querying Prometheus metrics, Loki logs, and Tempo traces.

**Example User Interactions:**
- "Was the abc app healthy yesterday?" → AI queries Prometheus, analyzes SLOs, provides verdict
- "How many errors occurred in the last 24 hours?" → AI queries Loki, counts errors, shows breakdown
- "What was the server impact during the incident?" → AI correlates alert history with infrastructure metrics

### Current Status (December 2024)

✅ **COMPLETE (Phases 1-2):**
- Full-featured dashboard builder (GridStack, variables, snapshots, playlists)
- LGTM stack deployed (Loki, Grafana, Tempo, Mimir, Alertmanager)
- Grafana SSO integration via auth proxy
- Prometheus datasource management with encryption
- iframe-based Grafana embedding (Logs, Traces, Alerts)
- Custom panel editor with PromQL syntax highlighting

🚧 **REMAINING (Phases 3-5):**
- AI chat integration with datasources (Natural language → PromQL/LogQL)
- Historical data service for metrics/logs retrieval
- Application profile management
- AI context enrichment with monitoring data
- Split-screen UI for chat + data visualization

### Timeline

- **Phase 1-2:** ✅ Complete (8 weeks)
- **Phase 3-5:** 🚧 Remaining (6-8 weeks estimated)
- **Total:** 14-16 weeks from start

---

## Current State Assessment

### ✅ Completed Infrastructure

#### 1. LGTM Observability Stack (docker-compose.yml)

**Fully Deployed Services:**

| Service | Container | Port | Status | Purpose |
|---------|-----------|------|--------|---------|
| **Prometheus** | aiops-prometheus | 9090 | ✅ Running | Metrics collection & storage (15d retention) |
| **Grafana Enterprise** | aiops-grafana | 3000 | ✅ Running | Unified visualization & dashboards |
| **Loki** | aiops-loki | 3100 | ✅ Running | Log aggregation & querying |
| **Tempo** | aiops-tempo | 3200, 4317, 4318 | ✅ Running | Distributed tracing (OTLP support) |
| **Mimir** | aiops-mimir | 9009 | ✅ Running | Long-term Prometheus metrics storage |
| **Alertmanager** | aiops-alertmanager | 9093 | ✅ Running | Alert routing & management |

**Configuration Highlights:**
- **SSO Enabled:** Grafana uses X-WEBAUTH-USER header for automatic user provisioning
- **White-labeled:** Custom branding via enterprise features + CSS injection
- **Integrated:** All datasources auto-provisioned via `grafana/provisioning/`
- **Secure:** Encryption for credentials (Fernet), JWT auth for API

#### 2. Dashboard Builder (Production Ready)

**Database Models Implemented:**
- `PrometheusDatasource` - Multi-instance Prometheus connections
- `PrometheusPanel` - Saved visualizations with PromQL queries
- `Dashboard` - Dashboard containers with metadata
- `DashboardPanel` - Panel layout (GridStack x/y/width/height)
- `DashboardVariable` - Template variables with query/custom/interval types
- `DashboardSnapshot` - Point-in-time frozen dashboards
- `Playlist` - Auto-rotating dashboard groups
- `PanelRow` - Collapsible row grouping
- `QueryHistory` - User query tracking with favorites
- `DashboardPermission` - Fine-grained ACLs

**API Endpoints Implemented:**
```python
# Dashboards (dashboards_api.py - 1,080 lines)
POST   /api/dashboards                    # Create dashboard
GET    /api/dashboards                    # List dashboards
GET    /api/dashboards/{id}               # Get dashboard
PUT    /api/dashboards/{id}               # Update dashboard
DELETE /api/dashboards/{id}               # Delete dashboard
POST   /api/dashboards/{id}/clone         # Clone dashboard
POST   /api/dashboards/{id}/panels        # Add panel to dashboard
PUT    /api/dashboards/{id}/panels/{pid}/position  # Update layout
GET    /api/dashboards/{id}/export        # Export JSON
POST   /api/dashboards/import             # Import JSON

# Panels (panels_api.py - 615 lines)
POST   /api/panels                        # Create panel
GET    /api/panels/{id}                   # Get panel
PUT    /api/panels/{id}                   # Update panel
DELETE /api/panels/{id}                   # Delete panel
POST   /api/panels/test-query             # Test PromQL query
GET    /api/panels/{id}/data              # Fetch panel data

# Variables (variables_api.py - 395 lines)
POST   /api/dashboards/{id}/variables     # Create variable
GET    /api/dashboards/{id}/variables     # List variables
PUT    /api/dashboards/{id}/variables/{vid}  # Update variable
DELETE /api/dashboards/{id}/variables/{vid}  # Delete variable
GET    /api/dashboards/{id}/variables/{vid}/values  # Get variable values

# Datasources (datasources_api.py)
POST   /api/datasources                   # Add Prometheus datasource
GET    /api/datasources                   # List datasources
PUT    /api/datasources/{id}              # Update datasource
DELETE /api/datasources/{id}              # Delete datasource
POST   /api/datasources/{id}/test         # Test connection
```

**UI Features Implemented:**
- GridStack.js v8.4 drag-and-drop layout
- CodeMirror v5.65 PromQL syntax highlighting
- Time range picker (presets + custom)
- Auto-refresh (5s - 3600s intervals)
- Edit mode with save/cancel
- Panel types: graph, stat, gauge, table, heatmap, bar, pie
- Variable chaining with dependencies
- Snapshot sharing with expiration
- Playlist kiosk mode

#### 3. Grafana SSO Proxy (grafana_proxy.py)

**Implemented Features:**
```python
# SSO Authentication
✅ X-WEBAUTH-USER header injection
✅ Automatic user provisioning in Grafana
✅ Session management
✅ Request/response proxying

# White-labeling
✅ HTML injection for branding removal
✅ CSS injection to hide Grafana logos
✅ Title replacement (Grafana → AIOps)
✅ Frame-busting header removal (X-Frame-Options)

# Proxy Capabilities
✅ Path rewriting for subpath deployment (/grafana)
✅ Redirect handling
✅ Error handling (502 Bad Gateway on failure)
✅ Support for all HTTP methods (GET/POST/PUT/DELETE/PATCH)
```

**iframe Templates:**
- `grafana_logs.html` - Loki Explore UI (read-only)
- `grafana_traces.html` - Tempo Explore UI (read-only)
- `grafana_alerts.html` - Alertmanager UI (read-only)
- `grafana_advanced.html` - Custom Grafana dashboards

#### 4. Prometheus Service (prometheus_service.py)

**Implemented Capabilities:**
```python
class PrometheusClient:
    ✅ query(promql: str)              # Instant query
    ✅ query_range(promql, start, end, step)  # Range query
    ✅ get_metadata()                  # Metric metadata
    ✅ get_label_names()               # All label names
    ✅ get_label_values(label)         # Values for label
    ✅ test_connection()               # Health check
```

---

### ❌ Missing Components (To Be Implemented)

#### 1. AI Chat Integration Services

**Required Services:**

```python
# 1. QueryTranslator Service (NOT IMPLEMENTED)
class QueryTranslator:
    """Convert natural language to PromQL/LogQL using LLM"""

    async def translate_to_promql(
        natural_query: str,
        app_context: ApplicationProfile
    ) -> str:
        """
        Input: "CPU usage for service X in last hour"
        Output: 'rate(cpu_usage{service="X"}[1h])'
        """
        pass

    async def translate_to_logql(
        natural_query: str,
        app_context: ApplicationProfile
    ) -> str:
        """
        Input: "errors for service X"
        Output: '{service="X"} |= "error" | json'
        """
        pass

    async def detect_intent(user_message: str) -> QueryIntent:
        """Determine if user wants metrics/logs/traces/conversation"""
        pass


# 2. HistoricalDataService (NOT IMPLEMENTED)
class HistoricalDataService:
    """Retrieve and aggregate monitoring data"""

    async def get_metrics_range(
        datasource_id: str,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str = "1m"
    ) -> TimeSeriesData:
        """Fetch time-series metrics from Prometheus"""
        pass

    async def get_logs_range(
        query: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> LogEntries:
        """Fetch logs from Loki"""
        pass

    async def get_application_health(
        app_id: str,
        time_range: str = "24h"
    ) -> HealthSummary:
        """Calculate health status from multiple metrics"""
        pass

    async def get_event_count(
        app_id: str,
        time_range: str = "24h",
        filters: dict = None
    ) -> EventCount:
        """Count events/logs matching filters"""
        pass


# 3. AIContextBuilder (NOT IMPLEMENTED)
class AIContextBuilder:
    """Enrich AI prompts with monitoring data"""

    async def build_context(
        session: ChatSession,
        user_query: str
    ) -> dict:
        """
        Aggregate context from:
        - Alert history (existing AIOps data)
        - Chat history (existing AIOps data)
        - Recent metrics (NEW - from Prometheus)
        - Recent logs (NEW - from Loki)
        - Application profile (NEW)
        """
        pass


# 4. LokiClient (NOT IMPLEMENTED)
class LokiClient:
    """Direct Loki API client for log queries"""

    async def query(logql: str, limit: int = 1000) -> LogEntries:
        """Execute LogQL query"""
        pass

    async def query_range(
        logql: str,
        start: datetime,
        end: datetime,
        limit: int = 1000
    ) -> LogEntries:
        """Execute LogQL range query"""
        pass


# 5. TempoClient (NOT IMPLEMENTED)
class TempoClient:
    """Direct Tempo API client for trace queries"""

    async def query_trace(trace_id: str) -> Trace:
        """Get trace by ID"""
        pass

    async def search(query: str, start: datetime, end: datetime) -> list[Trace]:
        """Search traces"""
        pass
```

#### 2. Missing Database Models

```python
# NOT IMPLEMENTED - Need to create migration
class ApplicationProfile(Base):
    """Application metadata for AI context"""
    __tablename__ = "application_profiles"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)  # e.g., "abc-app"
    description = Column(Text)
    architecture_info = Column(JSON)  # Architecture details
    service_mappings = Column(JSON)   # Service → metric mappings
    datasource_id = Column(String(36), ForeignKey("datasources.id"))
    default_metrics = Column(JSON)    # Common metrics to track
    slos = Column(JSON)               # Service level objectives
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


# NOT IMPLEMENTED - Need to create migration
class GrafanaDatasource(Base):
    """Grafana datasource connections (Loki, Tempo, Mimir)"""
    __tablename__ = "grafana_datasources"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50))  # loki, tempo, mimir, alertmanager
    url = Column(String(512), nullable=False)
    api_key_encrypted = Column(Text)  # Fernet encrypted
    is_default = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)
    config_json = Column(JSON)  # Datasource-specific config
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

#### 3. Missing UI Components

**Split-Screen Chat Layout:**
```html
<!-- NOT IMPLEMENTED - templates/ai_chat_enhanced.html -->
<div class="chat-container">
    <!-- Left Panel (60%): Chat conversation -->
    <div class="chat-panel">
        <div class="messages">
            <!-- User messages -->
            <!-- AI responses -->
            <!-- Query previews -->
        </div>
        <div class="input-area">
            <textarea>Ask a question...</textarea>
            <button>Send</button>
        </div>
    </div>

    <!-- Right Panel (40%): Data output -->
    <div class="data-panel">
        <!-- Structured results -->
        <!-- Tables, charts, metrics -->
        <!-- Export buttons (CSV, JSON, PDF) -->
    </div>
</div>
```

**Query Preview Component:**
```javascript
// NOT IMPLEMENTED
function showQueryPreview(naturalQuery, translatedQuery) {
    // Show what PromQL/LogQL will be executed
    // Allow user to edit before running
    // Display in chat before results
}
```

**Inline Visualization:**
```javascript
// NOT IMPLEMENTED
function renderInlineChart(chartData, panelConfig) {
    // Render ECharts/Chart.js in chat message
    // Make interactive (zoom, hover tooltips)
    // Support multiple chart types
}
```

---

## Architecture Overview

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Interface                              │
│  ┌────────────────────────┐  ┌────────────────────────────────────┐ │
│  │  Custom Dashboard      │  │   Enhanced AI Chat (NEW)           │ │
│  │  Builder (COMPLETE)    │  │   ┌──────────────────────────────┐ │ │
│  │  • GridStack layout    │  │   │  Left: Conversation          │ │ │
│  │  • PromQL editor       │  │   │  Right: Data Output          │ │ │
│  │  • Variables           │  │   └──────────────────────────────┘ │ │
│  │  • Snapshots           │  │                                    │ │
│  └────────────────────────┘  └────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                   ┌────────────┴───────────┐
                   │                        │
        ┌──────────▼──────────┐  ┌─────────▼──────────┐
        │  Dashboard APIs     │  │  Chat Service      │
        │  (COMPLETE)         │  │  (NEEDS EXTENSION) │
        │  • CRUD             │  │  ┌───────────────┐ │
        │  • Layout mgmt      │  │  │ Context       │ │
        │  • Variables        │  │  │ Builder (NEW) │ │
        │  • Permissions      │  │  └───────────────┘ │
        └─────────────────────┘  │  ┌───────────────┐ │
                                 │  │ Query         │ │
                                 │  │ Translator    │ │
                                 │  │ (NEW)         │ │
                                 │  └───────────────┘ │
                                 └─────────┬──────────┘
                                           │
                        ┌──────────────────┴─────────────────┐
                        │                                    │
              ┌─────────▼──────────┐            ┌───────────▼─────────┐
              │ Prometheus Service │            │ Historical Data     │
              │ (COMPLETE)         │            │ Service (NEW)       │
              │ • Query            │            │ • Metrics retrieval │
              │ • Query range      │            │ • Log retrieval     │
              │ • Metadata         │            │ • Aggregation       │
              └─────────┬──────────┘            │ • Health calc       │
                        │                       └──────────┬──────────┘
                        │                                  │
┌───────────────────────┴──────────────────────────────────┴───────────┐
│                       Data Sources Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Prometheus   │  │ Loki         │  │ Tempo        │              │
│  │ (DEPLOYED)   │  │ (DEPLOYED)   │  │ (DEPLOYED)   │              │
│  │ • Metrics    │  │ • Logs       │  │ • Traces     │              │
│  │ • 15d retain │  │ • Aggreg.    │  │ • OTLP       │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐                                │
│  │ Mimir        │  │ Alertmanager │                                │
│  │ (DEPLOYED)   │  │ (DEPLOYED)   │                                │
│  │ • Long-term  │  │ • Alert mgmt │                                │
│  └──────────────┘  └──────────────┘                                │
└───────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Natural Language Query

```
User: "Was abc app healthy yesterday?"
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│ 1. Chat Service receives message                           │
│    • Existing: Store in chat_messages table                │
│    • NEW: Trigger intent detection                         │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ 2. QueryTranslator.detect_intent()                         │
│    • Analyze: Is this a data query or conversation?        │
│    • Result: DATA_QUERY (health status)                    │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ 3. AIContextBuilder.build_context()                        │
│    ┌────────────────────────────────────────────────────┐ │
│    │ EXISTING AIOPS DATA:                                │ │
│    │ • Query alerts table for "abc" app                 │ │
│    │ • Get past AI analysis results                     │ │
│    │ • Retrieve chat history for context                │ │
│    │ • Find application metadata                        │ │
│    └────────────────────────────────────────────────────┘ │
│    ┌────────────────────────────────────────────────────┐ │
│    │ NEW MONITORING DATA:                               │ │
│    │ • Lookup ApplicationProfile for "abc"              │ │
│    │ • Get SLO definitions (error rate, latency)        │ │
│    │ • Identify relevant metrics                        │ │
│    └────────────────────────────────────────────────────┘ │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ 4. QueryTranslator.translate_to_promql()                   │
│    Input: "healthy yesterday" + app_context                │
│    Output: Multiple PromQL queries                         │
│    • rate(http_errors_total{app="abc"}[5m])               │
│    • up{app="abc"}                                         │
│    • histogram_quantile(0.95,                              │
│        http_duration_seconds{app="abc"})                   │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ 5. HistoricalDataService.get_metrics_range()               │
│    • Calculate "yesterday": start_of_day(-1), end_of_day(-1)│
│    • Execute queries against Prometheus                    │
│    • Collect results                                       │
│    Results:                                                │
│    • Error rate: 0.4% (below 2% SLO ✓)                    │
│    • Uptime: 99.8% (23h 57m)                              │
│    • P95 latency: 245ms (below 500ms SLO ✓)               │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ 6. Generate AI Response                                    │
│    • Send to LLM with enriched context:                    │
│      - User question                                       │
│      - Application SLOs                                    │
│      - Actual metric values                                │
│      - Past incidents (from existing data)                 │
│    • LLM analyzes and generates response                   │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ 7. Display Response (Split-Screen UI)                      │
│    ┌──────────────────────┬──────────────────────────────┐│
│    │ LEFT (Chat):         │ RIGHT (Data Panel):          ││
│    │                      │                              ││
│    │ User:                │                              ││
│    │ "Was abc app healthy │                              ││
│    │  yesterday?"         │                              ││
│    │                      │                              ││
│    │ AI:                  │ ┌──────────────────────────┐ ││
│    │ "Yes, abc app was    │ │ Health Metrics (Yest.)   │ ││
│    │  healthy yesterday.  │ │                          │ ││
│    │  Here are the key    │ │ ✅ Uptime: 99.8%         │ ││
│    │  metrics:            │ │ ✅ Error: 0.4% (<2% SLO) │ ││
│    │  [See data panel →]  │ │ ✅ Latency: 245ms        │ ││
│    │                      │ │    (<500ms SLO)          │ ││
│    │  Brief spike at      │ │                          │ ││
│    │  2:30 PM (15 min)    │ │ [Chart: Error Rate]      │ ││
│    │  due to deployment." │ │ [Chart: Latency P95]     │ ││
│    │                      │ │                          │ ││
│    │                      │ │ [Export CSV] [Export PDF]│ ││
│    │                      │ └──────────────────────────┘ ││
│    └──────────────────────┴──────────────────────────────┘│
└────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Overview

| Phase | Status | Duration | Focus |
|-------|--------|----------|-------|
| **Phase 1** | ✅ Complete | 4 weeks | Dashboard builder + Datasources |
| **Phase 2** | ✅ Complete | 4 weeks | LGTM stack + Grafana SSO + iframe embedding |
| **Phase 3** | 🚧 Pending | 3 weeks | Application profiles + Loki/Tempo clients |
| **Phase 4** | 🚧 Pending | 3 weeks | Query translator + Historical data service |
| **Phase 5** | 🚧 Pending | 2 weeks | AI context builder + Split-screen UI |

**Total Remaining:** 8 weeks

---

### Phase 3: Datasource Expansion (3 weeks)

**Goal:** Enable programmatic access to Loki and Tempo

#### Week 1: Loki Client & Application Profiles

**Tasks:**

1. **Create LokiClient Service** (2 days)
   - File: `app/services/loki_client.py`
   - Methods:
     - `query(logql: str, limit: int) -> LogEntries`
     - `query_range(logql: str, start: datetime, end: datetime) -> LogEntries`
     - `get_labels() -> list[str]`
     - `get_label_values(label: str) -> list[str]`
   - Use `httpx.AsyncClient` for API calls
   - Error handling and retry logic

2. **Create Database Migration for Application Profiles** (1 day)
   - File: `alembic/versions/030_add_application_profiles.py`
   - Schema:
     ```python
     create_table(
         'application_profiles',
         sa.Column('id', sa.String(36), primary_key=True),
         sa.Column('name', sa.String(100), nullable=False, unique=True),
         sa.Column('description', sa.Text),
         sa.Column('architecture_info', sa.JSON),  # {type, components, language}
         sa.Column('service_mappings', sa.JSON),   # {service: {metrics_prefix, log_label}}
         sa.Column('datasource_id', sa.String(36), ForeignKey('datasources.id')),
         sa.Column('default_metrics', sa.JSON),    # [metric1, metric2]
         sa.Column('slos', sa.JSON),               # {availability: 0.999, error_rate: 0.02}
         sa.Column('created_at', sa.DateTime),
         sa.Column('updated_at', sa.DateTime)
     )
     ```

3. **Create ApplicationProfile Model** (1 day)
   - File: `app/models_dashboards.py`
   - Add model with relationships
   - Add to SQLAlchemy Base

4. **Create Application Profiles API** (2 days)
   - File: `app/routers/applications_api.py`
   - Endpoints:
     ```python
     POST   /api/applications                 # Create profile
     GET    /api/applications                 # List profiles
     GET    /api/applications/{id}            # Get profile
     PUT    /api/applications/{id}            # Update profile
     DELETE /api/applications/{id}            # Delete profile
     GET    /api/applications/search?name=abc # Search by name
     ```

**Deliverables:**
- ✅ Loki client operational
- ✅ Application profiles CRUD API
- ✅ Database migration applied
- ✅ Unit tests for Loki client

#### Week 2: Tempo Client & Grafana Datasources

**Tasks:**

1. **Create TempoClient Service** (2 days)
   - File: `app/services/tempo_client.py`
   - Methods:
     - `get_trace(trace_id: str) -> Trace`
     - `search(query: str, start: datetime, end: datetime) -> list[Trace]`
     - `get_services() -> list[str]`

2. **Create GrafanaDatasource Migration** (1 day)
   - File: `alembic/versions/031_add_grafana_datasources.py`
   - Schema for Loki, Tempo, Mimir datasources

3. **Create Grafana Datasources API** (2 days)
   - File: `app/routers/grafana_datasources_api.py`
   - Endpoints:
     ```python
     POST   /api/grafana-datasources          # Add datasource (Loki/Tempo)
     GET    /api/grafana-datasources          # List datasources
     GET    /api/grafana-datasources/{id}     # Get datasource
     PUT    /api/grafana-datasources/{id}     # Update datasource
     DELETE /api/grafana-datasources/{id}     # Delete datasource
     POST   /api/grafana-datasources/{id}/test # Test connection
     ```

**Deliverables:**
- ✅ Tempo client operational
- ✅ Grafana datasources CRUD API
- ✅ Connection testing for Loki/Tempo

#### Week 3: Integration Testing

**Tasks:**

1. **Integration Tests** (3 days)
   - Test Loki queries against real Loki instance
   - Test Tempo trace retrieval
   - Test application profile CRUD
   - Verify datasource encryption

2. **Documentation** (2 days)
   - API documentation for new endpoints
   - Example LogQL queries
   - Application profile JSON schema examples

**Deliverables:**
- ✅ All integration tests passing
- ✅ API documentation updated
- ✅ Example data seeded

---

### Phase 4: AI Query Translation & Historical Data (3 weeks)

**Goal:** Enable natural language to query translation and data retrieval

#### Week 1: Query Translator Service

**Tasks:**

1. **Create QueryTranslator Service** (3 days)
   - File: `app/services/query_translator.py`
   - Use existing LLM integration (chat_service.py patterns)
   - Methods:
     ```python
     async def translate_to_promql(
         natural_query: str,
         app_context: ApplicationProfile
     ) -> str:
         # Use LLM to convert natural language to PromQL
         # Include app_context for metric names
         pass

     async def translate_to_logql(
         natural_query: str,
         app_context: ApplicationProfile
     ) -> str:
         # Use LLM to convert natural language to LogQL
         pass

     async def detect_intent(user_message: str) -> QueryIntent:
         # Determine: metrics, logs, traces, or conversation
         pass
     ```

2. **Create Translation Prompt Templates** (1 day)
   - File: `app/prompts/query_translation.py`
   - PromQL translation system prompt
   - LogQL translation system prompt
   - Intent detection prompt

3. **Query Validation** (1 day)
   - File: `app/services/query_validator.py`
   - Syntax validation before execution
   - Security checks (prevent injection)
   - Time range bounds enforcement

**Deliverables:**
- ✅ Query translator functional
- ✅ Intent detection working
- ✅ Query validation in place

#### Week 2: Historical Data Service

**Tasks:**

1. **Create HistoricalDataService** (4 days)
   - File: `app/services/historical_data_service.py`
   - Methods:
     ```python
     async def get_metrics_range(
         datasource_id: str,
         query: str,
         start_time: datetime,
         end_time: datetime,
         step: str = "1m"
     ) -> TimeSeriesData:
         # Use PrometheusClient.query_range()
         # Parse and structure results
         pass

     async def get_logs_range(
         query: str,
         start_time: datetime,
         end_time: datetime,
         limit: int = 1000
     ) -> LogEntries:
         # Use LokiClient.query_range()
         # Parse and structure log entries
         pass

     async def get_application_health(
         app_id: str,
         time_range: str = "24h"
     ) -> HealthSummary:
         # Fetch multiple metrics
         # Compare against SLOs
         # Calculate health score
         pass

     async def get_event_count(
         app_id: str,
         time_range: str = "24h",
         filters: dict = None
     ) -> EventCount:
         # Count log entries matching filters
         # Group by severity/level
         pass
     ```

2. **Data Aggregation Utilities** (1 day)
   - File: `app/utils/data_aggregation.py`
   - Downsampling for long time ranges
   - Percentile calculations
   - Time series summarization

**Deliverables:**
- ✅ Historical data service operational
- ✅ Health calculations working
- ✅ Event counting functional

#### Week 3: Caching & Performance

**Tasks:**

1. **Query Result Caching** (2 days)
   - Use Redis or in-memory caching
   - Cache key: hash(query + time_range)
   - TTL: 5 minutes (configurable)

2. **Performance Testing** (2 days)
   - Load test query translator
   - Measure query execution times
   - Optimize slow queries

3. **API Endpoints for Testing** (1 day)
   - File: `app/routers/queries_api.py`
   - Endpoints:
     ```python
     POST   /api/queries/translate           # Test translation
     POST   /api/queries/execute             # Execute query
     GET    /api/queries/history             # Query history
     ```

**Deliverables:**
- ✅ Caching implemented
- ✅ Performance benchmarks documented
- ✅ Test API endpoints available

---

### Phase 5: AI Context Builder & Enhanced UI (2 weeks)

**Goal:** Integrate everything into chat experience with split-screen UI

#### Week 1: AI Context Builder

**Tasks:**

1. **Create AIContextBuilder Service** (3 days)
   - File: `app/services/ai_context_builder.py`
   - Method:
     ```python
     async def build_context(
         session: ChatSession,
         user_query: str
     ) -> dict:
         # 1. Get existing AIOps data
         alert_history = get_alert_history(session)
         chat_history = get_chat_history(session)

         # 2. Detect if query needs data
         intent = await query_translator.detect_intent(user_query)

         # 3. If data query, fetch monitoring data
         if intent.needs_metrics:
             app_profile = get_application_profile(intent.app_name)
             recent_metrics = await historical_data.get_metrics_range(...)

         # 4. Build comprehensive context
         return {
             "alert_history": alert_history,
             "chat_history": chat_history,
             "recent_metrics": recent_metrics,
             "application_slos": app_profile.slos,
             "query_intent": intent
         }
     ```

2. **Integrate with Chat Service** (2 days)
   - File: `app/services/chat_service.py`
   - Modify `generate_response()` to use AIContextBuilder
   - Add context to LLM system prompt

**Deliverables:**
- ✅ Context builder operational
- ✅ Integrated with chat service
- ✅ Enriched AI responses

#### Week 2: Split-Screen UI

**Tasks:**

1. **Create Enhanced Chat Template** (3 days)
   - File: `templates/ai_chat_enhanced.html`
   - Split-screen layout:
     - Left: Chat conversation (60%)
     - Right: Data output panel (40%)
   - Resizable divider
   - Responsive (mobile collapse right panel)

2. **Data Visualization Components** (2 days)
   - Inline charts using ECharts
   - Data tables (sortable, filterable)
   - Export buttons (CSV, JSON, PDF)

3. **Query Preview Component** (1 day)
   - Show generated PromQL/LogQL before execution
   - Allow user to edit
   - Syntax highlighting

4. **Testing & Polish** (1 day)
   - Cross-browser testing
   - Mobile responsiveness
   - User acceptance testing

**Deliverables:**
- ✅ Split-screen UI functional
- ✅ Data visualization working
- ✅ Export functionality operational
- ✅ User-tested and polished

---

## Detailed Feature Specifications

### Feature 1: Application Profiles

**Purpose:** Store metadata about applications for AI context

**Data Model:**
```json
{
  "id": "app-abc-001",
  "name": "abc-app",
  "description": "Main web application",
  "architecture_info": {
    "type": "microservices",
    "components": ["web", "api", "worker", "database"],
    "language": "Python",
    "framework": "FastAPI"
  },
  "service_mappings": {
    "web": {
      "metrics_prefix": "abc_web_",
      "log_label": "app=abc-web"
    },
    "api": {
      "metrics_prefix": "abc_api_",
      "log_label": "app=abc-api"
    }
  },
  "default_metrics": [
    "http_requests_total",
    "http_request_duration_seconds",
    "http_errors_total",
    "up"
  ],
  "slos": {
    "availability": 0.999,
    "error_rate": 0.02,
    "p95_latency_ms": 500
  }
}
```

**API Examples:**
```bash
# Create application profile
curl -X POST http://localhost:8080/api/applications \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "abc-app",
    "description": "Main web application",
    "architecture_info": {...},
    "service_mappings": {...},
    "default_metrics": [...],
    "slos": {...}
  }'

# Get application profile
curl http://localhost:8080/api/applications/app-abc-001 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Feature 2: Query Translation

**Purpose:** Convert natural language to executable queries

**Translation Examples:**

| Natural Language | Translated Query | Type |
|------------------|------------------|------|
| "CPU usage for abc app in last hour" | `rate(cpu_usage_seconds_total{app="abc"}[1h])` | PromQL |
| "Errors in logs for service xyz" | `{service="xyz"} \|= "error" \| json` | LogQL |
| "95th percentile response time" | `histogram_quantile(0.95, rate(http_duration_seconds_bucket[5m]))` | PromQL |
| "Number of pod restarts" | `sum(kube_pod_container_status_restarts_total{app="abc"})` | PromQL |

**LLM Prompt Template:**
```python
PROMQL_TRANSLATION_PROMPT = """
You are a Prometheus expert. Convert the following natural language query to PromQL.

Application Context:
- Name: {app_name}
- Available metrics: {metric_list}
- Service labels: {service_labels}

User Query: {natural_query}

Return ONLY the PromQL query, nothing else.
"""

LOGQL_TRANSLATION_PROMPT = """
You are a Loki expert. Convert the following natural language query to LogQL.

Application Context:
- Name: {app_name}
- Log labels: {log_labels}

User Query: {natural_query}

Return ONLY the LogQL query, nothing else.
"""
```

---

### Feature 3: Historical Data Service

**Purpose:** Retrieve and aggregate monitoring data

**Method: get_application_health()**

```python
async def get_application_health(
    app_id: str,
    time_range: str = "24h"
) -> HealthSummary:
    """
    Calculate application health from multiple metrics.

    Returns:
        HealthSummary with:
        - overall_health: "healthy" | "degraded" | "unhealthy"
        - metrics: {metric_name: {value, status, slo}}
        - incidents: list of degradation periods
        - uptime_percentage: float
    """
    # 1. Get application profile
    app_profile = await get_application_profile(app_id)

    # 2. Calculate time range
    end_time = datetime.now()
    start_time = end_time - parse_duration(time_range)

    # 3. Fetch metrics
    queries = {
        "error_rate": f'rate(http_errors_total{{app="{app_profile.name}"}}[5m])',
        "uptime": f'up{{app="{app_profile.name}"}}',
        "latency_p95": f'histogram_quantile(0.95, http_duration_seconds{{app="{app_profile.name}"}})'
    }

    results = {}
    for metric_name, query in queries.items():
        data = await prometheus_client.query_range(
            query=query,
            start=start_time,
            end=end_time,
            step="1m"
        )
        results[metric_name] = data

    # 4. Compare against SLOs
    slos = app_profile.slos
    health_checks = {
        "error_rate": check_metric(results["error_rate"], slos["error_rate"], operator="<="),
        "uptime": check_metric(results["uptime"], slos["availability"], operator=">="),
        "latency_p95": check_metric(results["latency_p95"], slos["p95_latency_ms"], operator="<=")
    }

    # 5. Calculate overall health
    if all(check["status"] == "healthy" for check in health_checks.values()):
        overall_health = "healthy"
    elif any(check["status"] == "unhealthy" for check in health_checks.values()):
        overall_health = "unhealthy"
    else:
        overall_health = "degraded"

    return HealthSummary(
        overall_health=overall_health,
        metrics=health_checks,
        uptime_percentage=calculate_uptime(results["uptime"]),
        incidents=detect_incidents(results)
    )
```

---

### Feature 4: Split-Screen UI

**Purpose:** Better data visualization alongside chat

**Layout Specifications:**

```html
<div class="chat-container">
    <!-- Left Panel: Chat (60% width, resizable) -->
    <div class="chat-panel" style="flex: 0 0 60%">
        <!-- Chat messages -->
        <div class="messages-area">
            <div class="message user">
                <p>Was abc app healthy yesterday?</p>
            </div>
            <div class="message ai">
                <p>Yes, abc app was healthy yesterday. See detailed metrics →</p>
                <div class="query-preview">
                    <span class="label">Executed Queries:</span>
                    <code>rate(http_errors_total{app="abc"}[5m])</code>
                    <code>up{app="abc"}</code>
                </div>
            </div>
        </div>

        <!-- Input area -->
        <div class="input-area">
            <textarea placeholder="Ask about metrics, logs, or traces..."></textarea>
            <button>Send</button>
        </div>
    </div>

    <!-- Resizable Divider -->
    <div class="divider-handle"></div>

    <!-- Right Panel: Data Output (40% width, resizable, collapsible) -->
    <div class="data-panel" style="flex: 0 0 40%">
        <div class="panel-header">
            <h3>Health Metrics (Yesterday)</h3>
            <div class="actions">
                <button onclick="exportCSV()">CSV</button>
                <button onclick="exportJSON()">JSON</button>
                <button onclick="collapsePanel()">×</button>
            </div>
        </div>

        <!-- Summary Cards -->
        <div class="metrics-summary">
            <div class="metric-card success">
                <div class="metric-label">Uptime</div>
                <div class="metric-value">99.8%</div>
                <div class="metric-status">✓ Above SLO (99.9%)</div>
            </div>
            <div class="metric-card success">
                <div class="metric-label">Error Rate</div>
                <div class="metric-value">0.4%</div>
                <div class="metric-status">✓ Below SLO (2%)</div>
            </div>
            <div class="metric-card success">
                <div class="metric-label">P95 Latency</div>
                <div class="metric-value">245ms</div>
                <div class="metric-status">✓ Below SLO (500ms)</div>
            </div>
        </div>

        <!-- Charts -->
        <div class="charts-area">
            <div id="error-rate-chart" style="height: 200px"></div>
            <div id="latency-chart" style="height: 200px"></div>
        </div>

        <!-- Data Table (collapsible) -->
        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Error Rate</th>
                        <th>Latency (P95)</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Populated dynamically -->
                </tbody>
            </table>
        </div>
    </div>
</div>
```

**Responsive Behavior:**
- Desktop (>1024px): 60/40 split
- Tablet (768-1024px): 70/30 split
- Mobile (<768px): Stack vertically, chat above data panel

---

## Testing Strategy

### Unit Tests

**Coverage Targets:**
- LokiClient: 90%
- TempoClient: 90%
- QueryTranslator: 85%
- HistoricalDataService: 90%
- AIContextBuilder: 85%

**Example Test Cases:**

```python
# tests/test_query_translator.py
import pytest
from app.services.query_translator import QueryTranslator

@pytest.mark.asyncio
async def test_translate_to_promql_cpu_query():
    translator = QueryTranslator()
    app_context = ApplicationProfile(
        name="abc-app",
        default_metrics=["cpu_usage_seconds_total"]
    )

    result = await translator.translate_to_promql(
        natural_query="CPU usage for abc app in last hour",
        app_context=app_context
    )

    assert "rate(" in result
    assert "cpu_usage" in result
    assert 'app="abc-app"' in result
    assert "[1h]" in result


# tests/test_historical_data_service.py
@pytest.mark.asyncio
async def test_get_application_health():
    service = HistoricalDataService()

    # Mock Prometheus responses
    with patch('app.services.prometheus_client.query_range') as mock_query:
        mock_query.return_value = mock_metric_data()

        health = await service.get_application_health(
            app_id="app-abc-001",
            time_range="24h"
        )

        assert health.overall_health in ["healthy", "degraded", "unhealthy"]
        assert "error_rate" in health.metrics
        assert health.uptime_percentage > 0
```

### Integration Tests

**Test Scenarios:**

1. **End-to-End Chat Query:**
   ```python
   async def test_e2e_health_query():
       # 1. User sends message
       response = client.post("/api/chat/sessions/123/messages", json={
           "message": "Was abc app healthy yesterday?"
       })

       # 2. Verify intent detected
       assert "data_query" in response.json()

       # 3. Verify queries executed
       assert "promql_queries" in response.json()

       # 4. Verify AI response contains metrics
       assert "99.8%" in response.json()["ai_response"]
   ```

2. **Query Translation Accuracy:**
   ```python
   async def test_translation_accuracy():
       test_cases = [
           ("CPU usage for service X", "rate(cpu_usage"),
           ("errors in logs", "|= \"error\""),
           ("95th percentile latency", "histogram_quantile(0.95")
       ]

       for natural, expected_fragment in test_cases:
           result = await translator.translate(natural)
           assert expected_fragment in result
   ```

3. **Historical Data Retrieval:**
   ```python
   async def test_historical_data_retrieval():
       # Test with real Prometheus/Loki instances
       data = await historical_data.get_metrics_range(
           query='up{job="prometheus"}',
           start_time=datetime.now() - timedelta(hours=1),
           end_time=datetime.now()
       )

       assert len(data.series) > 0
       assert all(dp.timestamp is not None for dp in data.series[0].data_points)
   ```

### User Acceptance Testing

**Test Scenarios:**

| Scenario | User Action | Expected Result |
|----------|-------------|-----------------|
| Health Check | Ask "Was abc app healthy yesterday?" | AI provides yes/no + metrics summary, data panel shows charts |
| Event Count | Ask "How many errors in last 24h?" | AI provides count + breakdown, data panel shows table |
| Impact Analysis | Ask "Was server impacted during incident?" | AI correlates alert + metrics, shows timeline |
| Query Preview | Ask data question | User sees generated PromQL/LogQL before execution |
| Export Data | Click "Export CSV" in data panel | CSV file downloads with query results |

---

## Deployment Plan

### Prerequisites

1. **Environment Variables:**
   ```bash
   # Add to .env
   LOKI_URL=http://loki:3100
   TEMPO_URL=http://tempo:3200
   MIMIR_URL=http://mimir:9009
   ENABLE_AI_QUERY_TRANSLATION=true
   QUERY_CACHE_TTL_SECONDS=300
   MAX_QUERY_RANGE_HOURS=168  # 7 days
   ```

2. **Database Migrations:**
   ```bash
   # Run new migrations
   alembic upgrade head
   ```

3. **Seed Data (Optional):**
   ```bash
   # Create sample application profiles
   python scripts/seed_application_profiles.py
   ```

### Deployment Steps

**Stage 1: Infrastructure (Already Done)**
```bash
# Start LGTM stack
docker-compose up -d grafana loki tempo mimir alertmanager
```

**Stage 2: Phase 3 Deployment**
```bash
# 1. Pull latest code
git pull origin copilot/add-grafana-theming-branding

# 2. Run migrations
docker-compose exec remediation-engine alembic upgrade head

# 3. Restart services
docker-compose restart remediation-engine

# 4. Verify Loki/Tempo clients
curl http://localhost:8080/api/grafana-datasources
```

**Stage 3: Phase 4 Deployment**
```bash
# 1. Update code with query translator
git pull

# 2. Test query translation
curl -X POST http://localhost:8080/api/queries/translate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "CPU usage for abc app", "app_id": "app-abc-001"}'

# 3. Verify historical data service
curl http://localhost:8080/api/applications/app-abc-001/health?range=24h
```

**Stage 4: Phase 5 Deployment**
```bash
# 1. Deploy enhanced UI
git pull

# 2. Clear browser cache (new templates)

# 3. Test split-screen UI
# Navigate to /ai-chat-enhanced
```

### Rollback Plan

**If issues occur:**
```bash
# 1. Rollback database migrations
alembic downgrade -1

# 2. Revert code
git revert <commit-hash>

# 3. Restart services
docker-compose restart remediation-engine

# 4. Monitor logs
docker-compose logs -f remediation-engine
```

---

## Success Metrics

### Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Query Translation Accuracy | >85% | Manual review of 100 translations |
| Query Execution Time (P95) | <5 seconds | Prometheus histogram |
| Cache Hit Rate | >60% | Redis cache stats |
| System Availability | >99.9% | Uptime monitoring |
| API Error Rate | <1% | Error logs |

### User Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Successful Query Resolution | >80% | User confirms result is useful |
| User Satisfaction | >4/5 | Post-interaction survey |
| Time to Insight | <2 minutes | From question to answer |
| Feature Adoption | >60% users | Weekly active users using AI chat |
| Repeat Usage | >70% | Users who return within 7 days |

### Business Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| MTTR Reduction | 20% improvement | Average incident resolution time |
| Reduced Escalations | 15% fewer tickets | Support ticket volume |
| Self-Service Resolution | 30% of issues | Issues resolved without human help |
| Knowledge Retention | Historical analysis usage | Queries referencing past incidents |

---

## Appendices

### Appendix A: Example Queries

**Metric Queries:**
- "What's the average response time for service X?"
- "Show me memory usage for the last week"
- "Compare error rates between production and staging"
- "How many requests per second right now?"

**Log Queries:**
- "Find all errors containing 'database timeout'"
- "Show me the last 100 log entries for pod Y"
- "What were the logs during the incident?"
- "Count warnings in the last hour"

**Health Queries:**
- "Is service X healthy right now?"
- "What's the uptime for app Y this month?"
- "Show me SLO compliance for the last week"
- "Were there any outages yesterday?"

**Impact Queries:**
- "What services were affected by the outage?"
- "How many users were impacted?"
- "What was the blast radius of the incident?"
- "Show infrastructure metrics during the alert"

### Appendix B: Configuration Examples

**Application Profile Example:**
```json
{
  "name": "payment-service",
  "description": "Payment processing microservice",
  "architecture_info": {
    "type": "microservices",
    "components": ["api", "worker", "redis"],
    "language": "Go",
    "framework": "Gin"
  },
  "service_mappings": {
    "api": {
      "metrics_prefix": "payment_api_",
      "log_label": "service=payment-api"
    }
  },
  "default_metrics": [
    "payment_requests_total",
    "payment_duration_seconds",
    "payment_errors_total"
  ],
  "slos": {
    "availability": 0.9999,
    "error_rate": 0.001,
    "p95_latency_ms": 200
  }
}
```

**Grafana Datasource Configuration:**
```json
{
  "name": "Production Loki",
  "type": "loki",
  "url": "http://loki:3100",
  "is_default": true,
  "config_json": {
    "maxLines": 1000,
    "timeout": 30
  }
}
```

### Appendix C: Security Considerations

**Query Injection Prevention:**
- All translated queries validated before execution
- Parameterized queries where possible
- Time range limits enforced (max 7 days)
- Result set size limits (max 10,000 data points)

**Access Control:**
- Application profiles linked to user permissions
- Users can only query apps they have access to
- Datasource credentials encrypted (Fernet)
- Audit log for all query executions

**Rate Limiting:**
- Max 100 queries per user per hour
- Max 10 concurrent queries per user
- Exponential backoff on translation failures

### Appendix D: References

- [Prometheus Query API](https://prometheus.io/docs/prometheus/latest/querying/api/)
- [Loki Query API](https://grafana.com/docs/loki/latest/api/)
- [Tempo API](https://grafana.com/docs/tempo/latest/api_docs/)
- [PromQL Documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [LogQL Documentation](https://grafana.com/docs/loki/latest/logql/)

---

## Document Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-20 | Initial | Original planning documents created |
| 2.0 | 2025-12-26 | Consolidated | Merged 3 docs, updated status, removed completed items |

---

**END OF DOCUMENT**
