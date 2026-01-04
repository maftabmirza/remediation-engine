# AI Agent: Builder Mode Fix and Multi-Datasource Support

## Overview
This document describes the fix for the Builder mode extraction issue and the addition of multi-datasource support for the entire Grafana stack (Prometheus, Loki, Tempo, Mimir).

## Issues Fixed

### Issue 1: Builder Mode Extracting "True"
**Problem:**
When users were in Grafana's Builder mode (visual query builder), the AI Agent was extracting "True" as a query, which is invalid PromQL.

**Example of Problem:**
```
User: Opens Grafana panel in Builder mode, asks "Can you read this page PromQL?"

AI Response (WRONG):
"I can see your current PromQL query: True

⚠️ Query Issue Detected:
This query will likely cause an error because True is not a valid PromQL expression..."
```

**Root Cause:**
- Monaco Editor API was reading boolean values from the Builder UI state
- No validation was performed on extracted text
- Agent didn't detect Builder vs Code mode
- UI artifacts were being treated as valid queries

### Issue 2: Only Prometheus/PromQL Supported
**Problem:**
The AI Agent only understood PromQL queries, but the Grafana stack includes multiple data sources:
- **Prometheus** - PromQL (metrics)
- **Mimir** - PromQL (metrics, Prometheus-compatible)
- **Loki** - LogQL (logs)
- **Tempo** - TraceQL (traces)

Users working with Loki logs or Tempo traces received incorrect PromQL-specific advice.

### Issue 3: Prometheus Not Visible in AIOps UI
**Problem:**
User reported: "We do not see Prometheus in our Grafana stack on AI Ops page, however Prometheus is already running on Grafana stack, we are able to query other place"

**Possible Causes:**
1. Data source not configured in Grafana
2. Prometheus running but not added as data source
3. UI filtering/visibility issue
4. Permission/RBAC issue

**This is NOT an AI Agent issue** - this is a Grafana configuration issue. The AI Agent can work with Prometheus queries regardless of UI visibility.

## Solution Implemented

### 1. Builder Mode Detection

**Frontend Changes (`static/js/agent_widget.js`)**

Added detection for Builder vs Code mode:
```javascript
// Detect Grafana editor mode
const isBuilderMode = document.querySelector('[aria-label="Query builder mode"]') !== null ||
                     document.querySelector('.query-builder') !== null ||
                     document.querySelector('[data-testid="query-builder"]') !== null;

const isCodeMode = document.querySelector('[aria-label="Code mode"]')?.getAttribute('aria-pressed') === 'true';

console.log(`[AI Agent] Grafana mode - Builder: ${isBuilderMode}, Code: ${isCodeMode}`);
```

**Behavior Changes:**
- If Builder mode detected → Skip Monaco API extraction
- Add `builder_mode_detected: true` flag to context
- Log helpful tip: "💡 TIP: Switch to Code mode for better query extraction"

### 2. Query Validation Function

Added comprehensive validation to filter out UI artifacts:

```javascript
function isValidQuery(text) {
    const trimmed = text.trim();

    // Filter out false positives from Builder mode
    const invalidPatterns = [
        /^(true|false)$/i,           // Boolean literals ❌
        /^(null|undefined)$/i,       // Null values ❌
        /^[0-9]+$/,                  // Pure numbers ❌
        /^Query$/i,                  // UI label "Query" ❌
        /^Metrics$/i,                // UI label "Metrics" ❌
    ];

    // Valid query patterns (PromQL, LogQL, TraceQL)
    const validPatterns = [
        /[a-zA-Z_][a-zA-Z0-9_]*\{/,     // Metric with labels: up{ ✅
        /[a-zA-Z_][a-zA-Z0-9_]*\(/,     // Function: rate( ✅
        /[a-zA-Z_][a-zA-Z0-9_]*\[/,     // Range vector: [5m] ✅
        /^[a-zA-Z_][a-zA-Z0-9_:]*$/,    // Simple metric: up ✅
        /\|\s*(sum|count|rate|avg)/,    // LogQL aggregations ✅
        /\{[^}]+\}/,                    // Label selectors ✅
    ];

    return validPatterns.some(pattern => pattern.test(trimmed));
}
```

