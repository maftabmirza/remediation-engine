# AI Chat Features with Grafana Stack Analysis - Implementation Plan

## Executive Summary

This document outlines a comprehensive plan to enhance the existing AI chat features in the AIOps Remediation Engine with Grafana stack analysis capabilities. The enhancement will enable users to ask natural language questions about application health, events, and historical data, with the AI leveraging both AIOps context and Grafana metrics/logs to provide intelligent, data-driven responses.

## Problem Statement

Users need to interact with their monitoring data through natural language queries such as:
- "List how many events created for the abc app in last 24 hours"
- "Was abc app healthy yesterday?"
- "Was the server impacted during the incident?"
- "Show me CPU usage trends for service X"
- "What were the error rates when the alert fired?"

Currently, the system has:
- ✅ AI chat interface with LLM integration
- ✅ Alert ingestion from Alertmanager
- ✅ Prometheus metrics exposure
- ❌ No Grafana datasource integration
- ❌ No historical metrics/logs querying
- ❌ No context-aware query translation

## Current Architecture Analysis

### Existing Components

1. **Chat Infrastructure**
   - Models: `ChatSession`, `ChatMessage`
   - Services: `chat_service.py` with LangChain integration
   - Routes: REST API (`chat_api.py`) and WebSocket (`chat_ws.py`)
   - LLM Providers: Claude, GPT-4, Gemini, Llama (via LiteLLM)

2. **Monitoring Integration**
   - Prometheus metrics collection
   - Alertmanager webhook receiver
   - Alert storage and analysis

3. **Data Layer**
   - PostgreSQL database
   - Alert history with annotations
   - AI analysis results

### Architecture Gaps

1. **No Historical Data Access**: AI cannot query past metrics/logs
2. **No Grafana Integration**: No connection to Grafana datasources
3. **Limited Context**: AI lacks application architecture information
4. **No Query Translation**: Cannot convert natural language to PromQL/LogQL

## Proposed Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                           │
│                     (AI Chat Interface)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Enhanced Chat Service                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Context Builder                                         │   │
│  │  • Alert history                                         │   │
│  │  • Application metadata                                  │   │
│  │  • Recent metrics/events                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Query Translator (LLM-powered)                          │   │
│  │  • Natural language → PromQL                             │   │
│  │  • Natural language → LogQL                              │   │
│  │  • Query validation                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Grafana Integration Layer                       │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Prometheus    │  │  Loki          │  │  Custom          │  │
│  │  Client        │  │  Client        │  │  Datasources     │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Sources                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Prometheus    │  │  Loki          │  │  Grafana         │  │
│  │  (Metrics)     │  │  (Logs)        │  │  (Dashboards)    │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. Grafana Datasource Integration Service

**Purpose**: Manage connections to Grafana datasources and execute queries

**Key Features**:
- Connection management for multiple Grafana instances
- Prometheus API client for metric queries
- Loki API client for log queries
- Query result caching for performance
- Error handling and retry logic

**Database Schema**:
```python
class GrafanaDatasource(Base):
    id: UUID
    name: str
    type: str  # prometheus, loki, influxdb, etc.
    url: str
    api_key_encrypted: str
    is_default: bool
    is_enabled: bool
    config_json: dict  # Additional datasource-specific config
    created_at: datetime
    updated_at: datetime

class ApplicationProfile(Base):
    id: UUID
    name: str  # e.g., "abc-app"
    description: str
    architecture_info: dict  # JSON with architecture details
    service_mappings: dict  # Map service names to metrics/logs
    datasource_id: UUID  # FK to GrafanaDatasource
    default_metrics: list  # Common metrics to track
    created_at: datetime
    updated_at: datetime
```

