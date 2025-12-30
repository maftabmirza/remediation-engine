# Quick Start: Implement Drag-and-Drop in 1 Day

This guide will help you add drag-and-drop dashboard layout in less than 1 day.

## Step 1: Update dashboard_view.html (30 minutes)

Replace the current panels grid section with GridStack:

```html
{% extends "layout.html" %}
{% set active_page = 'dashboards' %}

{% block title %}Dashboard View{% endblock %}

{% block head %}
<!-- Add GridStack CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/gridstack@8.4.0/dist/gridstack.min.css" />
<style>
    .grid-stack-item-content {
        background: rgb(31, 41, 55);
        border: 1px solid rgb(55, 65, 81);
        border-radius: 0.5rem;
        padding: 1rem;
    }

    .panel-drag-handle {
        cursor: move;
        padding: 0.5rem;
        background: rgb(55, 65, 81);
        border-radius: 0.25rem;
        margin-bottom: 0.5rem;
    }

    .panel-drag-handle:hover {
        background: rgb(75, 85, 99);
    }

    .grid-stack-item.editing .panel-drag-handle {
        display: block;
    }

    .grid-stack-item:not(.editing) .panel-drag-handle {
        display: none;
    }

    .edit-mode-active .grid-stack {
        border: 2px dashed #3b82f6;
    }
</style>
{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
        <div class="flex items-center gap-4">
            <a href="/dashboards" class="text-gray-400 hover:text-white">
                <i class="fas fa-arrow-left"></i>
            </a>
            <div>
                <h1 id="dashboard-title" class="text-2xl font-bold">Loading...</h1>
                <p id="dashboard-description" class="text-gray-400 text-sm"></p>
            </div>
        </div>

        <div class="flex items-center gap-3">
            <!-- Edit Mode Toggle -->
            <button id="edit-mode-btn" onclick="toggleEditMode()"
                    class="px-4 py-2 rounded-lg border border-gray-600 hover:bg-gray-700">
                <i class="fas fa-edit mr-2"></i>
                <span id="edit-mode-text">Edit</span>
            </button>

            <!-- Time Range -->
            <select id="time-range" class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2">
                <option value="15m">Last 15m</option>
                <option value="1h">Last 1h</option>
                <option value="6h">Last 6h</option>
                <option value="24h" selected>Last 24h</option>
                <option value="7d">Last 7d</option>
                <option value="30d">Last 30d</option>
            </select>

            <!-- Refresh -->
            <button id="refresh-btn" onclick="refreshAllPanels()"
                    class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700">
                <i class="fas fa-sync-alt"></i>
            </button>
        </div>
    </div>

    <!-- GridStack Container -->
    <div id="panels-container" class="hidden">
        <div class="grid-stack"></div>
    </div>

    <!-- Loading State -->
    <div id="loading-state" class="text-center py-20">
        <i class="fas fa-spinner fa-spin text-4xl text-blue-400"></i>
    </div>
</div>

<!-- GridStack JS -->
<script src="https://cdn.jsdelivr.net/npm/gridstack@8.4.0/dist/gridstack-all.js"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>

<script>
const dashboardId = '{{ dashboard_id }}';
let dashboard = null;
let panels = [];
let grid = null;
let charts = {};
let editMode = false;

// Initialize on load
document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboard();
    initializeGrid();
    renderPanels();
});

function initializeGrid() {
    grid = GridStack.init({
        cellHeight: 80,
        margin: 10,
        resizable: {
            handles: 'e, se, s, sw, w'
        },
        draggable: {
            handle: '.panel-drag-handle'
        },
        disableDrag: true,  // Disabled by default
        disableResize: true  // Disabled by default
    });

    // Save layout on change
    grid.on('change', (event, items) => {
        if (!editMode) return;  // Only save in edit mode

        items.forEach(item => {
            savePanel Position(item.id, {
                grid_x: item.x,
                grid_y: item.y,
                grid_width: item.w,
                grid_height: item.h
            });
        });
    });
}

async function loadDashboard() {
    try {
        const response = await apiCall(`/api/dashboards/${dashboardId}`);
        dashboard = await response.json();

        document.getElementById('dashboard-title').textContent = dashboard.name;
        document.getElementById('dashboard-description').textContent = dashboard.description || '';

        panels = dashboard.panels || [];

        document.getElementById('loading-state').classList.add('hidden');
        document.getElementById('panels-container').classList.remove('hidden');
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        showToast('Failed to load dashboard', 'error');
    }
}

function renderPanels() {
    if (!grid) return;

    panels.forEach(panel => {
        // Create panel HTML
        const panelHtml = `
            <div class="grid-stack-item-content">
                <div class="panel-drag-handle">
                    <i class="fas fa-grip-vertical mr-2"></i>
                    <span class="font-medium">${escapeHtml(panel.panel_name)}</span>
                </div>
                <div id="chart-${panel.panel_id}" style="width: 100%; height: calc(100% - 50px);"></div>
            </div>
        `;

        // Add to grid
        grid.addWidget({
            x: panel.grid_x,
            y: panel.grid_y,
            w: panel.grid_width,
            h: panel.grid_height,
            content: panelHtml,
            id: panel.panel_id
        });

        // Load panel data and render chart
        loadPanelData(panel.panel_id);
    });
}

function toggleEditMode() {
    editMode = !editMode;

    const btn = document.getElementById('edit-mode-btn');
    const text = document.getElementById('edit-mode-text');
    const container = document.getElementById('panels-container');

    if (editMode) {
        // Enable editing
        grid.enable();
        text.textContent = 'Save';
        btn.classList.add('bg-blue-600', 'text-white');
        container.classList.add('edit-mode-active');
        document.querySelectorAll('.grid-stack-item').forEach(item => {
            item.classList.add('editing');
        });
    } else {
        // Disable editing
        grid.disable();
        text.textContent = 'Edit';
        btn.classList.remove('bg-blue-600', 'text-white');
        container.classList.remove('edit-mode-active');
        document.querySelectorAll('.grid-stack-item').forEach(item => {
            item.classList.remove('editing');
        });
        showToast('Layout saved', 'success');
    }
}

async function savePanelPosition(panelId, position) {
    try {
        await apiCall(`/api/dashboards/${dashboardId}/panels/${panelId}/position`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(position)
        });
    } catch (error) {
        console.error('Failed to save panel position:', error);
    }
}

async function loadPanelData(panelId) {
    try {
        const timeRange = document.getElementById('time-range').value;
        const response = await apiCall(`/api/panels/${panelId}/data?time_range=${timeRange}`);
        const data = await response.json();

        renderChart(panelId, data);
    } catch (error) {
        console.error(`Failed to load panel ${panelId}:`, error);
    }
}

function renderChart(panelId, data) {
    const chartDiv = document.getElementById(`chart-${panelId}`);
    if (!chartDiv) return;

    const chart = echarts.init(chartDiv);
    charts[panelId] = chart;

    // Parse Prometheus data
    const series = data.data.map(s => ({
        name: s.metric.instance || 'value',
        type: 'line',
        smooth: true,
        data: s.values.map(v => [v[0] * 1000, parseFloat(v[1])])
    }));

    const option = {
        tooltip: {
            trigger: 'axis'
        },
        legend: {
            data: series.map(s => s.name),
            textStyle: { color: '#9ca3af' }
        },
        xAxis: {
            type: 'time',
            axisLabel: { color: '#9ca3af' }
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#9ca3af' }
        },
        series: series,
        backgroundColor: 'transparent',
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        }
    };

    chart.setOption(option);

    // Resize on window resize
    window.addEventListener('resize', () => chart.resize());
}

function refreshAllPanels() {
    panels.forEach(panel => loadPanelData(panel.panel_id));
    showToast('Refreshed all panels', 'success');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
</script>
{% endblock %}
```