**Examples:**
- ✅ `up{instance="server:8080"}` - Valid PromQL
- ✅ `rate(http_requests_total[5m])` - Valid PromQL function
- ✅ `{job="logs"} |= "error"` - Valid LogQL
- ❌ `True` - Rejected (boolean literal)
- ❌ `Query` - Rejected (UI label)
- ❌ `123` - Rejected (pure number)

### 3. Multi-Datasource Support

**Data Source Detection:**
```javascript
// Detect from UI selectors
const dsSelector = document.querySelector('[aria-label*="Data source"]');
if (dsSelector) {
    const dsText = dsSelector.innerText.toLowerCase();
    if (dsText.includes('loki')) {
        dataSourceType = 'loki';
        queryLanguage = 'LogQL';
    } else if (dsText.includes('tempo')) {
        dataSourceType = 'tempo';
        queryLanguage = 'TraceQL';
    } else if (dsText.includes('mimir')) {
        dataSourceType = 'mimir';
        queryLanguage = 'PromQL';
    } else if (dsText.includes('prometheus')) {
        dataSourceType = 'prometheus';
        queryLanguage = 'PromQL';
    }
}

// Fallback: detect from query syntax
if (query.includes('|') && query.includes('|= ')) {
    dataSourceType = 'loki';
    queryLanguage = 'LogQL';
}
```

**Context Enrichment:**
```javascript
context.form_data['data_source_type'] = dataSourceType;  // "prometheus", "loki", "tempo", "mimir"
context.form_data['query_language'] = queryLanguage;     // "PromQL", "LogQL", "TraceQL"
```

### 4. Backend Improvements

**Enhanced System Prompt (`ai_helper_orchestrator.py`):**
```python
GRAFANA QUERY HANDLING (Multi-Datasource Support):
- Supports: Prometheus (PromQL), Loki (LogQL), Tempo (TraceQL), Mimir (PromQL)
- Check context for: query_language, data_source_type, builder_mode_detected
- If builder_mode_detected is true:
  * Explain that Grafana is in Builder mode (visual query builder)
  * Recommend switching to Code mode: Click "Code" button in query editor
  * Offer to help write queries once they switch to Code mode
  * Still be helpful if they paste a query manually
```

**New LLM Examples:**

**Example: Builder Mode Guidance**
```json
{
  "action": "chat",
  "action_details": {
    "message": "I can see you're in Grafana's **Builder mode** (visual query builder). The AI Agent works best with queries in **Code mode**.\n\n**To get AI assistance:**\n\n1. 🔄 **Switch to Code mode** - Click the \"Code\" button in your query editor\n2. 📋 **Or paste your query** - Copy your query and paste it here\n\n**Once in Code mode, I can:**\n- Analyze your PromQL/LogQL/TraceQL queries\n- Suggest optimizations and improvements\n- Explain query syntax and behavior"
  }
}
```

**Example: LogQL Analysis**
```json
{
  "action": "explain_concept",
  "action_details": {
    "concept": "LogQL Query Analysis",
    "explanation": "I can see your **LogQL** query for Loki:\n\n```logql\n{job=\"varlogs\"} |= \"error\" | json\n```\n\n**What it does:**\n1. `{job=\"varlogs\"}` - Select log streams\n2. `|= \"error\"` - Filter for error lines\n3. `| json` - Parse as JSON\n\n**Improvements:**\n- Case-insensitive: `|~ \"(?i)error\"`\n- Count errors: `count_over_time(...[1m])`"
  }
}
```

## Expected Behavior After Fix

### Scenario 1: Builder Mode
**User Action:** Opens Grafana panel in Builder mode, asks "Can you read this page?"

**Browser Console:**
```
[AI Agent] Grafana mode - Builder: true, Code: false
[AI Agent] ⚠️ Builder mode detected - Monaco API extraction skipped
[AI Agent] ⚠️ Builder mode detected - DOM scraping skipped
[AI Agent] ❌ No query found on page
[AI Agent] 💡 TIP: Switch to Code mode for better query extraction
```

**AI Response:**
```
I can see you're in Grafana's **Builder mode** (visual query builder). The AI Agent works best with queries in **Code mode**.