**API Endpoints**:
```python
# Datasource Management
POST   /api/grafana/datasources           # Add datasource
GET    /api/grafana/datasources           # List datasources
GET    /api/grafana/datasources/{id}      # Get datasource
PUT    /api/grafana/datasources/{id}      # Update datasource
DELETE /api/grafana/datasources/{id}      # Delete datasource

# Application Profiles
POST   /api/applications                  # Create app profile
GET    /api/applications                  # List app profiles
GET    /api/applications/{id}             # Get app profile
PUT    /api/applications/{id}             # Update app profile
DELETE /api/applications/{id}             # Delete app profile

# Query Execution
POST   /api/grafana/query/prometheus      # Execute PromQL query
POST   /api/grafana/query/loki            # Execute LogQL query
GET    /api/grafana/metrics/{app_id}      # Get metrics for app
GET    /api/grafana/logs/{app_id}         # Get logs for app
```

#### 2. Historical Data Service

**Purpose**: Retrieve and process historical monitoring data

**Key Features**:
- Time-series data retrieval
- Data aggregation and summarization
- Anomaly detection on historical data
- Event correlation with alerts

**Capabilities**:
```python
class HistoricalDataService:
    async def get_metrics_range(
        datasource_id: UUID,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str = "1m"
    ) -> TimeSeriesData
    
    async def get_logs_range(
        datasource_id: UUID,
        query: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> LogEntries
    
    async def get_application_health(
        app_id: UUID,
        time_range: str = "24h"
    ) -> HealthSummary
    
    async def get_event_count(
        app_id: UUID,
        time_range: str = "24h",
        filters: dict = None
    ) -> EventCount
    
    async def analyze_impact(
        app_id: UUID,
        alert_time: datetime,
        window: str = "1h"
    ) -> ImpactAnalysis
```

#### 3. AI Context Enhancement

**Purpose**: Enrich AI prompts with relevant monitoring data and context

**Enhanced System Prompt**:
```python
def get_enhanced_system_prompt(
    alert: Optional[Alert],
    app_profile: Optional[ApplicationProfile],
    recent_metrics: Optional[dict],
    recent_events: Optional[list]
) -> str:
    """
    Generate enhanced system prompt with:
    - Alert context (existing)
    - Application architecture
    - Recent metrics summary
    - Recent events/incidents
    - Available datasources
    - Query capabilities
    """
```

**Context Builder**:
```python
class AIContextBuilder:
    async def build_context(
        session: ChatSession,
        user_query: str
    ) -> dict:
        """
        Build comprehensive context including:
        1. Alert history for the session
        2. Application profile if linked
        3. Recent metrics (last 1h, 24h, 7d summaries)
        4. Recent similar incidents
        5. Available query capabilities
        """
```

#### 4. Natural Language Query Translator

**Purpose**: Convert natural language questions to executable queries

**LLM-Powered Translation**:
```python
class QueryTranslator:
    async def translate_to_promql(
        natural_query: str,
        app_context: ApplicationProfile
    ) -> str:
        """
        Use LLM to convert natural language to PromQL
        Example:
        Input: "CPU usage for abc app in last hour"
        Output: 'rate(cpu_usage{app="abc"}[1h])'
        """
    
    async def translate_to_logql(
        natural_query: str,
        app_context: ApplicationProfile
    ) -> str:
        """
        Use LLM to convert natural language to LogQL
        Example:
        Input: "errors for abc app in last 24 hours"
        Output: '{app="abc"} |= "error" | json'
        """
    
    async def detect_query_intent(
        user_message: str
    ) -> QueryIntent:
        """
        Determine if user is asking for:
        - Metrics query
        - Logs query
        - Historical analysis
        - General conversation
        """
```

**Query Validation**:
- Syntax validation before execution
- Time range bounds checking
- Resource limit enforcement
- Security filtering (prevent unauthorized access)

#### 5. Enhanced Chat Flow

**New Chat Processing Pipeline**:

```python
async def enhanced_chat_response(
    session_id: UUID,
    user_message: str
) -> AsyncGenerator[str, None]:
    """
    1. Detect query intent
    2. If data query detected:
       a. Translate to appropriate query language
       b. Execute query against datasource
       c. Summarize results
       d. Build enhanced context
    3. Generate AI response with data context
    4. Stream response to user
    """
```

