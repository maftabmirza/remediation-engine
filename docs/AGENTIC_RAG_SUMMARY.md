# Agentic RAG System - Feature Summary

## Overview

The Agentic RAG system replaces the traditional "all-context-upfront" approach with an LLM-driven information gathering pattern. Instead of loading all available data into a single prompt, the LLM dynamically fetches information through tools as needed.

## Problem Solved

| Before (Static) | After (Agentic) |
|-----------------|-----------------|
| Load ALL context upfront (~4000+ tokens) | Minimal context (~800 tokens) + on-demand |
| Irrelevant data dilutes useful info | LLM picks what matters |
| Same cost regardless of question | Pay only for what's used |
| Can't adapt to question type | Dynamic per question |

## Architecture

```
User Question
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  AgenticOrchestrator                                │
│  ┌───────────────┐    ┌──────────────────────────┐  │
│  │ Provider      │───▶│ NativeToolAgent          │  │
│  │ Router        │    │ (OpenAI/Anthropic/Google)│  │
│  │               │    └──────────────────────────┘  │
│  │ if native     │    ┌──────────────────────────┐  │
│  │ else ────────────▶│ ReActAgent (Ollama)      │  │
│  └───────────────┘    └──────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│  ToolRegistry (10 Tools)                            │
│  • search_knowledge      • query_grafana_metrics    │
│  • get_similar_incidents • query_grafana_logs       │
│  • get_recent_changes    • get_correlated_alerts    │
│  • get_runbook           • get_service_dependencies │
│  • get_feedback_history  • get_alert_details        │
└─────────────────────────────────────────────────────┘
```

## Provider Support

| Provider | Agent Type | Tool Calling |
|----------|------------|--------------|
| OpenAI | NativeToolAgent | Native function calling |
| Anthropic | NativeToolAgent | Native tool use |
| Google | NativeToolAgent | Native function calling |
| Ollama | ReActAgent | Text parsing (Action/Observation) |

## File Structure

```
app/services/agentic/
├── __init__.py           # Package exports
├── tool_registry.py      # Tool definitions + execution (~600 lines)
├── native_agent.py       # OpenAI/Anthropic/Google agent (~350 lines)
├── react_agent.py        # Ollama/local LLM agent (~300 lines)
└── orchestrator.py       # Router + streaming helper (~290 lines)

app/routers/
└── chat_ws.py            # Updated with ?agentic=true param

tests/unit/services/agentic/
├── test_tool_registry.py # Tool tests
├── test_agents.py        # Agent tests
└── test_orchestrator.py  # Orchestrator tests
```

## Tools Available

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `search_knowledge` | Search runbooks, SOPs, docs | query, doc_type, limit |
| `get_similar_incidents` | Past incidents via pgvector | limit |
| `get_recent_changes` | Deployments/config changes | service, hours_back |
| `get_runbook` | Remediation procedures | service, alert_type |
| `query_grafana_metrics` | Prometheus via Grafana | promql, time_range |
| `query_grafana_logs` | Loki logs via Grafana | logql, limit |
| `get_correlated_alerts` | Related alerts in group | (uses context) |
| `get_service_dependencies` | Upstream/downstream deps | service |
| `get_feedback_history` | Past user feedback | limit |
| `get_alert_details` | Full alert metadata | (uses context) |

## Configuration

```python
OrchestratorConfig(
    max_iterations=7,      # Max tool calls per conversation
    temperature=0.3,       # LLM temperature
    max_tokens=2000,       # Max tokens per response
    enable_streaming=True, # Stream responses
    log_tool_calls=True    # Log tool usage
)
```

## Usage

### WebSocket (Default: Agentic Mode)
```
ws://host/ws/chat/{session_id}?token=xxx&agentic=true
```

### Programmatic
```python
from app.services.agentic import AgenticOrchestrator

orchestrator = AgenticOrchestrator(db, provider, alert)
response = await orchestrator.run("Why is CPU high?")
# response.content, response.tool_calls_made, response.iterations
```

## Workflow Example

```
1. User: "Why is CPU high on api-server-01?"

2. LLM thinks: "I need to check similar incidents"
   → Calls: get_similar_incidents(limit=3)
   ← Returns: "Found 2 similar: memory leak Jan 5, traffic spike Dec 20"

3. LLM thinks: "Check recent changes"
   → Calls: get_recent_changes(service="api")
   ← Returns: "Deploy 2h ago: auth caching layer"

4. LLM thinks: "Get runbook"
   → Calls: get_runbook(service="api", alert_type="cpu")
   ← Returns: "Runbook: restart pods, check memory"

5. LLM: "Based on my investigation:
   - Similar incident Jan 5 was memory leak
   - Deploy 2h ago added auth caching
   - Recommended: kubectl rollout restart..."
```

## Branch

`claude/agentic-rag-implementation-5hqNQ`

## Dependencies

- Existing services (no changes required):
  - `SimilarityService`, `KnowledgeSearchService`
  - `ChangeImpactService`, `PrometheusClient`, `LokiClient`
- LiteLLM for multi-provider support
- pgvector for similarity search