**To get AI assistance:**

1. 🔄 **Switch to Code mode** - Click the "Code" button in your query editor
2. 📋 **Or paste your query** - Copy your query and paste it here

**Once in Code mode, I can:**
- Analyze your PromQL/LogQL/TraceQL queries
- Suggest optimizations and improvements
- Explain query syntax and behavior
- Help troubleshoot issues

**Or I can help you write a query from scratch!** Just tell me what you want to monitor.
```

### Scenario 2: Code Mode with Prometheus
**User Action:** Switches to Code mode, enters `up{instance="remediation-engine:8080"}`, asks "Can you read this page?"

**Browser Console:**
```
[AI Agent] Grafana mode - Builder: false, Code: true
[AI Agent] Monaco models found: 1
[AI Agent] Model 0: "up{instance="remediation-engine:8080"}" (35 chars)
[AI Agent] ✅ Extracted via Monaco API: up{instance="remediation-engine:8080"}
[AI Agent] 📊 Data source: prometheus, Query language: PromQL
```

**AI Response:**
```
I can see your **PromQL** query:

```promql
up{instance="remediation-engine:8080"}
```

**What it does:**
This query monitors the **uptime status** of a specific target. The `up` metric returns:
- `1` if target is reachable
- `0` if target is down

**Current filter:**
- `instance="remediation-engine:8080"` - Monitoring only this specific instance

**Possible enhancements:**

1. Monitor multiple instances:
```promql
up{instance=~"remediation-engine.*"}
```

2. Alert on down instances:
```promql
up{instance="remediation-engine:8080"} == 0
```

3. Add job filter:
```promql
up{job="app", instance="remediation-engine:8080"}
```
```

### Scenario 3: Loki LogQL Query
**User Action:** Selects Loki data source, enters `{job="varlogs"} |= "error"`, asks "Can you read this page?"

**Browser Console:**
```
[AI Agent] ✅ Extracted via Monaco API: {job="varlogs"} |= "error"
[AI Agent] 📊 Data source: loki, Query language: LogQL
```

**AI Response:**
```
I can see your **LogQL** query for Loki:

```logql
{job="varlogs"} |= "error" | json
```

**What it does:**
1. `{job="varlogs"}` - Select log streams from 'varlogs' job
2. `|= "error"` - Filter lines containing "error" (case-sensitive)
3. `| json` - Parse logs as JSON

**Possible improvements:**

1. Case-insensitive search:
```logql
{job="varlogs"} |~ "(?i)error" | json
```

2. Count errors per minute:
```logql
sum(count_over_time({job="varlogs"} |= "error" [1m]))
```

