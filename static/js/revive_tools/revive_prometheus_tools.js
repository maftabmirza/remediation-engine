/**
 * Prometheus/Grafana-specific client-side tools
 * Extract PromQL queries and metrics from monitoring pages
 */

(function () {
    'use strict';

    const DEBUG = true;

    function log(...args) {
        if (DEBUG) {
            console.log('%c[PrometheusTools]', 'color: #00BCD4; font-weight: bold', ...args);
        }
    }

    function error(...args) {
        console.error('%c[PrometheusTools]', 'color: #F44336; font-weight: bold', ...args);
    }

    /**
     * Validate if a string is a valid query (not UI artifact)
     */
    function isValidQuery(text) {
        const trimmed = text.trim();

        // Filter out common false positives
        const invalidPatterns = [
            /^(true|false)$/i,
            /^(null|undefined)$/i,
            /^[0-9]+$/,
            /^[\s\n\r]*$/,
            /^Query$/i,
            /^Metrics$/i,
            /^builder$/i,
        ];

        for (const pattern of invalidPatterns) {
            if (pattern.test(trimmed)) {
                log(`Rejected invalid query: "${trimmed}"`);
                return false;
            }
        }

        if (trimmed.length < 2) return false;

        // Valid query patterns (PromQL, LogQL, TraceQL)
        const validPatterns = [
            /[a-zA-Z_][a-zA-Z0-9_]*\{/,     // Metric with labels
            /[a-zA-Z_][a-zA-Z0-9_]*\(/,     // Function
            /[a-zA-Z_][a-zA-Z0-9_]*\[/,     // Range vector
            /^[a-zA-Z_][a-zA-Z0-9_:]*$/,    // Simple metric
            /\|\s*(sum|count|rate|avg)/,    // LogQL aggregations
            /\{[^}]+\}/,                    // Label selectors
        ];

        return validPatterns.some(pattern => pattern.test(trimmed));
    }

    /**
     * Detect Grafana editor mode
     */
    function detectGrafanaMode() {
        const isBuilderMode = document.querySelector('[aria-label="Query builder mode"]') !== null ||
            document.querySelector('.query-builder') !== null ||
            document.querySelector('[data-testid="query-builder"]') !== null;

        const isCodeMode = document.querySelector('[aria-label="Code mode"]')?.getAttribute('aria-pressed') === 'true' ||
            document.querySelector('.query-editor-toggle[aria-label*="Code"]') !== null;

        log(`Grafana mode - Builder: ${isBuilderMode}, Code: ${isCodeMode}`);

        return { isBuilderMode, isCodeMode };
    }

    /**
     * Detect data source type
     */
    function detectDataSource() {
        let dataSourceType = 'unknown';
        let queryLanguage = 'PromQL';

        const urlPath = window.location.pathname + window.location.search;
        const pageText = document.body.innerText;

        // Check for data source hints
        const dsSelector = document.querySelector('[aria-label*="Data source"], [data-testid="data-source-picker"]');
        if (dsSelector) {
            const dsText = (dsSelector.innerText || dsSelector.textContent || '').toLowerCase();
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

        log(`Detected data source: ${dataSourceType}, language: ${queryLanguage}`);

        return { dataSourceType, queryLanguage };
    }

    /**
     * Extract PromQL/LogQL query from editor
     */
    async function extractPromQLQuery(args = {}) {
        log('extractPromQLQuery called');

        let query = null;
        let extractionMethod = null;
        const { isBuilderMode, isCodeMode } = detectGrafanaMode();

        // Strategy 1: Monaco Editor API (most reliable for Code mode)
        if (window.monaco?.editor && !isBuilderMode) {
            try {
                const models = window.monaco.editor.getModels();
                log(`Monaco models found: ${models.length}`);

                if (models.length > 0) {
                    const allQueries = [];
                    models.forEach((model, idx) => {
                        const value = model.getValue();
                        log(`Model ${idx}: "${value.substring(0, 50)}..." (${value.length} chars)`);

                        if (value.trim().length > 0 && isValidQuery(value)) {
                            allQueries.push(value.trim());
                        }
                    });

                    if (allQueries.length > 0) {
                        query = allQueries.join('\n\n');
                        extractionMethod = 'monaco_api';
                        log(`✓ Extracted via Monaco API: ${query.substring(0, 100)}`);
                    }
                }
            } catch (e) {
                error('Error accessing Monaco models:', e);
            }
        }

        // Strategy 2: DOM Scraping (fallback)
        if (!query && !isBuilderMode) {
            log('Trying DOM scraping...');

            const selectors = [
                '.monaco-editor .view-lines .view-line',
                '.monaco-editor .view-lines',
                '[data-mprt="5"] .view-lines',
                '[data-mprt="7"] .view-lines',
                '.query-editor-row .monaco-editor',
            ];

            for (const selector of selectors) {
                const elements = document.querySelectorAll(selector);
                if (elements.length > 0) {
                    let extractedText = "";

                    elements.forEach(el => {
                        const text = el.innerText || el.textContent || '';
                        if (text.trim()) {
                            extractedText += text.trim() + '\n';
                        }
                    });

                    extractedText = extractedText.trim();
                    log(`Selector "${selector}" found ${elements.length} elements, text: "${extractedText.substring(0, 50)}"`);

                    if (extractedText.length > 1 && isValidQuery(extractedText)) {
                        query = extractedText;
                        extractionMethod = `dom_scrape:${selector}`;
                        log(`✓ Extracted via DOM scraping: ${query.substring(0, 100)}`);
                        break;
                    }
                }
            }
        }

        // Strategy 3: Slate Editor
        if (!query) {
            const slateLines = document.querySelectorAll('[data-slate-editor="true"]');
            if (slateLines.length > 0) {
                let slateText = "";
                slateLines.forEach(line => {
                    slateText += (line.innerText || line.textContent || '') + '\n';
                });
                slateText = slateText.trim();

                if (slateText.length > 1 && isValidQuery(slateText)) {
                    query = slateText;
                    extractionMethod = 'slate_editor';
                    log(`✓ Extracted via Slate: ${query.substring(0, 100)}`);
                }
            }
        }

        // Strategy 4: Textarea fallback
        if (!query) {
            const textareas = document.querySelectorAll('textarea');
            log(`Found ${textareas.length} textareas`);

            for (const ta of textareas) {
                if (ta.value && ta.value.trim().length > 0) {
                    log(`Textarea: "${ta.value.substring(0, 50)}..."`);

                    if (isValidQuery(ta.value)) {
                        query = ta.value.trim();
                        extractionMethod = 'textarea';
                        log(`✓ Extracted via textarea: ${query.substring(0, 100)}`);
                        break;
                    }
                }
            }
        }

        if (!query) {
            const message = isBuilderMode
                ? 'No query found. Builder mode detected - switch to Code mode for better extraction'
                : 'No PromQL query found on page';

            log('✗ ' + message);

            return {
                type: 'promql',
                data: null,
                error: message,
                builder_mode_detected: isBuilderMode
            };
        }

        const { dataSourceType, queryLanguage } = detectDataSource();

        // Auto-detect query language from syntax if data source is unknown
        if (dataSourceType === 'unknown' && query) {
            if (query.includes('|') && (query.includes('|= ') || query.includes('|~ '))) {
                queryLanguage = 'LogQL';
                dataSourceType = 'loki';
            } else if (query.includes('trace') || query.includes('span')) {
                queryLanguage = 'TraceQL';
                dataSourceType = 'tempo';
            }
        }

        const result = {
            query,
            data_source: dataSourceType,
            query_language: queryLanguage,
            extraction_method: extractionMethod,
            is_builder_mode: isBuilderMode,
            is_code_mode: isCodeMode,
            url: window.location.href
        };

        log('Query extraction complete:', result);

        return {
            type: 'promql',
            data: result,
            summary: `Found ${queryLanguage} query: ${query.substring(0, 50)}${query.length > 50 ? '...' : ''}`
        };
    }

    /**
     * Get dashboard panels
     */
    async function getDashboardPanels(args = {}) {
        log('getDashboardPanels called');

        const panels = [];

        // Look for Grafana panels
        const panelElements = document.querySelectorAll('.panel, [data-panel], .dashboard-panel');

        panelElements.forEach((panel, idx) => {
            const panelData = {
                order: idx + 1,
                title: null,
                type: null,
                query: null
            };

            const titleEl = panel.querySelector('.panel-title, h6');
            if (titleEl) {
                panelData.title = titleEl.innerText.trim();
            }

            const typeEl = panel.querySelector('[data-panel-type]');
            if (typeEl) {
                panelData.type = typeEl.getAttribute('data-panel-type');
            }

            panels.push(panelData);
        });

        log(`Found ${panels.length} dashboard panels`);

        return {
            type: 'dashboard_panels',
            data: {
                panels,
                count: panels.length
            },
            summary: `Found ${panels.length} panels on dashboard`
        };
    }

    // Register tools
    if (window.reviveToolRegistry) {
        window.reviveToolRegistry.register('extract_promql_query', {
            description: 'Extract PromQL, LogQL, or TraceQL query from the current Prometheus/Grafana page',
            category: 'monitoring',
            pageTypes: ['panels', 'grafana', 'prometheus'],
            parameters: [],
            handler: extractPromQLQuery
        });

        window.reviveToolRegistry.register('get_dashboard_panels', {
            description: 'List all panels on the current Grafana dashboard',
            category: 'monitoring',
            pageTypes: ['dashboards', 'grafana'],
            parameters: [],
            handler: getDashboardPanels
        });

        log('Registered 2 Prometheus/Grafana tools');
    } else {
        error('Tool registry not found!');
    }
})();
