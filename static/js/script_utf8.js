// AIOps Dashboard Logic
// Version: Premium Enterprise 3.0

document.addEventListener('DOMContentLoaded', () => {
    console.log("AIOps Dashboard Initialized");

    // 1. Initialize Global UI Logic (Sidebar, Animations)
    initGlobalUI();

    // 2. Route Initialization based on active page elements
    if (document.getElementById('mttrTrendChart')) {
        initCommandCenterCharts(); // New Command Center
    } else if (document.getElementById('trafficChart')) {
        initAppDetailCharts(); // App Details
    }
});

// ==========================================
// GLOBAL UI LOGIC
// ==========================================
function initGlobalUI() {
    // Subtle entrance animation for cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        // Skip cards that need overflow visible (e.g., toolbar with dropdowns)
        if (card.style.overflow === 'visible') return;
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        setTimeout(() => {
            card.style.transition = 'opacity 0.6s cubic-bezier(0.2, 0.8, 0.2, 1), transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1)';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
            // Remove transform after animation to avoid creating stacking context
            setTimeout(() => {
                card.style.transform = '';
                card.style.transition = '';
            }, 700);
        }, 80 * index);
    });

    // Sidebar Toggle Logic
    const appContainer = document.querySelector('.app-container');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');

    // Default state: check class
    // If appContainer has 'collapsed', it's closed.

    if (sidebarToggleBtn && appContainer) {
        sidebarToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const isCollapsed = appContainer.classList.toggle('collapsed');

            // Update Icon
            // Re-create the <i> tag because feather.replace() replaces it with an <svg>
            const newIcon = isCollapsed ? 'skip-forward' : 'skip-back';
            sidebarToggleBtn.innerHTML = `<i data-feather="${newIcon}"></i>`;

            if (typeof feather !== 'undefined') {
                feather.replace();
            }

            // Trigger resize for charts
            triggerResize();
        });
    }

    // No more Lock/Auto logic needed as hover is disabled.

    // Sidebar Hover Expansion REMOVED per user request
    // if (sidebar && appContainer) { ... }

    // Submenu Logic
    const submenuParents = document.querySelectorAll('.has-submenu');
    submenuParents.forEach(parent => {
        const navGroup = parent.parentElement;
        parent.addEventListener('click', () => {
            navGroup.classList.toggle('open');
        });
    });

    // RE-VIVE Chat Panel Logic
    initChatPanel();
}

// ==========================================
// RE-VIVE CHAT PANEL
// ==========================================
function initChatPanel() {
    const chatToggleBtn = document.getElementById('chatToggleBtn');
    const chatCloseBtn = document.getElementById('chatCloseBtn');
    const chatPanel = document.getElementById('chatPanel');
    const chatInput = document.getElementById('chatInput');
    const chatSendBtn = document.getElementById('chatSendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const appContainer = document.querySelector('.app-container');

    if (!chatToggleBtn || !chatPanel || !appContainer) return;

    // Toggle chat panel
    chatToggleBtn.addEventListener('click', () => {
        const isOpen = chatPanel.classList.toggle('open');
        appContainer.classList.toggle('chat-open', isOpen);
        chatToggleBtn.classList.toggle('active', isOpen);

        if (isOpen) {
            setTimeout(() => chatInput?.focus(), 350);
        }
        triggerResize();
    });

    // Close chat panel
    chatCloseBtn?.addEventListener('click', () => {
        chatPanel.classList.remove('open');
        appContainer.classList.remove('chat-open');
        chatToggleBtn.classList.remove('active');
        triggerResize();
    });

    // Send message
    const sendMessage = () => {
        const message = chatInput?.value.trim();
        if (!message) return;

        // Add user message
        addMessage(message, 'user');
        chatInput.value = '';

        // Simulate bot response
        setTimeout(() => {
            const responses = [
                "I'm analyzing the incident patterns. Based on the data, the Notification Service degradation appears to be related to a database connection pool exhaustion.",
                "Let me check the service health metrics. All critical services are operating within normal parameters except for the Payment Processing service showing elevated latency.",
                "Running diagnostics now. I've identified 3 potential root causes for the current P1 incidents. Would you like me to create a remediation playbook?",
                "I've correlated the recent alerts with historical data. This pattern matches a known issue from 2 weeks ago. The auto-remediation script resolved it in 4.2 minutes."
            ];
            const randomResponse = responses[Math.floor(Math.random() * responses.length)];
            addMessage(randomResponse, 'bot');
        }, 1000);
    };

    chatSendBtn?.addEventListener('click', sendMessage);
    chatInput?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Suggestion buttons
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            chatInput.value = btn.textContent;
            sendMessage();
        });
    });

    function addMessage(text, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${type}`;

        const avatarIcon = type === 'bot' ? 'cpu' : 'user';
        messageDiv.innerHTML = `
            <div class="message-avatar"><i data-feather="${avatarIcon}"></i></div>
            <div class="message-content">
                <div class="message-text">${text}</div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Re-render feather icons for new elements
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }
}