**Example User Flows**:

**Flow 1: Event Count Query**
```
User: "How many events were created for abc app in last 24 hours?"

System Actions:
1. Detect intent: Event count query
2. Identify app: "abc"
3. Parse time range: "24 hours"
4. Execute query: count_over_time({app="abc"}[24h])
5. Get result: 142 events
6. Generate response: "In the last 24 hours, the abc application 
   generated 142 events. Breaking this down: 95 info-level events,
   35 warnings, and 12 errors. The majority occurred between 
   2-4 PM UTC, coinciding with peak traffic hours."
```

**Flow 2: Health Status Query**
```
User: "Was abc app healthy yesterday?"

System Actions:
1. Detect intent: Health status query
2. Identify app: "abc"
3. Parse time range: "yesterday" → [start_of_yesterday, end_of_yesterday]
4. Execute multiple queries:
   - Error rate: rate(http_errors_total{app="abc"}[5m])
   - Uptime: up{app="abc"}
   - Response time: histogram_quantile(0.95, http_duration_seconds{app="abc"})
5. Analyze results against SLOs
6. Generate response: "The abc application was largely healthy 
   yesterday with 99.8% uptime. However, there was a brief degradation
   from 14:30-14:45 UTC where error rates spiked to 5.2% (above the
   2% SLO) and p95 latency increased to 850ms (above 500ms SLO).
   The issue self-resolved after 15 minutes."
```

**Flow 3: Impact Analysis**
```
User: "Was the server impacted during the last incident?"

System Actions:
1. Detect intent: Impact analysis
2. Find last incident: Query alert history
3. Get incident time window
4. Execute infrastructure metrics:
   - node_cpu_usage
   - node_memory_usage
   - node_disk_io
   - node_network_traffic
5. Compare with baseline
6. Generate response: "Yes, the server was significantly impacted.
   During the incident from 10:15-10:45 UTC:
   - CPU utilization spiked to 95% (baseline: 45%)
   - Memory usage reached 92% (baseline: 65%)
   - Network traffic increased 3x normal levels
   - Disk I/O operations backed up to 2000ms latency
   
   The root cause was a database connection pool exhaustion that
   cascaded to high CPU usage as connections queued."
```

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Objectives**:
- Set up Grafana datasource integration
- Create database schema
- Implement basic Prometheus/Loki clients

**Deliverables**:
1. Database migrations for new tables
2. GrafanaDatasource model and API endpoints
3. ApplicationProfile model and API endpoints
4. Basic Prometheus query client
5. Basic Loki query client
6. Admin UI for datasource management

**Testing**:
- Unit tests for datasource clients
- Integration tests with test Prometheus/Loki instances
- API endpoint tests

### Phase 2: Historical Data Service (Week 3-4)

**Objectives**:
- Build historical data retrieval service
- Implement data aggregation
- Create helper functions for common queries

**Deliverables**:
1. HistoricalDataService implementation
2. Pre-defined query templates
3. Caching layer for query results
4. Data summarization utilities
5. API endpoints for historical data

**Testing**:
- Query execution tests
- Performance benchmarks
- Cache behavior tests

### Phase 3: AI Context Enhancement (Week 5-6)

**Objectives**:
- Enhance AI prompts with monitoring data
- Build context aggregation system
- Integrate with existing chat service

**Deliverables**:
1. AIContextBuilder implementation
2. Enhanced system prompt generation
3. Context summarization logic
4. Integration with chat_service.py
5. Token management for large contexts

**Testing**:
- Context building tests
- Prompt generation tests
- Integration tests with chat flow

### Phase 4: Query Translation (Week 7-8)

**Objectives**:
- Implement natural language to query translation
- Add query intent detection
- Build query validation

