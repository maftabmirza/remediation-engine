# Quick Reference: AI Chat with Grafana Integration

## 📋 TL;DR

**Goal**: Enable users to ask questions about application health and get data-driven answers from actual monitoring systems.

**Example Questions**:
- "How many events were created for abc app in last 24 hours?" → Answer: 142 events (95 info, 35 warn, 12 error)
- "Was abc app healthy yesterday?" → Answer: Yes, 99.8% uptime, 0.4% error rate, within SLOs
- "Was the server impacted?" → Answer: Yes, CPU spiked to 95%, memory hit 92%

## 🎯 What We're Building

### Current State ❌
- AI can only discuss alerts
- Cannot access historical metrics or logs
- No connection to Grafana/Prometheus/Loki
- Users must manually check dashboards

### Future State ✅
- AI queries actual monitoring data
- Answers with facts, not assumptions
- Integrates Prometheus (metrics) and Loki (logs)
- Natural language → Data queries → Intelligent responses

## 🏗️ Architecture (Simplified)

```
User asks question
    ↓
AI detects: "This needs data"
    ↓
Translate: "errors in last 24h" → {app="abc"} |= "error" [24h]
    ↓
Execute query against Prometheus/Loki
    ↓
Get results: 142 events
    ↓
AI response: "142 events found (95 info, 35 warn, 12 error)..."
```

## 🔧 What We Need to Build

### 5 Main Components

1. **Grafana Datasource Connector**
   - Connect to Prometheus (metrics) and Loki (logs)
   - Execute PromQL and LogQL queries
   - Cache results for performance

2. **Application Profiles**
   - Define what metrics belong to which app
   - Store SLOs (e.g., error rate < 2%)
   - Map service names to metrics

3. **Query Translator**
   - Natural language → PromQL/LogQL
   - Uses LLM to understand intent
   - Example: "show errors" → `{app="abc"} |= "error"`

4. **Context Builder**
   - Gather relevant data before AI responds
   - Fetch recent metrics, events, health status
   - Enrich AI prompt with actual data

5. **Enhanced Chat Flow**
   - Detect if question needs data
   - Execute queries
   - Build response with facts
   - Stream to user

## 📊 Database Changes

### New Tables

```sql
-- Store Grafana/Prometheus/Loki connection info
grafana_datasources
  - url, api_key, type (prometheus/loki)

-- Store app metadata
application_profiles
  - name, metrics to track, SLOs, architecture info

-- Enhanced chat sessions
chat_sessions (add application_id link)

-- Query cache for performance
query_cache (hash, result, expires_at)
```

## 🚀 Implementation Timeline

### 12-Week Plan (6 Phases)

| Phase | Weeks | Focus | Output |
|-------|-------|-------|--------|
| 1 | 1-2 | Foundation | Datasource API clients, DB schema |
| 2 | 3-4 | Data Retrieval | Historical data service, caching |
| 3 | 5-6 | AI Enhancement | Context builder, enriched prompts |
| 4 | 7-8 | Translation | Natural language → queries |
| 5 | 9-10 | Integration | End-to-end chat flow |
| 6 | 11-12 | Polish | Optimization, documentation |

## 💡 Example Flows

### Flow 1: Event Count
```
User: "How many events for abc app in last 24 hours?"

System:
1. Detect: Event count query
2. App: "abc", Time: "24h"
3. Query: count_over_time({app="abc"}[24h])
4. Execute against Loki
5. Result: 142 events
6. AI: "142 events in last 24 hours: 95 info, 35 warnings, 12 errors. 
       Most occurred 2-4 PM UTC during peak traffic."
```

### Flow 2: Health Status
```
User: "Was abc app healthy yesterday?"

System:
1. Detect: Health query
2. Load app SLOs (error rate < 2%, uptime > 99.9%)
3. Execute queries:
   - Error rate: rate(errors{app="abc"})[1d]
   - Uptime: up{app="abc"}
4. Compare with SLOs
5. AI: "Mostly healthy: 99.8% uptime. Brief degradation at 2:30 PM 
       where errors spiked to 5.2% (above SLO). Self-resolved in 15 min."
```

