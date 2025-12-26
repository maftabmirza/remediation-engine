# Plan Updates - December 26, 2025

**Supersedes sections in:** CONSOLIDATED_IMPLEMENTATION_PLAN.md

---

## Change Summary

### 1. ✅ Existing Split-Screen UI Discovered

**Location:** `http://localhost:8080/ai` (templates/ai_chat.html)

**Current Layout:**
- Left Pane (40%): Chat interface with AI
- Right Pane (60%): Terminal for command execution

**Impact on Plan:**
- ❌ **Remove:** "Create Enhanced Chat Template" from Phase 5
- ✅ **Replace with:** "Enhance Existing Template with Toggle"
- ⏱️ **Time Savings:** ~2 days (split-screen layout already built)

---

### 2. 🚫 Caching Deferred to Future

**Decision:** Remove query result caching from Phase 4 implementation
**Reason:** Focus on core functionality first, optimize later

**Changes:**

#### Phase 4, Week 3: Testing & API Endpoints (was "Caching & Performance")

**Tasks:**

1. **API Endpoints for Testing** (2 days)
   - File: `app/routers/queries_api.py`
   - Endpoints:
     ```python
     POST   /api/queries/translate           # Test translation
     POST   /api/queries/execute             # Execute query
     GET    /api/queries/history             # Query history
     ```

2. **Performance Testing** (2 days)
   - Load test query translator
   - Measure query execution times
   - Optimize slow queries

3. **Integration Testing** (1 day)
   - End-to-end query flow testing
   - Translation accuracy validation
   - Error handling verification

**Deliverables:**
- ✅ Test API endpoints available
- ✅ Performance benchmarks documented
- ✅ Integration tests passing

**Note:** ⚠️ Query result caching (Redis) deferred to future optimization phase

---

### 3. 📱 Updated Phase 5: UI Enhancement with Toggle

**Goal:** Extend existing `/ai` page to show data output alongside terminal

#### Week 1: AI Context Builder & Backend Integration (unchanged)

**Tasks:**
1. Create `AIContextBuilder` service
2. Integrate with `chat_service.py`
3. Return structured data for visualization

#### Week 2: UI Enhancement with Toggle (UPDATED)

**Tasks:**

