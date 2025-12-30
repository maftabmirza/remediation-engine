# Implementation Roadmap: Grafana-Level Dashboard Builder
## Achieving 80% Parity with Grafana

**Target**: Transform basic dashboard builder into production-grade Grafana alternative
**Timeline**: 6-8 weeks
**Outcome**: Users have full control to design custom dashboards

---

## Phase 1: Critical Foundation (Weeks 1-3)

### 1.1 Drag-and-Drop Dashboard Layout ⭐ PRIORITY 1
**Effort**: 3-4 days
**Impact**: CRITICAL - Core user expectation
**Status**: NOT IMPLEMENTED

**What to Build**:
- Integrate GridStack.js library
- Make panels draggable and resizable
- Save layout changes to database
- Support custom grid positions (x, y, width, height)

**Technical Implementation**:

```html
<!-- Add to dashboard_view.html -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/gridstack@8.4.0/dist/gridstack.min.css" />
<script src="https://cdn.jsdelivr.net/npm/gridstack@8.4.0/dist/gridstack-all.js"></script>

<div class="grid-stack">
    <!-- Panels will be grid-stack-item -->
</div>

<script>
// Initialize GridStack
const grid = GridStack.init({
    cellHeight: 70,
    margin: 10,
    resizable: {
        handles: 'e, se, s, sw, w'
    },
    draggable: {
        handle: '.panel-drag-handle'
    }
});

// On drag/resize end, save to database
grid.on('change', function(event, items) {
    items.forEach(item => {
        updatePanelPosition(item.id, {
            grid_x: item.x,
            grid_y: item.y,
            grid_width: item.w,
            grid_height: item.h
        });
    });
});
</script>
```

**API Updates**:
```python
# app/routers/dashboards_api.py - Already exists, just use it
PUT /api/dashboards/{dashboard_id}/panels/{panel_id}/position
{
    "grid_x": 0,
    "grid_y": 0,
    "grid_width": 6,
    "grid_height": 4
}
```

**Files to Modify**:
- `templates/dashboard_view.html` - Add GridStack integration
- `app/routers/dashboards_api.py` - ✅ Already has position endpoint

**Testing**:
- [ ] Drag panel - saves position
- [ ] Resize panel - saves size
- [ ] Multiple panels don't overlap
- [ ] Layout persists on reload

---

### 1.2 PromQL Syntax Highlighting ⭐ PRIORITY 2
**Effort**: 2-3 days
**Impact**: HIGH - Makes query writing professional
**Status**: NOT IMPLEMENTED

**What to Build**:
- Replace plain textarea with CodeMirror editor
- Add PromQL syntax highlighting
- Add line numbers and auto-indent
- Keyboard shortcuts (Ctrl+Enter to test)

**Technical Implementation**:

```html
<!-- Add to templates/panels.html -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/theme/monokai.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/promql/promql.min.js"></script>

<script>
// Initialize CodeMirror
const queryEditor = CodeMirror.fromTextArea(document.getElementById('query-editor'), {
    mode: 'promql',
    theme: 'monokai',
    lineNumbers: true,
    lineWrapping: true,
    indentUnit: 2,
    tabSize: 2,
    extraKeys: {
        "Ctrl-Enter": testQuery,
        "Cmd-Enter": testQuery
    }
});

// Get value
const query = queryEditor.getValue();

// Set value
queryEditor.setValue('rate(http_requests_total[5m])');
</script>
```

**Files to Modify**:
- `templates/panels.html` - Replace textarea with CodeMirror
- `static/css/custom.css` - Add CodeMirror styling

**Testing**:
- [ ] Syntax highlighting works
- [ ] Line numbers display
- [ ] Ctrl+Enter tests query
- [ ] Copy/paste works

---

### 1.3 Advanced Chart Configuration ⭐ PRIORITY 3
**Effort**: 4-5 days
**Impact**: HIGH - Makes charts look professional
**Status**: PARTIAL (basic ECharts only)

