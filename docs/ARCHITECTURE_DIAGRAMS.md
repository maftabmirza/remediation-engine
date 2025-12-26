# AI Chat with Grafana Integration - Architecture Diagrams

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                             │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AI Chat Interface (Web UI)                                  │  │
│  │  • Natural language input                                    │  │
│  │  • Streaming responses                                       │  │
│  │  • Inline data visualization                                 │  │
│  │  • Query preview (optional)                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
└───────────────────────────┬───────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    REMEDIATION ENGINE (FastAPI)                      │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Enhanced Chat Service (chat_service.py)                     │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │  │
│  │  │   Intent     │  │   Query      │  │    Context       │  │  │
│  │  │  Detection   │→ │ Translation  │→ │    Builder       │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  │  │
│  │         │                  │                    │            │  │
│  │         └──────────────────┴────────────────────┘            │  │
│  │                            │                                  │  │
│  │                            ▼                                  │  │
│  │  ┌───────────────────────────────────────────────────────┐  │  │
│  │  │  Historical Data Service (new)                        │  │  │
│  │  │  • Metrics retrieval                                  │  │  │
│  │  │  • Logs retrieval                                     │  │  │
│  │  │  • Data aggregation                                   │  │  │
│  │  │  • Result caching                                     │  │  │
│  │  └───────────────────────────────────────────────────────┘  │  │
│  │                            │                                  │  │
│  └────────────────────────────┼──────────────────────────────────┘  │
│                               │                                     │
│  ┌────────────────────────────┼──────────────────────────────────┐  │
│  │  Grafana Integration Layer │                                  │  │
│  │  ┌──────────────┐  ┌───────┴────────┐  ┌─────────────────┐  │  │
│  │  │ Prometheus   │  │  Loki Client   │  │  Datasource     │  │  │
│  │  │   Client     │  │                │  │   Manager       │  │  │
│  │  └──────────────┘  └────────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Database (PostgreSQL)                                       │  │
│  │  • grafana_datasources                                       │  │
│  │  • application_profiles                                      │  │
│  │  • chat_sessions (enhanced)                                  │  │
│  │  • chat_messages                                             │  │
│  │  • alerts (existing)                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
└───────────────────────────┬───────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MONITORING STACK (External)                       │
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ Prometheus   │    │     Loki     │    │     Grafana          │  │
│  │ (Metrics)    │    │    (Logs)    │    │  (Dashboards)        │  │
│  │              │    │              │    │                      │  │
│  │ • PromQL API │    │ • LogQL API  │    │ • Visualization      │  │
│  │ • Metrics DB │    │ • Log Store  │    │ • Alerting           │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow - Query Execution