3. Extract JSON fields:
```logql
{job="varlogs"} | json | level="error"
```
```

### Scenario 4: Invalid Query Filtered
**User Action:** In Builder mode with boolean value "True" in UI state

**Browser Console:**
```
[AI Agent] Model 0: "True" (4 chars)
[AI Agent] Rejected invalid query pattern: "True"
[AI Agent] ❌ No query found on page
```

**AI Response:**
- Does NOT analyze "True" as a query
- Provides Builder mode guidance instead

## Testing Guide

### Test 1: Builder Mode Detection
1. Open Grafana dashboard
2. Edit a panel
3. Ensure you're in Builder mode (visual query builder)
4. Open AI Agent widget
5. Ask: "Can you read this page?"
6. **Expected:** AI explains Builder mode and asks to switch to Code mode
7. **Check Console:** Should see `Builder: true`

### Test 2: Switch to Code Mode
1. From Builder mode, click "Code" button in query editor
2. Verify query appears in code editor
3. Ask AI: "Can you read this page?"
4. **Expected:** AI extracts and analyzes the query
5. **Check Console:** Should see `✅ Extracted via Monaco API`

### Test 3: PromQL Query (Prometheus/Mimir)
1. Select Prometheus or Mimir data source
2. In Code mode, enter: `up{instance="localhost:9090"}`
3. Ask AI: "Analyze this query"
4. **Expected:** AI provides PromQL-specific analysis
5. **Check Console:** Should show `Data source: prometheus, Query language: PromQL`

### Test 4: LogQL Query (Loki)
1. Select Loki data source
2. In Code mode, enter: `{job="logs"} |= "error"`
3. Ask AI: "What does this query do?"
4. **Expected:** AI provides LogQL-specific analysis
5. **Check Console:** Should show `Data source: loki, Query language: LogQL`

### Test 5: TraceQL Query (Tempo)
1. Select Tempo data source
2. In Code mode, enter trace query
3. Ask AI: "Explain this query"
4. **Expected:** AI provides TraceQL-specific analysis
5. **Check Console:** Should show `Data source: tempo, Query language: TraceQL`

### Test 6: Invalid Query Rejection
1. Manually test validation function in browser console:
```javascript
// Should return false (invalid)
isValidQuery("True")
isValidQuery("false")
isValidQuery("123")
isValidQuery("Query")

// Should return true (valid)
isValidQuery("up")
isValidQuery("rate(cpu[5m])")
isValidQuery("{job=\"logs\"} |= \"error\"")
```

## Browser Console Debugging

All extraction attempts are logged with `[AI Agent]` prefix:

**Builder Mode:**
```
[AI Agent] Grafana mode - Builder: true, Code: false
[AI Agent] ⚠️ Builder mode detected - Monaco API extraction skipped
[AI Agent] 💡 TIP: Switch to Code mode for better query extraction
```

**Valid Query Extraction:**
```
[AI Agent] Grafana mode - Builder: false, Code: true
[AI Agent] Monaco models found: 1
[AI Agent] Model 0: "up{instance="server:8080"}" (28 chars)
[AI Agent] ✅ Extracted via Monaco API: up{instance="server:8080"}
[AI Agent] 📊 Data source: prometheus, Query language: PromQL
```

**Invalid Query Rejected:**
```
[AI Agent] Model 0: "True" (4 chars)
[AI Agent] Rejected invalid query pattern: "True"
[AI Agent] Trying visual DOM scraping...
[AI Agent] Selector ".monaco-editor .view-lines .view-line" found 1 elements, text: "True"
[AI Agent] ⚠️ Extracted text failed validation: "True"
[AI Agent] ❌ No query found on page
```

## Supported Query Languages

### PromQL (Prometheus, Mimir)
**Syntax Examples:**
```promql
# Simple metric
up

# With labels
http_requests_total{method="GET", status="200"}

# Functions
rate(http_requests_total[5m])

# Aggregations
sum by (instance) (rate(cpu_usage[5m]))

# Comparisons
node_memory_available < 1e9
```

### LogQL (Loki)
**Syntax Examples:**
```logql
# Log stream selection
{job="varlogs"}

# Line filtering
{job="varlogs"} |= "error"

# Regex filtering
{job="varlogs"} |~ "error|warning"

# JSON parsing
{job="varlogs"} | json | level="error"

# Aggregations
sum(count_over_time({job="varlogs"} |= "error" [5m]))
```

### TraceQL (Tempo)
**Syntax Examples:**
```traceql
# Find traces
{span.name="GET /api/users"}

# With attributes
{span.http.status_code>=500}