## Step 2: Test It (10 minutes)

1. Restart your application
2. Go to any dashboard view
3. Click "Edit" button
4. Drag panels around
5. Resize panels
6. Click "Save"
7. Refresh page - layout should persist!

## Step 3: Add Panel Actions (20 minutes)

Add edit/duplicate/remove buttons to panels:

```javascript
// Add to panel HTML in renderPanels()
const panelHtml = `
    <div class="grid-stack-item-content">
        <div class="panel-drag-handle flex justify-between items-center">
            <div>
                <i class="fas fa-grip-vertical mr-2"></i>
                <span class="font-medium">${escapeHtml(panel.panel_name)}</span>
            </div>
            <div class="panel-actions flex gap-2">
                <button onclick="editPanel('${panel.panel_id}')" class="text-blue-400 hover:text-blue-300" title="Edit">
                    <i class="fas fa-pencil-alt"></i>
                </button>
                <button onclick="duplicatePanel('${panel.panel_id}')" class="text-green-400 hover:text-green-300" title="Duplicate">
                    <i class="fas fa-copy"></i>
                </button>
                <button onclick="removePanel('${panel.panel_id}')" class="text-red-400 hover:text-red-300" title="Remove">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
        <div id="chart-${panel.panel_id}" style="width: 100%; height: calc(100% - 50px);"></div>
    </div>
`;

// Add functions
function editPanel(panelId) {
    // Redirect to panels page with edit
    window.location.href = `/panels?edit=${panelId}`;
}

async function duplicatePanel(panelId) {
    try {
        await apiCall(`/api/panels/${panelId}/clone`, { method: 'POST' });
        showToast('Panel duplicated', 'success');
        location.reload();
    } catch (error) {
        showToast('Failed to duplicate panel', 'error');
    }
}

async function removePanel(panelId) {
    if (!confirm('Remove this panel from dashboard?')) return;

    try {
        await apiCall(`/api/dashboards/${dashboardId}/panels/${panelId}`, { method: 'DELETE' });
        grid.removeWidget(document.querySelector(`[gs-id="${panelId}"]`));
        showToast('Panel removed', 'success');
    } catch (error) {
        showToast('Failed to remove panel', 'error');
    }
}
```

## Step 4: Test Complete Workflow (15 minutes)

1. ✅ Create dashboard
2. ✅ Add 5 panels
3. ✅ View dashboard
4. ✅ Click "Edit"
5. ✅ Drag panels around
6. ✅ Resize panels
7. ✅ Click "Save"
8. ✅ Refresh page - layout persists
9. ✅ Edit a panel
10. ✅ Duplicate a panel
11. ✅ Remove a panel

## Common Issues

**Issue**: Panels don't save position
**Fix**: Check browser console for API errors, verify endpoint exists

**Issue**: Can't drag panels
**Fix**: Make sure edit mode is enabled

**Issue**: Charts don't render
**Fix**: Check that ECharts is loaded, verify panel data API returns data

**Issue**: GridStack not loading
**Fix**: Check CDN URLs are accessible, verify no console errors

## Next Steps

After drag-drop works:

1. Add CodeMirror for syntax highlighting
2. Add advanced chart configuration
3. Add dashboard variables
4. Add time range picker

## Done!

You now have drag-and-drop dashboard layout just like Grafana! 🎉

The full implementation takes 6-8 weeks, but this gives you the #1 most important feature in less than 1 day.