```
┌──────────────┐
│     User     │
└──────┬───────┘
       │ "Was abc app healthy yesterday?"
       ▼
┌────────────────────────────────────────────────────────┐
│  Step 1: Chat Message Received                        │
│  • Save user message to chat_messages                 │
│  • Load chat history                                  │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Step 2: Intent Detection                             │
│  • Analyze: Is this a data query?                     │
│  • Result: YES - Health status query                  │
│  • Extract: app="abc", timerange="yesterday"          │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Step 3: Query Translation (LLM-powered)              │
│  • Input: "was abc app healthy yesterday"             │
│  • Output: Multiple PromQL queries:                   │
│    1. rate(http_errors_total{app="abc"}[1d])         │
│    2. up{app="abc"}                                   │
│    3. histogram_quantile(0.95,                        │
│         http_duration_seconds{app="abc"})             │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Step 4: Query Validation                             │
│  • Check syntax                                       │
│  • Verify time range (within limits)                  │
│  • Check user permissions                             │
│  • Estimate result size                               │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Step 5: Execute Queries (Parallel)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐│
│  │ Query 1  │  │ Query 2  │  │      Query 3         ││
│  │   to     │  │   to     │  │        to            ││
│  │Prometheus│  │Prometheus│  │    Prometheus        ││
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘│
│       │             │                    │            │
│       └─────────────┴────────────────────┘            │
│                     │                                 │
└─────────────────────┼─────────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────────┐
│  Step 6: Results Aggregation                          │
│  • Error rate: 0.4%                                   │
│  • Uptime: 99.8%                                      │
│  • P95 latency: 245ms                                 │
│  • Cache results (5 min TTL)                          │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Step 7: Context Building                             │
│  • Gather alert history for abc app                   │
│  • Load application profile & SLOs                    │
│  • Add query results to context                       │
│  • Identify anomalies (compare with SLOs)             │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Step 8: AI Response Generation                       │
│  • Enhanced prompt with data context                  │
│  • LLM generates response                             │
│  • Stream response to user                            │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Step 9: Save & Display                               │
│  • Save AI response to chat_messages                  │
│  • Display to user with inline visualizations         │
│  • Log query execution for audit                      │
└────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

```
                  ┌──────────────────┐
                  │   User Query     │
                  └────────┬─────────┘
                           │
                  ┌────────▼─────────┐
                  │  Chat WebSocket  │
                  └────────┬─────────┘
                           │
              ┌────────────▼────────────┐
              │   Enhanced Chat Service  │
              └───┬────────────────┬────┘
                  │                │
         ┌────────▼─────┐    ┌────▼──────────────┐
         │   Intent     │    │  Load Chat        │
         │  Detector    │    │  History          │
         └────────┬─────┘    └───────────────────┘
                  │
                  ├─ Is Data Query? ──No──> Normal Chat Flow
                  │
                  └─ Yes
                     │
         ┌───────────▼────────────┐
         │   Query Translator     │
         │   (LLM-powered)        │
         └───────────┬────────────┘
                     │
         ┌───────────▼────────────┐
         │  Application Profile   │
         │  Lookup                │
         └───────────┬────────────┘
                     │
         ┌───────────▼────────────┐
         │   Query Validator      │
         └───────────┬────────────┘
                     │
         ┌───────────▼────────────┐
         │   Cache Check          │
         └───┬──────────────┬─────┘
             │              │
       Cache Hit      Cache Miss
             │              │
             │     ┌────────▼─────────────┐
             │     │  Historical Data     │
             │     │  Service             │
             │     └────────┬─────────────┘
             │              │
             │     ┌────────▼─────────────┐
             │     │  Grafana Integration │
             │     │  Layer               │
             │     └───┬──────────┬───────┘
             │         │          │
             │    ┌────▼───┐  ┌──▼───────┐
             │    │Prometheus │ Loki    │
             │    │  Query   │  Query   │
             │    └────┬───┘  └──┬───────┘
             │         │         │
             │         └────┬────┘
             │              │
             └──────────────┼─────────────┐
                            │             │
                   ┌────────▼─────────┐   │
                   │  Results         │   │
                   │  Aggregation     │   │
                   └────────┬─────────┘   │
                            │             │
                   ┌────────▼─────────────▼┐
                   │   Context Builder     │
                   └────────┬──────────────┘
                            │
                   ┌────────▼──────────────┐
                   │  LLM Service          │
                   │  (Generate Response)  │
                   └────────┬──────────────┘
                            │
                   ┌────────▼──────────────┐
                   │  Stream to User       │
                   └───────────────────────┘
```

## Database Schema

```
┌─────────────────────────────────────────┐
│         grafana_datasources             │
├─────────────────────────────────────────┤
│ id                    UUID PK            │
│ name                  VARCHAR(100)       │
│ type                  VARCHAR(50)        │ ← prometheus, loki, etc.
│ url                   VARCHAR(255)       │
│ api_key_encrypted     TEXT               │
│ is_default            BOOLEAN            │
│ is_enabled            BOOLEAN            │
│ config_json           JSONB              │
│ created_at            TIMESTAMP          │
│ updated_at            TIMESTAMP          │
└─────────────────────────────────────────┘
                ▲
                │
                │ FK: datasource_id
                │