function triggerResize() {
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 300);
}

// ==========================================
// COMMAND CENTER CHARTS
// ==========================================
let cmdCharts = {};

function initCommandCenterCharts() {
    console.log("Initializing Command Center Dashboard...");

    // MTTR Trend Chart (30 Days)
    const mttrDom = document.getElementById('mttrTrendChart');
    if (mttrDom) {
        const chart = echarts.init(mttrDom);
        const days = Array.from({ length: 30 }, (_, i) => `Day ${i + 1}`);
        const mttrData = [42, 45, 38, 40, 35, 32, 28, 30, 26, 24, 22, 25, 20, 18, 16,
            19, 15, 14, 12, 13, 11, 10, 9, 11, 8, 9, 8, 7, 8, 8.2];

        chart.setOption({
            tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.95)', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' }, formatter: '{b}<br/>MTTR: {c} mins' },
            grid: { left: '3%', right: '3%', top: '8%', bottom: '8%', containLabel: true },
            xAxis: {
                type: 'category',
                data: days,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: { color: '#94a3b8', fontSize: 10, interval: 5 }
            },
            yAxis: {
                type: 'value',
                name: 'Minutes',
                nameTextStyle: { color: '#94a3b8', fontSize: 10 },
                splitLine: { lineStyle: { color: '#f1f5f9' } },
                axisLabel: { color: '#94a3b8', fontSize: 10 }
            },
            series: [{
                type: 'line',
                data: mttrData,
                smooth: true,
                symbol: 'none',
                lineStyle: { width: 2, color: '#10b981' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(16, 185, 129, 0.15)' },
                        { offset: 1, color: 'rgba(16, 185, 129, 0)' }
                    ])
                }
            }]
        });
        cmdCharts.mttrTrend = chart;
    }

    // Incident Volume Trend (7 Days by Priority)
    const incidentDom = document.getElementById('incidentTrendChart');
    if (incidentDom) {
        const chart = echarts.init(incidentDom);
        const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

        chart.setOption({
            tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.95)', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' } },
            grid: { left: '3%', right: '3%', top: '12%', bottom: '8%', containLabel: true },
            xAxis: {
                type: 'category',
                data: days,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: { color: '#94a3b8', fontSize: 10 }
            },
            yAxis: {
                type: 'value',
                name: 'Incidents',
                nameTextStyle: { color: '#94a3b8', fontSize: 10 },
                splitLine: { lineStyle: { color: '#f1f5f9' } },
                axisLabel: { color: '#94a3b8', fontSize: 10 }
            },
            series: [
                {
                    name: 'P1 Critical',
                    type: 'bar',
                    stack: 'incidents',
                    data: [2, 1, 3, 2, 1, 0, 1],
                    itemStyle: { color: '#ef4444', borderRadius: [0, 0, 0, 0] }
                },
                {
                    name: 'P2 High',
                    type: 'bar',
                    stack: 'incidents',
                    data: [5, 8, 6, 4, 7, 3, 2],
                    itemStyle: { color: '#f59e0b' }
                },
                {
                    name: 'P3 Normal',
                    type: 'bar',
                    stack: 'incidents',
                    data: [12, 15, 10, 18, 14, 8, 6],
                    itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] }
                }
            ]
        });
        cmdCharts.incidentTrend = chart;
    }

    // Global Infrastructure Map
    const mapDom = document.getElementById('globalGeoMap');
    if (mapDom) {
        const chart = echarts.init(mapDom);
        chart.setOption({
            tooltip: { trigger: 'item', backgroundColor: 'rgba(255,255,255,0.95)', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' } },
            series: [{
                type: 'graph',
                layout: 'none',
                roam: true,
                label: { show: true, position: 'bottom', fontSize: 10, color: '#64748b', fontWeight: 500 },
                lineStyle: { color: '#e2e8f0', width: 1.5, curveness: 0.2 },
                data: [
                    { name: 'US-East', x: 220, y: 120, symbolSize: 28, itemStyle: { color: '#10b981' } },
                    { name: 'US-West', x: 80, y: 130, symbolSize: 22, itemStyle: { color: '#10b981' } },
                    { name: 'EU-West', x: 400, y: 90, symbolSize: 24, itemStyle: { color: '#f59e0b' } },
                    { name: 'EU-Central', x: 440, y: 100, symbolSize: 20, itemStyle: { color: '#10b981' } },
                    { name: 'AP-South', x: 560, y: 180, symbolSize: 22, itemStyle: { color: '#f59e0b' } },
                    { name: 'AP-Southeast', x: 620, y: 200, symbolSize: 26, itemStyle: { color: '#ef4444' } },
                    { name: 'AP-Northeast', x: 700, y: 120, symbolSize: 22, itemStyle: { color: '#10b981' } },
                    { name: 'SA-East', x: 280, y: 260, symbolSize: 18, itemStyle: { color: '#10b981' } },
                    { name: 'AU-East', x: 720, y: 280, symbolSize: 18, itemStyle: { color: '#10b981' } },
                    { name: 'ME-South', x: 500, y: 160, symbolSize: 16, itemStyle: { color: '#10b981' } },
                    { name: 'AF-South', x: 460, y: 240, symbolSize: 16, itemStyle: { color: '#10b981' } }
                ],
                links: [
                    { source: 'US-East', target: 'US-West' },
                    { source: 'US-East', target: 'EU-West' },
                    { source: 'US-East', target: 'SA-East' },
                    { source: 'EU-West', target: 'EU-Central' },
                    { source: 'EU-West', target: 'ME-South' },
                    { source: 'EU-Central', target: 'AP-South' },
                    { source: 'AP-South', target: 'AP-Southeast' },
                    { source: 'AP-Southeast', target: 'AP-Northeast' },
                    { source: 'AP-Southeast', target: 'AU-East' },
                    { source: 'ME-South', target: 'AF-South' }
                ]
            }]
        });
        cmdCharts.geoMap = chart;
    }

    // Service Sparklines
    initSparkline('sparkApi', [99.9, 99.95, 99.99, 99.98, 99.99, 99.99, 99.97, 99.99], '#10b981');
    initSparkline('sparkAuth', [99.9, 99.92, 99.95, 99.98, 99.96, 99.98, 99.97, 99.98], '#10b981');
    initSparkline('sparkPayment', [99.8, 99.7, 99.5, 99.3, 99.2, 99.4, 99.45, 99.45], '#f59e0b');
    initSparkline('sparkDb', [99.95, 99.97, 99.96, 99.98, 99.97, 99.96, 99.97, 99.97], '#10b981');
    initSparkline('sparkNotif', [99.5, 99.2, 98.5, 97.8, 97.5, 97.2, 97.2, 97.2], '#ef4444');
    initSparkline('sparkCdn', [100, 100, 100, 100, 100, 100, 100, 100], '#10b981');

    // Resize Observer
    window.addEventListener('resize', () => {
        Object.values(cmdCharts).forEach(c => c && c.resize());
    });
}