**What to Build**:
- UI for axis configuration (min, max, labels)
- Unit formatting (bytes, seconds, percent)
- Color schemes and gradients
- Threshold lines and colored regions
- Legend customization

**Technical Implementation**:

```python
# Add to app/models_dashboards.py - visualization_config structure
visualization_config = {
    "axis": {
        "y_min": 0,
        "y_max": 100,
        "y_label": "CPU %",
        "x_label": "Time"
    },
    "units": "percent",  # bytes, seconds, milliseconds, percent, custom
    "decimals": 2,
    "colors": ["#5470c6", "#91cc75", "#fac858"],
    "thresholds": [
        {"value": 75, "color": "#fac858", "label": "Warning"},
        {"value": 90, "color": "#ee6666", "label": "Critical"}
    ],
    "legend": {
        "show": true,
        "position": "bottom"  # top, bottom, left, right
    },
    "gradient": true
}
```

```javascript
// Update renderChart() in dashboard_view.html
function renderChart(panel, data) {
    const config = panel.visualization_config || {};

    const option = {
        xAxis: {
            type: 'time',
            name: config.axis?.x_label,
            min: config.axis?.x_min,
            max: config.axis?.x_max
        },
        yAxis: {
            type: 'value',
            name: config.axis?.y_label,
            min: config.axis?.y_min,
            max: config.axis?.y_max,
            axisLabel: {
                formatter: function(value) {
                    return formatUnit(value, config.units, config.decimals);
                }
            }
        },
        series: [{
            data: data,
            type: 'line',
            smooth: true,
            areaStyle: config.gradient ? {} : null,
            color: config.colors?.[0],
            markLine: {
                data: config.thresholds?.map(t => ({
                    yAxis: t.value,
                    label: { formatter: t.label },
                    lineStyle: { color: t.color }
                }))
            }
        }],
        legend: config.legend
    };

    chart.setOption(option);
}

function formatUnit(value, unit, decimals = 2) {
    const formatted = value.toFixed(decimals);
    switch(unit) {
        case 'bytes':
            return formatBytes(value);
        case 'percent':
            return formatted + '%';
        case 'seconds':
            return formatted + 's';
        case 'milliseconds':
            return formatted + 'ms';
        default:
            return formatted;
    }
}

function formatBytes(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return bytes.toFixed(2) + ' ' + units[i];
}
```

**UI Components to Add** (in panel creation modal):
```html
<!-- Add to templates/panels.html modal -->
<div class="space-y-4">
    <h3>Chart Configuration</h3>

    <!-- Axis Settings -->
    <div class="grid grid-cols-2 gap-4">
        <input type="text" placeholder="Y-Axis Label" id="y-axis-label">
        <select id="unit-format">
            <option value="">Auto</option>
            <option value="percent">Percent (%)</option>
            <option value="bytes">Bytes</option>
            <option value="seconds">Seconds</option>
            <option value="milliseconds">Milliseconds</option>
        </select>
    </div>

    <!-- Color Scheme -->
    <select id="color-scheme">
        <option>Default Blue</option>
        <option>Green Success</option>
        <option>Red Alert</option>
        <option>Rainbow</option>
    </select>

    <!-- Thresholds -->
    <div id="thresholds-config">
        <button onclick="addThreshold()">+ Add Threshold</button>
        <!-- Dynamic threshold rows -->
    </div>
</div>
```

**Files to Modify**:
- `templates/panels.html` - Add chart config UI
- `templates/dashboard_view.html` - Use visualization_config
- `app/models_dashboards.py` - ✅ Already has visualization_config field

**Testing**:
- [ ] Y-axis shows custom label
- [ ] Units format correctly (KB, MB, GB)
- [ ] Threshold lines appear on chart
- [ ] Colors apply correctly
- [ ] Legend shows/hides

---

### 1.4 Panel Edit in Dashboard ⭐ PRIORITY 4
**Effort**: 3-4 days
**Impact**: HIGH - Improves workflow significantly
**Status**: NOT IMPLEMENTED

