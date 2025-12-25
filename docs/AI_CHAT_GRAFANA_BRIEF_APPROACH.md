# AI Chat with Grafana Stack Analysis - Brief Approach

## Overview

Enhance the existing AI chat feature to intelligently answer questions about application health, events, and historical data by integrating with Grafana stack (Prometheus, Loki, Grafana).

## Problem We're Solving

**Current State**: 
- AI chat can discuss alerts but cannot access historical metrics or logs
- Users manually check Grafana dashboards for application health data
- No correlation between AI analysis and actual monitoring data

**Desired State**:
- Users ask: "Was abc app healthy yesterday?" → AI queries metrics and provides data-driven answer
- Users ask: "List events for abc app in last 24 hours" → AI retrieves and summarizes log data
- Users ask: "Was server impacted?" → AI correlates infrastructure metrics with incidents

## High-Level Architecture

```
User Question (Natural Language)
        ↓
AI Chat Interface (existing)
        ↓
Enhanced Chat Service:
  1. Detect if question needs data (is it about metrics/logs/health?)
  2. Translate question to appropriate query (PromQL/LogQL)
  3. Execute query against Grafana datasources
  4. Get results and enrich AI context
  5. Generate intelligent response with actual data
        ↓
Response to User (with facts, not assumptions)
```

## Key Components to Build

### 1. Grafana Datasource Connector
**What**: Python service to connect to Prometheus and Loki  
**Why**: Need to retrieve actual metrics and logs  
**How**: Use Prometheus API client and Loki API for queries  

### 2. Application Profile Manager
**What**: Store metadata about applications (what metrics to track, where logs are)  
**Why**: AI needs to know which metrics belong to which app  
**How**: New database table + API to configure apps  

### 3. Query Translator
**What**: Convert "show me errors" → `{app="abc"} |= "error"`  
**Why**: Users speak English, datasources speak PromQL/LogQL  
**How**: Use LLM (same one as chat) to translate natural language to query syntax  

### 4. Context Builder
**What**: Gather relevant historical data before AI responds  
**Why**: AI needs facts (actual metrics) not just alert info  
**How**: Fetch recent metrics, events, health status and add to AI prompt  

### 5. Enhanced Chat Flow
**What**: Modified chat pipeline that can query data sources  
**Why**: Current chat only has alert context, needs monitoring data  
**How**: Detect data queries → execute → summarize → respond  

## Example User Flows

### Example 1: Event Count
```
User: "How many events created for abc app in last 24 hours?"

Behind the scenes:
1. Detect: This is a log/event query
2. Identify: app = "abc", timerange = "24h"
3. Translate: {app="abc"}[24h] | count_over_time
4. Execute: Query Loki
5. Result: 142 events (95 info, 35 warning, 12 error)
6. AI Response: "The abc application generated 142 events in the 
   last 24 hours: 95 info-level, 35 warnings, and 12 errors. 
   The majority occurred during peak hours (2-4 PM UTC)."
```

### Example 2: Health Check
```
User: "Was abc app healthy yesterday?"

Behind the scenes:
1. Detect: Health status query
2. Get app profile: What defines "healthy" for abc?
3. Execute multiple queries:
   - Error rate: rate(errors_total{app="abc"})[1d]
   - Uptime: up{app="abc"}
   - Latency: http_duration_p95{app="abc"}
4. Compare against SLOs
5. AI Response: "The abc app was mostly healthy yesterday with 
   99.8% uptime. There was a 15-minute degradation at 2:30 PM 
   where error rate spiked to 5.2% (above 2% SLO) and latency 
   increased to 850ms (above 500ms SLO). Issue self-resolved."
```

### Example 3: Impact Analysis
```
User: "Was the server impacted during the last incident?"

Behind the scenes:
1. Detect: Impact query + find last incident
2. Get incident time: Query alert history
3. Query infrastructure metrics at that time:
   - CPU, Memory, Disk I/O, Network
4. Compare with baseline
5. AI Response: "Yes, significant impact. During incident 
   (10:15-10:45 UTC):
   - CPU spiked to 95% (baseline: 45%)
   - Memory hit 92% (baseline: 65%)
   - Network traffic 3x normal
   Root cause: Database connection pool exhaustion"
```

## Implementation Approach

### Phase 1: Foundation (Weeks 1-2)
- Set up Grafana/Prometheus/Loki in docker-compose
- Create database schema for datasources & app profiles
- Build basic Prometheus and Loki API clients
- Add admin UI to configure datasources

### Phase 2: Query Execution (Weeks 3-4)
- Build historical data service (fetch metrics/logs)
- Implement query caching for performance
- Create helper functions for common queries
- Test with real monitoring data

### Phase 3: AI Integration (Weeks 5-6)
- Enhance AI prompts with monitoring data context
- Build context aggregator (collect relevant data)
- Integrate with existing chat service
- Handle large context windows efficiently