function initSparkline(id, data, color) {
    const dom = document.getElementById(id);
    if (!dom) return;
    const chart = echarts.init(dom);
    chart.setOption({
        grid: { top: 2, bottom: 2, left: 0, right: 0 },
        xAxis: { type: 'category', show: false },
        yAxis: { type: 'value', show: false, min: 'dataMin' },
        series: [{
            type: 'line',
            data: data,
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 1.5, color: color },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: color },
                    { offset: 1, color: 'rgba(255,255,255,0)' }
                ]),
                opacity: 0.2
            }
        }]
    });
    cmdCharts[id] = chart;
}

// ==========================================
// APP DETAILS CHARTS
// ==========================================
let appCharts = {};
let forecastChartInstance = null;
let topologyChartInstance = null;

function initAppDetailCharts() {
    console.log("Initializing App Details...");

    // 1. Traffic Chart (Live)
    const trafficDom = document.getElementById('trafficChart');
    if (trafficDom) {
        appCharts.traffic = echarts.init(trafficDom);
        const option = {
            tooltip: { trigger: 'axis' },
            grid: { left: '2%', right: '2%', bottom: '2%', top: '5%', containLabel: true },
            xAxis: {
                type: 'category', boundaryGap: false,
                data: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'],
                axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#64748b' }
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } },
                axisLabel: { color: '#64748b' }
            },
            series: [{
                name: 'Requests/sec', type: 'line', smooth: true, showSymbol: false,
                lineStyle: { width: 3, color: '#3b82f6' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(59, 130, 246, 0.2)' },
                        { offset: 1, color: 'rgba(59, 130, 246, 0)' }
                    ])
                },
                data: [1200, 1900, 1500, 2200, 2800, 2400]
            }]
        };
        appCharts.traffic.setOption(option);
    }

    // 2. Error Chart
    const errorDom = document.getElementById('errorChart');
    if (errorDom) {
        appCharts.error = echarts.init(errorDom);
        const option = {
            tooltip: { trigger: 'axis' },
            grid: { left: '2%', right: '2%', bottom: '2%', top: '5%', containLabel: true },
            xAxis: {
                type: 'category', data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#64748b' }
            },
            yAxis: {
                type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }, axisLabel: { color: '#64748b' }
            },
            series: [{
                name: 'Error Rate %', type: 'bar', barWidth: '40%',
                itemStyle: { borderRadius: [4, 4, 0, 0], color: '#10b981' },
                data: [0.2, 0.15, 0.5, 0.2, 0.1, 0.05, 0.1]
            }]
        };
        appCharts.error.setOption(option);
    }

    // 3. Forecast Chart
    const forecastDom = document.getElementById('forecastChart');
    if (forecastDom) {
        forecastChartInstance = echarts.init(forecastDom);
        const option = {
            tooltip: { trigger: 'axis' },
            legend: { top: 0, right: 0, icon: 'circle', textStyle: { color: '#64748b' } },
            grid: { left: '2%', right: '2%', bottom: '2%', containLabel: true },
            xAxis: {
                type: 'category', boundaryGap: false,
                data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Next Mon', 'Next Tue'],
                axisLine: { show: false }, axisLabel: { color: '#64748b' }
            },
            yAxis: {
                type: 'value', name: 'Storage (GB)', nameLocation: 'end',
                splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }, axisLabel: { color: '#64748b' }
            },
            series: [
                {
                    name: 'Actual Usage', type: 'line', smooth: true, symbol: 'none',
                    data: [120, 132, 145, 160, 165, 170, 185, null, null],
                    lineStyle: { width: 3, color: '#8b5cf6' }
                },
                {
                    name: 'Predicted', type: 'line', smooth: true, symbol: 'none',
                    data: [null, null, null, null, null, null, 185, 200, 220],
                    lineStyle: { width: 3, type: 'dashed', color: '#8b5cf6' },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(139, 92, 246, 0.1)' },
                            { offset: 1, color: 'rgba(139, 92, 246, 0)' }
                        ])
                    }
                }
            ]
        };
        forecastChartInstance.setOption(option);
    }

    // 4. Topology Chart
    const topoDom = document.getElementById('topologyChart');
    if (topoDom) {
        topologyChartInstance = echarts.init(topoDom);
        const nodes = [
            { name: 'LB-01', x: 300, y: 50, symbolSize: 35, itemStyle: { color: '#3b82f6' } },
            { name: 'Web-01', x: 200, y: 150, symbolSize: 25, itemStyle: { color: '#10b981' } },
            { name: 'Web-02', x: 400, y: 150, symbolSize: 25, itemStyle: { color: '#10b981' } },
            { name: 'API-GW', x: 300, y: 250, symbolSize: 35, itemStyle: { color: '#8b5cf6' } },
            { name: 'Auth', x: 150, y: 350, symbolSize: 25, itemStyle: { color: '#10b981' } },
            { name: 'Pay', x: 300, y: 350, symbolSize: 25, itemStyle: { color: '#f59e0b' } },
            { name: 'Inv', x: 450, y: 350, symbolSize: 25, itemStyle: { color: '#10b981' } },
            { name: 'DB-Main', x: 300, y: 450, symbolSize: 45, itemStyle: { color: '#ef4444' } }
        ];
        const links = [
            { source: 'LB-01', target: 'Web-01' }, { source: 'LB-01', target: 'Web-02' },
            { source: 'Web-01', target: 'API-GW' }, { source: 'Web-02', target: 'API-GW' },
            { source: 'API-GW', target: 'Auth' }, { source: 'API-GW', target: 'Pay' }, { source: 'API-GW', target: 'Inv' },
            { source: 'Pay', target: 'DB-Main' }, { source: 'Inv', target: 'DB-Main' }
        ];

        const option = {
            tooltip: {},
            series: [{
                type: 'graph', layout: 'none', data: nodes, links: links, roam: true,
                label: { show: true, position: 'bottom', color: '#64748b', fontSize: 10 },
                lineStyle: { color: '#cbd5e1', width: 2, curveness: 0.1 },
                emphasis: { focus: 'adjacency', lineStyle: { width: 4 } }
            }]
        };
        topologyChartInstance.setOption(option);
    }

    // Resize Listener
    window.addEventListener('resize', () => {
        Object.values(appCharts).forEach(c => c && c.resize());
        if (forecastChartInstance) forecastChartInstance.resize();
        if (topologyChartInstance) topologyChartInstance.resize();
    });
}