**Deliverables**:
1. QueryTranslator implementation
2. Intent detection system
3. Query validation framework
4. Translation prompt templates
5. Example query library

**Testing**:
- Translation accuracy tests
- Intent detection tests
- Edge case handling tests

### Phase 5: Enhanced Chat Flow (Week 9-10)

**Objectives**:
- Integrate all components into chat flow
- Build end-to-end query processing
- Optimize response generation

**Deliverables**:
1. Enhanced chat pipeline
2. Query execution orchestration
3. Result formatting and presentation
4. Error handling and fallbacks
5. UI improvements for data visualization

**Testing**:
- End-to-end user flow tests
- Performance tests under load
- Error scenario tests
- User acceptance testing

### Phase 6: Polish and Documentation (Week 11-12)

**Objectives**:
- Performance optimization
- Documentation
- Training and rollout

**Deliverables**:
1. Performance optimizations
2. User documentation
3. Admin guide for datasource setup
4. Example queries and use cases
5. Training materials
6. Deployment guide

## Technical Specifications

### Required Dependencies

Add to `requirements.txt`:
```
# Grafana/Prometheus integration
prometheus-api-client==0.5.5
prometheus-client==0.19.0  # Already exists
requests==2.31.0

# Time series processing
pandas==2.1.4
numpy==1.26.2

# Query optimization
cachetools==5.3.2
```

### Configuration

Add to `.env`:
```bash
# Grafana Integration
GRAFANA_DEFAULT_URL=http://grafana:3000
GRAFANA_API_KEY=
PROMETHEUS_URL=http://prometheus:9090
LOKI_URL=http://loki:3100

# Query Limits
MAX_QUERY_RANGE_HOURS=168  # 7 days
MAX_QUERY_RESULTS=10000
QUERY_CACHE_TTL_SECONDS=300  # 5 minutes
```

### Docker Compose Enhancement

Add to `docker-compose.yml`:
```yaml
  prometheus:
    image: prom/prometheus:latest
    container_name: aiops-prometheus
    restart: unless-stopped
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - aiops-network

  grafana:
    image: grafana/grafana:latest
    container_name: aiops-grafana
    restart: unless-stopped
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
    networks:
      - aiops-network

  loki:
    image: grafana/loki:latest
    container_name: aiops-loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/local-config.yaml
      - loki_data:/loki
    networks:
      - aiops-network

volumes:
  prometheus_data:
  grafana_data:
  loki_data:
```

## Security Considerations

### Access Control
1. **Datasource Credentials**: Store encrypted using existing Fernet encryption
2. **Query Permissions**: Validate user has access to requested datasources
3. **Query Injection**: Sanitize and validate all translated queries
4. **Rate Limiting**: Limit query frequency per user/session
5. **Resource Limits**: Enforce max query range and result size

### Data Privacy
1. **Sensitive Logs**: Filter out sensitive information from logs
2. **Metric Labels**: Sanitize metric labels that may contain PII
3. **Audit Trail**: Log all query executions for compliance
4. **Data Retention**: Respect datasource retention policies

## Performance Optimization

### Caching Strategy
1. **Query Results**: Cache for 5 minutes (configurable)
2. **Application Profiles**: Cache in-memory with Redis
3. **Datasource Metadata**: Cache datasource capabilities
4. **Translation Cache**: Cache query translations for common patterns

### Query Optimization
1. **Time Range Limits**: Prevent excessively long queries
2. **Result Pagination**: Limit result set sizes
3. **Parallel Queries**: Execute multiple queries concurrently
4. **Query Downsampling**: Automatically downsample for long ranges

### Response Optimization
1. **Streaming**: Stream AI responses as they're generated
2. **Progressive Loading**: Show data as it arrives
3. **Lazy Evaluation**: Only execute queries when needed
4. **Background Pre-fetching**: Pre-fetch common queries

## Monitoring and Observability