### Phase 4: Query Translation (Weeks 7-8)
- Build LLM-powered query translator
- Create query intent detection (is user asking for data?)
- Add query validation (prevent bad queries)
- Build library of example translations

### Phase 5: End-to-End (Weeks 9-10)
- Integrate all components into chat flow
- Add error handling and fallbacks
- Optimize response times
- User testing and refinement

### Phase 6: Polish (Weeks 11-12)
- Performance optimization (caching, parallel queries)
- Documentation (user guide, admin setup)
- UI improvements (show charts inline, query preview)
- Training and rollout

## Technical Stack

**New Dependencies**:
- `prometheus-api-client` - Query Prometheus
- `requests` - HTTP calls to Loki/Grafana
- `pandas` (optional) - Data processing
- `cachetools` - Query result caching

**New Infrastructure**:
- Prometheus (already partially integrated)
- Grafana (for visualization reference)
- Loki (for log aggregation)

**Database Changes**:
- `grafana_datasources` table (connection info)
- `application_profiles` table (app metadata)
- Extend `chat_sessions` with datasource context

## Key Design Decisions

### 1. Why LLM-based Query Translation?
**Alternative**: Rule-based parser (if X then query Y)  
**Chosen**: LLM translation  
**Reason**: Handles natural language variations better, easier to extend

### 2. Why Direct API vs. Grafana API?
**Alternative**: Use Grafana's unified API  
**Chosen**: Direct Prometheus/Loki APIs  
**Reason**: More flexible, works without Grafana, simpler

### 3. Why Cache Query Results?
**Reason**: Metrics don't change retroactively, avoid repeated expensive queries

### 4. Why Application Profiles?
**Reason**: AI needs to know what metrics/logs are relevant for each app

## Security & Performance

### Security
- Encrypt datasource credentials (use existing Fernet encryption)
- Validate all translated queries before execution
- Rate limit queries per user
- Audit log all query executions
- Sanitize query results (no PII in logs)

### Performance
- Cache query results (5 min TTL)
- Limit query time ranges (max 7 days)
- Limit result set sizes (max 10k points)
- Execute multiple queries in parallel
- Stream AI responses (don't wait for all data)

## Success Criteria

**Technical**:
- Query translation accuracy >85%
- Response time <5 seconds (p95)
- Cache hit rate >60%
- System stays available >99.9%

**User**:
- 80% of data queries return useful results
- Users rate feature >4/5
- 60% of users use feature weekly
- 20% reduction in time to insight

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM translates query wrong | Users get wrong data | Show generated query, allow edit, validate results |
| Queries are slow | Poor UX | Aggressive caching, query limits, async execution |
| Datasource unavailable | Feature broken | Graceful degradation, retry logic, cached fallback |
| LLM hallucinates analysis | Incorrect conclusions | Ground in actual data, show sources, confidence scores |

## Future Enhancements

**After MVP**:
- Machine learning anomaly detection
- Interactive charts embedded in chat
- Automated root cause analysis (correlate metrics with issues)
- Predictive alerts based on patterns
- Auto-generate runbooks from successful resolutions
- Multi-datasource correlation (join Prometheus + Elasticsearch + custom DBs)

## Getting Started (When Implementation Begins)

1. **Review this plan** with team and stakeholders
2. **Set up test environment**: Deploy Prometheus, Loki, Grafana
3. **Create sample data**: Generate test metrics and logs for abc app
4. **Start Phase 1**: Database schema and basic API clients
5. **Iterate**: Build incrementally, test with real users

## Comparison: Before vs After

### Before
```
User: "Was abc app healthy yesterday?"
AI: "I don't have access to historical metrics. You can check 
     the Grafana dashboard or Prometheus queries to see the 
     health metrics for yesterday."
```

### After
```
User: "Was abc app healthy yesterday?"
AI: "Yes, abc app was healthy yesterday. Here are the key metrics:
     ✅ Uptime: 99.8% (23h 57m up)
     ✅ Error rate: 0.4% (below 2% SLO)
     ✅ P95 latency: 245ms (below 500ms SLO)
     ⚠️  Brief spike at 2:30 PM (15 min degradation)
     
     The spike was caused by a deployment that triggered cache 
     invalidation. Auto-recovered after 15 minutes."
```

## Conclusion

This approach enhances the existing AI chat with **data-driven intelligence** by:

1. **Connecting** to Grafana stack (Prometheus, Loki)
2. **Translating** natural language questions to queries
3. **Retrieving** actual historical metrics and logs
4. **Enriching** AI context with real data
5. **Responding** with fact-based analysis instead of speculation

The result is an AI assistant that combines LLM intelligence with monitoring data reality, helping users get faster, more accurate answers about their applications.

**This is planning only** - no code changes yet. Next step: Get approval and start Phase 1 implementation.