┌─────────────────────────────────────────┐
│        application_profiles             │
├─────────────────────────────────────────┤
│ id                    UUID PK            │
│ name                  VARCHAR(100)       │ ← e.g., "abc-app"
│ description           TEXT               │
│ architecture_info     JSONB              │ ← Service topology
│ service_mappings      JSONB              │ ← Metric/log mappings
│ datasource_id         UUID FK            │
│ default_metrics       JSONB              │ ← Common queries
│ slos                  JSONB              │ ← SLO thresholds
│ created_at            TIMESTAMP          │
│ updated_at            TIMESTAMP          │
└─────────────────────────────────────────┘
                ▲
                │
                │ FK: application_id (optional)
                │
┌─────────────────────────────────────────┐
│          chat_sessions                  │
├─────────────────────────────────────────┤
│ id                    UUID PK            │
│ user_id               UUID FK            │
│ alert_id              UUID FK (optional) │
│ application_id        UUID FK (NEW)      │ ← Link to app
│ title                 VARCHAR(255)       │
│ llm_provider_id       UUID FK            │
│ context_data          JSONB (NEW)        │ ← Cached metrics
│ created_at            TIMESTAMP          │
│ updated_at            TIMESTAMP          │
└─────────────────────────────────────────┘
                │
                │ FK: session_id
                ▼
┌─────────────────────────────────────────┐
│          chat_messages                  │
├─────────────────────────────────────────┤
│ id                    UUID PK            │
│ session_id            UUID FK            │
│ role                  VARCHAR(20)        │ ← user, assistant
│ content               TEXT               │
│ metadata_json         JSONB (NEW)        │ ← Queries executed
│ tokens_used           INTEGER            │
│ created_at            TIMESTAMP          │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│          query_cache (NEW)              │
├─────────────────────────────────────────┤
│ id                    UUID PK            │
│ query_hash            VARCHAR(64)        │ ← Hash of query
│ datasource_id         UUID FK            │
│ query_text            TEXT               │
│ result_data           JSONB              │
│ execution_time_ms     INTEGER            │
│ expires_at            TIMESTAMP          │
│ created_at            TIMESTAMP          │
└─────────────────────────────────────────┘
```

## Sequence Diagram - Complete Flow

```
User        Chat UI     Chat Service    Query Translator   Datasource Client   Prometheus   AI/LLM
 │             │              │                │                   │               │           │
 │  Message    │              │                │                   │               │           │
 ├────────────>│              │                │                   │               │           │
 │             │  POST /chat  │                │                   │               │           │
 │             ├─────────────>│                │                   │               │           │
 │             │              │ Save message   │                   │               │           │
 │             │              ├───────────┐    │                   │               │           │
 │             │              │           │    │                   │               │           │
 │             │              │<──────────┘    │                   │               │           │
 │             │              │                │                   │               │           │
 │             │              │ Detect intent  │                   │               │           │
 │             │              ├──────────────>│                   │               │           │
 │             │              │                │                   │               │           │
 │             │              │   Is data query?                   │               │           │
 │             │              │<───────────────┤                   │               │           │
 │             │              │      YES       │                   │               │           │
 │             │              │                │                   │               │           │
 │             │              │ Translate query│                   │               │           │
 │             │              ├───────────────────────────────────────────────────────────────>│
 │             │              │                │"translate to PromQL"              │           │
 │             │              │                │                   │               │           │
 │             │              │<───────────────────────────────────────────────────────────────┤
 │             │              │                │  PromQL query     │               │           │
 │             │              │                │                   │               │           │
 │             │              │ Execute query  │                   │               │           │
 │             │              ├────────────────┼──────────────────>│               │           │
 │             │              │                │                   │  HTTP GET     │           │
 │             │              │                │                   ├──────────────>│           │
 │             │              │                │                   │               │           │
 │             │              │                │                   │  Results      │           │
 │             │              │                │                   │<──────────────┤           │
 │             │              │                │   Metrics data    │               │           │
 │             │              │<───────────────┼───────────────────┤               │           │
 │             │              │                │                   │               │           │
 │             │              │ Build context  │                   │               │           │
 │             │              ├───────────┐    │                   │               │           │
 │             │              │           │    │                   │               │           │
 │             │              │<──────────┘    │                   │               │           │
 │             │              │                │                   │               │           │
 │             │              │ Generate response with context     │               │           │
 │             │              ├───────────────────────────────────────────────────────────────>│
 │             │              │                │                   │               │           │
 │             │              │<───────────────────────────────────────────────────────────────┤
 │             │              │                │  AI response (stream)             │           │
 │             │              │                │                   │               │           │
 │             │  Stream      │                │                   │               │           │
 │             │<─────────────┤                │                   │               │           │
 │  Display    │              │                │                   │               │           │
 │<────────────┤              │                │                   │               │           │
 │             │              │                │                   │               │           │
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Docker Host                                 │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Docker Network: aiops-network                                │  │
│  │                                                                 │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │  │
│  │  │ PostgreSQL   │  │ Prometheus   │  │    Grafana         │  │  │
│  │  │   :5432      │  │   :9090      │  │     :3000          │  │  │
│  │  └──────────────┘  └──────────────┘  └────────────────────┘  │  │
│  │                                                                 │  │
│  │  ┌──────────────┐  ┌──────────────────────────────────────┐  │  │
│  │  │    Loki      │  │  Remediation Engine (FastAPI)        │  │  │
│  │  │   :3100      │  │        :8080                          │  │  │
│  │  └──────────────┘  │  • Chat Service                       │  │  │
│  │                     │  • Grafana Integration                │  │  │
│  │                     │  • LLM Service                        │  │  │
│  │                     └──────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ Port 8080
                                    │
                          ┌─────────┴─────────┐
                          │   Users / Alerts  │
                          └───────────────────┘
