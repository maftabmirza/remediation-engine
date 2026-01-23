/**
 * RE-VIVE Widget for Grafana Stack Pages (Docked Panel Design)
 * 
 * Matches the current RE-VIVE implementation: fixed right-side panel
 * that pushes the main content when opened.
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('RE-VIVE: DOMContentLoaded fired');
    console.log('RE-VIVE: window.self === window.top:', window.self === window.top);

    // Inject Widget HTML if not present
    if (!document.getElementById('agent-widget')) {
        console.log('RE-VIVE: Widget HTML not found, injecting...');
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
                            👋 Hi! I can help you understand this Grafana page, explain queries, or suggest improvements. What would you like to know?
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
        document.body.insertAdjacentHTML('beforeend', widgetHTML);
        console.log('RE-VIVE: Widget HTML injected');
    } else {
        console.log('RE-VIVE: Widget HTML already exists');
    }

    const agentWindow = document.getElementById('agent-window');
    const closeBtn = document.getElementById('agent-close');
    const input = document.getElementById('agent-input');
    const sendBtn = document.getElementById('agent-send');
    const messagesContainer = document.getElementById('agent-messages');

    let isOpen = false;
    let sessionId = getValidSessionId();

    function getValidSessionId() {
        let id = localStorage.getItem('revive_grafana_session_id');
        // Check if ID is a valid UUID v4
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

        if (id && !uuidRegex.test(id)) {
            console.warn('RE-VIVE: Invalid session ID format detected. Regenerating...');
            localStorage.removeItem('revive_grafana_session_id');
            id = null;
        }

        if (!id) {
            return generateSessionId();
        }
        return id;
    }

    function generateSessionId() {
        // Use crypto API if available for standard UUID
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            const id = crypto.randomUUID();
            localStorage.setItem('revive_grafana_session_id', id);
            return id;
        }

        // Fallback for older browsers (RFC4122)
        const id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
        localStorage.setItem('revive_grafana_session_id', id);
        return id;
    }

    function setOpen(nextOpen) {
        isOpen = !!nextOpen;
        if (isOpen) {
            agentWindow.classList.add('visible');
            document.body.classList.add('ai-helper-open');
            const widget = document.getElementById('agent-widget');
            if (widget) widget.style.pointerEvents = 'auto';

            // METHOD 1: Direct Resize of Parent Containers with !important
            // METHOD 1: Direct Resize of Parent Containers with !important
            // Since this script runs in the parent page, we can target the containers directly.
            // We use setProperty(..., 'important') to override any existing !important CSS.
            const containers = document.querySelectorAll('.grafana-container, .prometheus-container');
            containers.forEach(container => {
                container.style.setProperty('width', 'auto', 'important');
                container.style.setProperty('right', '380px', 'important');
            });

            // Still target body just in case
            document.body.style.setProperty('margin-right', '380px', 'important');
            document.body.style.setProperty('width', 'calc(100% - 380px)', 'important');

            // METHOD 3: Send message to parent (Redundant if running in parent, but safe)
            window.postMessage({ type: 'REVIVE_TOGGLE', isOpen: true }, '*');
            if (window.parent && window.parent !== window) {
                window.parent.postMessage({ type: 'REVIVE_TOGGLE', isOpen: true }, '*');
            }

            setTimeout(() => input?.focus(), 0);
        } else {
            agentWindow.classList.remove('visible');
            document.body.classList.remove('ai-helper-open');
            const widget = document.getElementById('agent-widget');
            if (widget) widget.style.pointerEvents = 'none';

            // RESTORE
            const containers = document.querySelectorAll('.grafana-container, .prometheus-container');
            containers.forEach(container => {
                // Restore to original width (controlled by CSS)
                // We remove the inline properties so CSS takes over
                container.style.removeProperty('width');
                container.style.removeProperty('right');
            });

            document.body.style.setProperty('margin-right', '0', 'important');
            document.body.style.setProperty('width', '100%', 'important');

            window.postMessage({ type: 'REVIVE_TOGGLE', isOpen: false }, '*');
            if (window.parent && window.parent !== window) {
                window.parent.postMessage({ type: 'REVIVE_TOGGLE', isOpen: false }, '*');
            }
        }
    }

    function toggleWindow() {
        console.log('RE-VIVE: toggleWindow() called, current isOpen:', isOpen);
        setOpen(!isOpen);
    }

    // Extract page context for Grafana
    function extractPageContext() {
        // Try getting iframe window/location
        let win = window;
        const iframe = document.getElementById('grafana-iframe') || document.getElementById('prometheus-iframe');
        if (iframe && iframe.contentWindow) {
            try {
                // Accessing location might throw if cross-origin, but we expect same-origin
                const iframeLoc = iframe.contentWindow.location;
                if (iframeLoc.href !== 'about:blank') {
                    win = iframe.contentWindow;
                }
            } catch (e) { }
        }

        const context = {
            page_type: 'grafana_stack',
            url: win.location.href,
            title: win.document.title || document.title,
            timestamp: new Date().toISOString()
        };

        // Detect specific page type using effectively "win"
        const path = win.location.pathname;
        const href = win.location.href;

        if (path.includes('prometheus') || path.includes('graph')) {
            context.page_type = 'prometheus';
            context.query = extractPrometheusQuery(win);
        } else if (path.includes('explore')) {
            if (href.includes('Loki')) {
                context.page_type = 'loki';
                context.query = extractLogQuery(win);
            } else if (href.includes('Tempo')) {
                context.page_type = 'tempo';
                context.query = extractTraceQuery(win);
            }
        } else if (path.includes('alerting') || path.includes('alerts')) {
            context.page_type = 'alertmanager';
            context.alerts = extractVisibleAlerts(); // Updated to handle iframe internally or pass doc?
            // extractVisibleAlerts handles getting doc internally.
        } else if (path.includes('dashboard') || path.includes('d/') || path.includes('grafana-advanced')) {
            context.page_type = 'grafana_dashboard';
            context.dashboard = extractDashboardInfo(); // extractDashboardInfo handles getting doc internally.

            // Check if we are in Edit Panel mode
            const urlParams = new URLSearchParams(win.location.search);
            if (urlParams.has('editPanel')) {
                // We are editing a panel, try to reading the query
                const query = extractPrometheusQuery(win);
                if (query) {
                    context.query = query;
                    console.log('RE-VIVE: Extracted query in Edit Panel mode:', query);
                }
            }
        }

        // Add visible text (sanitized and truncated)
        const visibleText = extractVisibleText();
        if (visibleText) {
            context.visible_content = visibleText.substring(0, 1500); // Increased limit
            console.log(`RE-VIVE: Extracted visible text length: ${visibleText.length} chars`);
        } else {
            console.warn('RE-VIVE: No visible text extracted from page/iframe');
        }

        console.log('RE-VIVE: Full Page Context:', context);
        return context;
    }

    function extractPrometheusQuery(win) {
        win = win || window;
        const urlParams = new URLSearchParams(win.location.search);
        let query = urlParams.get('g0.expr') || urlParams.get('expr') || null;

        if (!query) {
            // Try to extract from Monaco Editor (CodeMirror-like) lines in Edit View
            try {
                // Try standard Monaco view-lines first
                let editorLines = win.document.querySelectorAll('.monaco-editor .view-line');

                // Fallback: try Slate editor (newer Grafana versions use Slate for some inputs)
                if (editorLines.length === 0) {
                    editorLines = win.document.querySelectorAll('[data-slate-editor="true"]');
                }

                // Fallback: CodeMirror (older Grafana)
                if (editorLines.length === 0) {
                    editorLines = win.document.querySelectorAll('.CodeMirror-line');
                }

                if (editorLines.length > 0) {
                    const lines = [];
                    editorLines.forEach(line => lines.push(line.textContent.replace(/\u00A0/g, ' '))); // Replace &nbsp;
                    query = lines.join('\n').trim();
                    if (query) console.log('RE-VIVE: Extracted query from Editor:', query);
                }
            } catch (e) {
                console.warn('RE-VIVE: Failed to extract from Editor:', e);
            }
        }
        return query;
    }

    function extractLogQuery(win) {
        win = win || window;
        try {
            const urlHash = win.location.hash;
            if (urlHash.includes('expr')) {
                const match = urlHash.match(/"expr":"([^"]+)"/);
                return match ? decodeURIComponent(match[1]) : null;
            }
        } catch (e) {
            console.warn('Failed to extract log query:', e);
        }
        return null;
    }

    function extractTraceQuery(win) {
        win = win || window;
        try {
            const urlHash = win.location.hash;
            if (urlHash.includes('query')) {
                const match = urlHash.match(/"query":"([^"]+)"/);
                return match ? decodeURIComponent(match[1]) : null;
            }
        } catch (e) {
            console.warn('Failed to extract trace query:', e);
        }
        return null;
    }

    function extractVisibleAlerts() {
        // Try getting iframe document
        let doc = document;
        const iframe = document.getElementById('grafana-iframe');
        if (iframe && iframe.contentDocument) {
            try { doc = iframe.contentDocument; } catch (e) { }
        }

        const alerts = [];
        // Look for alert rows or cards in Grafana/Alertmanager UI
        doc.querySelectorAll('[class*="alert"], [role="alert"], .alert-rule-item').forEach(el => {
            const text = el.textContent.trim();
            if (text && text.length < 300) {
                alerts.push(text.replace(/\s+/g, ' '));
            }
        });
        return alerts.slice(0, 10);
    }

    function extractDashboardInfo() {
        // Try getting iframe document
        let doc = document;
        const iframe = document.getElementById('grafana-iframe');
        if (iframe && iframe.contentDocument) {
            try { doc = iframe.contentDocument; } catch (e) { }
        }

        const info = { name: doc.title || document.title };
        const panels = [];

        // Grafana usually puts panel titles in elements with specific classes
        // Adjust selectors based on Grafana version inspecting
        const selectors = [
            '.panel-title-text',
            '.panel-title',
            'h2',
            '[aria-label="Panel header title item"]'
        ];

        for (const selector of selectors) {
            if (panels.length > 0) break; // Found some with previous selector
            doc.querySelectorAll(selector).forEach(el => {
                const text = el.textContent.trim();
                if (text) panels.push(text);
            });
        }

        if (panels.length > 0) {
            info.panels = panels.slice(0, 15); // Increased limit
        }
        return info;
    }

    function extractVisibleText() {
        // Try to get content from the Grafana iframe first
        const iframe = document.getElementById('grafana-iframe') || document.getElementById('prometheus-iframe');
        let sourceDocument = document;

        if (iframe && iframe.contentDocument) {
            try {
                // Check if we can access the iframe content (Same-Origin check)
                const iframeDoc = iframe.contentDocument;
                if (iframeDoc && iframeDoc.body && iframeDoc.body.innerText.length > 50) {
                    sourceDocument = iframeDoc;
                    console.log('RE-VIVE: Successfully accessed iframe content');
                }
            } catch (e) {
                console.warn('RE-VIVE: Cannot access iframe content (Cross-Origin restricted):', e);
            }
        }

        const body = sourceDocument.body.cloneNode(true);
        body.querySelectorAll('script, style, noscript').forEach(el => el.remove());
        return body.textContent.trim().replace(/\s+/g, ' ');
    }

    function addMessage(text, type, queryId = null) {
        const div = document.createElement('div');
        div.className = `agent-message ${type}`;

        if (queryId) {
            div.dataset.queryId = queryId;
        }

        // Markdown parsing if marked is available
        if (typeof marked !== 'undefined') {
            div.innerHTML = marked.parse(text);
        } else {
            div.textContent = text;
        }

        messagesContainer.appendChild(div);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'agent-message ai typing-indicator';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    async function sendQuery(query) {
        addMessage(query, 'user');
        showTypingIndicator();

        try {
            const context = extractPageContext();

            const response = await fetch('/api/revive/grafana/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({
                    query: query,
                    page_context: context,
                    session_id: sessionId
                })
            });

            hideTypingIndicator();

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            addMessage(data.response, 'ai', data.query_id);

        } catch (error) {
            hideTypingIndicator();
            addMessage('Sorry, I encountered an error. Please try again.', 'ai');
            console.error('RE-VIVE query error:', error);
        }
    }

    // Event listeners
    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            setOpen(false);
        });
    }

    function handleSend() {
        const query = input.value.trim();
        if (query) {
            sendQuery(query);
            input.value = '';
        }
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', handleSend);
    }

    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSend();
            }
        });
    }

    // Add toggle button to top of Grafana iframe (if in iframe context)
    // This will be visible when looking at the Grafana page
    // Add toggle button to top of Grafana iframe (if in iframe context)
    // This will be visible when looking at the Grafana page
    if (window.self !== window.top) {
        // Check if the parent already has a toggle (e.g. we are in the AIOps wrapper)
        let parentHasToggle = false;
        try {
            if (window.parent && window.parent.document.getElementById('ai-helper-toggle')) {
                parentHasToggle = true;
                console.log('RE-VIVE: Detected parent wrapper, suppressing duplicate toggle button');
            }
        } catch (e) {
            // Cross-origin, cannot check parent. Assume standalone or external embed.
        }

        if (!parentHasToggle) {
            // We're in an iframe without a parent controller - add a floating toggle button
            const toggleBtn = document.createElement('button');
            toggleBtn.id = 'grafana-ai-toggle';
            toggleBtn.className = 'grafana-ai-toggle';
            toggleBtn.innerHTML = '<i class="fas fa-robot"></i> RE-VIVE';
            toggleBtn.onclick = toggleWindow;
            document.body.appendChild(toggleBtn);
        }
    }

    // Bind to the global header toggle button (if present)
    console.log('RE-VIVE: Looking for #ai-helper-toggle button...');
    const headerToggle = document.getElementById('ai-helper-toggle');
    console.log('RE-VIVE: Header toggle found:', !!headerToggle);
    if (headerToggle) {
        console.log('RE-VIVE: Attaching click listener to header toggle');
        headerToggle.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('RE-VIVE: Header toggle clicked!');
            toggleWindow();
        });
        console.log('RE-VIVE: Header toggle listener attached successfully');
    } else {
        console.warn('RE-VIVE: Header toggle button NOT found in DOM');
    }

    // Keyboard shortcut: Ctrl+Shift+A to toggle
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === 'A') {
            e.preventDefault();
            toggleWindow();
        }
    });

    // Handle resize
    const resizeHandle = document.getElementById('agent-resize-handle');
    let isResizing = false;

    if (resizeHandle) {
        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            document.body.style.cursor = 'ew-resize';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            const width = window.innerWidth - e.clientX;
            if (width > 300 && width < 800) {
                document.documentElement.style.setProperty('--ai-helper-width', width + 'px');

                // Real-time resize
                const containers = document.querySelectorAll('.grafana-container, .prometheus-container');
                containers.forEach(container => {
                    container.style.setProperty('width', 'auto', 'important');
                    container.style.setProperty('right', width + 'px', 'important');
                });
            }
        });

        document.addEventListener('mouseup', () => {
            isResizing = false;
            document.body.style.cursor = '';
        });
    }

    // LISTENER FOR PARENT WINDOW COMMANDS
    window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'REVIVE_TOGGLE_CMD') {
            toggleWindow();
        }
    });
});
