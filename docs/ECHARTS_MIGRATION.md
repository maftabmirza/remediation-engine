# Migration from Chart.js to Apache ECharts

## Overview

This document outlines the migration from Chart.js to Apache ECharts to achieve Grafana-level visualization quality within our custom AIOps UI.

## Why Apache ECharts?

### Advantages over Chart.js:

| Feature | Chart.js | Apache ECharts | Grafana |
|---------|----------|----------------|---------|
| **Interactivity** | Basic | Advanced | Advanced |
| **Performance** | Good (<1000 points) | Excellent (millions) | Excellent |
| **Visual Quality** | Good | Excellent | Excellent |
| **Built-in Features** | Basic | Rich | Very Rich |
| **Customization** | Medium | High | High |
| **Mobile Support** | Good | Excellent | Good |
| **File Size** | 150KB | 350KB (tree-shakable) | N/A |
| **Learning Curve** | Easy | Medium | N/A |

### Key ECharts Features We'll Use:

1. **DataZoom** - Interactive timeline zooming (like Grafana)
2. **ToolTip** - Rich hover tooltips with custom formatting
3. **Legend** - Interactive legend to show/hide series
4. **Grid** - Multiple chart grids in single canvas
5. **Animation** - Smooth transitions and loading states
6. **Theme** - Dark theme matching Grafana's aesthetic
7. **Responsive** - Auto-resize with container

## Migration Plan

### Phase 1: Setup (Completed)
- [x] Add Apache ECharts CDN to base template
- [x] Create ECharts configuration helper
- [x] Define dark theme matching Grafana

### Phase 2: Dashboard Charts (This PR)
- [x] Migrate Alert Trend chart
- [x] Migrate Severity Distribution chart
- [ ] Add new Infrastructure Metrics charts

### Phase 3: Advanced Visualizations (Future)
- [ ] Alert heatmaps
- [ ] Correlation matrices
- [ ] Network topology graphs
- [ ] Real-time streaming charts

## Implementation

### 1. CDN Integration

Add to `templates/base.html`:

```html
<!-- Apache ECharts -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
```

### 2. Theme Configuration

```javascript
// Grafana-inspired dark theme
const grafanaDarkTheme = {
    color: [
        '#7EB26D', '#EAB839', '#6ED0E0', '#EF843C', '#E24D42',
        '#1F78C1', '#BA43A9', '#705DA0', '#508642', '#CCA300'
    ],
    backgroundColor: 'transparent',
    textStyle: {
        color: '#D8D9DA',
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto'
    },
    title: {
        textStyle: { color: '#D8D9DA' },
        subtextStyle: { color: '#9CA3AF' }
    },
    line: {
        itemStyle: { borderWidth: 2 },
        lineStyle: { width: 2 },
        symbolSize: 6,
        symbol: 'circle',
        smooth: true
    },
    grid: {
        borderColor: '#374151',
        top: 40,
        bottom: 30,
        left: 50,
        right: 20
    },
    categoryAxis: {
        axisLine: { lineStyle: { color: '#374151' } },
        splitLine: { lineStyle: { color: '#1F2937' } },
        axisLabel: { color: '#9CA3AF' }
    },
    valueAxis: {
        axisLine: { lineStyle: { color: '#374151' } },
        splitLine: { lineStyle: { color: '#1F2937' } },
        axisLabel: { color: '#9CA3AF' }
    },
    tooltip: {
        backgroundColor: '#1F2937',
        borderColor: '#374151',
        textStyle: { color: '#D8D9DA' }
    }
};

// Register theme
echarts.registerTheme('grafana-dark', grafanaDarkTheme);
```

### 3. Chart Migration Examples

#### Before (Chart.js):

```javascript
new Chart(ctx, {
    type: 'line',
    data: {
        labels: ['Jan', 'Feb', 'Mar'],
        datasets: [{
            label: 'Alerts',
            data: [12, 19, 3],
            borderColor: '#60a5fa'
        }]
    }
});
```

#### After (ECharts):

```javascript
const chart = echarts.init(container, 'grafana-dark');
chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
        type: 'category',
        data: ['Jan', 'Feb', 'Mar']
    },
    yAxis: { type: 'value' },
    series: [{
        name: 'Alerts',
        type: 'line',
        data: [12, 19, 3],
        smooth: true,
        areaStyle: { opacity: 0.3 }
    }],
    dataZoom: [{
        type: 'inside',
        start: 0,
        end: 100
    }]
});
```

## Advanced Features

### 1. Real-Time Updates

```javascript
setInterval(() => {
    const newData = fetchLatestMetrics();
    chart.setOption({
        series: [{
            data: newData
        }]
    });
}, 5000);
```

### 2. Interactive Drill-Down

```javascript
chart.on('click', (params) => {
    const timestamp = params.name;
    const value = params.value;
    // Navigate to alert detail
    window.location.href = `/alerts?time=${timestamp}`;
});
```

### 3. Multiple Y-Axes

```javascript
{
    yAxis: [
        { type: 'value', name: 'Alerts' },
        { type: 'value', name: 'CPU %' }
    ],
    series: [
        { name: 'Alerts', data: alertData, yAxisIndex: 0 },
        { name: 'CPU', data: cpuData, yAxisIndex: 1 }
    ]
}
```

## Performance Optimization

### 1. Lazy Loading

```javascript
// Load ECharts only when needed
function loadChart(container) {
    if (!window.echarts) {
        loadScript('https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js')
            .then(() => initChart(container));
    } else {
        initChart(container);
    }
}
```

### 2. Data Sampling

```javascript
series: [{
    data: largeDataset,
    sampling: 'lttb',  // Largest-Triangle-Three-Buckets algorithm
    large: true,
    largeThreshold: 2000
}]
```

### 3. Dispose on Unmount

```javascript
// Clean up chart instances
function destroyChart(chartInstance) {
    if (chartInstance) {
        chartInstance.dispose();
    }
}
```

## Comparison: Before vs After

### Before (Chart.js):
- Basic line/bar/pie charts
- Limited customization
- Manual tooltip formatting
- No built-in zoom
- Requires separate plugins for advanced features

### After (ECharts):
- Rich interactive charts
- Grafana-level customization
- Built-in tooltips with formatting
- Native zoom and pan
- All features included

## Compatibility

| Browser | Chart.js | ECharts |
|---------|----------|---------|
| Chrome | ✓ | ✓ |
| Firefox | ✓ | ✓ |
| Safari | ✓ | ✓ |
| Edge | ✓ | ✓ |
| IE11 | ✓ | ⚠️ (requires polyfill) |

## Migration Checklist

- [x] Add ECharts CDN
- [x] Create theme configuration
- [x] Migrate Alert Trend chart
- [x] Migrate Severity Distribution
- [x] Add infrastructure metrics charts
- [ ] Update alert detail page charts
- [ ] Add network topology visualization
- [ ] Create heatmap for alert patterns
- [ ] Implement real-time streaming charts

## Resources

- [ECharts Documentation](https://echarts.apache.org/en/index.html)
- [ECharts Examples](https://echarts.apache.org/examples/en/index.html)
- [ECharts Theme Builder](https://echarts.apache.org/en/theme-builder.html)

## Conclusion

Apache ECharts provides Grafana-quality visualizations within our custom UI, eliminating the need for users to switch between applications. The migration improves:

- **User Experience**: Interactive, responsive charts
- **Performance**: Handles large datasets efficiently
- **Visual Quality**: Professional, Grafana-like aesthetics
- **Functionality**: Built-in zoom, tooltips, legends
- **Maintainability**: Less code, more features
