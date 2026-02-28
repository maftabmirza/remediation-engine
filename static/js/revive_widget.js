
document.addEventListener('DOMContentLoaded', () => {
    // Skip widget injection on debug pages that intentionally test dual-widget conflicts
    const currentPath = window.location.pathname;
    if (currentPath.startsWith('/grafana-debug/')) {
        console.log('[RE-VIVE base] Skipping — debug page:', currentPath);
        return;
    }

    // Inject Widget HTML if not present
    const appContainer = document.querySelector('.app-container');
    if (appContainer && !document.getElementById('agent-widget')) {
        const widgetHTML = `
            <div id="agent-widget">
                <div id="agent-window">
                    <div id="agent-resize-handle" class="resize-handle"></div>
                    <div class="agent-header">
                        <div class="flex items-center gap-2">
                            <div class="w-2 h-2 rounded-full bg-green-400"></div>
                            <span class="font-semibold text-white">RE-VIVE</span>
                        </div>
                        <button id="agent-close" class="text-gray-400 hover:text-white transition-colors">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div id="agent-messages" class="agent-messages">
                        <div class="agent-message ai">
                            Hello! I can help you investigate alerts, run analytics, or answer questions about your infrastructure. How can I assist you today?
                        </div>
                    </div>
                    <div class="agent-input-area">
                        <div class="relative">
                            <input type="text" id="agent-input" 
                                class="w-full bg-gray-800 border border-gray-700 rounded-lg pl-4 pr-10 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
                                placeholder="Ask me something...">
                            <button id="agent-send" class="absolute right-2 top-1/2 -translate-y-1/2 text-blue-400 hover:text-blue-300 transition-colors">
                                <i class="fas fa-paper-plane"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        appContainer.insertAdjacentHTML('beforeend', widgetHTML);
    }

    const fab = document.getElementById('agent-fab');
    const topToggle = document.getElementById('ai-helper-toggle');
    const agentWindow = document.getElementById('agent-window');
    const closeBtn = document.getElementById('agent-close');
    const input = document.getElementById('agent-input');
    const sendBtn = document.getElementById('agent-send');
    const messagesContainer = document.getElementById('agent-messages');

    let isOpen = false;
    let sessionId = localStorage.getItem('ai_helper_session_id'); // Load from storage

    function setOpen(nextOpen) {
        isOpen = !!nextOpen;
        if (isOpen) {
            appContainer.classList.add('ai-open');
            // agentWindow.classList.add('visible'); // Handled by CSS
            setTimeout(() => input?.focus(), 0);
        } else {
            appContainer.classList.remove('ai-open');
            // agentWindow.classList.remove('visible'); // Handled by CSS
        }
    }

    function toggleWindow() {
        setOpen(!isOpen);
    }

    function addMessage(text, type, queryId = null) {
        const div = document.createElement('div');
        div.className = `agent-message ${type}`;

        // Store queryId (audit_log_id) for tracking
        if (queryId) {
            div.dataset.queryId = queryId;
        }

        // Simple markdown parsing if marked is available
        if (typeof marked !== 'undefined') {
            div.innerHTML = marked.parse(text);
        } else {
            div.textContent = text;
        }

        // Add tracking for Runbook links (only for AI messages)
        if (type === 'ai') {
            // Match new runbook URL format (/runbooks/{id})
            const links = div.querySelectorAll('a[href*="/runbooks/"]');
            links.forEach(link => {
                link.addEventListener('click', (e) => {
                    // Track the click
                    try {
                        const url = new URL(link.href, window.location.origin);
                        const parts = url.pathname.split('/');
                        const runbookId = parts[parts.length - 1];
                        // Get queryId from this message div or fallback to global/parent
                        const logId = div.dataset.queryId;

                        if (logId && runbookId) {
                            console.log('Tracking runbook click:', runbookId, 'for log:', logId);
                            trackSolutionChoice(logId, {
                                solution_chosen_id: runbookId,
                                solution_chosen_type: 'runbook',
                                user_action: 'clicked_link'
                            });
                        } else {
                            console.warn('Cannot track click: missing queryId or runbookId');
                        }
                    } catch (err) {
                        console.error('Error tracking click:', err);
                    }
                });
            });
        }

        messagesContainer.appendChild(div);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Wire toggles
    if (topToggle) {
        topToggle.addEventListener('click', (e) => {
            e.preventDefault();
            toggleWindow();
        });
    }

    // Keep backward compatibility: if fab exists on any pages, clicking it toggles.
    if (fab) {
        fab.addEventListener('click', (e) => {
            e.preventDefault();
            toggleWindow();
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            setOpen(false);
        });
    }

    async function trackSolutionChoice(auditLogId, choiceData) {
        try {
            await fetch('/api/ai-helper/track-choice', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    audit_log_id: auditLogId,
                    source: 'agent_widget',
                    choice_data: choiceData
                })
            });
        } catch (err) {
            console.error('Failed to track solution choice:', err);
        }
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.id = 'agent-typing';
        div.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        messagesContainer.appendChild(div);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function removeTyping() {
        const el = document.getElementById('agent-typing');
        if (el) el.remove();
    }

    // Extract rich page context for AI Helper
    function getPageContext() {
        const context = {
            url: window.location.href,
            title: document.title,
            page_type: 'unknown',
            form_data: {},
            page_text: document.body.innerText.substring(0, 10000), // Cap at 10k chars
        };

        // Detect page type
        if (window.location.pathname.includes('/panels')) {
            context.page_type = 'panels';
        } else if (window.location.pathname.includes('/runbooks')) {
            context.page_type = 'runbooks';
        } else if (window.location.pathname.includes('/alerts')) {
            context.page_type = 'alerts';
        } else if (window.location.pathname.includes('/knowledge')) {
            context.page_type = 'knowledge';
        } else if (window.location.pathname.includes('/dashboards')) {
            context.page_type = 'dashboards';
        }

        // 1. Generic Form Extraction (All visible forms)
        // Prioritize modals if open, otherwise scan main content
        const modal = document.querySelector('.fixed:not(.hidden)');
        const searchRoot = modal || document.body;

        const inputs = searchRoot.querySelectorAll('input:not([type="hidden"]), textarea, select');
        inputs.forEach(input => {
            if (input.offsetParent === null) return; // Skip invisible inputs
            const label = input.id || input.name || input.getAttribute('aria-label');
            if (label && input.value) {
                context.form_data[label] = input.value;
            }
        });

        // 2. Special Handling for Runbook Steps (Dynamic Content)
        // 2. Special Handling for Runbook Steps (Dynamic Content)
        if (context.page_type === 'runbooks') {
            // A. Try standard edit form (has .step-card)
            const steps = document.querySelectorAll('.step-card');
            if (steps.length > 0) {
                let stepsText = "Runbook Configured Steps:\n";
                steps.forEach((step, idx) => {
                    const name = step.querySelector('.step-name')?.value || 'Unnamed Step';
                    const cmd = step.querySelector('.CodeMirror')?.CodeMirror?.getValue() ||
                        step.querySelector('textarea')?.value ||
                        'No command';
                    stepsText += `Step ${idx + 1}: ${name}\nCommand: ${cmd}\n---\n`;
                });
                context.form_data['runbook_steps_summary'] = stepsText;
                context.page_text += "\n\n" + stepsText;
            } else {
                // B. Fallback for Runbook View page (no .step-card, use generic structure)
                // Look for the specific styling of step containers
                const stepValContainers = document.querySelectorAll('.border.border-gray-700.rounded-lg.p-4.bg-gray-800');
                if (stepValContainers.length > 0) {
                    let stepsText = "Runbook Steps (View Mode):\n";
                    stepValContainers.forEach((step, idx) => {
                        const nameEl = step.querySelector('h4');
                        const name = nameEl ? nameEl.innerText : 'Unnamed Step';

                        // Commands are in pre > code blocks
                        const cmdEl = step.querySelector('pre code') || step.querySelector('pre');
                        const cmd = cmdEl ? cmdEl.innerText : 'No command visible';

                        stepsText += `Step ${idx + 1}: ${name}\nCommand: ${cmd}\n---\n`;
                    });
                    context.form_data['runbook_steps_summary'] = stepsText;
                    context.page_text += "\n\n" + stepsText;
                }
            }
        }

        // 3. Special handling for CodeMirror editors (PromQL query, Runbook commands)
        const cmEditors = searchRoot.querySelectorAll('.CodeMirror');
        cmEditors.forEach((cm, idx) => {
            if (cm.CodeMirror) {
                const query = cm.CodeMirror.getValue();
                if (query) {
                    // Start with generic key
                    context.form_data[`editor_${idx}`] = query;
                    // If it looks like PromQL/Loki, map to specific key
                    if (context.page_type === 'panels' || context.page_type === 'alerts') {
                        context.form_data['promql_query'] = query;
                    }
                }
            }
        });

        // Also check for global queryEditor (panels page specific)
        if (typeof queryEditor !== 'undefined' && queryEditor && typeof queryEditor.getValue === 'function') {
            const query = queryEditor.getValue();
            if (query) {
                context.form_data['promql_query'] = query;
            }
        }

        // Check for Grafana Iframe (Same-Origin via Proxy)
        const grafanaIframe = document.getElementById('grafana-iframe');
        if (grafanaIframe) {
            context.is_grafana = true;
            try {
                // Try to access iframe content (only works if same-origin)
                const iframeDoc = grafanaIframe.contentDocument || grafanaIframe.contentWindow.document;
                if (iframeDoc) {
                    context.grafana_url = iframeDoc.location.href;
                    context.grafana_title = iframeDoc.title;

                    // Try to finding queries in Grafana (very specific selectors, might change)
                    const queryInputs = iframeDoc.querySelectorAll('textarea[class*="query"], .monaco-editor');
                    if (queryInputs.length > 0) {
                        context.has_grafana_query_editor = true;
                    }
                }
            } catch (e) {
                console.log('Cannot access Grafana iframe content (likely cross-origin restriction even with proxy):', e);
                context.grafana_access_error = true;
            }
        }

        // Check if running INSIDE Grafana (Native Injection)
        if (window.location.pathname.startsWith('/grafana/')) {
            context.is_grafana = true;
            context.is_native_grafana = true; // Flag to indicate we are inside

            // We can access DOM directly!
            // Try to find CodeMirror editors (Old Grafana / Specific Plugins)
            const codeMirrors = document.querySelectorAll('.CodeMirror');
            codeMirrors.forEach(cm => {
                if (cm.CodeMirror) {
                    const query = cm.CodeMirror.getValue();
                    if (query) context.form_data['promql_query'] = query;
                }
            });

            // Enhanced Query Extraction with Multiple Strategies
            // Supports: PromQL, LogQL, TraceQL for Grafana stack (Prometheus, Loki, Tempo, Mimir)
            let queryFound = false;

            // Detect Grafana editor mode (Builder vs Code)
            const isBuilderMode = document.querySelector('[aria-label="Query builder mode"]') !== null ||
                document.querySelector('.query-builder') !== null ||
                document.querySelector('[data-testid="query-builder"]') !== null;

            const isCodeMode = document.querySelector('[aria-label="Code mode"]')?.getAttribute('aria-pressed') === 'true' ||
                document.querySelector('.query-editor-toggle[aria-label*="Code"]') !== null;

            console.log(`[AI Agent] Grafana mode - Builder: ${isBuilderMode}, Code: ${isCodeMode}`);

            // Helper: Validate if extracted text is a real query (not UI artifacts)
            function isValidQuery(text) {
                const trimmed = text.trim();

                // Filter out common false positives from Builder mode
                const invalidPatterns = [
                    /^(true|false)$/i,           // Boolean literals
                    /^(null|undefined)$/i,       // Null values
                    /^[0-9]+$/,                  // Pure numbers
                    /^[\s\n\r]*$/,              // Empty/whitespace
                    /^Query$/i,                  // UI label "Query"
                    /^Metrics$/i,                // UI label "Metrics"
                    /^builder$/i,                // UI label "Builder"
                ];

                for (const pattern of invalidPatterns) {
                    if (pattern.test(trimmed)) {
                        console.log(`[AI Agent] Rejected invalid query pattern: "${trimmed}"`);
                        return false;
                    }
                }

                // Must have at least 2 characters and look like a query
                if (trimmed.length < 2) return false;

                // Valid query patterns (PromQL, LogQL, TraceQL)
                const validPatterns = [
                    /[a-zA-Z_][a-zA-Z0-9_]*\{/,     // Metric with labels: up{
                    /[a-zA-Z_][a-zA-Z0-9_]*\(/,     // Function: rate(
                    /[a-zA-Z_][a-zA-Z0-9_]*\[/,     // Range vector: [5m]
                    /^[a-zA-Z_][a-zA-Z0-9_:]*$/,    // Simple metric: up, node_cpu
                    /\|\s*(sum|count|rate|avg)/,    // LogQL aggregations
                    /\{[^}]+\}/,                    // Label selectors
                ];

                return validPatterns.some(pattern => pattern.test(trimmed));
            }

            // Strategy 1: Try Monaco Editor API (Most Reliable for Code Mode)
            if (window.monaco && window.monaco.editor && !isBuilderMode) {
                try {
                    const models = window.monaco.editor.getModels();
                    console.log(`[AI Agent] Monaco models found: ${models.length}`);

                    if (models.length > 0) {
                        // Extract all valid queries from models
                        const allQueries = [];
                        models.forEach((model, idx) => {
                            const value = model.getValue();
                            console.log(`[AI Agent] Model ${idx}: "${value.substring(0, 50)}..." (${value.length} chars)`);

                            if (value.trim().length > 0 && isValidQuery(value)) {
                                allQueries.push(value.trim());
                            }
                        });

                        if (allQueries.length > 0) {
                            const combinedQuery = allQueries.join('\n\n');
                            context.form_data['query'] = combinedQuery;
                            context.form_data['promql_query'] = combinedQuery; // Backward compat
                            context.form_data['extraction_method'] = 'monaco_api';
                            queryFound = true;
                            console.log(`[AI Agent] Γ£à Extracted via Monaco API: ${combinedQuery.substring(0, 100)}`);
                        }
                    }
                } catch (e) {
                    console.log('[AI Agent] Error accessing Monaco models:', e);
                }
            } else if (isBuilderMode) {
                console.log('[AI Agent] ΓÜá∩╕Å Builder mode detected - Monaco API extraction skipped');
            }

            // Strategy 2: Visual DOM Scraping (More Aggressive, with validation)
            if (!queryFound && !isBuilderMode) {
                console.log('[AI Agent] Trying visual DOM scraping...');

                // Try multiple selectors for Monaco Editor
                const selectors = [
                    '.monaco-editor .view-lines .view-line',  // Individual lines
                    '.monaco-editor .view-lines',             // Container
                    '[data-mprt="5"] .view-lines',           // Grafana specific
                    '[data-mprt="7"] .view-lines',           // Grafana specific (variant)
                    '.query-editor-row .monaco-editor',      // Query row
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
                        console.log(`[AI Agent] Selector "${selector}" found ${elements.length} elements, text: "${extractedText.substring(0, 50)}"`);

                        // Validate extracted query
                        if (extractedText.length > 1 && isValidQuery(extractedText)) {
                            context.form_data['query'] = extractedText;
                            context.form_data['promql_query'] = extractedText; // Backward compat
                            context.form_data['extraction_method'] = `dom_scrape:${selector}`;
                            queryFound = true;
                            console.log(`[AI Agent] Γ£à Extracted via DOM scraping (${selector}): ${extractedText.substring(0, 100)}`);
                            break;
                        } else if (extractedText.length > 0) {
                            console.log(`[AI Agent] ΓÜá∩╕Å Extracted text failed validation: "${extractedText}"`);
                        }
                    }
                }
            } else if (isBuilderMode && !queryFound) {
                console.log('[AI Agent] ΓÜá∩╕Å Builder mode detected - DOM scraping skipped');
            }

            // Strategy 3: Slate Editor (Prometheus Explore)
            if (!queryFound) {
                const slateLines = document.querySelectorAll('[data-slate-editor="true"]');
                if (slateLines.length > 0) {
                    let slateText = "";
                    slateLines.forEach(line => {
                        slateText += (line.innerText || line.textContent || '') + '\n';
                    });
                    slateText = slateText.trim();

                    if (slateText.length > 1 && isValidQuery(slateText)) {
                        context.form_data['query'] = slateText;
                        context.form_data['promql_query'] = slateText;
                        context.form_data['extraction_method'] = 'slate_editor';
                        queryFound = true;
                        console.log(`[AI Agent] Γ£à Extracted via Slate: ${slateText.substring(0, 100)}`);
                    }
                }
            }

            // Strategy 4: Textarea Fallback (with validation)
            if (!queryFound) {
                const textareas = document.querySelectorAll('textarea');
                console.log(`[AI Agent] Found ${textareas.length} textareas`);

                textareas.forEach((ta, idx) => {
                    if (ta.value && ta.value.trim().length > 0) {
                        console.log(`[AI Agent] Textarea ${idx}: "${ta.value.substring(0, 50)}..."`);

                        if (isValidQuery(ta.value)) {
                            context.form_data['query'] = ta.value.trim();
                            context.form_data['promql_query'] = ta.value.trim();
                            context.form_data['extraction_method'] = 'textarea';
                            queryFound = true;
                            console.log(`[AI Agent] Γ£à Extracted via textarea: ${ta.value.substring(0, 100)}`);
                        }
                    }
                });
            }

            // Strategy 5: Input fields (last resort, with validation)
            if (!queryFound) {
                const inputs = document.querySelectorAll('input[type="text"]');
                inputs.forEach((inp, idx) => {
                    if (inp.value && inp.value.trim().length > 2) {
                        if (isValidQuery(inp.value)) {
                            console.log(`[AI Agent] Found valid query in input ${idx}: ${inp.value}`);
                            if (!context.form_data['query']) {
                                context.form_data['query'] = inp.value.trim();
                                context.form_data['promql_query'] = inp.value.trim();
                                context.form_data['extraction_method'] = 'input_field';
                                queryFound = true;
                            }
                        }
                    }
                });
            }

            // Detect data source type (Prometheus, Loki, Tempo, Mimir)
            let dataSourceType = 'unknown';
            let queryLanguage = 'PromQL'; // Default

            // Check URL and UI elements for data source hints
            const urlPath = window.location.pathname + window.location.search;
            const pageText = document.body.innerText;

            if (urlPath.includes('datasource') || pageText.includes('Data source')) {
                // Try to detect from data source selector
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
            }

            // Fallback: detect from query syntax
            if (dataSourceType === 'unknown' && queryFound) {
                const query = context.form_data['query'] || '';
                if (query.includes('|') && (query.includes('|= ') || query.includes('|~ '))) {
                    dataSourceType = 'loki';
                    queryLanguage = 'LogQL';
                } else if (query.includes('trace') || query.includes('span')) {
                    dataSourceType = 'tempo';
                    queryLanguage = 'TraceQL';
                } else {
                    dataSourceType = 'prometheus'; // Default to Prometheus/Mimir
                    queryLanguage = 'PromQL';
                }
            }

            context.form_data['data_source_type'] = dataSourceType;
            context.form_data['query_language'] = queryLanguage;

            // Log final result
            if (queryFound) {
                console.log(`[AI Agent] Γ£à Query extracted successfully via ${context.form_data['extraction_method']}`);
                console.log(`[AI Agent] ≡ƒôè Data source: ${dataSourceType}, Query language: ${queryLanguage}`);
            } else {
                console.log('[AI Agent] Γ¥î No query found on page');
                context.form_data['query_extraction_failed'] = true;

                // Add helpful context about Builder mode
                if (isBuilderMode) {
                    context.form_data['builder_mode_detected'] = true;
                    console.log('[AI Agent] ≡ƒÆí TIP: Switch to Code mode for better query extraction');
                }
            }
        }

        return context;
    }

    async function sendMessage() {
        const text = input.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        input.value = '';
        showTyping();

        try {
            console.log('%c[RE-VIVE Widget] 🚀 Sending Query', 'color: #2196F3; font-weight: bold; font-size: 14px');
            console.log('User Query:', text);

            // Get page context using client-side tools if available
            let pageContext = null;
            let clientToolsUsed = false;

            if (window.reviveToolRegistry) {
                console.log('%c[RE-VIVE Widget] Using Client-Side Tools for Context', 'color: #4CAF50; font-weight: bold');

                const pageType = window.reviveToolRegistry.detectPageType();
                console.log('Detected Page Type:', pageType);

                const availableTools = window.reviveToolRegistry.getAvailableTools(pageType);
                console.log('Available Tools:', availableTools.map(t => t.name));

                // Execute page-specific tool based on page type
                let pageSpecificContext = null;

                try {
                    if (pageType === 'runbooks') {
                        console.log('%c[RE-VIVE Widget] Extracting Runbook Context...', 'color: #9C27B0; font-weight: bold');
                        pageSpecificContext = await window.reviveToolRegistry.execute('read_runbook_page');
                        console.log('Runbook Context:', pageSpecificContext);
                        clientToolsUsed = true;
                    } else if (pageType === 'alerts') {
                        console.log('%c[RE-VIVE Widget] Extracting Alert Context...', 'color: #FF5722; font-weight: bold');
                        pageSpecificContext = await window.reviveToolRegistry.execute('read_alert_page');
                        console.log('Alert Context:', pageSpecificContext);
                        clientToolsUsed = true;
                    } else if (pageType === 'panels' || pageType === 'grafana' || pageType === 'prometheus') {
                        console.log('%c[RE-VIVE Widget] Extracting PromQL Context...', 'color: #00BCD4; font-weight: bold');
                        pageSpecificContext = await window.reviveToolRegistry.execute('extract_promql_query');
                        console.log('PromQL Context:', pageSpecificContext);
                        clientToolsUsed = true;
                    }

                    // Always get generic page context
                    const genericContext = await window.reviveToolRegistry.execute('get_page_context');
                    console.log('Generic Context:', genericContext);

                    // Check if tool execution succeeded
                    if (!genericContext.success) {
                        throw new Error(genericContext.error || 'Failed to get page context');
                    }

                    // Combine contexts
                    pageContext = {
                        ...genericContext.result.data,
                        client_tools_available: true,
                        client_tools_used: clientToolsUsed,
                        page_specific_data: pageSpecificContext && pageSpecificContext.success ? pageSpecificContext.result.data : null
                    };

                } catch (toolError) {
                    console.error('%c[RE-VIVE Widget] Tool Execution Error:', 'color: #F44336; font-weight: bold', toolError);
                    // Fallback to old context extraction
                    pageContext = getPageContext();
                    pageContext.client_tools_available = false;
                    pageContext.client_tools_error = toolError.message;
                }
            } else {
                console.log('%c[RE-VIVE Widget] Client Tools Not Available - Using Legacy Context', 'color: #FF9800; font-weight: bold');
                pageContext = getPageContext();
                pageContext.client_tools_available = false;
            }

            const payload = {
                query: text,
                page_context: pageContext
            };

            if (sessionId) {
                payload.session_id = sessionId;
            }

            // LOG FULL PAYLOAD BEING SENT
            console.group('%c[RE-VIVE Widget] 📤 Payload Sent to Backend', 'color: #E91E63; font-weight: bold; font-size: 13px');
            console.log('Query:', payload.query);
            console.log('Session ID:', payload.session_id || 'none');
            console.log('Page Context:', payload.page_context);
            console.table({
                'Page Type': payload.page_context?.page_type || 'unknown',
                'Page Title': payload.page_context?.title || 'unknown',
                'Client Tools Used': payload.page_context?.client_tools_used ? 'YES' : 'NO',
                'Has Runbook Data': !!payload.page_context?.page_specific_data?.runbook_id,
                'Has Steps': payload.page_context?.page_specific_data?.steps?.length || 0,
                'Has PromQL Query': !!payload.page_context?.page_specific_data?.query
            });
            console.groupEnd();

            const response = await fetch('/api/revive/app/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error('Failed to get response');
            }

            const data = await response.json();

            // LOG RESPONSE FROM BACKEND
            console.group('%c[RE-VIVE Widget] 📥 Response from Backend', 'color: #00BCD4; font-weight: bold; font-size: 13px');
            console.log('Full Response:', data);
            console.log('Response Text Length:', data.response?.length || 0);
            console.groupEnd();

            // Update session ID if returned
            if (data.session_id) {
                sessionId = data.session_id;
                localStorage.setItem('ai_helper_session_id', sessionId); // Save to storage
            }

            removeTyping();

            // Extract the actual message content based on AIHelperResponse schema
            let aiText = "";

            // 0. Use direct response if available (Standard AI Helper format)
            if (data.response) {
                aiText = data.response;
            }
            // 1. Try to get a user-friendly message/explanation from action details
            else if (data.action_details) {
                if (data.action_details.message) {
                    aiText = data.action_details.message;
                } else if (data.action_details.explanation) {
                    aiText = data.action_details.explanation;
                }
            }

            // 2. If we have form fields, append them nicely
            if (data.action === 'suggest_form_values' && data.action_details && data.action_details.form_fields) {
                aiText += "\n\n**Suggested Values:**\n```json\n" + JSON.stringify(data.action_details.form_fields, null, 2) + "\n```";
            }

            // 3. Fallback to reasoning if text is still empty
            if (!aiText && data.reasoning) {
                aiText = data.reasoning;
            } else if (!aiText && data.action_details && Object.keys(data.action_details).length > 0) {
                // If no text but we have details, visualize them
                aiText = "Here are the details:\n\n```json\n" + JSON.stringify(data.action_details, null, 2) + "\n```";
            }

            if (!aiText) {
                aiText = "I processed your request but have no specific response to show.";
            }

            addMessage(aiText, 'ai', data.query_id);

        } catch (error) {
            console.error('%c[RE-VIVE Widget] ❌ Error:', 'color: #F44336; font-weight: bold; font-size: 14px', error);
            removeTyping();
            addMessage('Sorry, I encountered an error. Please try again.', 'ai');
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Resize Logic
    const resizeHandle = document.getElementById('agent-resize-handle');
    let isResizing = false;
    let startX, startWidth;

    if (resizeHandle) {
        resizeHandle.addEventListener('mousedown', initResize);
    }

    function initResize(e) {
        isResizing = true;
        startX = e.clientX;
        // startWidth = parseInt(document.defaultView.getComputedStyle(agentWindow).width, 10);
        // Instead of element width, we need the current variable or column width
        const rootStyles = getComputedStyle(document.documentElement);
        const currentVal = rootStyles.getPropertyValue('--ai-helper-width').trim();
        startWidth = parseInt(currentVal, 10) || 380; // Default fallback

        document.documentElement.addEventListener('mousemove', doResize);
        document.documentElement.addEventListener('mouseup', stopResize);

        // Prevent selection during resize
        document.body.style.userSelect = 'none';
        agentWindow.style.transition = 'none'; // Disable transition during drag
        appContainer.style.transition = 'none'; // Disable grid transition
    }

    function doResize(e) {
        if (!isResizing) return;

        // Calculate new width (drag left increases width)
        // delta is (startX - currentX) because we are dragging the left edge
        const newWidth = startWidth + (startX - e.clientX);

        // Min width 300px, Max width 800px or window width - 40px
        const maxWidth = Math.min(800, window.innerWidth - 300);

        if (newWidth >= 300 && newWidth <= maxWidth) {
            // agentWindow.style.width = newWidth + 'px';
            document.documentElement.style.setProperty('--ai-helper-width', `${newWidth}px`);
        }
    }

    function stopResize() {
        isResizing = false;
        document.documentElement.removeEventListener('mousemove', doResize);
        document.documentElement.removeEventListener('mouseup', stopResize);
        document.body.style.userSelect = '';
        agentWindow.style.transition = ''; // Restore transition
        appContainer.style.transition = ''; // Restore grid transition
    }

});