**What to Build**:
- Edit mode toggle button
- Inline panel editing (click to edit)
- Quick actions menu (edit, duplicate, delete)
- Live preview of changes

**Technical Implementation**:

```html
<!-- Add to dashboard_view.html header -->
<button id="edit-mode-toggle" onclick="toggleEditMode()">
    <i class="fas fa-edit"></i>
    <span id="edit-mode-text">Edit Mode</span>
</button>

<!-- Add to each panel -->
<div class="panel-card" data-panel-id="${panel.id}">
    <!-- Edit overlay (only visible in edit mode) -->
    <div class="panel-edit-overlay hidden">
        <button onclick="editPanel('${panel.id}')" title="Edit Query">
            <i class="fas fa-pencil-alt"></i>
        </button>
        <button onclick="duplicatePanel('${panel.id}')" title="Duplicate">
            <i class="fas fa-copy"></i>
        </button>
        <button onclick="inspectPanel('${panel.id}')" title="Inspect">
            <i class="fas fa-search"></i>
        </button>
        <button onclick="removePanel('${panel.id}')" title="Remove">
            <i class="fas fa-trash"></i>
        </button>
    </div>

    <!-- Chart canvas -->
    <div id="chart-${panel.id}"></div>
</div>

<script>
let editMode = false;

function toggleEditMode() {
    editMode = !editMode;
    document.getElementById('edit-mode-text').textContent = editMode ? 'View Mode' : 'Edit Mode';

    // Show/hide edit overlays
    document.querySelectorAll('.panel-edit-overlay').forEach(overlay => {
        overlay.classList.toggle('hidden', !editMode);
    });

    // Enable/disable GridStack dragging
    if (typeof grid !== 'undefined') {
        grid.enableMove(editMode);
        grid.enableResize(editMode);
    }
}

function editPanel(panelId) {
    // Open modal with panel data
    fetch(`/api/panels/${panelId}`)
        .then(r => r.json())
        .then(panel => {
            // Populate edit modal
            showPanelEditModal(panel);
        });
}

function inspectPanel(panelId) {
    // Show panel inspector modal
    showPanelInspector(panelId);
}
</script>
```

**Files to Modify**:
- `templates/dashboard_view.html` - Add edit mode UI
- Add panel edit modal to dashboard_view.html

**Testing**:
- [ ] Toggle edit mode
- [ ] Edit button opens modal
- [ ] Changes save and refresh chart
- [ ] Duplicate creates copy
- [ ] Remove deletes panel

---

## Phase 2: High-Value Features (Weeks 4-6)

### 2.1 Dashboard Variables 🎯 GAME CHANGER
**Effort**: 5-7 days
**Impact**: VERY HIGH - Enables dynamic dashboards
**Status**: NOT IMPLEMENTED

**What to Build**:
- Variable definitions (query, custom, interval)
- Variable dropdowns in dashboard header
- Template variable substitution in queries
- Multi-select support

**Example**:
```
Variable: instance
Type: Query
Query: label_values(up, instance)

Then in panel query:
rate(http_requests_total{instance="$instance"}[5m])
```

**Database Schema**:
```python
# Add new table
class DashboardVariable(Base):
    __tablename__ = "dashboard_variables"

    id = Column(String(36), primary_key=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"))
    name = Column(String(100), nullable=False)  # $instance
    label = Column(String(255))  # Display label
    type = Column(String(50))  # query, custom, interval, textbox
    query = Column(Text)  # For query type
    options = Column(JSON)  # For custom type
    default_value = Column(String(255))
    multi = Column(Boolean, default=False)
    include_all = Column(Boolean, default=False)
```

**Implementation Steps**:
1. Create migration for dashboard_variables table
2. Add CRUD API for variables
3. Add UI for variable management
4. Implement variable substitution in queries
5. Add variable dropdowns to dashboard header