### New Metrics to Add
```python
# Grafana Integration Metrics
GRAFANA_QUERIES_TOTAL = Counter(
    'aiops_grafana_queries_total',
    'Total queries to Grafana datasources',
    ['datasource_type', 'status']
)

GRAFANA_QUERY_DURATION = Histogram(
    'aiops_grafana_query_duration_seconds',
    'Time to execute Grafana queries',
    ['datasource_type']
)

QUERY_TRANSLATIONS_TOTAL = Counter(
    'aiops_query_translations_total',
    'Natural language query translations',
    ['target_language', 'status']
)

CONTEXT_BUILD_DURATION = Histogram(
    'aiops_context_build_duration_seconds',
    'Time to build AI context'
)
```

### Dashboards
1. **Grafana Integration Dashboard**: Query stats, error rates, latency
2. **AI Chat Performance**: Response times, token usage, cache hit rates
3. **Query Translation Dashboard**: Translation accuracy, common patterns

## User Experience Enhancements

### UI Components

1. **Datasource Status Indicator**: Show connected datasources in chat
2. **Query Preview**: Show generated queries before execution (optional)
3. **Data Visualization**: Inline charts for metric queries
4. **Historical Context Panel**: Show relevant historical data
5. **Suggested Queries**: Auto-suggest common queries for the context

### Example UI Flow

```
┌─────────────────────────────────────────────────────────┐
│  Chat: abc-app Incident Analysis                       │
├─────────────────────────────────────────────────────────┤
│  Connected to: Prometheus (healthy), Loki (healthy)   │
├─────────────────────────────────────────────────────────┤
│  User: How many errors in the last 24 hours?          │
│                                                          │
│  AI: Let me check the error metrics...                 │
│      [Executing: sum(rate(http_errors{app="abc"}[24h]))]│
│                                                          │
│      In the last 24 hours, abc-app had:                │
│      • Total errors: 142                                │
│      • Error rate: 0.8% of requests                    │
│      • Peak: 18 errors at 14:30 UTC                    │
│                                                          │
│      [Chart showing error rate over time]              │
│                                                          │
│      This is within normal range. The spike at 14:30  │
│      correlates with the deployment event.             │
├─────────────────────────────────────────────────────────┤
│  Suggested: • Show me the error logs                   │
│             • What was the CPU usage?                  │
│             • Compare with last week                    │
└─────────────────────────────────────────────────────────┘
```

## Alternative Approaches Considered

### Approach 1: Direct Grafana API
- **Pros**: Official API, dashboard reuse
- **Cons**: Complex API, limited to Grafana installations
- **Decision**: Use datasource APIs directly for flexibility

### Approach 2: Prometheus Federation
- **Pros**: Standard Prometheus feature
- **Cons**: Requires special setup, limited to Prometheus
- **Decision**: Support but don't require it

### Approach 3: Pre-built Query Templates Only
- **Pros**: Fast, reliable, no translation needed
- **Cons**: Limited flexibility, can't handle arbitrary questions
- **Decision**: Combine templates with LLM translation

### Approach 4: Rule-based Query Parser
- **Pros**: Deterministic, fast
- **Cons**: Limited coverage, maintenance burden
- **Decision**: Use LLM for flexibility, add rule-based fallback

## Success Metrics

### Technical Metrics
- Query translation accuracy: >85%
- Query execution time: p95 < 5 seconds
- Cache hit rate: >60%
- System availability: >99.9%

### User Metrics
- Successful query resolution: >80%
- User satisfaction: >4/5 rating
- Time to insight: <2 minutes average
- Adoption rate: >60% of users use feature weekly

### Business Metrics
- MTTR reduction: 20% improvement
- Reduced escalations: 15% fewer tickets
- Self-service resolution: 30% of issues
- Knowledge retention: Historical analysis usage

## Risks and Mitigations

### Risk 1: Query Translation Accuracy
- **Impact**: Users get wrong data
- **Likelihood**: Medium
- **Mitigation**: Show generated query, allow manual edit, validate results

