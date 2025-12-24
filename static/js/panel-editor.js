/**
 * Panel Editor - Shared JavaScript Functions
 * Used by both panels.html and dashboard_view.html
 */

// ========== Configuration ==========
const PanelEditor = {
    previewChart: null,
    thresholdCounter: 0,

    // Color palette for charts
    colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'],

    // Query examples
    queryExamples: {
        'cpu': '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
        'memory': '(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1024 / 1024 / 1024',
        'disk': '100 - ((node_filesystem_avail_bytes{mountpoint="/",fstype!="rootfs"} * 100) / node_filesystem_size_bytes{mountpoint="/",fstype!="rootfs"})',
        'network_rx': 'rate(node_network_receive_bytes_total[5m]) / 1024 / 1024',
        'network_tx': 'rate(node_network_transmit_bytes_total[5m]) / 1024 / 1024',
        'http_rate': 'sum(rate(http_requests_total[5m])) by (method, status)',
        'http_errors': '(sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) * 100',
        'http_latency': 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
        'alerts': 'ALERTS{alertstate="firing"}',
        'up': 'up'
    },

    // ========== Query Testing ==========
    async testQuery(options = {}) {
        const datasourceId = document.getElementById('panel-datasource').value;
        const query = document.getElementById('query-editor').value;
        const panelType = document.getElementById('panel-type').value;
        const timeRange = document.getElementById('panel-time-range').value;

        if (!datasourceId || !query) {
            if (typeof showToast === 'function') {
                showToast('Please select a datasource and enter a query', 'error');
            }
            return;
        }

        const statusDiv = document.getElementById('query-status');
        const resultDiv = document.getElementById('query-result');
        const chartDiv = document.getElementById('query-preview-chart');
        const dataDiv = document.getElementById('query-data-preview');
        const jsonPre = document.getElementById('query-data-json');

        resultDiv.classList.remove('hidden');
        statusDiv.innerHTML = '<div class="text-gray-400"><i class="fas fa-spinner fa-spin mr-2"></i>Testing query...</div>';
        chartDiv.classList.add('hidden');
        dataDiv.classList.add('hidden');

        try {
            // First, validate the query
            const testResponse = await fetch('/api/panels/test-query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ datasource_id: datasourceId, promql_query: query })
            });
            const testResult = await testResponse.json();

            if (!testResult.valid) {
                statusDiv.innerHTML = `<div class="text-red-400">✗ ${testResult.message}</div>`;
                return;
            }

            // If valid, fetch actual data for preview
            const dataResponse = await fetch(`/api/snapshots/query/data?promql_query=${encodeURIComponent(query)}&time_range=${timeRange}`);
            const queryData = await dataResponse.json();

            if (queryData.data && Array.isArray(queryData.data) && queryData.data.length > 0) {
                const result = queryData.data;

                // Show raw data preview
                jsonPre.textContent = JSON.stringify(result.slice(0, 3), null, 2);
                if (result.length > 3) {
                    jsonPre.textContent += `\n... and ${result.length - 3} more series`;
                }
                dataDiv.classList.remove('hidden');

                // Render preview chart
                this.renderPreviewChart(result, panelType);
                chartDiv.classList.remove('hidden');

                statusDiv.innerHTML = `
                    <div class="text-green-400 font-medium">✓ Query successful - ${result.length} series returned</div>
                    <div class="text-xs text-green-300 mt-1">Result Type: ${testResult.result_type || 'matrix'} | Time Range: ${timeRange}</div>
                `;
            } else if (queryData.error) {
                statusDiv.innerHTML = `<div class="text-green-400">✓ Query valid</div><div class="text-yellow-400 text-xs mt-1">⚠ ${queryData.error}</div>`;
            } else {
                statusDiv.innerHTML = `<div class="text-green-400">✓ Query valid</div><div class="text-yellow-400 text-xs mt-1">⚠ No data returned for the selected time range</div>`;
            }
        } catch (error) {
            console.error('Query test error:', error);
            statusDiv.innerHTML = `<div class="text-red-400">Error: ${error.message}</div>`;
        }
    },

    // ========== Chart Rendering ==========
    renderPreviewChart(data, panelType) {
        const chartDiv = document.getElementById('query-preview-chart');

        // Show the container before initializing
        chartDiv.classList.remove('hidden');
        chartDiv.style.width = '100%';
        chartDiv.style.minHeight = '250px';

        // Dispose old chart if exists
        if (this.previewChart) {
            this.previewChart.dispose();
            this.previewChart = null;
        }

        const self = this;
        setTimeout(() => {
            try {
                // For table, just show data
                if (panelType === 'table') {
                    const tableData = data.slice(0, 10).map(series => {
                        const metric = series.metric || {};
                        const value = series.values ? series.values[series.values.length - 1][1] : (series.value ? series.value[1] : 'N/A');
                        return { metric: JSON.stringify(metric), value: parseFloat(value).toFixed(2) };
                    });
                    chartDiv.innerHTML = `<div class="text-xs text-gray-400 p-4"><pre>${JSON.stringify(tableData, null, 2)}</pre></div>`;
                    return;
                }

                self.previewChart = echarts.init(chartDiv, 'dark');

                // Build series for line/area chart (default)
                const series = data.slice(0, 5).map((s, idx) => {
                    const label = self.getMetricLabel(s.metric);
                    const values = s.values || (s.value ? [[s.value[0], s.value[1]]] : []);
                    const isArea = panelType === 'area' || panelType === 'stacked_area';
                    return {
                        name: label,
                        type: 'line',
                        smooth: true,
                        showSymbol: false,
                        data: values.map(v => [new Date(v[0] * 1000), parseFloat(v[1]) || 0]),
                        lineStyle: { width: 2 },
                        itemStyle: { color: self.colors[idx % self.colors.length] },
                        areaStyle: isArea ? { opacity: 0.3 } : null
                    };
                });

                const option = {
                    backgroundColor: 'transparent',
                    tooltip: {
                        trigger: 'axis',
                        backgroundColor: '#1f2937',
                        borderColor: '#374151',
                        textStyle: { color: '#e5e7eb' }
                    },
                    legend: {
                        show: series.length > 1 && series.length <= 5,
                        bottom: 0,
                        textStyle: { color: '#9ca3af', fontSize: 10 }
                    },
                    grid: { top: 20, right: 20, bottom: 40, left: 60 },
                    xAxis: {
                        type: 'time',
                        axisLine: { lineStyle: { color: '#374151' } },
                        axisLabel: { color: '#9ca3af', fontSize: 10 },
                        splitLine: { show: false }
                    },
                    yAxis: {
                        type: 'value',
                        axisLine: { lineStyle: { color: '#374151' } },
                        axisLabel: { color: '#9ca3af', fontSize: 10 },
                        splitLine: { lineStyle: { color: '#1f2937' } }
                    },
                    series: series
                };

                self.previewChart.setOption(option, true);
                self.previewChart.resize();
            } catch (err) {
                console.error('Error rendering preview chart:', err);
                chartDiv.innerHTML = '<div class="text-red-400 text-sm p-4">Error rendering chart</div>';
            }
        }, 100);
    },

    getMetricLabel(metric) {
        if (!metric) return 'value';
        const keys = Object.keys(metric);
        if (keys.length === 0) return 'value';
        if (keys.includes('instance')) return metric.instance;
        if (keys.includes('job')) return metric.job;
        return metric[keys[0]] || 'value';
    },

    getLatestValue(data) {
        if (!data || data.length === 0) return 0;
        const first = data[0];
        if (first.values && first.values.length > 0) {
            return parseFloat(first.values[first.values.length - 1][1]) || 0;
        }
        if (first.value) {
            return parseFloat(first.value[1]) || 0;
        }
        return 0;
    },

    // ========== Query Examples ==========
    loadQueryExample() {
        const exampleType = document.getElementById('query-examples').value;
        const queryEditor = document.getElementById('query-editor');

        if (exampleType && this.queryExamples[exampleType] && queryEditor) {
            queryEditor.value = this.queryExamples[exampleType];
            document.getElementById('query-examples').value = '';
        }
    },

    // ========== Chart Configuration Toggle ==========
    toggleChartConfig() {
        const section = document.getElementById('chart-config-section');
        const icon = document.getElementById('chart-config-icon');
        const text = document.getElementById('chart-config-text');

        if (section.classList.contains('hidden')) {
            section.classList.remove('hidden');
            icon.classList.remove('fa-chevron-down');
            icon.classList.add('fa-chevron-up');
            text.textContent = 'Hide';
        } else {
            section.classList.add('hidden');
            icon.classList.remove('fa-chevron-up');
            icon.classList.add('fa-chevron-down');
            text.textContent = 'Show';
        }
    },

    // ========== Threshold Management ==========
    addThreshold(existing = null) {
        const container = document.getElementById('thresholds-container');
        const thresholdId = `threshold-${this.thresholdCounter++}`;
        const value = existing ? existing.value : '';
        const label = existing ? (existing.label || '') : '';
        const color = existing ? (existing.color || '#fac858') : '#fac858';

        const thresholdHtml = `
            <div id="${thresholdId}" class="flex items-center gap-2 bg-gray-700/50 p-2 rounded">
                <input type="number" step="any" placeholder="Value" value="${value}"
                    class="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white threshold-value"
                    data-threshold-id="${thresholdId}">
                <input type="text" placeholder="Label" value="${label}"
                    class="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white threshold-label"
                    data-threshold-id="${thresholdId}">
                <input type="color" value="${color}"
                    class="w-12 h-8 bg-gray-700 border border-gray-600 rounded cursor-pointer threshold-color"
                    data-threshold-id="${thresholdId}">
                <button type="button" onclick="PanelEditor.removeThreshold('${thresholdId}')"
                    class="text-red-400 hover:text-red-300 px-2">
                    <i class="fas fa-trash text-sm"></i>
                </button>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', thresholdHtml);
    },

    removeThreshold(thresholdId) {
        document.getElementById(thresholdId)?.remove();
    },

    // ========== Collect Chart Configuration ==========
    collectChartConfig() {
        const yAxisMin = document.getElementById('y-axis-min').value;
        const yAxisMax = document.getElementById('y-axis-max').value;
        const yAxisLabel = document.getElementById('y-axis-label').value;
        const unitFormat = document.getElementById('unit-format').value;
        const decimals = parseInt(document.getElementById('decimals').value) || 2;
        const colorScheme = document.getElementById('color-scheme').value;
        const useGradient = document.getElementById('use-gradient').checked;
        const legendPosition = document.getElementById('legend-position').value;
        const showLegend = document.getElementById('show-legend').checked;

        const thresholds = [];
        document.querySelectorAll('.threshold-value').forEach(input => {
            const thresholdId = input.getAttribute('data-threshold-id');
            const value = parseFloat(input.value);
            const label = document.querySelector(`.threshold-label[data-threshold-id="${thresholdId}"]`).value;
            const color = document.querySelector(`.threshold-color[data-threshold-id="${thresholdId}"]`).value;
            if (!isNaN(value)) thresholds.push({ value, label, color });
        });

        return {
            axis: {
                y_min: yAxisMin ? parseFloat(yAxisMin) : null,
                y_max: yAxisMax ? parseFloat(yAxisMax) : null,
                y_label: yAxisLabel || null
            },
            units: unitFormat || null,
            decimals,
            color_scheme: colorScheme,
            gradient: useGradient,
            thresholds: thresholds.length > 0 ? thresholds : null,
            legend: { show: showLegend, position: legendPosition }
        };
    },

    // ========== Load Visualization Config into Form ==========
    loadVisualizationConfig(config) {
        if (!config) config = {};

        document.getElementById('y-axis-min').value = config.axis?.y_min || '';
        document.getElementById('y-axis-max').value = config.axis?.y_max || '';
        document.getElementById('y-axis-label').value = config.axis?.y_label || '';
        document.getElementById('unit-format').value = config.units || '';
        document.getElementById('decimals').value = config.decimals || 2;
        document.getElementById('color-scheme').value = config.color_scheme || 'default';
        document.getElementById('use-gradient').checked = config.gradient || false;
        document.getElementById('legend-position').value = config.legend?.position || 'bottom';
        document.getElementById('show-legend').checked = config.legend?.show !== false;

        // Load thresholds
        const thresholdsContainer = document.getElementById('thresholds-container');
        thresholdsContainer.innerHTML = '';
        this.thresholdCounter = 0;
        if (config.thresholds && config.thresholds.length > 0) {
            config.thresholds.forEach(threshold => {
                this.addThreshold(threshold);
            });
        }
    }
};

// ========== Global Function Wrappers (for onclick handlers) ==========
function testQuery() {
    PanelEditor.testQuery();
}

function loadQueryExample() {
    PanelEditor.loadQueryExample();
}

function toggleChartConfig() {
    PanelEditor.toggleChartConfig();
}

function addThreshold(existing = null) {
    PanelEditor.addThreshold(existing);
}

function removeThreshold(thresholdId) {
    PanelEditor.removeThreshold(thresholdId);
}

function collectChartConfig() {
    return PanelEditor.collectChartConfig();
}