**Files to Create/Modify**:
- `alembic/versions/024_add_dashboard_variables.py` - NEW
- `app/models_dashboards.py` - Add DashboardVariable model
- `app/routers/dashboard_variables_api.py` - NEW
- `templates/dashboard_view.html` - Add variable dropdowns

---

### 2.2 Custom Time Range Picker 📅
**Effort**: 2-3 days
**Impact**: HIGH - Better time exploration
**Status**: PARTIAL (preset only)

**What to Build**:
- Calendar date picker
- Custom "From" and "To" inputs
- Quick ranges (last 5m, 1h, etc.)
- Zoom functionality on charts

**Library to Use**: flatpickr

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>

<div class="time-range-picker">
    <button id="quick-ranges">Last 1h ▼</button>
    <input type="text" id="custom-range" placeholder="Select custom range">
</div>

<script>
flatpickr("#custom-range", {
    mode: "range",
    enableTime: true,
    dateFormat: "Y-m-d H:i",
    onChange: function(selectedDates) {
        if (selectedDates.length === 2) {
            refreshAllPanels(selectedDates[0], selectedDates[1]);
        }
    }
});
</script>
```

---

### 2.3 Panel Inspector 🔍
**Effort**: 2 days
**Impact**: HIGH - Essential for debugging
**Status**: NOT IMPLEMENTED

**What to Build**:
- View actual PromQL query
- See raw JSON response
- Query statistics (execution time, series count)
- Data table view

```html
<!-- Inspector Modal -->
<div id="inspector-modal">
    <div class="tabs">
        <button class="active">Query</button>
        <button>Data</button>
        <button>JSON</button>
        <button>Stats</button>
    </div>

    <div class="tab-content">
        <!-- Query Tab -->
        <pre id="inspector-query"></pre>

        <!-- Data Tab -->
        <table id="inspector-data"></table>

        <!-- JSON Tab -->
        <pre id="inspector-json"></pre>

        <!-- Stats Tab -->
        <div id="inspector-stats">
            <p>Series: <span id="series-count"></span></p>
            <p>Duration: <span id="query-duration"></span>ms</p>
            <p>Data points: <span id="data-points"></span></p>
        </div>
    </div>
</div>
```

---

### 2.4 Query Autocomplete 💡
**Effort**: 3-4 days
**Impact**: MEDIUM-HIGH - Makes query writing easier
**Status**: NOT IMPLEMENTED

**What to Build**:
- Fetch metrics from Prometheus
- Autocomplete metric names
- Suggest label names
- Suggest label values

**API Endpoint**:
```python
@router.get("/api/datasources/{datasource_id}/metrics")
async def get_metrics(datasource_id: str):
    """Get list of all metrics from Prometheus"""
    # Query: {__name__=~".+"}
    pass

@router.get("/api/datasources/{datasource_id}/labels")
async def get_label_names(datasource_id: str, metric: str):
    """Get label names for a metric"""
    pass

@router.get("/api/datasources/{datasource_id}/label-values")
async def get_label_values(datasource_id: str, label: str):
    """Get possible values for a label"""
    pass
```

**Integration with CodeMirror**:
```javascript
queryEditor.on("inputRead", function(cm, change) {
    if (change.text[0].match(/[a-z]/i)) {
        CodeMirror.commands.autocomplete(cm);
    }
});

CodeMirror.registerHelper("hint", "promql", function(cm) {
    const cursor = cm.getCursor();
    const token = cm.getTokenAt(cursor);

    // Fetch suggestions from API
    return fetchAutocompleteSuggestions(token.string);
});
```

---

## Phase 3: Polish & Enhancement (Weeks 7-8)

### 3.1 Alert Annotations
- Fetch alerts from Prometheus
- Overlay on charts as vertical lines
- Show alert details on hover

### 3.2 Dashboard Import/Export
- Export dashboard as JSON
- Import dashboard from JSON
- Share between instances

### 3.3 Additional Panel Types
- Heatmap
- Bar chart
- Histogram

### 3.4 Query Caching
- Redis integration
- Cache query results
- Configurable TTL

---

## Testing Strategy

### Unit Tests
```python
# tests/test_dashboard_layout.py
def test_update_panel_position():
    response = client.put(f"/api/dashboards/{dash_id}/panels/{panel_id}/position", json={
        "grid_x": 6,
        "grid_y": 0,
        "grid_width": 6,
        "grid_height": 4
    })
    assert response.status_code == 200

