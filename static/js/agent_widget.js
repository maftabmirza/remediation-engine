
document.addEventListener('DOMContentLoaded', () => {
    // Inject Widget HTML if not present
    if (!document.getElementById('agent-widget')) {
        const widgetHTML = `
            <div id="agent-widget">
                <div id="agent-window">
                    <div id="agent-resize-handle" class="resize-handle"></div>
                    <div class="agent-header">
                        <div class="flex items-center gap-2">
                            <div class="w-2 h-2 rounded-full bg-green-400"></div>
                            <span class="font-semibold text-white">AI Assistant</span>
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
                <button id="agent-fab">
                    <i class="fas fa-robot text-white text-xl"></i>
                </button>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', widgetHTML);
    }

    const fab = document.getElementById('agent-fab');
    const agentWindow = document.getElementById('agent-window');
    const closeBtn = document.getElementById('agent-close');
    const input = document.getElementById('agent-input');
    const sendBtn = document.getElementById('agent-send');
    const messagesContainer = document.getElementById('agent-messages');

    let isOpen = false;
    let sessionId = localStorage.getItem('ai_helper_session_id'); // Load from storage

    function toggleWindow() {
        isOpen = !isOpen;
        if (isOpen) {
            agentWindow.classList.add('visible');
            input.focus();
        } else {
            agentWindow.classList.remove('visible');
        }
    }

    function addMessage(text, type) {
        const div = document.createElement('div');
        div.className = `agent-message ${type}`;
        // Simple markdown parsing if marked is available
        if (typeof marked !== 'undefined') {
            div.innerHTML = marked.parse(text);
        } else {
            div.textContent = text;
        }
        messagesContainer.appendChild(div);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
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
            visible_content: {}
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

        // Extract form data if a modal is open
        const modal = document.querySelector('.fixed:not(.hidden)');
        if (modal) {
            // Get all input fields
            const inputs = modal.querySelectorAll('input:not([type="hidden"]), textarea, select');
            inputs.forEach(input => {
                const label = input.id || input.name;
                if (label && input.value) {
                    context.form_data[label] = input.value;
                }
            });

            // Special handling for CodeMirror editors (PromQL query)
            const cmEditors = modal.querySelectorAll('.CodeMirror');
            cmEditors.forEach((cm, idx) => {
                if (cm.CodeMirror) {
                    const query = cm.CodeMirror.getValue();
                    if (query) {
                        context.form_data['promql_query'] = query;
                    }
                }
            });
        }

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

            // Try to read textual queries from Monaco Editor (New Grafana)
            // Try getting content from Monaco Editor (Global)
            if (window.monaco && window.monaco.editor) {
                try {
                    const models = window.monaco.editor.getModels();
                    if (models.length > 0) {
                        // Filter for likely query models (non-empty)
                        const relevantModels = models.filter(m => m.getValue().trim().length > 0);
                        // Enhance: Join with separator to distinguish multiple queries if present
                        const code = relevantModels.map(m => m.getValue()).join('\n\n---\n\n');

                        // We relax the check: if there is ANY code, we take it.
                        if (code && code.trim().length > 0) {
                            context.form_data['monaco_query'] = code;
                            context.form_data['promql_query'] = code;
                        }
                    }
                } catch (e) {
                    console.log('Error accessing Monaco models:', e);
                }
            }

            // Fallback: Scrape text from Monaco DOM lines (Visual scraping)
            // Only runs if we haven't found a query yet from the official API
            if (!context.form_data['promql_query']) {
                const monacoLines = document.querySelectorAll('.monaco-editor .view-lines');
                let fullText = "";
                monacoLines.forEach(lines => {
                    fullText += lines.innerText + "\n";
                    // Add newline after each line div
                });

                // Also check for Slate editor (used in some explore/prometheus views)
                if (!fullText) {
                    const slateLines = document.querySelectorAll('[data-slate-editor="true"]');
                    slateLines.forEach(line => {
                        fullText += line.innerText + "\n";
                    });
                }

                // Generous check: If we have > 2 chars, it might be a query (e.g. "up")
                if (fullText && fullText.trim().length > 2) {
                    context.form_data['promql_query'] = fullText.trim();
                }
            }

            // General textarea fallback
            const textareas = document.querySelectorAll('textarea');
            textareas.forEach(ta => {
                if (ta.value && (ta.value.includes('rate(') || ta.value.includes('{') || ta.value.length > 10)) {
                    context.form_data['potential_promql'] = ta.value;
                }
            });
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
            const payload = {
                query: text,
                page_context: getPageContext()
            };

            if (sessionId) {
                payload.session_id = sessionId;
            }

            const response = await fetch('/api/ai-helper/query', {
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

            // Update session ID if returned
            if (data.session_id) {
                sessionId = data.session_id;
                localStorage.setItem('ai_helper_session_id', sessionId); // Save to storage
            }

            removeTyping();

            // Extract the actual message content based on AIHelperResponse schema
            let aiText = "";

            // 1. Try to get a user-friendly message/explanation
            if (data.action_details) {
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
            } else if (!aiText) {
                aiText = "I processed your request but have no specific response to show.";
            }

            addMessage(aiText, 'ai');

        } catch (error) {
            console.error('AI Error:', error);
            removeTyping();
            addMessage('Sorry, I encountered an error. Please try again.', 'ai');
        }
    }

    fab.addEventListener('click', toggleWindow);
    closeBtn.addEventListener('click', toggleWindow);

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
        startWidth = parseInt(document.defaultView.getComputedStyle(agentWindow).width, 10);

        document.documentElement.addEventListener('mousemove', doResize);
        document.documentElement.addEventListener('mouseup', stopResize);

        // Prevent selection during resize
        document.body.style.userSelect = 'none';
        agentWindow.style.transition = 'none'; // Disable transition during drag
    }

    function doResize(e) {
        if (!isResizing) return;

        // Calculate new width (drag left increases width)
        // delta is (startX - currentX) because we are dragging the left edge
        const newWidth = startWidth + (startX - e.clientX);

        // Min width 300px, Max width 800px or window width - 40px
        const maxWidth = Math.min(800, window.innerWidth - 40);

        if (newWidth >= 300 && newWidth <= maxWidth) {
            agentWindow.style.width = newWidth + 'px';
        }
    }

    function stopResize() {
        isResizing = false;
        document.documentElement.removeEventListener('mousemove', doResize);
        document.documentElement.removeEventListener('mouseup', stopResize);
        document.body.style.userSelect = '';
        agentWindow.style.transition = ''; // Restore transition
    }

});