### Risk 2: Performance Degradation
- **Impact**: Slow responses, poor UX
- **Likelihood**: Medium
- **Mitigation**: Aggressive caching, query limits, async processing

### Risk 3: Datasource Connectivity
- **Impact**: Feature unavailable
- **Likelihood**: Low
- **Mitigation**: Graceful degradation, fallback to cached data, retry logic

### Risk 4: LLM Hallucination
- **Impact**: Incorrect analysis
- **Likelihood**: Low
- **Mitigation**: Ground responses in actual data, show sources, confidence scores

### Risk 5: Security Vulnerabilities
- **Impact**: Data exposure
- **Likelihood**: Low
- **Mitigation**: Query sanitization, access controls, audit logging

## Future Enhancements

### Phase 2 Features (Post-MVP)
1. **Machine Learning Integration**
   - Anomaly detection on metrics
   - Predictive alerts
   - Pattern recognition

2. **Advanced Visualizations**
   - Interactive charts in chat
   - Dashboard embedding
   - Custom report generation

3. **Multi-Datasource Correlation**
   - Join data from multiple sources
   - Cross-platform analysis
   - Unified view

4. **Automated RCA**
   - Root cause analysis using historical patterns
   - Correlation with deployments/changes
   - Impact assessment

5. **Runbook Integration**
   - Auto-suggest runbooks based on patterns
   - Generate runbooks from successful resolutions
   - Track resolution patterns

## Conclusion

This implementation plan provides a comprehensive roadmap for integrating Grafana stack analysis into the AIOps Remediation Engine's AI chat features. By following this phased approach, we can:

1. **Enhance User Experience**: Enable natural language queries for monitoring data
2. **Improve Incident Response**: Faster access to relevant historical data
3. **Increase Automation**: AI-powered query translation and analysis
4. **Maintain Flexibility**: Support multiple datasources and query languages
5. **Ensure Quality**: Comprehensive testing and validation at each phase

The plan balances ambition with pragmatism, starting with core functionality and building towards advanced features. Each phase delivers value independently while building towards the complete vision.

## Next Steps

1. **Review and Approval**: Stakeholder review of this plan
2. **Resource Allocation**: Assign development team
3. **Environment Setup**: Deploy test Grafana/Prometheus stack
4. **Sprint Planning**: Break down Phase 1 into sprints
5. **Kickoff**: Begin implementation

## Appendix

### A. Example Queries

**Metric Queries**:
- "What's the average response time for service X?"
- "Show me memory usage for the last week"
- "Compare error rates between production and staging"

**Log Queries**:
- "Find all errors containing 'database timeout'"
- "Show me the last 100 log entries for pod Y"
- "What were the logs during the incident?"

**Health Queries**:
- "Is service X healthy right now?"
- "What's the uptime for app Y this month?"
- "Show me SLO compliance"

**Impact Queries**:
- "What services were affected by the outage?"
- "How many users were impacted?"
- "What was the blast radius?"

### B. Query Translation Examples

```
Natural: "CPU usage for app abc in last hour"
PromQL: rate(cpu_usage_seconds_total{app="abc"}[1h])

Natural: "Errors in logs for service xyz"
LogQL: {service="xyz"} |= "error" | json | line_format "{{.level}}: {{.message}}"

Natural: "95th percentile response time"
PromQL: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

Natural: "Number of pod restarts"
PromQL: sum(kube_pod_container_status_restarts_total{app="abc"})
```

### C. Sample Application Profile

```json
{
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

### D. References

- [Prometheus Query API](https://prometheus.io/docs/prometheus/latest/querying/api/)
- [Loki Query API](https://grafana.com/docs/loki/latest/api/)
- [Grafana HTTP API](https://grafana.com/docs/grafana/latest/http_api/)
- [PromQL Documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [LogQL Documentation](https://grafana.com/docs/loki/latest/logql/)