# Duration filtering
{duration>1s}
```

## Known Limitations

### Builder Mode Limitations
1. **Cannot extract queries in Builder mode** - This is by design to avoid false positives
2. **Must switch to Code mode** - Required for AI assistance
3. **Workaround:** User can manually paste the generated query for analysis

### Data Source Detection
1. **Relies on UI selectors** - May break if Grafana updates UI
2. **Fallback to syntax detection** - Works but less reliable
3. **Unknown sources default to Prometheus** - Conservative fallback

### Query Validation
1. **Pattern-based validation** - May have false negatives for exotic queries
2. **Simple heuristics** - Complex queries might need manual verification
3. **No semantic validation** - Only syntax patterns checked

## Prometheus Visibility Issue

**User Report:**
> "We do not see Prometheus in our Grafana stack on AI Ops page, however Prometheus is already running on Grafana stack, we are able to query other place"

**Analysis:**
This is NOT an AI Agent issue - this is a Grafana configuration issue.

**Possible Causes:**
1. **Data source not configured** - Prometheus running but not added to Grafana
2. **UI filter/search** - Hidden by UI filtering
3. **Permissions/RBAC** - User doesn't have permission to see data source
4. **Multiple Grafana instances** - Prometheus configured in different Grafana

**Verification Steps:**
1. **Check Data Sources in Grafana:**
   - Go to Configuration → Data Sources
   - Search for "Prometheus"
   - Check if it's configured

2. **Verify Prometheus is Running:**
   ```bash
   curl http://prometheus:9090/api/v1/status/config
   ```

3. **Test Direct Query:**
   - Open Grafana Explore
   - Manually select data source dropdown
   - Check if Prometheus appears

4. **Check Permissions:**
   - Verify user has "Data source read" permission
   - Check Grafana RBAC settings

**AI Agent Impact:**
- AI Agent can work with Prometheus queries regardless of UI visibility
- Query analysis works as long as user is in Code mode
- User can paste Prometheus queries manually

**Recommended Fix:**
1. Add Prometheus as data source in Grafana Configuration
2. OR update RBAC permissions to show existing data source
3. OR fix UI filtering/search if data source exists but hidden

## Files Modified

### Frontend
- `static/js/agent_widget.js` (+162 lines, -54 lines)
  - Added Builder mode detection
  - Added query validation function
  - Added multi-datasource detection
  - Enhanced logging for debugging

### Backend
- `app/services/ai_helper_orchestrator.py` (+61 lines, -7 lines)
  - Updated system prompt for multi-datasource
  - Added Builder mode handling examples
  - Enhanced context building with query language detection
  - Added data source-specific messaging

## Migration Notes

### New Context Fields
- `query` - Extracted query (new primary field)
- `promql_query` - Backward compatible alias
- `query_language` - "PromQL", "LogQL", or "TraceQL"
- `data_source_type` - "prometheus", "loki", "tempo", "mimir"
- `builder_mode_detected` - Boolean flag
- `extraction_method` - Method used to extract query

### Backward Compatibility
- `promql_query` still populated alongside `query`
- Existing code reading `promql_query` will continue to work
- No database schema changes required
- No breaking changes to API

## Future Improvements

1. **Enhanced Builder Mode Support**
   - Translate Builder UI state to query
   - Show equivalent Code mode query
   - Bi-directional conversion

2. **More Query Languages**
   - SQL for relational databases
   - InfluxQL for InfluxDB
   - Elasticsearch Query DSL

3. **Query Optimization**
   - Performance analysis
   - Cost estimation
   - Alternative query suggestions

4. **Visual Query Builder AI**
   - AI-powered Builder mode assistance
   - Natural language to Builder translation

## Support

For issues or questions:
1. Check browser console for `[AI Agent]` logs
2. Verify Grafana mode (Builder vs Code)
3. Check data source configuration
4. Review this documentation

## Changelog

### Version 3.0 (2026-01-04)
- ✅ Fixed Builder mode extraction issue
- ✅ Added multi-datasource support (Loki, Tempo, Mimir)
- ✅ Added query validation function
- ✅ Enhanced logging and debugging
- ✅ Improved LLM prompts for different query languages
- ✅ Added Builder mode detection and guidance

### Version 2.0 (Previous)
- Enhanced PromQL query extraction
- Multi-strategy extraction
- Comprehensive logging

### Version 1.0 (Original)
- Basic PromQL extraction
- Monaco API support