```

## Data Flow - Context Building

```
┌────────────────────────────────────────────────────────┐
│            Context Builder Input                       │
│  • User query: "Was abc app healthy yesterday?"       │
│  • Chat history: Last 10 messages                     │
│  • Session metadata: alert_id, app_id                 │
└────────────────────────┬───────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌─────────────┐  ┌──────────────┐  ┌─────────────────┐
│   Alert     │  │ Application  │  │   Historical    │
│  History    │  │   Profile    │  │     Data        │
└──────┬──────┘  └──────┬───────┘  └────────┬────────┘
       │                │                    │
       │                │          ┌─────────┴─────────┐
       │                │          │                   │
       │                │     ┌────▼─────┐      ┌─────▼────┐
       │                │     │ Metrics  │      │  Logs    │
       │                │     │ Summary  │      │ Summary  │
       │                │     └────┬─────┘      └─────┬────┘
       │                │          │                   │
       └────────────────┴──────────┴───────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│              Enriched Context                          │
│                                                         │
│  System Prompt:                                        │
│  • You are an SRE AI with access to monitoring data   │
│  • Application: abc-app (Python/FastAPI)              │
│  • Architecture: 3 microservices + PostgreSQL         │
│                                                         │
│  Current Alert:                                        │
│  • High Error Rate (5.2%) at 2:30 PM                  │
│  • Duration: 15 minutes                                │
│                                                         │
│  Yesterday's Metrics (24h):                            │
│  • Uptime: 99.8%                                       │
│  • Avg Error Rate: 0.4%                                │
│  • P95 Latency: 245ms                                  │
│  • Total Requests: 1.2M                                │
│                                                         │
│  SLOs:                                                 │
│  • Availability: >99.9%                                │
│  • Error Rate: <2%                                     │
│  • P95 Latency: <500ms                                 │
│                                                         │
│  Recent Events (24h):                                  │
│  • 142 total events (95 info, 35 warn, 12 error)      │
│  • Spike at 2:30 PM during deployment                  │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
                   ┌──────────┐
                   │   LLM    │
                   └──────────┘
```

## Summary

These diagrams illustrate:

1. **System Architecture**: How components interact within the remediation engine
2. **Data Flow**: Step-by-step query execution from user input to AI response
3. **Component Interaction**: Detailed flow between services
4. **Database Schema**: New tables and relationships for Grafana integration
5. **Sequence Diagram**: Complete message flow across all components
6. **Deployment**: Docker-based deployment architecture
7. **Context Building**: How monitoring data enriches AI prompts

The architecture is designed to be:
- **Modular**: Each component has clear responsibilities
- **Scalable**: Caching and async processing for performance
- **Extensible**: Easy to add new datasource types
- **Maintainable**: Clean separation of concerns