# tests/test_variables.py
def test_variable_substitution():
    variable = create_variable(name="instance", query="label_values(up, instance)")
    query = "rate(http_requests_total{instance=\"$instance\"}[5m])"
    result = substitute_variables(query, {"instance": "server1"})
    assert result == 'rate(http_requests_total{instance="server1"}[5m])'
```

### Integration Tests
```python
# tests/test_dashboard_workflow.py
def test_full_dashboard_workflow():
    # Create dashboard
    dash = create_dashboard("Test Dashboard")

    # Add variable
    var = add_variable(dash.id, name="instance", type="query")

    # Create panel with variable
    panel = create_panel(promql_query='up{instance="$instance"}')

    # Add to dashboard
    add_panel_to_dashboard(dash.id, panel.id)

    # Test rendering
    response = client.get(f"/dashboard-view/{dash.id}")
    assert response.status_code == 200
```

### UI Tests (Manual Checklist)
- [ ] Drag panel - saves position
- [ ] Resize panel - saves size
- [ ] Edit panel - updates chart
- [ ] Variable dropdown - filters all panels
- [ ] Time picker - updates all panels
- [ ] Inspector - shows correct data
- [ ] Syntax highlighting - works in editor
- [ ] Autocomplete - suggests metrics

---

## Deployment Checklist

Before deploying to production:

- [ ] Run database migrations
- [ ] Test with real Prometheus data
- [ ] Load test with 50+ panels
- [ ] Check browser compatibility (Chrome, Firefox, Safari)
- [ ] Verify mobile responsiveness
- [ ] Test with slow network
- [ ] Verify all APIs have authentication
- [ ] Check for SQL injection vulnerabilities
- [ ] Ensure XSS protection
- [ ] Test with multiple concurrent users

---

## Expected Outcomes

After full implementation:

✅ **Users can**:
- Drag and drop panels anywhere
- Resize panels to any size
- Edit panels directly from dashboard
- Use variables to create dynamic dashboards
- Pick custom time ranges with calendar
- Inspect panel data and queries
- Write PromQL with autocomplete
- Configure chart axes, units, colors
- Add threshold lines and colored regions

✅ **Dashboards will**:
- Look professional like Grafana
- Be fully customizable
- Update dynamically with variables
- Persist layout changes
- Support complex queries

✅ **Feature Parity**: 80% vs Grafana

---

## Quick Start After Implementation

```bash
# 1. Run migrations
alembic upgrade head

# 2. Restart application
docker-compose restart web

# 3. Test features
# - Create dashboard
# - Add panels
# - Toggle edit mode
# - Drag panels around
# - Add variables
# - Test time picker
# - Inspect panels
```

---

## Maintenance & Future

**Weekly**:
- Monitor query performance
- Check error logs
- Review user feedback

**Monthly**:
- Update GridStack.js
- Update CodeMirror
- Update ECharts

**Quarterly**:
- Add new panel types
- Implement user requests
- Optimize performance

---

## Resources

- GridStack.js Docs: https://gridstackjs.com/
- CodeMirror Docs: https://codemirror.net/
- ECharts Docs: https://echarts.apache.org/
- Prometheus API: https://prometheus.io/docs/prometheus/latest/querying/api/
- Grafana for inspiration: https://grafana.com/

---

**Document Version**: 1.0
**Created**: December 2025
**Target Completion**: 6-8 weeks from start
**Status**: Ready for implementation