### Flow 3: Impact Analysis
```
User: "Was server impacted during last incident?"

System:
1. Find last incident time
2. Query infrastructure metrics at that time
3. Compare with baseline
4. AI: "Yes, significant impact:
       - CPU: 95% (baseline 45%)
       - Memory: 92% (baseline 65%)
       - Network: 3x normal
       Root cause: Database connection pool exhaustion"
```

## 🔐 Security & Performance

### Security
- ✅ Encrypt datasource credentials
- ✅ Validate queries before execution
- ✅ Rate limit per user
- ✅ Audit log all queries
- ✅ Sanitize results (no PII)

### Performance
- ✅ Cache query results (5 min)
- ✅ Limit query ranges (max 7 days)
- ✅ Limit result sizes (max 10k)
- ✅ Execute queries in parallel
- ✅ Stream AI responses

## 📦 Tech Stack

### New Dependencies
```python
prometheus-api-client==0.5.5  # Query Prometheus
requests==2.31.0               # HTTP client
pandas==2.1.4                  # Data processing
cachetools==5.3.2              # Query caching
```

### Infrastructure (Docker)
```yaml
services:
  prometheus:  # Metrics database
  loki:        # Log aggregation
  grafana:     # Visualization (optional)
```

## 📈 Success Metrics

### Technical
- Query translation accuracy: **>85%**
- Response time (p95): **<5 seconds**
- Cache hit rate: **>60%**
- Availability: **>99.9%**

### User
- Successful queries: **>80%**
- User satisfaction: **>4/5**
- Weekly active users: **>60%**
- MTTR reduction: **20%**

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Wrong query translation | Show generated query, allow edit |
| Slow queries | Caching, limits, async execution |
| Datasource down | Graceful degradation, cached fallback |
| LLM hallucination | Ground in actual data, show sources |

## 🎓 Key Decisions

### Why LLM for Query Translation?
- **Flexible**: Handles natural language variations
- **Extensible**: Easy to add new query types
- **Better UX**: Users don't need to know PromQL

### Why Direct API (not Grafana API)?
- **Simpler**: Direct to Prometheus/Loki
- **Flexible**: Works without Grafana
- **Faster**: No additional hop

### Why Cache Results?
- **Performance**: Metrics don't change retroactively
- **Cost**: Avoid expensive repeated queries
- **Reliability**: Fallback when datasource slow

## 📚 Documentation Created

1. **GRAFANA_AI_CHAT_INTEGRATION_PLAN.md** (27KB)
   - Complete technical specification
   - Detailed implementation guide
   - API specs, schemas, security

2. **AI_CHAT_GRAFANA_BRIEF_APPROACH.md** (10KB)
   - Executive summary
   - High-level approach
   - Example flows

3. **ARCHITECTURE_DIAGRAMS.md** (26KB)
   - System architecture (ASCII art)
   - Data flows
   - Sequence diagrams

4. **QUICK_REFERENCE.md** (This file)
   - Quick overview
   - Key concepts
   - Easy reference

## 🔄 Next Steps

1. **Review**: Stakeholder approval of plan
2. **Setup**: Deploy test Grafana/Prometheus/Loki
3. **Implement**: Start Phase 1 (Foundation)
4. **Iterate**: Build incrementally, test often
5. **Deploy**: Roll out to users

## 📝 Notes

- **This is planning only** - no code yet
- **Incremental approach** - each phase delivers value
- **Built on existing** - leverages current chat infrastructure
- **Extensible design** - easy to add more datasources later

## 🔗 Related Files

- Main Plan: `docs/GRAFANA_AI_CHAT_INTEGRATION_PLAN.md`
- Brief Approach: `docs/AI_CHAT_GRAFANA_BRIEF_APPROACH.md`
- Architecture: `docs/ARCHITECTURE_DIAGRAMS.md`
- Current Chat: `app/services/chat_service.py`
- Current Models: `app/models_chat.py`

---

**Ready for implementation when approved!** 🚀