1. **Enhance Existing AI Chat Template** (3 days)
   - File: `templates/ai_chat.html` ✅ (modify existing, don't create new)
   - Add toggle button to right pane header:
     ```html
     <div class="pane-toggle">
       <button id="terminalModeBtn" class="active" onclick="showTerminal()">
         <i class="fas fa-terminal"></i> Terminal
       </button>
       <button id="dataOutputModeBtn" onclick="showDataOutput()">
         <i class="fas fa-chart-line"></i> Data Output
       </button>
     </div>
     ```

   - Add data output pane (hidden by default):
     ```html
     <!-- Existing Terminal Pane -->
     <div id="terminalPane" class="pane-content">
       <!-- SSH terminal (existing functionality) -->
     </div>

     <!-- NEW: Data Output Pane -->
     <div id="dataOutputPane" class="pane-content hidden">
       <!-- Metrics/logs visualization -->
       <div id="metricsSummary"></div>
       <div id="chartsArea"></div>
       <div id="dataTable"></div>
       <div id="queryPreview"></div>
     </div>
     ```

   - Toggle logic:
     ```javascript
     function showTerminal() {
       document.getElementById('terminalPane').classList.remove('hidden');
       document.getElementById('dataOutputPane').classList.add('hidden');
       // Update button states
     }

     function showDataOutput() {
       document.getElementById('terminalPane').classList.add('hidden');
       document.getElementById('dataOutputPane').classList.remove('hidden');
       // Update button states
     }

     // Auto-switch when query results arrive
     function displayQueryResults(data) {
       populateDataPane(data);
       showDataOutput();  // Automatic toggle
     }
     ```

2. **Data Visualization Components** (2 days)
   - Metric summary cards (SLO status, health indicators)
   - ECharts integration for time-series graphs
   - Data tables (sortable, filterable)
   - Export buttons (CSV, JSON)
   - Query preview (show PromQL/LogQL executed)

3. **Testing & Polish** (1 day)
   - Test toggle functionality
   - Verify auto-switch on data queries
   - Cross-browser testing
   - Mobile responsiveness

**Deliverables:**
- ✅ Toggle between Terminal and Data Output modes
- ✅ Data visualization in right pane
- ✅ Export functionality (CSV, JSON)
- ✅ Seamless integration with existing chat

**Key Benefit:** Reuses existing 40/60 split layout, only adds toggle and data pane

---

## Updated Architecture: Split-Screen with Toggle

```
┌─────────────────────────────────────────────────────────┐
│                /ai - AI Assistant Page                   │
├──────────────────────┬──────────────────────────────────┤
│  LEFT PANE (40%)     │  RIGHT PANE (60%)                │
│  ┌────────────────┐  │  ┌────────────────────────────┐  │
│  │ Chat Interface │  │  │ [Terminal] [Data Output]   │  │
│  │                │  │  │        Toggle Buttons       │  │
│  │ User: "Was abc │  │  └────────────────────────────┘  │
│  │ app healthy    │  │                                  │
│  │ yesterday?"    │  │  ┌────────────────────────────┐  │
│  │                │  │  │ Terminal Pane (Existing)   │  │
│  │ AI: "Yes, see  │  │  │ • SSH command execution    │  │
│  │ metrics →"     │  │  │ • Server management        │  │
│  │                │  │  │ • Output display           │  │
│  │                │  │  └────────────────────────────┘  │
│  │                │  │                                  │
│  │ [Send]         │  │  ┌────────────────────────────┐  │
│  └────────────────┘  │  │ Data Output Pane (NEW)     │  │
│                      │  │ • Health metrics           │  │
│                      │  │ • Charts (ECharts)         │  │
│                      │  │ • Data tables              │  │
│                      │  │ • Export (CSV/JSON)        │  │
│                      │  │ • Query preview            │  │
│                      │  └────────────────────────────┘  │
└──────────────────────┴──────────────────────────────────┘
```

**User Experience:**

1. **Default State:** Terminal pane visible
2. **User asks data query:** "Was abc app healthy yesterday?"
3. **Backend processes:** AI + query translation + metrics fetch
4. **Auto-switch:** Right pane automatically switches to "Data Output"
5. **Display:** Metrics, charts, tables appear
6. **Manual toggle:** User can switch back to Terminal anytime

---

## Updated Timeline

| Phase | Original | Updated | Change |
|-------|----------|---------|--------|
| Phase 4 Week 3 | Caching & Performance | Testing & API Endpoints | -2 days caching |
| Phase 5 Week 2 | Create new template (3d) | Enhance existing (3d) | No change (but simpler) |
| **Total** | **8 weeks** | **~7.5 weeks** | **Faster due to reuse** |

---

## Performance Optimization (Updated)

### Immediate (Phases 3-5)

1. **Query Optimization**
   - Time range limits (max 7 days)
   - Result pagination (max 10,000 data points)
   - Parallel query execution
   - Query downsampling for long ranges

2. **Response Optimization**
   - Stream AI responses as generated
   - Progressive loading (show data as it arrives)
   - Lazy evaluation (only query when needed)

### Future (Post-Phase 5)

1. **Caching** ⚠️ **DEFERRED**
   - Redis query result cache (5-minute TTL)
   - Application profile in-memory cache
   - Translation cache for common patterns
   - Background pre-fetching

2. **Advanced Optimizations**
   - Query result compression
   - WebSocket for real-time updates
   - Query plan optimization

---

## Files to Modify (Updated)

### Phase 5 Changes

**Before (Original Plan):**
```
templates/
└── ai_chat_enhanced.html  ❌ CREATE NEW TEMPLATE
```

**After (Updated Plan):**
```
templates/
└── ai_chat.html  ✅ MODIFY EXISTING TEMPLATE
    - Add toggle buttons to right pane header
    - Add data output pane (hidden by default)
    - Add toggle JavaScript functions
    - Add ECharts integration
    - Add data table component
    - Add export functionality
```

**Impact:** No new template, just enhance existing one (~300 lines of additions)

---

## Testing Updates

### Integration Tests (Updated)

**Test: Toggle Functionality**
```python
async def test_toggle_terminal_data_output():
    # 1. Load /ai page
    response = client.get("/ai")
    assert response.status_code == 200

    # 2. Verify default state (Terminal visible)
    assert "terminalPane" in response.text
    assert "dataOutputPane hidden" in response.text

    # 3. Send data query
    response = client.post("/api/chat/sessions/123/messages", json={
        "message": "Was abc app healthy yesterday?"
    })

    # 4. Verify data payload returned
    assert "metrics_data" in response.json()

    # 5. Verify UI switches to data output
    # (Frontend test - use Playwright/Selenium)
```

**Test: Auto-Switch on Data Query**
```javascript
// Frontend test
test('auto-switches to data output on metrics query', async () => {
  // 1. Send query
  await sendMessage("Show me CPU usage");

  // 2. Wait for response
  await waitFor(() =>
    expect(screen.getByTestId('dataOutputPane')).toBeVisible()
  );

  // 3. Verify terminal is hidden
  expect(screen.getByTestId('terminalPane')).not.toBeVisible();

  // 4. Verify data is populated
  expect(screen.getByText(/CPU Usage/i)).toBeInTheDocument();
});
```

---

## Summary of Changes

### ✅ What Changed

1. **Removed from plan:**
   - Query result caching (Redis) - deferred to future
   - Creating new `ai_chat_enhanced.html` template

2. **Added to plan:**
   - Leverage existing `/ai` page and template
   - Toggle functionality between Terminal and Data Output
   - Auto-switch behavior on data queries

3. **Timeline impact:**
   - Slightly faster due to template reuse
   - Simpler implementation (less new code)

### 📋 Action Items

**For Phase 4:**
- Remove "caching implementation" from Week 3 tasks
- Focus on testing and API endpoints

**For Phase 5:**
- Update plan to enhance `ai_chat.html` (not create new template)
- Add toggle implementation as primary task
- Test auto-switch behavior

**For Documentation:**
- Update IMPLEMENTATION_STATUS.md to reflect toggle approach
- Add screenshot/mockup of toggle UI

---

## Next Steps

1. ✅ Review this update document
2. ✅ Incorporate changes into main planning docs
3. 🚧 Begin Phase 3 implementation (Loki/Tempo clients)
4. 🚧 Start Phase 4 after Phase 3 complete

---

**Document Version:** 1.0
**Date:** 2025-12-26
**Status:** Approved for implementation
