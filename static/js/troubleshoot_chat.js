/**
 * Standalone AI Chat Page JavaScript
 * Provides AI chat and terminal functionality without alert context
 */

// Global state
let chatSocket = null;
let terminalSocket = null;
var currentSessionId = null;
let currentSession = null;
let term = null;
let fitAddon = null;
let availableProviders = [];
let commandHistory = [];
const MAX_HISTORY_SIZE = 50;
let lastMessageRole = null;
let currentMessageDiv = null;
// chatFontSize and termFontSize removed/handled by AIChatBase
let currentServerId = null;
let currentServerProtocol = 'ssh';
let storedServers = [];
let isAgentMode = false;
let agentSocket = null;
let currentAgentSession = null;
let inlineChatVisible = false;
let currentSelection = '';
let analysisButton = null;
let autoAnalyzeTimer = null;
let pendingCommandCancelled = false;  // Flag to cancel pending command polling
let currentStreamController = null;   // AbortController for streaming requests
let isStreaming = false;              // Flag to track if streaming is active

// Command Queue for multiple command suggestions
let commandQueue = [];        // Array of {id, server, command, explanation, status, output, exitCode}
let commandQueueContainerId = null;  // ID of the container holding the command queue

// Reasoning panel state
let reasoningHistory = [];  // Store reasoning steps
let reasoningPanelVisible = true;

// Command History Functions
function addToCommandHistory(command, output, exitCode, success) {
    const entry = {
        id: Date.now(),
        command: command,
        output: output,
        exitCode: exitCode,
        success: success,
        timestamp: new Date().toISOString(),
        displayTime: new Date().toLocaleTimeString()
    };
    commandHistory.unshift(entry);
    if (commandHistory.length > MAX_HISTORY_SIZE) {
        commandHistory = commandHistory.slice(0, MAX_HISTORY_SIZE);
    }
    updateCommandHistoryPanel();
    updateHistoryCount();
    return entry;
}

function getCommandHistoryContext() {
    if (commandHistory.length === 0) return '';
    const recentCommands = commandHistory.slice(0, 10);
    let context = '\n\n[COMMAND HISTORY - Recent commands executed in this session]\n';
    recentCommands.forEach((entry, index) => {
        const status = entry.success ? '✓' : '✗';
        const outputPreview = entry.output ? entry.output.substring(0, 200) : '(no output)';
        context += `${index + 1}. [${status}] ${entry.command} (exit: ${entry.exitCode})\n`;
        if (entry.output) {
            context += `   Output: ${outputPreview}${entry.output.length > 200 ? '...' : ''}\n`;
        }
    });
    return context;
}

function toggleCommandHistory() {
    const panel = document.getElementById('commandHistoryPanel');
    if (!panel) return;
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) {
        updateCommandHistoryPanel();
    }
}

function clearCommandHistory() {
    commandHistory = [];
    updateCommandHistoryPanel();
    showToast('Command history cleared', 'success');
}

function updateHistoryCount() {
    const countEl = document.getElementById('historyCount');
    if (countEl) {
        countEl.textContent = commandHistory.length;
    }
}

function updateCommandHistoryPanel() {
    const panel = document.getElementById('commandHistoryPanel');
    if (!panel) return;
    const listEl = panel.querySelector('.history-list');
    if (!listEl) return;
    if (commandHistory.length === 0) {
        listEl.innerHTML = '<p class="text-gray-500 text-sm text-center py-4">No commands executed yet</p>';
        return;
    }
    listEl.innerHTML = commandHistory.slice(0, 20).map(entry => `
        <div class="history-item bg-gray-800 rounded p-2 mb-2 group hover:bg-gray-700 transition-colors">
            <div class="flex items-center justify-between">
                <div class="flex items-center flex-1 min-w-0">
                    <i class="fas ${entry.success ? 'fa-check-circle text-green-400' : 'fa-times-circle text-red-400'} mr-2 flex-shrink-0"></i>
                    <span class="font-mono text-xs text-gray-300 truncate">${escapeHtml(entry.command)}</span>
                </div>
                <div class="flex items-center space-x-1 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button data-cmd="${escapeHtml(entry.command)}" onclick="rerunCommand(this.dataset.cmd)" class="text-blue-400 hover:text-blue-300 text-xs px-1" title="Re-run"><i class="fas fa-redo"></i></button>
                    <button data-cmd="${escapeHtml(entry.command)}" onclick="copyToClipboard(this.dataset.cmd)" class="text-gray-400 hover:text-white text-xs px-1" title="Copy"><i class="fas fa-copy"></i></button>
                </div>
            </div>
            <div class="text-[10px] text-gray-500 mt-1">${entry.displayTime} • exit ${entry.exitCode}</div>
        </div>
    `).join('');
}

// ============= REASONING PANEL =============

function initReasoningPanel() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages || document.getElementById('reasoningPanel')) {
        return; // Already exists or can't create
    }

    const panel = document.createElement('div');
    panel.id = 'reasoningPanel';
    panel.className = 'reasoning-panel hidden bg-gray-900 border border-gray-700 rounded-lg mb-4';
    panel.innerHTML = `
        <div class="reasoning-header flex justify-between items-center p-2 border-b border-gray-700 cursor-pointer" 
             onclick="toggleReasoningPanel()">
            <span class="text-sm font-medium text-gray-300">
                <i class="fas fa-brain mr-2 text-purple-400"></i>AI Reasoning
            </span>
            <i class="fas fa-chevron-down text-gray-500" id="reasoningToggleIcon"></i>
        </div>
        <div class="reasoning-body p-3 max-h-64 overflow-y-auto" id="reasoningBody">
            <div class="text-gray-500 text-sm">Waiting for investigation to start...</div>
        </div>
    `;

    chatMessages.parentElement.insertBefore(panel, chatMessages);
}

function toggleReasoningPanel() {
    const panel = document.getElementById('reasoningPanel');
    const icon = document.getElementById('reasoningToggleIcon');
    if (!panel) return;

    reasoningPanelVisible = !reasoningPanelVisible;

    if (reasoningPanelVisible) {
        panel.classList.remove('collapsed');
        icon.className = 'fas fa-chevron-down text-gray-500';
    } else {
        panel.classList.add('collapsed');
        icon.className = 'fas fa-chevron-right text-gray-500';
    }
}

function handleReasoningEvent(data) {
    reasoningHistory.push(data);
    renderReasoningSteps();

    // Show panel if hidden
    const panel = document.getElementById('reasoningPanel');
    if (panel && panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
    }
}

function renderReasoningSteps() {
    const body = document.getElementById('reasoningBody');
    if (!body) return;

    const phaseIcons = {
        'identify': '🔍',
        'verify': '✅',
        'investigate': '📊',
        'plan': '🧠',
        'act': '🛠️'
    };

    const phaseTitles = {
        'identify': 'Identify',
        'verify': 'Verify',
        'investigate': 'Investigate',
        'plan': 'Plan',
        'act': 'Act'
    };

    const phaseColors = {
        'identify': 'border-blue-500',
        'verify': 'border-green-500',
        'investigate': 'border-yellow-500',
        'plan': 'border-purple-500',
        'act': 'border-pink-500'
    };

    const currentPhase = reasoningHistory.length > 0 ? reasoningHistory[reasoningHistory.length - 1].phase : null;

    body.innerHTML = reasoningHistory.map((step, i) => {
        const isCurrent = step.phase === currentPhase && i === reasoningHistory.length - 1;
        const icon = phaseIcons[step.phase] || '❓';
        const title = phaseTitles[step.phase] || step.phase;
        const borderColor = phaseColors[step.phase] || 'border-gray-500';

        return `
            <div class="reasoning-step ${isCurrent ? 'current' : ''} mb-3 pl-4 border-l-2 ${borderColor}">
                <div class="flex items-center text-xs font-medium mb-1">
                    <span class="mr-2">${icon}</span>
                    <span>${title}</span>
                    ${isCurrent ? '<span class="ml-2 text-blue-400">← Current</span>' : ''}
                </div>
                ${step.thought ? `<div class="text-gray-400 text-xs italic mb-1">"${escapeHtml(step.thought)}"</div>` : ''}
                ${step.tool ? `
                    <div class="text-xs mt-1">
                        <span class="text-yellow-400">Tool:</span> <code class="text-green-400">${escapeHtml(step.tool)}</code>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');

    // Auto-scroll to bottom
    body.scrollTop = body.scrollHeight;
}

function resetReasoningPanel() {
    reasoningHistory = [];
    const body = document.getElementById('reasoningBody');
    if (body) {
        body.innerHTML = '<div class="text-gray-500 text-sm">Waiting for investigation to start...</div>';
    }
    const panel = document.getElementById('reasoningPanel');
    if (panel) {
        panel.classList.add('hidden');
    }
}

// Font Size Controls
function adjustChatFont(delta) {
    AIChatBase.adjustChatFont(delta);
}

function adjustTermFont(delta) {
    if (!term) return;
    const newSize = Math.max(8, Math.min(24, term.options.fontSize + delta));
    term.options.fontSize = newSize;
    fitAddon.fit();
}

// Chat Session Management
function getTroubleshootContextFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const rawContext = params.get('context');
    if (!rawContext) return null;

    try {
        const parsed = JSON.parse(rawContext);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (error) {
        try {
            const parsed = JSON.parse(decodeURIComponent(rawContext));
            return parsed && typeof parsed === 'object' ? parsed : null;
        } catch (decodeError) {
            console.warn('Failed to parse troubleshoot context from URL', decodeError);
            return null;
        }
    }
}

function clearTroubleshootContextFromUrl() {
    const params = new URLSearchParams(window.location.search);
    if (!params.has('context')) return;
    params.delete('context');
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash || ''}`;
    window.history.replaceState({}, document.title, nextUrl);
}

function buildIncidentPrefillPrompt(context) {
    const lines = ['Please troubleshoot this incident:'];

    if (context.title) {
        lines.push(`Title: ${context.title}`);
    }
    if (context.description) {
        lines.push(`Description: ${context.description}`);
    }
    if (context.service) {
        lines.push(`Service: ${context.service}`);
    }
    if (context.id) {
        lines.push(`Incident ID: ${context.id}`);
    }

    lines.push('Suggest investigation steps and the first safe command to run.');
    return lines.join('\n');
}

function prefillIncidentContext(context) {
    const input = document.getElementById('chatInput');
    if (!input) return;

    const prompt = buildIncidentPrefillPrompt(context);
    input.value = prompt;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();

    const titleEl = document.getElementById('currentSessionTitle');
    if (titleEl && context.title) {
        titleEl.textContent = `Incident: ${context.title}`;
    }

    // Auto-send the prefilled message after a short delay so the UI settles
    setTimeout(() => {
        const form = document.getElementById('chatForm');
        if (form) {
            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }
    }, 600);
}

async function initChatSession() {
    try {
        await loadAvailableProviders();

        const troubleshootContext = getTroubleshootContextFromUrl();
        const shouldForceNewSession = !!troubleshootContext;

        if (shouldForceNewSession) {
            // Force a brand-new session when arriving from incident page
            let newSession;
            try {
                const createResponse = await apiCall('/api/troubleshoot/sessions', {
                    method: 'POST',
                    body: JSON.stringify({})
                });
                // apiCall may return raw Response (troubleshoot template) or parsed JSON (base.html)
                if (createResponse && typeof createResponse.ok !== 'undefined') {
                    // Raw Response object
                    if (!createResponse.ok) throw new Error('Failed to create session (HTTP ' + createResponse.status + ')');
                    newSession = await createResponse.json();
                } else {
                    // Already-parsed JSON
                    newSession = createResponse;
                }
            } catch (fetchErr) {
                console.error('Session creation failed, retrying with fetch:', fetchErr);
                const fallback = await fetch('/api/troubleshoot/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                if (!fallback.ok) throw new Error('Failed to create incident troubleshoot session');
                newSession = await fallback.json();
            }
            currentSession = newSession;
            currentSessionId = currentSession.id;
            clearTroubleshootContextFromUrl();
            console.log('Created new incident troubleshoot session:', currentSessionId);
        } else {
            // Get or create standalone session
            const response = await apiCall('/api/troubleshoot/sessions/standalone');

            if (response.ok) {
                currentSession = await response.json();
                currentSessionId = currentSession.id;
                console.log('Using chat session:', currentSessionId);
            } else {
                // Fallback: create new session
                const createResponse = await apiCall('/api/troubleshoot/sessions', {
                    method: 'POST',
                    body: JSON.stringify({})
                });
                if (!createResponse.ok) throw new Error('Failed to create chat session');
                currentSession = await createResponse.json();
                currentSessionId = currentSession.id;
            }
        }

        updateModelSelector();

        // Skip loading history if in General Inquiry mode to prevent overwriting
        if (typeof currentChatMode !== 'undefined' && currentChatMode === 'general') {
            console.log('Skipping troubleshoot history load (Inquiry Mode active)');
            // Still connect WebSocket for status updates if needed, checking logic inside connectChatWebSocket
        } else {
            await loadMessageHistory(currentSession.id);
        }

        connectChatWebSocket(currentSession.id);

        if (shouldForceNewSession && troubleshootContext) {
            // Show welcome then immediately prefill and auto-send incident context
            showWelcomeScreen();
            prefillIncidentContext(troubleshootContext);
            showToast('New incident troubleshooting session started', 'info');
        }
    } catch (error) {
        console.error('Chat init failed:', error);
        showToast('Failed to initialize chat', 'error');
    }
}

async function loadAvailableProviders() {
    try {
        // Show connecting status
        updateModelStatusIcon('connecting');

        const response = await apiCall('/api/troubleshoot/providers');
        if (!response.ok) throw new Error('Failed to load providers');
        availableProviders = await response.json();

        // Use new dropdown if available, fallback to legacy select
        if (typeof populateModelDropdown === 'function') {
            populateModelDropdown(availableProviders);
        } else {
            // Legacy select element fallback
            const selector = document.getElementById('modelSelector');
            if (selector) {
                if (availableProviders.length === 0) {
                    selector.innerHTML = '<option value="">No providers configured</option>';
                } else {
                    selector.innerHTML = availableProviders.map(p =>
                        `<option value="${p.id}">${p.provider_name}${p.is_default ? ' ⭐' : ''}</option>`
                    ).join('');
                }
            }
        }
        updateModelStatusIcon('connected');
    } catch (error) {
        console.error('Failed to load providers:', error);
        updateModelStatusIcon('disconnected');
    }
}

function updateModelSelector() {
    // Set selected model ID for new dropdown
    if (currentSession && currentSession.llm_provider_id) {
        if (typeof selectedModelId !== 'undefined') {
            selectedModelId = currentSession.llm_provider_id;
        }
        // Update tooltip with model name
        const provider = availableProviders.find(p => p.id === currentSession.llm_provider_id);
        if (provider) {
            const btn = document.getElementById('llmIconBtn');
            if (btn) btn.title = `LLM: ${provider.provider_name || provider.name}`;
        }
    } else {
        const defaultProvider = availableProviders.find(p => p.is_default);
        if (defaultProvider) {
            if (typeof selectedModelId !== 'undefined') {
                selectedModelId = defaultProvider.id;
            }
            const btn = document.getElementById('llmIconBtn');
            if (btn) btn.title = `LLM: ${defaultProvider.provider_name || defaultProvider.name}`;
        }
    }
}

function updateModelStatusIcon(status) {
    const iconWrap = document.getElementById('llmIconStatus');
    const dot = document.getElementById('llmStatusDot');
    const badge = document.getElementById('llmStatusBadge');
    const statusClasses = ['ts-llm-icon-connected', 'ts-llm-icon-disconnected', 'ts-llm-icon-connecting'];

    // Icon color: green when connected, red/warning when not
    if (iconWrap) {
        iconWrap.classList.remove(...statusClasses);
        iconWrap.classList.add(status === 'connected' ? 'ts-llm-icon-connected' :
            status === 'disconnected' ? 'ts-llm-icon-disconnected' : 'ts-llm-icon-connecting');
    }
    if (dot) {
        dot.classList.remove('ts-llm-status-connected', 'ts-llm-status-disconnected', 'ts-llm-status-connecting');
        dot.title = status === 'connected' ? 'Connected' : status === 'disconnected' ? 'Disconnected' : 'Connecting';
        dot.classList.add(status === 'connected' ? 'ts-llm-status-connected' :
            status === 'disconnected' ? 'ts-llm-status-disconnected' : 'ts-llm-status-connecting');
    }
    if (badge) {
        const labels = { connected: 'Connected', disconnected: 'Disconnected', connecting: 'Connecting' };
        badge.textContent = labels[status] || 'Connecting';
        badge.className = 'ts-llm-status-badge ts-llm-status-badge-' + status;
    }
}

async function switchModel(providerId) {
    if (!currentSessionId || !providerId) return;
    try {
        const response = await apiCall(`/api/troubleshoot/sessions/${currentSessionId}/provider`, {
            method: 'PATCH',
            body: JSON.stringify({ provider_id: providerId })
        });
        if (!response.ok) throw new Error('Failed to switch model');
        const result = await response.json();
        showToast(`Switched to ${result.provider_name} - ${result.model_name}`, 'success');
        const container = document.getElementById('chatMessages');
        const msg = document.createElement('div');
        msg.className = 'text-center text-xs text-gray-500 my-2 italic';
        msg.innerHTML = `<i class="fas fa-sync-alt mr-1"></i>Now using: ${result.provider_name} - ${result.model_name}`;
        container.appendChild(msg);
        container.scrollTop = container.scrollHeight;
        currentSession.llm_provider_id = providerId;
    } catch (error) {
        console.error('Failed to switch model:', error);
        showToast('Failed to switch model', 'error');
    }
}

async function loadMessageHistory(sessionId) {
    try {
        const response = await apiCall(`/api/troubleshoot/sessions/${sessionId}/messages`);
        if (!response.ok) throw new Error('Failed to load history');
        const data = await response.json();
        
        // Handle both old format (array) and new format (object with messages + pii_mapping)
        const messages = Array.isArray(data) ? data : (data.messages || []);
        const piiMapping = data.pii_mapping || {};
        
        // Store PII mapping for de-anonymization
        if (Object.keys(piiMapping).length > 0) {
            window.currentPiiMapping = piiMapping;
            console.log('🔍 PII: Loaded mapping for de-anonymization:', Object.keys(piiMapping).length, 'entries');
        }
        
        const container = document.getElementById('chatMessages');
        container.innerHTML = '';
        if (messages.length === 0) {
            showWelcomeScreen();
            return;
        }
        messages.forEach(msg => {
            // De-anonymize content for user display (replace placeholders with original values)
            let displayContent = msg.content;
            if (piiMapping && Object.keys(piiMapping).length > 0) {
                for (const [placeholder, original] of Object.entries(piiMapping)) {
                    displayContent = displayContent.split(placeholder).join(original);
                }
            }
            
            if (msg.role === 'user') {
                AIChatBase.appendUserMessage(displayContent);
            } else if (msg.role === 'assistant') {
                AIChatBase.appendAIMessage(displayContent, {
                    skipRunButtons: true,
                    messageId: msg.id
                });
            }
        });
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Failed to load chat history:', error);
        showWelcomeScreen();
    }
}

function showWelcomeScreen() {
    AIChatBase.showWelcomeScreen(
        "Troubleshoot Console",
        "Connect to a server and ask me anything to start investigation.",
        [
            { text: "What can you help me with?", icon: "fas fa-question-circle" },
            { text: "How do I check disk space on a Linux server?", icon: "fas fa-terminal" },
            { text: "Show me common troubleshooting commands", icon: "fas fa-wrench" },
            { text: "Explain how to analyze server logs", icon: "fas fa-file-alt" }
        ]
    );
}

function sendSuggestion(text) {
    const input = document.getElementById('chatInput');
    input.value = text;
    sendMessage(new Event('submit'));
}

// WebSocket Chat Connection
let wsReconnectAttempts = 0;
const MAX_WS_RECONNECT_ATTEMPTS = 3;

function connectChatWebSocket(sessionId) {
    // Skip WebSocket if we've exceeded max attempts - chat works via REST API
    if (wsReconnectAttempts >= MAX_WS_RECONNECT_ATTEMPTS) {
        console.log('WebSocket disabled - using REST API for chat');
        updateModelStatusIcon('connected'); // Show as connected since REST works
        return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('token');
    if (!token) {
        // Don't show error - just skip WebSocket, REST will still work
        console.log('No token for WebSocket, using REST API');
        return;
    }

    try {
        chatSocket = new WebSocket(`${protocol}//${window.location.host}/ws/chat/${sessionId}?token=${token}`);
        chatSocket.onopen = () => {
            wsReconnectAttempts = 0; // Reset on successful connection
            updateModelStatusIcon('connected');
        };
        chatSocket.onmessage = (event) => {
            const msg = event.data;
            if (msg === '[DONE]') return;
            appendAIMessage(msg);
        };
        chatSocket.onerror = () => {
            wsReconnectAttempts++;
            console.log(`WebSocket error (attempt ${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})`);
        };
        chatSocket.onclose = () => {
            updateModelStatusIcon('connected'); // Still show connected - REST works
            // Only reconnect if under max attempts
            if (wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS && currentSessionId) {
                setTimeout(() => {
                    connectChatWebSocket(currentSessionId);
                }, 5000); // Increase delay to 5 seconds
            }
        };
    } catch (e) {
        console.log('WebSocket not available, using REST API');
        wsReconnectAttempts = MAX_WS_RECONNECT_ATTEMPTS;
    }
}

function appendAIMessage(text, skipRunButtons = false) {
    removeTypingIndicator();
    const container = document.getElementById('chatMessages');

    // Handle PROGRESS events
    const progressRegex = /\[PROGRESS\](.*?)\[\/PROGRESS\]/g;
    let progressMatch;
    while ((progressMatch = progressRegex.exec(text)) !== null) {
        try {
            const progressData = JSON.parse(progressMatch[1]);
            if (typeof handleProgressEvent === 'function') {
                handleProgressEvent(progressData);
            }
        } catch (e) {
            console.error('Failed to parse PROGRESS event:', e);
        }
    }

    // Handle REASONING events
    const reasoningRegex = /\[REASONING\](.*?)\[\/REASONING\]/g;
    let reasoningMatch;
    while ((reasoningMatch = reasoningRegex.exec(text)) !== null) {
        try {
            const reasoningData = JSON.parse(reasoningMatch[1]);
            if (typeof handleReasoningEvent === 'function') {
                handleReasoningEvent(reasoningData);
            }
        } catch (e) {
            console.error('Failed to parse REASONING event:', e);
        }
    }

    // Check for CMD_CARD markers and extract them (but don't render yet)
    const cmdCardRegex = /\[CMD_CARD\](.*?)\[\/CMD_CARD\]/g;
    let match;
    let hasCards = false;
    let extractedCommands = [];
    let cardDataList = [];  // Store cards to render AFTER text

    // Block tool names being suggested as shell commands (AI hallucination)
    const toolNames = [
        'query_grafana_metrics', 'query_grafana_logs', 'get_recent_changes',
        'get_similar_incidents', 'search_knowledge', 'get_correlated_alerts',
        'get_service_dependencies', 'get_feedback_history', 'get_alert_details',
        'get_proven_solutions', 'suggest_ssh_command'
    ];

    while ((match = cmdCardRegex.exec(text)) !== null) {
        try {
            const cardData = JSON.parse(match[1]);
            // Skip if the command is a tool name (AI hallucination)
            const cmdBase = (cardData.command || '').trim().split(/\s+/)[0];
            if (toolNames.includes(cmdBase)) {
                console.warn('Skipping CMD_CARD with tool name as command:', cmdBase);
                continue;  // Skip this invalid card
            }
            hasCards = true;
            extractedCommands.push(cardData.command);
            cardDataList.push(cardData);  // Save for later rendering
        } catch (e) {
            console.error('Failed to parse CMD_CARD:', e);
        }
    }

    // Check for SUGGESTIONS markers and extract them
    const suggestionsRegex = /\[SUGGESTIONS\](.*?)\[\/SUGGESTIONS\]/gs;
    let suggestionsList = [];
    let suggestMatch;
    while ((suggestMatch = suggestionsRegex.exec(text)) !== null) {
        try {
            const suggestions = JSON.parse(suggestMatch[1]);
            if (Array.isArray(suggestions)) {
                suggestionsList = suggestionsList.concat(suggestions);
            }
        } catch (e) {
            console.error('Failed to parse SUGGESTIONS:', e);
        }
    }

    // Check for FILE_OPEN markers
    const fileOpenRegex = /\[FILE_OPEN\](.*?)\[\/FILE_OPEN\]/g;
    let fileMatch;
    while ((fileMatch = fileOpenRegex.exec(text)) !== null) {
        const path = fileMatch[1].trim();
        if (path) {
            openFile(path); // Auto-open file
        }
    }

    // Check for CHANGESET markers
    const changeSetRegex = /\[CHANGESET_ID\](.*?)\[\/CHANGESET_ID\]/g;
    let csMatch;
    while ((csMatch = changeSetRegex.exec(text)) !== null) {
        const csId = csMatch[1].trim();
        if (csId) {
            loadChangeSet(csId); // Auto-load changeset
        }
    }

    // Remove tags from text
    let cleanText = text.replace(cmdCardRegex, '');
    cleanText = cleanText.replace(suggestionsRegex, '');
    cleanText = cleanText.replace(fileOpenRegex, '');
    cleanText = cleanText.replace(changeSetRegex, '');
    cleanText = cleanText.replace(progressRegex, '');  // Remove progress markers
    cleanText = cleanText.replace(reasoningRegex, '');  // Remove reasoning markers

    // When CMD_CARD is present, aggressively clean up duplicate command text
    if (hasCards) {
        // Remove fenced code blocks
        cleanText = cleanText.replace(/```[\s\S]*?```/g, '');
        // Remove inline code
        cleanText = cleanText.replace(/`[^`]+`/g, '');
        // Remove the actual command text that might appear as plain text
        for (const cmd of extractedCommands) {
            // Escape special regex chars in command
            const escapedCmd = cmd.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            cleanText = cleanText.replace(new RegExp(escapedCmd, 'g'), '');
        }
        // Clean up leftover "Calling tool:" lines
        cleanText = cleanText.replace(/🔍 \*Calling tool:.*?\*\n?/g, '');
    }

    // Always clean up command-like patterns that appear after "Calling tool:" notifications
    // (These are leaked from LLM text content)
    cleanText = cleanText.replace(/(\*Calling tool:.*?\*.*?)\n(sudo\s+\S+.*)/g, '$1');
    cleanText = cleanText.replace(/\n(sudo\s+\S+[^\n]*)\n\n🔍/g, '\n\n🔍');

    // RENDER TEXT FIRST (before command cards)
    if (cleanText.trim() !== '') {
        if (lastMessageRole !== 'assistant' || !currentMessageDiv) {
            const wrapper = document.createElement('div');
            wrapper.className = 'flex justify-start w-full pr-2';
            const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            wrapper.innerHTML = `
                <div class="ai-message-wrapper w-full">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center">
                            <div class="w-6 h-6 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center mr-2">
                                <i class="fas fa-robot text-white text-xs"></i>
                            </div>
                            <span class="text-xs text-gray-400">AI Assistant</span>
                        </div>
                        <!-- Feedback Buttons (only in troubleshoot mode) -->
                        <div class="feedback-buttons hidden" id="feedback-${messageId}">
                            <button onclick="submitFeedback('${messageId}', true, this)" 
                                    class="text-xs text-gray-500 hover:text-green-400 px-2 py-1 transition-colors"
                                    title="This solution was helpful">
                                <i class="fas fa-thumbs-up"></i>
                            </button>
                            <button onclick="submitFeedback('${messageId}', false, this)" 
                                    class="text-xs text-gray-500 hover:text-red-400 px-2 py-1 transition-colors"
                                    title="This solution didn't help">
                                <i class="fas fa-thumbs-down"></i>
                            </button>
                        </div>
                    </div>
                    <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700 text-sm ai-message-content shadow-lg" data-full-text="" data-message-id="${messageId}"></div>
                </div>
            `;
            container.appendChild(wrapper);
            currentMessageDiv = wrapper.querySelector('.ai-message-content');
            lastMessageRole = 'assistant';
        }
        if (currentMessageDiv) {
            const currentText = currentMessageDiv.getAttribute('data-full-text') || '';
            let newText = currentText + cleanText;

            // Post-process for tags that may have been split across chunks (reconstituted in newText)
            // 1. SUGGESTIONS
            const fullSuggestionsRegex = /\[SUGGESTIONS\](.*?)\[\/SUGGESTIONS\]/gs;
            let fullMatch;
            let foundFullSuggestions = false;
            let extractedFullSuggestions = [];

            while ((fullMatch = fullSuggestionsRegex.exec(newText)) !== null) {
                try {
                    const parsed = JSON.parse(fullMatch[1]);
                    if (Array.isArray(parsed)) {
                        extractedFullSuggestions = extractedFullSuggestions.concat(parsed);
                        foundFullSuggestions = true;
                    }
                } catch (e) { /* ignore parse errors until fully formed */ }
            }

            if (foundFullSuggestions) {
                newText = newText.replace(fullSuggestionsRegex, '');
                renderSuggestionButtons(extractedFullSuggestions);
            }

            currentMessageDiv.setAttribute('data-full-text', newText);
            currentMessageDiv.innerHTML = marked.parse(newText);

            // Show feedback buttons in troubleshoot mode after message content is added
            const chatMode = typeof currentChatMode !== 'undefined' ? currentChatMode : 'troubleshoot';
            if (chatMode === 'troubleshoot') {
                const messageId = currentMessageDiv.getAttribute('data-message-id');
                if (messageId) {
                    const feedbackDiv = document.getElementById(`feedback-${messageId}`);
                    if (feedbackDiv) {
                        feedbackDiv.classList.remove('hidden');
                    }
                }
            }

            // Only add "Run in Terminal" buttons in Inquiry mode (troubleshoot uses CMD_CARDs)
            if (!skipRunButtons && !hasCards && chatMode === 'general') {
                addRunButtons(currentMessageDiv);
            }
        }

    }

    // RENDER COMMAND CARDS AFTER TEXT (with queue system)
    if (cardDataList.length > 0) {
        // Reset command queue for this new batch
        commandQueue = [];
        const queueContainerId = 'cmd-queue-' + Date.now();
        commandQueueContainerId = queueContainerId;

        // Create queue container
        const queueWrapper = document.createElement('div');
        queueWrapper.id = queueContainerId;
        queueWrapper.className = 'command-queue-container my-4 border border-gray-700 rounded-lg bg-gray-900/50 p-4';

        // Queue header
        queueWrapper.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                    <i class="fas fa-list text-purple-400"></i>
                    <span class="text-sm font-medium text-gray-300">Command Queue (${cardDataList.length} commands)</span>
                </div>
                <span class="text-xs text-gray-500" id="${queueContainerId}-status">Waiting for execution...</span>
            </div>
            <div id="${queueContainerId}-cards" class="space-y-2"></div>
            <div id="${queueContainerId}-actions" class="mt-4 flex gap-3 border-t border-gray-700 pt-3" style="${cardDataList.length === 1 ? 'display: none;' : ''}">
                <button id="${queueContainerId}-continue" onclick="continueWithAI('${queueContainerId}')" 
                        class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded font-medium transition-colors flex items-center justify-center">
                    <i class="fas fa-robot mr-2"></i>Continue with AI
                </button>
                <button onclick="skipAllCommands('${queueContainerId}')" 
                        class="bg-yellow-600 hover:bg-yellow-500 text-white text-sm px-3 py-2 rounded font-medium transition-colors"
                        title="Skip all remaining commands">
                    <i class="fas fa-forward mr-1"></i>Skip All
                </button>
            </div>
        `;
        container.appendChild(queueWrapper);

        // Render individual command cards inside queue
        const cardsContainer = document.getElementById(`${queueContainerId}-cards`);
        for (const cardData of cardDataList) {
            const cardId = 'cmd-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

            // Add to queue
            commandQueue.push({
                id: cardId,
                server: cardData.server,
                command: cardData.command,
                explanation: cardData.explanation,
                status: 'pending',  // pending, executed, skipped
                output: null,
                exitCode: null
            });

            // Render card
            const cardEl = document.createElement('div');
            cardEl.id = cardId;
            cardEl.dataset.queueId = queueContainerId;
            cardEl.className = 'command-card bg-gray-800 rounded-lg border border-gray-700 overflow-hidden';
            cardEl.innerHTML = `
                <div class="flex items-center justify-between px-3 py-2 bg-gray-900 border-b border-gray-700">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-terminal text-green-400"></i>
                        <span class="text-xs text-gray-400">Command</span>
                    </div>
                    <span class="text-xs text-gray-500">${escapeHtml(cardData.server)}</span>
                </div>
                <div class="p-3">
                    <div class="bg-black rounded p-2 font-mono text-sm text-green-300 mb-2 overflow-x-auto">
                        ${escapeHtml(cardData.command)}
                    </div>
                    <div class="text-xs text-gray-400 mb-2">
                        <i class="fas fa-info-circle mr-1"></i>${escapeHtml(cardData.explanation)}
                    </div>
                    <div class="cmd-actions flex gap-2">
                        <button data-cmd="${escapeHtml(cardData.command)}" data-server="${escapeHtml(cardData.server)}" 
                                onclick="runQueuedCommand('${cardId}', this)" 
                                class="flex-1 bg-green-600 hover:bg-green-500 text-white text-xs px-3 py-1.5 rounded font-medium transition-colors flex items-center justify-center">
                            <i class="fas fa-play mr-1"></i>Run
                        </button>
                        <button data-cmd="${escapeHtml(cardData.command)}" data-server="${escapeHtml(cardData.server)}" data-explanation="${escapeHtml(cardData.explanation)}"
                                onclick="openCommandEditor('${cardId}', this.dataset.cmd, this.dataset.server, this.dataset.explanation)" 
                                class="bg-blue-600 hover:bg-blue-500 text-white text-xs px-2 py-1.5 rounded font-medium transition-colors"
                                title="Edit command before running">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="skipQueuedCommand('${cardId}')" 
                                class="bg-yellow-600 hover:bg-yellow-500 text-white text-xs px-2 py-1.5 rounded font-medium transition-colors"
                                title="Skip this command">
                            <i class="fas fa-forward"></i>
                        </button>
                        <button data-cmd="${escapeHtml(cardData.command)}" onclick="copyToClipboard(this.dataset.cmd)" 
                                class="bg-gray-600 hover:bg-gray-500 text-white text-xs px-2 py-1.5 rounded font-medium transition-colors"
                                title="Copy command">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                    <div class="cmd-output hidden"></div>
                </div>
            `;
            cardsContainer.appendChild(cardEl);
        }
    }

    // RENDER FOLLOW-UP SUGGESTIONS
    if (suggestionsList.length > 0) {
        renderSuggestionButtons(suggestionsList);
    }

    container.scrollTop = container.scrollHeight;
}

// Render follow-up suggestion buttons
function renderSuggestionButtons(suggestions) {
    const container = document.getElementById('chatMessages');

    const wrapper = document.createElement('div');
    wrapper.className = 'flex justify-start w-full pr-2 my-3';
    wrapper.innerHTML = `
        <div class="w-full">
            <div class="text-xs text-gray-500 mb-2"><i class="fas fa-lightbulb mr-1"></i>Suggested next steps:</div>
            <div class="flex flex-wrap gap-2 suggestion-buttons">
                ${suggestions.map(s => `
                    <button onclick="sendSuggestionAction('${escapeHtml(s.text || s).replace(/'/g, "\\'")}')" 
                            class="bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm px-3 py-2 rounded-lg border border-gray-600 hover:border-purple-500 transition-all flex items-center gap-2">
                        <i class="fas ${getIconForSuggestion(s.text || s)} text-purple-400"></i>
                        <span>${escapeHtml(s.text || s)}</span>
                    </button>
                `).join('')}
            </div>
        </div>
    `;
    container.appendChild(wrapper);
    lastMessageRole = 'suggestions';
}

// Get appropriate icon for suggestion type
function getIconForSuggestion(text) {
    const lower = text.toLowerCase();
    if (lower.includes('log') || lower.includes('check')) return 'fa-search';
    if (lower.includes('restart') || lower.includes('start')) return 'fa-play';
    if (lower.includes('stop') || lower.includes('kill')) return 'fa-stop';
    if (lower.includes('status')) return 'fa-info-circle';
    if (lower.includes('fix') || lower.includes('repair')) return 'fa-wrench';
    if (lower.includes('close') || lower.includes('done') || lower.includes('resolved')) return 'fa-check-circle';
    if (lower.includes('config')) return 'fa-cog';
    if (lower.includes('metric') || lower.includes('monitor')) return 'fa-chart-line';
    return 'fa-arrow-right';
}

// Send a suggestion as user input
function sendSuggestionAction(text) {
    const input = document.getElementById('chatInput');
    input.value = text;
    // Trigger the form submit
    const form = document.getElementById('chatForm');
    if (form) {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    }
}

/**
 * Submit feedback on AI solution
 * @param {string} messageId - The unique message ID
 * @param {boolean} helpful - Whether the solution was helpful
 * @param {HTMLElement} button - The button element that was clicked
 */
async function submitFeedback(messageId, helpful, button) {
    try {
        // Get the message content
        const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageDiv) {
            console.error('Message not found:', messageId);
            return;
        }

        const aiResponseText = messageDiv.getAttribute('data-full-text') || messageDiv.textContent;
        const currentToken = localStorage.getItem('token');

        // Attempt to find the preceding user message for context (BETTER EMBEDDINGS)
        let userProblemContext = "";
        try {
            // Traverse up to the major wrapper
            const aiMessageRow = button.closest('.flex.justify-start') || messageDiv.closest('.flex.justify-start');
            if (aiMessageRow) {
                let sibling = aiMessageRow.previousElementSibling;
                // Look back up to 5 siblings to find the user message
                let attempts = 0;
                while (sibling && attempts < 5) {
                    // User messages have 'justify-end' class (see appendUserMessage)
                    if (sibling.classList.contains('justify-end')) {
                        const text = sibling.textContent.trim();
                        // Skip system messages formatted in brackets like [Command Queue...]
                        if (text.startsWith('[') && text.endsWith(']')) {
                            console.log("Skipping system message:", text);
                            sibling = sibling.previousElementSibling;
                            continue;
                        }

                        userProblemContext = text;
                        console.log("Found user context:", userProblemContext);
                        break;
                    }
                    sibling = sibling.previousElementSibling;
                    attempts++;
                }
            }
        } catch (e) {
            console.warn("Failed to find user context:", e);
        }

        // Construct a rich problem description for embedding
        // If we found the user's question, use that as the primary signal
        let finalProblemDesc = "";
        if (userProblemContext) {
            finalProblemDesc = `User asked: ${userProblemContext}`;
        } else {
            finalProblemDesc = `AI Context: ${aiResponseText.substring(0, 200)}`;
        }

        // Ensure session_id is a valid UUID string or null
        let sessionId = null;
        if (typeof currentSessionId !== 'undefined' && currentSessionId) {
            // Check if it's a valid UUID (simple regex)
            const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            if (uuidRegex.test(String(currentSessionId))) {
                sessionId = String(currentSessionId);
            } else {
                console.warn("Current session ID is not a valid UUID, sending null:", currentSessionId);
            }
        }

        // Prepare feedback payload matching SolutionFeedbackCreate schema
        const feedback = {
            solution_type: 'agent_suggestion',
            solution_reference: aiResponseText.substring(0, 200) || "No reference",
            problem_description: finalProblemDesc.substring(0, 500),
            success: helpful,
            session_id: sessionId,
            user_feedback: helpful ? 'Solution was helpful' : 'Solution did not help'
        };

        console.log('Using token:', currentToken ? 'Yes (Present)' : 'No (Missing)');
        console.log('Submitting feedback payload:', JSON.stringify(feedback, null, 2));

        // Submit to API using direct fetch to ensure headers are correct
        const response = await fetch('/api/v1/solution-feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentToken}`
            },
            body: JSON.stringify(feedback)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Feedback submission failed:', response.status, errorText);
            try {
                const errorJson = JSON.parse(errorText);
                console.error('Validation details:', errorJson);
            } catch (e) { }

            throw new Error(`Failed to submit feedback: ${response.status} ${errorText}`);
        }

        const result = await response.json();
        console.log('Feedback submitted successfully:', result);

        // Show success state
        const feedbackDiv = button.closest('.feedback-buttons');
        if (feedbackDiv) {
            feedbackDiv.innerHTML = `
                <span class="text-xs ${helpful ? 'text-green-400' : 'text-yellow-400'} px-2 py-1">
                    <i class="fas ${helpful ? 'fa-check' : 'fa-info-circle'} mr-1"></i>
                    ${helpful ? 'Thanks for feedback!' : 'Noted, thanks!'}
                </span>
            `;
        }

        // Optional: Show toast notification
        if (typeof showToast === 'function') {
            showToast('Feedback submitted', 'success');
        }

    } catch (error) {
        console.error('Error submitting feedback:', error);
        if (typeof showToast === 'function') {
            showToast('Failed to submit feedback', 'error');
        }
    }
}

// Render a structured command card from [CMD_CARD] data
function renderCommandCard(command, server, explanation) {
    const container = document.getElementById('chatMessages');
    const cardId = 'cmd-' + Date.now();

    const wrapper = document.createElement('div');
    wrapper.className = 'flex justify-start w-full pr-2 my-2';
    wrapper.id = cardId;
    wrapper.innerHTML = `
        <div class="w-full bg-gray-800 rounded-lg border border-gray-700 overflow-hidden shadow-lg">
            <div class="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-700">
                <div class="flex items-center gap-2">
                    <i class="fas fa-terminal text-green-400"></i>
                    <span class="text-xs text-gray-400">Command Suggestion</span>
                </div>
                <span class="text-xs text-gray-500">${escapeHtml(server)}</span>
            </div>
            <div class="p-4">
                <div class="bg-black rounded p-3 font-mono text-sm text-green-300 mb-3 overflow-x-auto">
                    ${escapeHtml(command)}
                </div>
                <div class="text-xs text-gray-400 mb-3">
                    <i class="fas fa-info-circle mr-1"></i>${escapeHtml(explanation)}
                </div>
                <div class="cmd-actions flex gap-2">
                    <button data-cmd="${escapeHtml(command)}" data-server="${escapeHtml(server)}" data-explanation="${escapeHtml(explanation)}" 
                            onclick="openCommandEditor('${cardId}', this.dataset.cmd, this.dataset.server, this.dataset.explanation)" 
                            class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded font-medium transition-colors flex items-center justify-center">
                        <i class="fas fa-play mr-2"></i>Review & Run
                    </button>
                    <button data-cmd="${escapeHtml(command)}" onclick="skipCommand('${cardId}', this.dataset.cmd)" 
                            class="bg-yellow-600 hover:bg-yellow-500 text-white text-sm px-3 py-2 rounded font-medium transition-colors"
                            title="Skip this command">
                        <i class="fas fa-forward"></i>
                    </button>
                    <button data-cmd="${escapeHtml(command)}" onclick="copyToClipboard(this.dataset.cmd)" 
                            class="bg-gray-600 hover:bg-gray-500 text-white text-sm px-3 py-2 rounded font-medium transition-colors"
                            title="Copy command">
                        <i class="fas fa-copy"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
    container.appendChild(wrapper);
    container.scrollTop = container.scrollHeight;
    lastMessageRole = 'assistant';
}

// NEW: Command editor modal
function openCommandEditor(cardId, command, server, explanation) {
    // Remove existing modal if open
    closeCommandEditor();

    const modal = document.createElement('div');
    modal.id = 'commandEditorModal';
    modal.className = 'fixed inset-0 bg-black/70 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-gray-800 border border-gray-600 rounded-lg w-full max-w-lg mx-4 shadow-2xl">
            <div class="flex justify-between items-center p-4 border-b border-gray-700">
                <h3 class="text-lg font-medium text-white">
                    <i class="fas fa-edit mr-2 text-blue-400"></i>Review Command
                </h3>
                <button onclick="closeCommandEditor()" class="text-gray-400 hover:text-white">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="p-4">
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Target Server</label>
                    <div class="bg-gray-900 p-2 rounded text-sm text-gray-300">
                        <i class="fas fa-server mr-2 text-blue-400"></i>${escapeHtml(server)}
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Command</label>
                    <div class="relative">
                        <textarea id="editableCommand" 
                                  class="w-full bg-gray-900 border border-gray-700 rounded p-3 font-mono text-sm text-green-400 focus:border-blue-500 focus:outline-none"
                                  rows="3">${escapeHtml(command)}</textarea>
                        <button onclick="resetCommand('${escapeHtml(command).replace(/'/g, "\\'")}')" 
                                class="absolute top-2 right-2 text-xs text-gray-500 hover:text-white"
                                title="Reset to original">
                            <i class="fas fa-undo"></i>
                        </button>
                    </div>
                    <div id="commandModifiedBadge" class="hidden text-xs text-yellow-400 mt-1">
                        <i class="fas fa-exclamation-triangle mr-1"></i>Modified from original
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Explanation</label>
                    <div class="bg-gray-900/50 p-2 rounded text-xs text-gray-400 italic">
                        "${escapeHtml(explanation)}"
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Safety Check</label>
                    <div id="safetyCheckResult" class="bg-gray-900 p-2 rounded text-sm">
                        <i class="fas fa-spinner fa-spin mr-2 text-blue-400"></i>Validating...
                    </div>
                </div>
            </div>
            
            <div class="flex justify-end gap-2 p-4 border-t border-gray-700 bg-gray-900/50">
                <button onclick="closeCommandEditor()" 
                        class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">
                    Cancel
                </button>
                <button onclick="copyToClipboard(document.getElementById('editableCommand').value)" 
                        class="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors">
                    <i class="fas fa-copy mr-1"></i>Copy
                </button>
                <button id="executeBtn" onclick="executeFromEditor('${cardId}', '${escapeHtml(server)}')" 
                        class="px-4 py-2 text-sm bg-green-600 hover:bg-green-500 text-white rounded font-medium transition-colors">
                    <i class="fas fa-play mr-1"></i>Execute
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Setup change detection
    const textarea = document.getElementById('editableCommand');
    textarea.addEventListener('input', () => {
        const modified = textarea.value !== command;
        document.getElementById('commandModifiedBadge').classList.toggle('hidden', !modified);
        if (modified) {
            validateCommand(textarea.value, server);
        }
    });

    // Initial validation
    validateCommand(command, server);
}

async function validateCommand(command, server) {
    const resultDiv = document.getElementById('safetyCheckResult');
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin mr-2 text-blue-400"></i>Validating...';

    try {
        const response = await fetch('/api/troubleshoot/commands/validate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ command, server })
        });
        const data = await response.json();

        const icons = {
            'allowed': '<i class="fas fa-check-circle text-green-400 mr-2"></i>',
            'warning': '<i class="fas fa-exclamation-triangle text-yellow-400 mr-2"></i>',
            'blocked': '<i class="fas fa-ban text-red-400 mr-2"></i>',
            'unknown': '<i class="fas fa-question-circle text-gray-400 mr-2"></i>'
        };

        resultDiv.innerHTML = `${icons[data.result] || ''}${data.message}`;

        // Disable execute button if blocked
        const execBtn = document.getElementById('executeBtn');
        if (execBtn) {
            execBtn.disabled = data.result === 'blocked';
            execBtn.classList.toggle('opacity-50', data.result === 'blocked');
            execBtn.classList.toggle('cursor-not-allowed', data.result === 'blocked');
        }
    } catch (err) {
        console.error(err);
        if (resultDiv) resultDiv.innerHTML = '<i class="fas fa-question-circle text-gray-400 mr-2"></i>Could not validate';
    }
}

function closeCommandEditor() {
    const modal = document.getElementById('commandEditorModal');
    if (modal) modal.remove();
}

function resetCommand(original) {
    const textarea = document.getElementById('editableCommand');
    if (textarea) {
        textarea.value = original;
        textarea.dispatchEvent(new Event('input'));
    }
}

function executeFromEditor(cardId, server) {
    const command = document.getElementById('editableCommand').value;
    closeCommandEditor();

    // Update the original card's command display if modified
    const card = document.getElementById(cardId);
    if (card) {
        const codeBlock = card.querySelector('.font-mono');
        if (codeBlock) codeBlock.innerText = command;

        // Update data attributes on buttons for subsequent clicks
        const buttons = card.querySelectorAll('.cmd-actions button');
        buttons.forEach(btn => btn.setAttribute('data-cmd', command));
    }

    // Execute via existing flow
    executeCommandWithOutput(cardId, command);
}

// Skip a suggested command and notify the Agent
async function skipCommand(cardId, command) {
    const card = document.getElementById(cardId);
    if (card) {
        const actionsDiv = card.querySelector('.cmd-actions');
        if (actionsDiv) {
            actionsDiv.innerHTML = '<div class="text-yellow-400 text-sm p-2"><i class="fas fa-forward mr-2"></i>Command skipped.</div>';
        }
    }

    // Send skip notification to Agent so it knows to move on
    showToast('Command skipped', 'info');
    await autoSendCommandOutputToAgent(command, '[USER SKIPPED THIS COMMAND]', false, -1);
}

// ============= COMMAND EDITOR MODAL =============

function openCommandEditor(cardId, command, server, explanation) {
    // Remove any existing modal
    closeCommandEditor();

    const modal = document.createElement('div');
    modal.id = 'commandEditorModal';
    modal.className = 'fixed inset-0 bg-black/70 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-gray-800 border border-gray-600 rounded-lg w-full max-w-2xl mx-4 shadow-2xl">
            <div class="flex justify-between items-center p-4 border-b border-gray-700">
                <h3 class="text-lg font-medium text-white">
                    <i class="fas fa-edit mr-2 text-blue-400"></i>Review Command Before Execution
                </h3>
                <button onclick="closeCommandEditor()" class="text-gray-400 hover:text-white transition-colors">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="p-4">
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Target Server</label>
                    <div class="bg-gray-900 p-2 rounded text-sm text-gray-300">
                        <i class="fas fa-server mr-2 text-blue-400"></i>${escapeHtml(server)}
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Command</label>
                    <div class="relative">
                        <textarea id="editableCommand" 
                                  class="w-full bg-gray-900 border border-gray-700 rounded p-3 font-mono text-sm text-green-400 focus:border-blue-500 focus:outline-none resize-none"
                                  rows="4">${escapeHtml(command)}</textarea>
                        <button onclick="resetCommand('${escapeHtml(command).replace(/'/g, "\\'")}', '${cardId}')" 
                                class="absolute top-2 right-2 text-xs text-gray-500 hover:text-white px-2 py-1 bg-gray-800 rounded transition-colors"
                                title="Reset to original">
                            <i class="fas fa-undo mr-1"></i>Reset
                        </button>
                    </div>
                    <div id="commandModifiedBadge" class="hidden text-xs text-yellow-400 mt-1">
                        <i class="fas fa-exclamation-triangle mr-1"></i>Modified from original suggestion
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Explanation</label>
                    <div class="bg-gray-900/50 p-2 rounded text-xs text-gray-400 italic">
                        "${escapeHtml(explanation)}"
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Safety Check</label>
                    <div id="safetyCheckResult" class="bg-gray-900 p-2 rounded text-sm">
                        <i class="fas fa-spinner fa-spin mr-2 text-blue-400"></i>Validating command...
                    </div>
                </div>
            </div>
            
            <div class="flex justify-end gap-2 p-4 border-t border-gray-700 bg-gray-900/50">
                <button onclick="closeCommandEditor()" 
                        class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">
                    Cancel
                </button>
                <button onclick="copyCommandFromEditor()" 
                        class="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors">
                    <i class="fas fa-copy mr-1"></i>Copy
                </button>
                <button id="executeBtn" onclick="executeFromEditor('${cardId}', '${escapeHtml(server)}')" 
                        class="px-4 py-2 text-sm bg-green-600 hover:bg-green-500 text-white rounded font-medium transition-colors">
                    <i class="fas fa-play mr-1"></i>Execute
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Store original command
    modal.dataset.originalCommand = command;
    modal.dataset.cardId = cardId;

    // Setup change detection
    const textarea = document.getElementById('editableCommand');
    textarea.addEventListener('input', () => {
        const modified = textarea.value !== command;
        document.getElementById('commandModifiedBadge').classList.toggle('hidden', !modified);
        // Re-validate when modified
        validateCommand(textarea.value, server);
    });

    // Initial validation
    validateCommand(command, server);
}

async function validateCommand(command, server) {
    const resultDiv = document.getElementById('safetyCheckResult');
    if (!resultDiv) return;

    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin mr-2 text-blue-400"></i>Validating...';

    try {
        const response = await fetch('/api/commands/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command, server })
        });

        if (!response.ok) {
            throw new Error('Validation failed');
        }

        const data = await response.json();

        const icons = {
            'allowed': '<i class="fas fa-check-circle text-green-400 mr-2"></i>',
            'warning': '<i class="fas fa-exclamation-triangle text-yellow-400 mr-2"></i>',
            'blocked': '<i class="fas fa-ban text-red-400 mr-2"></i>'
        };

        const colors = {
            'allowed': 'text-green-400',
            'warning': 'text-yellow-400',
            'blocked': 'text-red-400'
        };

        resultDiv.innerHTML = `<span class="${colors[data.result] || 'text-gray-400'}">${icons[data.result] || ''}${escapeHtml(data.message || 'Unknown status')}</span>`;

        // Disable execute button if blocked
        const executeBtn = document.getElementById('executeBtn');
        if (executeBtn) {
            executeBtn.disabled = data.result === 'blocked';
            executeBtn.classList.toggle('opacity-50', data.result === 'blocked');
            executeBtn.classList.toggle('cursor-not-allowed', data.result === 'blocked');
        }
    } catch (err) {
        console.error('Validation error:', err);
        resultDiv.innerHTML = '<i class="fas fa-question-circle text-gray-400 mr-2"></i>Could not validate command';
    }
}

function resetCommand(originalCommand, cardId) {
    const textarea = document.getElementById('editableCommand');
    if (textarea) {
        textarea.value = originalCommand;
        document.getElementById('commandModifiedBadge').classList.add('hidden');

        // Re-validate original command
        const modal = document.getElementById('commandEditorModal');
        if (modal) {
            const card = document.getElementById(cardId);
            if (card) {
                const server = card.querySelector('.text-gray-500')?.textContent || '';
                validateCommand(originalCommand, server);
            }
        }
    }
}

function copyCommandFromEditor() {
    const textarea = document.getElementById('editableCommand');
    if (textarea) {
        copyToClipboard(textarea.value);
    }
}

function closeCommandEditor() {
    const modal = document.getElementById('commandEditorModal');
    if (modal) {
        modal.remove();
    }
}

function executeFromEditor(cardId, server) {
    const textarea = document.getElementById('editableCommand');
    if (!textarea) return;

    const command = textarea.value.trim();
    if (!command) {
        showToast('Command cannot be empty', 'error');
        return;
    }

    closeCommandEditor();

    // Update the queue item with the edited command
    const queueItem = commandQueue.find(c => c.id === cardId);
    if (queueItem) {
        queueItem.command = command;
    }

    // Update the displayed command in the card
    const card = document.getElementById(cardId);
    if (card) {
        const cmdDisplay = card.querySelector('.bg-black');
        if (cmdDisplay) {
            cmdDisplay.textContent = command;
        }
    }

    // Execute via existing flow
    runQueuedCommand(cardId, { dataset: { cmd: command, server: server } });
}

// ============= COMMAND QUEUE SYSTEM =============

// Run a command from the queue (doesn't auto-send to AI)
// Run a command from the queue (doesn't auto-send to AI)
async function runQueuedCommand(cardId, btnEl) {
    const card = document.getElementById(cardId);
    if (!card) return;

    const localQueueId = card.dataset.queueId || commandQueueContainerId;
    console.debug('[AIQ] runQueuedCommand start', { cardId, localQueueId });

    let command, server;
    let queueItem = commandQueue.find(c => c.id === cardId);

    if (queueItem) {
        command = queueItem.command;
        server = queueItem.server;
    } else {
        // Fallback: load from button dataset (handles cases where queue memory is lost)
        if (btnEl && btnEl.dataset.cmd) {
            command = btnEl.dataset.cmd;
            server = btnEl.dataset.server;
            console.debug('[AIQ] queue item missing, using fallback dataset', { cardId });

            // Reconstruct item to avoid crash and allow status updates
            queueItem = {
                id: cardId,
                command: command,
                server: server,
                explanation: 'Reconstructed from fallback',
                status: 'pending',
                output: null,
                exitCode: null
            };
            commandQueue.push(queueItem);
        } else {
            console.error('Command data not found for card:', cardId);
            showToast('Error: Command data lost. Please refresh.', 'error');
            return;
        }
    }

    // Update UI to show running
    const actionsDiv = card.querySelector('.cmd-actions');
    actionsDiv.innerHTML = '<div class="text-blue-400 text-xs p-2"><i class="fas fa-spinner fa-spin mr-1"></i>Running...</div>';

    try {
        // Execute command via terminal
        console.debug('[AIQ] executing command', { cardId, server, command });
        const result = await executeCommandViaTerminal(command, server);

        console.debug('[AIQ] command execution result', { cardId, timedOut: result.timedOut, exitCode: result.exitCode, outputLen: result.output ? result.output.length : 0 });

        // If command needs interaction/pager, allow manual capture
        if (result.timedOut) {
            actionsDiv.innerHTML = `
                <div class="flex flex-col gap-2 p-3 bg-gray-900 rounded border border-yellow-600">
                    <div class="text-yellow-400 text-xs font-bold">
                        <i class="fas fa-clock mr-2"></i>Command still running / waiting for input
                    </div>
                    <div class="text-gray-300 text-xs">
                        If the command opened a pager (e.g., press <b>q</b>) or needs input, complete it in the terminal, then:
                    </div>
                    <div class="flex gap-2">
                        <button onclick="captureQueuedOutput('${cardId}', '${command.replace(/'/g, "\\'")}', ${result.startLine})" 
                                class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-2 rounded transition-colors flex items-center justify-center">
                            <i class="fas fa-camera mr-1"></i>Capture Output
                        </button>
                        <button onclick="skipQueuedCommand('${cardId}')" 
                                class="bg-yellow-600 hover:bg-yellow-500 text-white text-xs px-3 py-2 rounded transition-colors" title="Skip this command">
                            <i class="fas fa-forward"></i>
                        </button>
                    </div>
                </div>
            `;
            showToast('Command may need interaction. Complete it in terminal, then capture output.', 'warning');
            return;
        }

        // Update queue item
        queueItem.status = 'executed';
        queueItem.output = result.output;
        queueItem.exitCode = result.exitCode;

        // Update card UI
        const isSuccess = result.exitCode === 0 || result.exitCode === null;
        const statusColor = isSuccess ? 'text-green-400' : 'text-red-400';
        const statusIcon = isSuccess ? 'fa-check-circle' : 'fa-times-circle';

        actionsDiv.innerHTML = `<div class="${statusColor} text-xs p-2"><i class="fas ${statusIcon} mr-1"></i>${isSuccess ? 'Executed' : 'Failed (exit ' + result.exitCode + ')'}</div>`;

        // Show output
        const outputDiv = card.querySelector('.cmd-output');
        if (outputDiv && result.output) {
            let displayOutput = result.output;
            if (displayOutput.length > 2000) {
                displayOutput = displayOutput.substring(0, 1000) + '\n... [truncated] ...\n' + displayOutput.substring(displayOutput.length - 1000);
            }
            outputDiv.innerHTML = `<div class="border-t border-gray-700 p-2 bg-gray-950 mt-2 rounded"><pre class="text-xs text-gray-300 overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap">${escapeHtml(displayOutput)}</pre></div>`;
            outputDiv.classList.remove('hidden');
        }

        showToast(`Command executed ${isSuccess ? 'successfully' : 'with errors'}`, isSuccess ? 'success' : 'warning');

        // Auto-save command outcome for learning (fire-and-forget)
        saveCommandOutcome(command, result.output, isSuccess, result.exitCode);

    } catch (err) {
        console.debug('[AIQ] command execution error', { cardId, error: err && err.message ? err.message : String(err) });
        // Update queue item
        queueItem.status = 'executed';
        queueItem.output = 'Error: ' + err.message;
        queueItem.exitCode = -1;

        actionsDiv.innerHTML = '<div class="text-red-400 text-xs p-2"><i class="fas fa-times-circle mr-1"></i>Failed to execute</div>';
        showToast('Command execution failed: ' + err.message, 'error');

        // Auto-save failed outcome for learning
        saveCommandOutcome(command, err.message, false, -1);
    }

    // Update queue status
    updateQueueStatusForQueue(localQueueId);
    console.debug('[AIQ] runQueuedCommand end', { cardId, localQueueId });
}

function captureQueuedOutput(cardId, command, startLine) {
    const card = document.getElementById(cardId);
    if (!card || !term) return;

    const localQueueId = card.dataset.queueId || commandQueueContainerId;
    console.debug('[AIQ] captureQueuedOutput', { cardId, startLine, localQueueId });

    const endLine = term.buffer.active.baseY + term.buffer.active.cursorY;
    const output = getTerminalOutputRange(startLine, endLine);

    let queueItem = commandQueue.find(c => c.id === cardId);
    if (!queueItem) {
        const serverLabel = card.querySelector('span.text-xs.text-gray-500')?.textContent || 'unknown';
        queueItem = {
            id: cardId,
            server: serverLabel,
            command: command,
            explanation: 'Reconstructed from capture',
            status: 'pending',
            output: null,
            exitCode: null
        };
        commandQueue.push(queueItem);
    }

    queueItem.status = 'executed';
    queueItem.output = output;
    queueItem.exitCode = 0;

    const actionsDiv = card.querySelector('.cmd-actions');
    actionsDiv.innerHTML = '<div class="text-green-400 text-xs p-2"><i class="fas fa-check-circle mr-1"></i>Output captured</div>';

    const outputDiv = card.querySelector('.cmd-output');
    if (outputDiv && output) {
        let displayOutput = output;
        if (displayOutput.length > 2000) {
            displayOutput = displayOutput.substring(0, 1000) + '\n... [truncated] ...\n' + displayOutput.substring(displayOutput.length - 1000);
        }
        outputDiv.innerHTML = `<div class="border-t border-gray-700 p-2 bg-gray-950 mt-2 rounded"><pre class="text-xs text-gray-300 overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap">${escapeHtml(displayOutput)}</pre></div>`;
        outputDiv.classList.remove('hidden');
    }

    showToast('Output captured', 'success');
    updateQueueStatusForQueue(localQueueId);
    console.debug('[AIQ] captureQueuedOutput done', { cardId, localQueueId, outputLen: output ? output.length : 0 });
}

// Skip a command in the queue (doesn't send to AI)
// Skip a command in the queue (doesn't send to AI)
function skipQueuedCommand(cardId) {
    const card = document.getElementById(cardId);
    if (!card) return;

    const localQueueId = card.dataset.queueId || commandQueueContainerId;

    // Find in queue (try to update status if possible)
    const queueItem = commandQueue.find(c => c.id === cardId);
    if (queueItem) {
        queueItem.status = 'skipped';
        queueItem.output = '[USER SKIPPED THIS COMMAND]';
    }

    // Update UI regardless of queue state
    const actionsDiv = card.querySelector('.cmd-actions');
    actionsDiv.innerHTML = '<div class="text-yellow-400 text-xs p-2"><i class="fas fa-forward mr-1"></i>Skipped</div>';

    showToast('Command skipped', 'info');
    updateQueueStatusForQueue(localQueueId);
}

// Skip all remaining pending commands
function skipAllCommands(queueContainerId) {
    for (const item of commandQueue) {
        if (item.status === 'pending') {
            item.status = 'skipped';
            item.output = '[USER SKIPPED THIS COMMAND]';

            const card = document.getElementById(item.id);
            if (card) {
                const actionsDiv = card.querySelector('.cmd-actions');
                actionsDiv.innerHTML = '<div class="text-yellow-400 text-xs p-2"><i class="fas fa-forward mr-1"></i>Skipped</div>';
            }
        }
    }

    showToast('All remaining commands skipped', 'info');
    updateQueueStatus();
}

// Update queue status display and show Continue button when ready
function updateQueueStatus() {
    updateQueueStatusForQueue(commandQueueContainerId);
}

function updateQueueStatusForQueue(queueId) {
    if (!queueId) {
        console.debug('[AIQ] updateQueueStatusForQueue skipped: no queueId');
        return;
    }

    const pendingCount = commandQueue.filter(c => c.status === 'pending').length;
    const executedCount = commandQueue.filter(c => c.status === 'executed').length;
    const skippedCount = commandQueue.filter(c => c.status === 'skipped').length;

    const statusEl = document.getElementById(`${queueId}-status`);
    const actionsEl = document.getElementById(`${queueId}-actions`);

    if (statusEl) {
        if (pendingCount === 0) {
            statusEl.textContent = `✅ ${executedCount} executed, ${skippedCount} skipped`;
            statusEl.className = 'text-xs text-green-400';
        } else {
            statusEl.textContent = `⏳ ${pendingCount} pending, ${executedCount} executed, ${skippedCount} skipped`;
            statusEl.className = 'text-xs text-gray-500';
        }
    }

    // Auto-continue when all commands are handled
    console.debug('[AIQ] queue status', { pendingCount, executedCount, skippedCount, queueId });
    maybeAutoContinueQueue(queueId, pendingCount, executedCount, skippedCount);
}

function maybeAutoContinueQueue(queueContainerId, pendingCount, executedCount, skippedCount) {
    const queueWrapper = document.getElementById(queueContainerId);
    if (!queueWrapper) return;

    if (pendingCount === 0 && (executedCount > 0 || skippedCount > 0)) {
        console.debug('[AIQ] auto-continue eligible', { queueContainerId, executedCount, skippedCount });
        if (queueWrapper.dataset.autoContinueTriggered === 'true') return;
        queueWrapper.dataset.autoContinueTriggered = 'true';

        // Small delay to allow UI to update before continuing
        setTimeout(() => {
            continueWithAI(queueContainerId);
        }, 300);
    }
}

// Continue with AI - sends all queue outputs to agent
async function continueWithAI(queueContainerId) {
    console.debug('[AIQ] continueWithAI start', { queueContainerId });
    const queueWrapper = document.getElementById(queueContainerId);
    if (queueWrapper) {
        if (queueWrapper.dataset.continueInProgress === 'true') return;
        queueWrapper.dataset.continueInProgress = 'true';
    }
    // Robustness: Reconstruct queue from DOM if missing
    if (commandQueue.length === 0) {
        const container = document.getElementById(queueContainerId + '-cards');
        if (container) {
            console.warn('Command queue missing, reconstructing from DOM for report');
            const cards = container.querySelectorAll('.command-card');
            cards.forEach(card => {
                const btn = card.querySelector('button[data-cmd]');
                if (btn) {
                    const cmd = btn.dataset.cmd;
                    const srv = btn.dataset.server;
                    let status = 'pending';
                    let output = '';
                    const actDiv = card.querySelector('.cmd-actions');
                    if (actDiv && actDiv.innerHTML.includes('text-green-400')) status = 'executed';
                    else if (actDiv && actDiv.innerHTML.includes('text-yellow-400')) status = 'skipped';

                    const outDiv = card.querySelector('.cmd-output pre');
                    if (outDiv) output = outDiv.textContent;

                    commandQueue.push({
                        id: card.id,
                        command: cmd,
                        server: srv,
                        status: status,
                        output: output,
                        exitCode: 0
                    });
                }
            });
        }
    }

    if (commandQueue.length === 0) {
        console.warn('continueWithAI: Queue is empty even after reconstruction attempt.');
        showToast('Error: No execution data found to send.', 'error');
        if (queueWrapper) queueWrapper.dataset.continueInProgress = 'false';
        console.debug('[AIQ] continueWithAI aborted: empty queue', { queueContainerId });
        return;
    }

    // Disable button
    const actionsEl = document.getElementById(`${queueContainerId}-actions`);
    // Store original content for restore on error
    const originalBtnContent = actionsEl ? actionsEl.innerHTML : '';

    if (actionsEl) {
        actionsEl.innerHTML = '<div class="text-blue-400 text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Sending to AI...</div>';
    }

    try {
        // Reset streaming flag to prevent deadlocks
        isStreaming = false;

        // Save queue items BEFORE streaming (AI response may create new queue)
        const itemsToSend = [...commandQueue];
        const savedQueueId = queueContainerId;
        console.debug('[AIQ] continueWithAI preparing', { savedQueueId, itemCount: itemsToSend.length });

        // Build summary message
        let summaryMsg = '### Command Execution Results\n\n';

        for (const item of itemsToSend) {
            const statusEmoji = item.status === 'executed' ? (item.exitCode === 0 ? '✅' : '❌') : '⏭️';
            summaryMsg += `${statusEmoji} **${item.command}** (${item.server})\n`;

            if (item.status === 'executed' && item.output) {
                let output = item.output;
                if (output.length > 800) {
                    output = output.substring(0, 400) + '\n...[truncated]...\n' + output.substring(output.length - 400);
                }
                summaryMsg += `\`\`\`\n${output}\n\`\`\`\n\n`;
            } else if (item.status === 'skipped') {
                summaryMsg += `*User skipped this command*\n\n`;
            }
        }

        summaryMsg += '\n**What should I do next?**';

        // Add as user message visually
        appendUserMessage('[Command Queue Complete - Continuing with AI]');

        // Show typing indicator
        showTypingIndicator();

        // Send via streaming
        await sendStreamingMessage(summaryMsg);

        // Only clear queue if a NEW queue wasn't created during streaming
        // (AI response creates new queue with different ID)
        if (commandQueueContainerId === savedQueueId) {
            commandQueue = [];
            commandQueueContainerId = null;
            console.debug('[AIQ] continueWithAI cleared old queue', { savedQueueId });
        } else {
            console.debug('[AIQ] continueWithAI: new queue created during streaming, not clearing', { savedQueueId, newQueueId: commandQueueContainerId });
        }

        console.log('✅ Sent command queue results to AI');
        console.debug('[AIQ] continueWithAI sent', { savedQueueId, itemsSent: itemsToSend.length });

        if (actionsEl) {
            actionsEl.innerHTML = '<div class="text-green-400 text-sm"><i class="fas fa-check mr-2"></i>Sent to AI</div>';
        }
    } catch (err) {
        console.error('continueWithAI failed:', err);
        showToast('Failed to send report to AI', 'error');

        // Restore button
        if (actionsEl && originalBtnContent) {
            actionsEl.innerHTML = originalBtnContent;
        }
        if (queueWrapper) queueWrapper.dataset.continueInProgress = 'false';
    }

    if (queueWrapper) queueWrapper.dataset.continueInProgress = 'false';
}

// Execute command and capture output (helper function)
// Execute command and capture output (helper function)
async function executeCommandViaTerminal(command, server) {
    if (!currentServerId) {
        throw new Error('Not connected to any server');
    }

    // Reset cancellation flag
    pendingCommandCancelled = false;

    // Remember terminal buffer position before command
    const startLine = term ? term.buffer.active.baseY + term.buffer.active.cursorY : 0;
    console.debug('[AIQ] executeCommandViaTerminal start', { server, startLine, command });

    // Write command to terminal (raw string with \r for enter)
    if (terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
        // Ensure we send as string
        terminalSocket.send(String(command) + '\r');
    } else {
        throw new Error('Terminal not connected');
    }

    // Wait for output (poll for prompt AND new content)
    const MAX_WAIT = 30; // 30 seconds max
    let waitCount = 0;
    let timedOut = false;

    // Wait for initial echo/reaction
    await new Promise(resolve => setTimeout(resolve, 500));

    while (waitCount < MAX_WAIT) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        waitCount++;

        // Stop if cancelled
        if (pendingCommandCancelled) break;

        if (!term) break;

        // Check if we have new content
        const currentLine = term.buffer.active.baseY + term.buffer.active.cursorY;

        // Only check for prompt if we have moved past the start line OR if we have significant new content on the same line
        if (currentLine > startLine) {
            // Get the last line content
            const buffer = term.buffer.active;
            const lastLine = buffer.getLine(buffer.baseY + buffer.cursorY);
            if (lastLine) {
                const lineText = lastLine.translateToString(true).trim();
                // Common shell prompts
                if (lineText.endsWith('$') || lineText.endsWith('#') || lineText.endsWith('>') || lineText.endsWith(':~$')) {
                    break;
                }
            }
        }
    }

    if (waitCount >= MAX_WAIT) {
        timedOut = true;
    }

    const endLine = term ? term.buffer.active.baseY + term.buffer.active.cursorY : startLine;
    const output = getTerminalOutputRange(startLine, endLine);
    const exitCode = 0; // Assume success for now since we're using terminal capture

    console.debug('[AIQ] executeCommandViaTerminal end', { server, startLine, endLine, timedOut, outputLen: output ? output.length : 0 });
    return { output, exitCode, timedOut, startLine, endLine };
}

function appendUserMessage(text) {
    AIChatBase.appendUserMessage(text);
    lastMessageRole = 'user';
}

/**
 * Show a PII redaction notification after the user message
 * The original message is kept, but user is informed PII was redacted before sending to AI
 */
function updateLastUserMessageWithRedaction() {
    const container = document.getElementById('chatMessages');
    if (!container) return;
    
    // Find the last user message (has justify-end class)
    const allMessages = container.querySelectorAll('.flex.justify-end');
    const lastUserMsg = allMessages[allMessages.length - 1];
    
    if (lastUserMsg) {
        // Check if notification already exists
        if (lastUserMsg.nextSibling && lastUserMsg.nextSibling.classList && 
            lastUserMsg.nextSibling.classList.contains('pii-redaction-notification')) {
            return; // Already added
        }
        
        // Add a small notification below the user message
        const notification = document.createElement('div');
        notification.className = 'flex justify-end mb-3 pii-redaction-notification';
        notification.innerHTML = `
            <div class="text-xs flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-amber-900/20 to-amber-800/10 rounded-lg backdrop-blur-sm">
                <svg class="w-3.5 h-3.5 text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd"></path>
                </svg>
                <span class="text-amber-300 font-medium">🔒 PII Detected & Redacted</span>
            </div>
        `;
        lastUserMsg.parentNode.insertBefore(notification, lastUserMsg.nextSibling);
    }
}

/**
 * Highlight PII detections in the last user message
 */
function highlightPIIInLastUserMessage(detections, originalText) {
    const container = document.getElementById('chatMessages');
    if (!container || !window.piiFeedbackUI) {
        console.warn('🔍 PII: Cannot highlight - container or piiFeedbackUI not found');
        return;
    }
    
    // Find the last user message element (has justify-end class, but not pii-redaction-notification)
    const allMessages = container.querySelectorAll('.flex.justify-end');
    let lastUserMsg = null;
    for (let i = allMessages.length - 1; i >= 0; i--) {
        if (!allMessages[i].classList.contains('pii-redaction-notification')) {
            lastUserMsg = allMessages[i];
            break;
        }
    }
    
    if (lastUserMsg) {
        // Find the actual text content div
        const messageContent = lastUserMsg.querySelector('.user-message-text');
        
        if (messageContent) {
            console.log('🔍 PII: Highlighting in user message element');
            window.piiFeedbackUI.highlightDetections(messageContent, detections, originalText);
        } else {
            console.warn('🔍 PII: Could not find message content element with .user-message-text class');
        }
    } else {
        console.warn('🔍 PII: Could not find last user message');
    }
}

function getTerminalContent() {
    if (!term) return '';
    const buffer = term.buffer.active;
    const lines = [];
    const start = Math.max(0, buffer.baseY + buffer.cursorY - 100);
    const end = buffer.baseY + buffer.cursorY + 1;
    for (let i = start; i < end; i++) {
        const line = buffer.getLine(i);
        if (line) {
            lines.push(line.translateToString(true));
        }
    }
    return lines.join('\n').trim();
}

function getTerminalOutputRange(startLine, endLine) {
    if (!term) return '';
    const buffer = term.buffer.active;
    const lines = [];
    const start = Math.max(0, startLine);
    const end = Math.min(endLine, buffer.baseY + buffer.cursorY);

    for (let i = start; i <= end; i++) {
        const line = buffer.getLine(i);
        if (line) {
            lines.push(line.translateToString(true));
        }
    }

    const joined = lines.join('\n').trim();
    console.debug('[AIQ] getTerminalOutputRange', { start, end, lines: lines.length, outputLen: joined.length });
    return joined;
}

async function sendMessage(e) {
    e.preventDefault();

    // Cancel any pending command polling when user sends a new message
    if (pendingCommandCancelled === false) {
        pendingCommandCancelled = true;
    }

    if (analysisButton) {
        analysisButton.remove();
        analysisButton = null;
    }
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    // Reset progress and reasoning panels for new investigation
    if (typeof resetProgress === 'function') {
        resetProgress();
    }
    if (typeof resetReasoningPanel === 'function') {
        resetReasoningPanel();
    }

    // Detect "issue resolved" type messages and show feedback prompt (lenient for typos)
    const resolvedPatterns = /\b(issue|problem|fixed|works|working|worked|solv|resolv|done|thank|thanks)\b/i;
    if (resolvedPatterns.test(text)) {
        showSessionFeedbackButton();
        // Auto-expand the feedback panel
        setTimeout(() => {
            const expanded = document.getElementById('sessionFeedbackExpanded');
            if (expanded) expanded.classList.remove('hidden');
        }, 500);
    }

    appendUserMessage(escapeHtml(text));
    input.value = '';  // Clear input immediately after sending
    showTypingIndicator();

    // Troubleshooting mode: Use SSE streaming for real-time responses
    const termContent = getTerminalContent();
    let finalMessage = text;
    if (termContent) {
        finalMessage += `\n\n[SYSTEM: The user has the following active terminal output. Use it if relevant to the query.]\n\`\`\`\n${termContent}\n\`\`\``;
    }

    // Use SSE streaming endpoint
    await sendStreamingMessage(finalMessage);
}

// Send message using SSE streaming for real-time token display
async function sendStreamingMessage(message) {
    // Create abort controller for cancel functionality
    currentStreamController = new AbortController();
    isStreaming = true;

    try {
        const token = localStorage.getItem('token');
        const response = await fetch('/api/troubleshoot/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            }),
            signal: currentStreamController.signal
        });

        if (!response.ok) {
            removeTypingIndicator();
            appendAIMessage('Failed to get response from AI. Please try again.');
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullResponse = '';
        let firstChunkReceived = false;
        let piiMapping = {}; // Store mapping of redacted placeholders to original values
        let piiDetections = []; // Store PII detections for highlighting
        let originalUserMessage = message; // Store original message for highlighting

        // Keep typing indicator visible until first content chunk arrives

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'session') {
                            currentSessionId = data.session_id;
                            // Set session ID for PII feedback
                            if (window.piiFeedbackUI) {
                                window.piiFeedbackUI.setSessionId(currentSessionId);
                            }
                        } else if (data.type === 'pii_detections') {
                            // Store detections for highlighting user message
                            piiDetections = data.detections || [];
                            console.log('🔍 PII: Received detections for highlighting:', piiDetections);
                        } else if (data.type === 'redacted_input') {
                            // PII was detected - store mapping for de-anonymizing AI response
                            piiMapping = data.pii_mapping || {};
                            // Show notification that PII was redacted
                            updateLastUserMessageWithRedaction();
                            // Highlight PII in user message if detections available
                            if (piiDetections.length > 0 && window.piiFeedbackUI) {
                                highlightPIIInLastUserMessage(piiDetections, originalUserMessage);
                            }
                        } else if (data.type === 'chunk') {
                            // Remove typing indicator on first content chunk
                            if (!firstChunkReceived) {
                                removeTypingIndicator();
                                firstChunkReceived = true;
                            }
                            // De-anonymize the chunk using Presidio's mapping
                            let processedChunk = data.content;
                            for (const [placeholder, original] of Object.entries(piiMapping)) {
                                processedChunk = processedChunk.split(placeholder).join(original);
                            }
                            fullResponse += processedChunk;
                            // Stream de-anonymized content to UI
                            appendStreamingChunk(processedChunk);
                        } else if (data.type === 'done') {
                            // Finalize the message and render suggestions
                            finalizeStreamingMessage(fullResponse);
                        } else if (data.type === 'error') {
                            appendAIMessage(`Error: ${data.content}`);
                        } else if (data.type === 'cancelled') {
                            appendAIMessage('*Response cancelled by user.*');
                        }
                    } catch (e) {
                        console.error('Failed to parse SSE data:', e);
                    }
                }
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Stream aborted by user');
        } else {
            removeTypingIndicator();
            console.error('Streaming error:', error);
            appendAIMessage('Error communicating with AI service. Please try again.');
        }
    } finally {
        isStreaming = false;
        currentStreamController = null;
        removeTypingIndicator();
    }
}

// Append streaming chunk to current message
function appendStreamingChunk(chunk) {
    const container = document.getElementById('chatMessages');

    if (lastMessageRole !== 'assistant' || !currentMessageDiv) {
        // Create new message wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'flex justify-start w-full pr-2';
        wrapper.innerHTML = `
            <div class="ai-message-wrapper w-full">
                <div class="flex items-center mb-2">
                    <div class="w-6 h-6 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center mr-2">
                        <i class="fas fa-robot text-white text-xs"></i>
                    </div>
                    <span class="text-xs text-gray-400">AI Assistant</span>
                </div>
                <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700 text-sm ai-message-content shadow-lg streaming-message" data-full-text=""></div>
            </div>
        `;
        container.appendChild(wrapper);
        currentMessageDiv = wrapper.querySelector('.ai-message-content');
        lastMessageRole = 'assistant';
    }

    if (currentMessageDiv) {
        const currentText = currentMessageDiv.getAttribute('data-full-text') || '';
        const newText = currentText + chunk;
        currentMessageDiv.setAttribute('data-full-text', newText);

        // Clean CMD_CARD markers for display (will be rendered at end)
        let displayText = newText.replace(/\[CMD_CARD\].*?\[\/CMD_CARD\]/gs, '');
        currentMessageDiv.innerHTML = marked.parse(displayText);
    }

    container.scrollTop = container.scrollHeight;
}

// Finalize streaming message - render command cards and suggestions
function finalizeStreamingMessage(fullText) {
    if (currentMessageDiv) {
        // Remove the temporary streaming message to prevent duplication
        // The final render via appendAIMessage will replace it
        const wrapper = currentMessageDiv.closest('.flex');
        if (wrapper) {
            wrapper.remove();
        }
        currentMessageDiv = null;
    }

    // Now process the full response for CMD_CARDs and suggestions
    appendAIMessage(fullText, true);  // skipRunButtons = true since we handle cards
}

// Cancel ongoing streaming request
function cancelStreaming() {
    if (currentStreamController && isStreaming) {
        currentStreamController.abort();
        showToast('Response cancelled', 'info');
    }
}

function showTypingIndicator() {
    AIChatBase.showTypingIndicator('AI is thinking...');
}

function removeTypingIndicator() {
    AIChatBase.removeTypingIndicator();
}

// Utility Functions
function escapeHtml(text) {
    return AIChatBase.escapeHtml(text);
}

function copyToClipboard(text) {
    return AIChatBase.copyToClipboard(text);
}

// Clear Chat Functions
function clearChat() {
    document.getElementById('clearChatModal').classList.remove('hidden');
}

function closeClearChatModal() {
    document.getElementById('clearChatModal').classList.add('hidden');
}

function confirmClearChat() {
    closeClearChatModal();
    const container = document.getElementById('chatMessages');
    container.innerHTML = '';
    showWelcomeScreen();
    lastMessageRole = null;
    currentMessageDiv = null;
    showToast('Chat cleared', 'success');
}

// Event Listeners
document.addEventListener('keydown', function (e) {
    if (e.target && e.target.id === 'chatInput') {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(e);
        }
    }
    // Ctrl+L - Clear chat
    if (e.ctrlKey && e.key === 'l') {
        e.preventDefault();
        clearChat();
    }
    // Ctrl+K - Focus chat input
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        const input = document.getElementById('chatInput');
        if (input) input.focus();
    }
    // Ctrl+` - Focus terminal
    if (e.ctrlKey && e.key === '`') {
        e.preventDefault();
        if (term) term.focus();
    }
    // Escape - Clear chat input
    if (e.key === 'Escape') {
        const input = document.getElementById('chatInput');
        if (input && document.activeElement === input) {
            input.value = '';
            input.blur();
        }
    }
    // Ctrl+I when not in input - toggle inline chat
    if (e.ctrlKey && e.key === 'i' && !e.target.matches('input, textarea')) {
        e.preventDefault();
        toggleInlineChat();
    }
    // Escape - close inline chat
    if (e.key === 'Escape' && inlineChatVisible) {
        closeInlineChat();
    }
    // Ctrl+Shift+A - Open Agent Mode
    if (e.ctrlKey && e.shiftKey && e.key === 'A') {
        e.preventDefault();
        if (!isAgentMode) {
            openAgentModal();
        } else {
            stopAgent();
        }
    }
});

// Initialize on page load
window.addEventListener('load', function () {
    if (typeof marked === 'undefined') {
        console.error('marked.js failed to load from CDN');
        showToast('Failed to load chat library', 'error');
        return;
    }
    console.log('Initializing AI Chat...');

    // Initialize Base Rendering - configured for Troubleshoot icons
    AIChatBase.init({
        aiIconClass: 'fas fa-robot',
        aiGradientClass: 'from-purple-600 to-blue-600',
        aiName: 'AI Assistant',
        userGradientClass: 'bg-blue-600 shadow-md'
    });

    initChatSession();
});

window.addEventListener('resize', () => {
    if (fitAddon) fitAddon.fit();
});

// Terminal Functions
function initTerminal() {
    if (term) return;
    term = new Terminal({
        cursorBlink: true,
        theme: { background: '#000000', foreground: '#ffffff' },
        fontSize: 12,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace'
    });
    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal'));
    fitAddon.fit();
    window.addEventListener('resize', () => fitAddon.fit());
    term.onData(data => {
        if (terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
            terminalSocket.send(data);
        }
    });
    term.attachCustomKeyEventHandler((event) => {
        if (event.ctrlKey && event.key === 'i' && event.type === 'keydown') {
            event.preventDefault();
            toggleInlineChat();
            return false;
        }
        return true;
    });
    term.onSelectionChange(() => {
        const selection = term.getSelection();
        if (selection && selection.trim().length > 0) {
            showExplainButton(selection);
        } else {
            hideExplainButton();
        }
    });
}

// Server Modal Functions
async function openServerModal() {
    const modal = document.getElementById('serverModal');
    const list = document.getElementById('serverList');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    try {
        const response = await apiCall('/api/servers');
        if (!response.ok) throw new Error('Failed to load servers');
        const servers = await response.json();
        storedServers = servers; // Cache for protocol lookup
        if (servers.length === 0) {
            list.innerHTML = '<p class="text-gray-400 text-sm p-2">No servers configured.</p>';
            return;
        }
        list.innerHTML = servers.map(server => `
            <div class="p-3 bg-gray-800 rounded cursor-pointer hover:bg-gray-700 transition-colors" onclick="connectTerminal('${server.id}')">
                <div class="flex justify-between items-center">
                    <div class="font-bold text-blue-400">${server.name}</div>
                    <span class="text-xs bg-gray-700 px-2 py-1 rounded">${server.environment}</span>
                </div>
                <div class="text-xs text-gray-400 mt-1">
                    <i class="fas fa-server mr-1"></i>${server.username}@${server.hostname}:${server.port}
                </div>
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = `<p class="text-red-400 text-sm p-2">Error: ${error.message}</p>`;
    }
}

function closeServerModal() {
    const modal = document.getElementById('serverModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    // Reset to saved servers tab
    switchServerTab('saved');
}

function switchServerTab(tab) {
    const tabSaved = document.getElementById('tabSavedServers');
    const tabQuick = document.getElementById('tabQuickConnect');
    const paneSaved = document.getElementById('savedServersPane');
    const paneQuick = document.getElementById('quickConnectPane');

    if (tab === 'saved') {
        tabSaved.className = 'px-4 py-2 text-sm font-medium border-b-2 border-purple-500 text-purple-400';
        tabQuick.className = 'px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-400 hover:text-gray-300';
        paneSaved.classList.remove('hidden');
        paneQuick.classList.add('hidden');
    } else {
        tabSaved.className = 'px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-400 hover:text-gray-300';
        tabQuick.className = 'px-4 py-2 text-sm font-medium border-b-2 border-purple-500 text-purple-400';
        paneSaved.classList.add('hidden');
        paneQuick.classList.remove('hidden');
        // Focus on host input
        setTimeout(() => document.getElementById('adhocHost')?.focus(), 100);
    }
}

function connectAdhoc() {
    const host = document.getElementById('adhocHost').value.trim();
    const port = parseInt(document.getElementById('adhocPort').value) || 22;
    const username = document.getElementById('adhocUsername').value.trim();
    const password = document.getElementById('adhocPassword').value;

    if (!host) {
        showToast('Please enter a hostname or IP address', 'error');
        return;
    }
    if (!username) {
        showToast('Please enter a username', 'error');
        return;
    }

    closeServerModal();
    initTerminal();

    // Mark as ad-hoc connection (no server ID)
    currentServerId = null;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('token');

    if (terminalSocket) terminalSocket.close();

    // Build WebSocket URL with query parameters
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal/adhoc?token=${encodeURIComponent(token)}&host=${encodeURIComponent(host)}&port=${port}&username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}&cols=${term.cols}&rows=${term.rows}`;

    terminalSocket = new WebSocket(wsUrl);

    document.getElementById('termStatus').textContent = `Connecting to ${host}...`;
    document.getElementById('termStatus').className = 'text-xs text-yellow-400';

    terminalSocket.onopen = () => {
        document.getElementById('termStatus').textContent = `${username}@${host}`;
        document.getElementById('termStatus').className = 'text-xs text-green-400';
        term.reset();
        term.write(`\r\n\x1b[32mConnected to ${host}...\x1b[0m\r\n`);
        showToast(`Connected to ${host}`, 'success');
    };

    terminalSocket.onmessage = (event) => {
        const data = event.data;
        if (data.startsWith('{"type":')) {
            try {
                const msg = JSON.parse(data);
                if (msg.type === 'ping' || msg.type === 'pong') return;
                if (msg.type === 'error') {
                    term.write(`\r\n\x1b[31mError: ${msg.message}\x1b[0m\r\n`);
                    return;
                }
                return;
            } catch (e) { }
        }
        term.write(data);
    };

    terminalSocket.onclose = () => {
        document.getElementById('termStatus').textContent = 'Disconnected';
        document.getElementById('termStatus').className = 'text-xs text-red-400';
        term.write('\r\n\x1b[31mConnection closed.\x1b[0m\r\n');
    };

    terminalSocket.onerror = (error) => {
        console.error('Ad-hoc WebSocket error:', error);
        showToast(`Connection failed to ${host}`, 'error');
    };

    // Clear password from input for security
    document.getElementById('adhocPassword').value = '';
}

function connectTerminal(serverId) {
    closeServerModal();
    initTerminal();
    currentServerId = serverId;

    // Find server to determine protocol
    const server = storedServers.find(s => s.id === serverId);
    if (server) {
        currentServerProtocol = server.protocol || 'ssh';
        console.log(`Connected to ${server.name} via ${currentServerProtocol}`);
    } else {
        currentServerProtocol = 'ssh'; // Default
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('token');
    if (terminalSocket) terminalSocket.close();
    terminalSocket = new WebSocket(`${protocol}//${window.location.host}/ws/terminal/${serverId}?token=${token}&cols=${term.cols}&rows=${term.rows}`);
    document.getElementById('termStatus').textContent = 'Connecting...';
    document.getElementById('termStatus').className = 'text-xs text-yellow-400';
    terminalSocket.onopen = () => {
        document.getElementById('termStatus').textContent = 'Connected';
        document.getElementById('termStatus').className = 'text-xs text-green-400';
        term.reset();
        term.write('\r\n\x1b[32mConnected to server...\x1b[0m\r\n');
    };
    terminalSocket.onmessage = (event) => {
        const data = event.data;
        if (data.startsWith('{"type":')) {
            try {
                const msg = JSON.parse(data);
                if (msg.type === 'ping' || msg.type === 'pong') return;
                if (msg.type === 'error') {
                    term.write(`\r\n\x1b[31mError: ${msg.message}\x1b[0m\r\n`);
                    return;
                }
                return;
            } catch (e) { }
        }
        term.write(data);
    };
    terminalSocket.onclose = () => {
        document.getElementById('termStatus').textContent = 'Disconnected';
        document.getElementById('termStatus').className = 'text-xs text-red-400';
        term.write('\r\n\x1b[31mConnection closed.\x1b[0m\r\n');
    };
}

// Protocol-aware Command Execution
async function executeCommandWithOutput(cardId, command) {
    const card = document.getElementById(cardId);
    if (!card || !currentServerId) {
        showToast('No server connected. Connect to a server first.', 'error');
        return;
    }

    console.log(`Executing command via ${currentServerProtocol}: ${command}`);

    if (currentServerProtocol === 'ssh') {
        await tryAdaptiveExecution(cardId, command);
    } else {
        await executeWinRmWithTimeout(cardId, command);
    }
}

// SSH: Terminal-Centric Execution (User Preferred)
async function tryAdaptiveExecution(cardId, command) {
    const card = document.getElementById(cardId);
    const actionsDiv = card.querySelector('.cmd-actions');

    // Reset cancellation flag at start of new command
    pendingCommandCancelled = false;

    // Remember terminal buffer position before command
    const startLine = term ? term.buffer.active.baseY + term.buffer.active.cursorY : 0;

    // 1. Send to terminal (Real Execution)
    if (terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
        terminalSocket.send(command + '\r');
    } else {
        showToast('Terminal not connected', 'error');
        actionsDiv.innerHTML = '<div class="text-red-400 text-sm p-2">Error: Terminal disconnected</div>';
        return;
    }

    // 2. Show "Running" status
    actionsDiv.innerHTML = `
        <div class="flex flex-col gap-2 p-3 bg-gray-900 rounded border border-gray-700">
            <div class="text-green-400 text-sm font-bold animate-pulse">
                <i class="fas fa-terminal mr-2"></i>Running in Terminal...
            </div>
            <div class="text-gray-300 text-xs">
                Waiting for command to complete (auto-capture in 30s)...
            </div>
        </div>
    `;

    // 3. Poll for command completion (check for prompt return)
    const TIMEOUT_MS = 30000;
    const POLL_INTERVAL = 1000;
    let elapsed = 0;

    const checkCompletion = () => {
        if (!term) return false;

        // Get current terminal content after command
        const currentLine = term.buffer.active.baseY + term.buffer.active.cursorY;
        if (currentLine <= startLine) return false;

        // Check if we've returned to a shell prompt (ends with $ or # or >)
        const lastLine = term.buffer.active.getLine(currentLine);
        if (lastLine) {
            const text = lastLine.translateToString(true).trim();
            if (text.endsWith('$') || text.endsWith('#') || text.endsWith('>') || text.endsWith(':~$')) {
                return true;
            }
        }
        return false;
    };

    const pollPromise = new Promise((resolve) => {
        const interval = setInterval(() => {
            elapsed += POLL_INTERVAL;

            // Check if user cancelled by sending a new message
            if (pendingCommandCancelled) {
                clearInterval(interval);
                resolve('cancelled');
            } else if (checkCompletion()) {
                clearInterval(interval);
                resolve('completed');
            } else if (elapsed >= TIMEOUT_MS) {
                clearInterval(interval);
                resolve('timeout');
            }
        }, POLL_INTERVAL);
    });

    const result = await pollPromise;

    if (result === 'completed') {
        // Auto-capture output
        await captureTerminalOutput(cardId, command);
    } else if (result === 'cancelled') {
        // User sent a new message - cancel this command
        actionsDiv.innerHTML = `
            <div class="text-gray-400 text-sm p-2">
                <i class="fas fa-ban mr-2"></i>Command cancelled - processing your new message...
            </div>
        `;
    } else {
        // Timeout - show manual capture button
        actionsDiv.innerHTML = `
            <div class="flex flex-col gap-2 p-3 bg-gray-900 rounded border border-yellow-600">
                <div class="text-yellow-400 text-sm font-bold">
                    <i class="fas fa-clock mr-2"></i>Command may need interaction
                </div>
                <div class="text-gray-300 text-xs">
                    The command is taking longer than expected. Please interact with it in the terminal, then:
                </div>
                <button onclick="captureTerminalOutput('${cardId}', '${command.replace(/'/g, "\\'")}')" 
                        class="w-full bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded text-sm transition-colors flex items-center justify-center mt-2">
                    <i class="fas fa-camera mr-2"></i>Capture Output & Continue
                </button>
            </div>
        `;
    }
}

// Helper to capture terminal buffer
async function captureTerminalOutput(cardId, command) {
    if (!term) {
        showToast('Terminal instance not found', 'error');
        return;
    }

    // Capture last 100 lines of buffer
    const buffer = [];
    const activeBuffer = term.buffer.active;
    const end = activeBuffer.baseY + activeBuffer.cursorY;
    const start = Math.max(0, end - 100);

    for (let i = start; i <= end; i++) {
        const line = activeBuffer.getLine(i);
        if (line) {
            buffer.push(line.translateToString(true));
        }
    }
    const output = buffer.join('\n');

    // Auto-detect success from output (look for error patterns) - for internal tracking
    const hasErrors = /error|failed|failure|exception|denied|not found|cannot|unable/i.test(output);
    const autoSuccess = !hasErrors;

    // Show simple "Output captured" status (no per-command feedback)
    const card = document.getElementById(cardId);
    if (card) {
        const actionsDiv = card.querySelector('.cmd-actions');
        if (actionsDiv) {
            actionsDiv.innerHTML = '<div class="text-green-400 text-sm p-2"><i class="fas fa-check mr-2"></i>Output captured.</div>';
        }
    }

    // Send to Agent
    showToast('Output captured and sent to Agent', 'success');
    await autoSendCommandOutputToAgent(command, output, autoSuccess, 0);

    // Show session feedback button after first command
    showSessionFeedbackButton();
}

// Submit feedback on whether a solution worked
// function submitFeedback removed (replaced by robust version above)

// Auto-save command execution outcome for learning system (fire-and-forget)
async function saveCommandOutcome(command, output, success, exitCode) {
    try {
        // Truncate output for storage
        const truncatedOutput = output ? output.substring(0, 500) : '';

        await apiCall('/api/v1/solution-feedback', {
            method: 'POST',
            body: JSON.stringify({
                solution_type: 'command',
                solution_reference: command,
                success: success,
                session_id: currentSessionId,
                problem_description: `Command: ${command}\nExit code: ${exitCode}\nOutput: ${truncatedOutput}`
            })
        });
        console.debug('[AIQ] Auto-saved command outcome for learning', { command: command.substring(0, 50), success, exitCode });
    } catch (error) {
        // Fire-and-forget - don't block on errors
        console.debug('[AIQ] Failed to auto-save command outcome:', error);
    }
}

// ============================================================================
// Session-Level Feedback (Floating Button)
// ============================================================================

let sessionFeedbackButtonVisible = false;

// ============================================================================
// Agent Mode: Execute in Terminal (not in background)
// ============================================================================

let currentApprovalStep = null;
let agentCommandInFlight = false;

async function executeAgentStepInTerminal(step) {
    if (!step || !step.content) return;
    if (!terminalSocket || terminalSocket.readyState !== WebSocket.OPEN) {
        showToast('Terminal not connected (agent cannot execute)', 'error');
        return;
    }
    if (!agentSocket || agentSocket.readyState !== WebSocket.OPEN) {
        showToast('Agent connection not ready', 'error');
        return;
    }
    if (agentCommandInFlight) {
        showToast('Another agent command is still running', 'info');
        return;
    }

    agentCommandInFlight = true;
    try {
        const sanitizeAgentCommand = (cmd) => {
            if (!cmd || typeof cmd !== 'string') return cmd;
            let out = cmd.trim();

            // Avoid systemd pager blocking the terminal ("press q")
            if (/^\s*systemctl\s+status\b/i.test(out) && !/\s--no-pager\b/i.test(out)) {
                out = out + ' --no-pager';
            }

            // Avoid journalctl pager blocking the terminal
            if (/^\s*journalctl\b/i.test(out) && !/\s--no-pager\b/i.test(out)) {
                out = out + ' --no-pager';
            }

            return out;
        };

        // Use the same terminal-centric execution used elsewhere in /troubleshoot.
        const cmd = sanitizeAgentCommand(step.content);
        const result = await executeCommandViaTerminal(cmd, currentServerId);
        const output = (result && result.output) ? result.output : '';
        const exitCode = (result && typeof result.exitCode === 'number') ? result.exitCode : 0;

        agentSocket.send(JSON.stringify({
            type: 'command_result',
            output: output,
            exit_code: exitCode
        }));
    } catch (e) {
        console.error('Agent terminal execution failed:', e);
        agentSocket.send(JSON.stringify({
            type: 'command_result',
            output: `Terminal execution failed: ${e && e.message ? e.message : String(e)}`,
            exit_code: 1
        }));
    } finally {
        agentCommandInFlight = false;
    }
}

// Show floating feedback button after first command execution
function showSessionFeedbackButton() {
    if (sessionFeedbackButtonVisible) return;
    sessionFeedbackButtonVisible = true;

    // Create floating button container
    const existingBtn = document.getElementById('sessionFeedbackBtn');
    if (existingBtn) return;

    const feedbackBtn = document.createElement('div');
    feedbackBtn.id = 'sessionFeedbackBtn';
    feedbackBtn.innerHTML = `
        <div class="fixed bottom-20 left-4 z-50 flex flex-col items-start gap-2">
            <div id="sessionFeedbackExpanded" class="hidden bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-xl">
                <div class="text-gray-300 text-sm mb-2 font-medium">Was this session helpful?</div>
                <div class="flex gap-2">
                    <button onclick="submitSessionFeedback(true)" 
                            class="bg-green-600 hover:bg-green-500 text-white text-sm px-4 py-2 rounded transition-colors flex items-center">
                        <i class="fas fa-thumbs-up mr-2"></i>Yes
                    </button>
                    <button onclick="submitSessionFeedback(false)" 
                            class="bg-red-600 hover:bg-red-500 text-white text-sm px-4 py-2 rounded transition-colors flex items-center">
                        <i class="fas fa-thumbs-down mr-2"></i>No
                    </button>
                    <button onclick="hideSessionFeedbackExpanded()" 
                            class="bg-gray-600 hover:bg-gray-500 text-white text-sm px-2 py-2 rounded transition-colors">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <button onclick="toggleSessionFeedback()" 
                    class="bg-blue-600 hover:bg-blue-500 text-white p-3 rounded-full shadow-lg transition-all hover:scale-110"
                    title="Rate this session">
                <i class="fas fa-star text-lg"></i>
            </button>
        </div>
    `;
    document.body.appendChild(feedbackBtn);
}

function toggleSessionFeedback() {
    const expanded = document.getElementById('sessionFeedbackExpanded');
    if (expanded) {
        expanded.classList.toggle('hidden');
    }
}

function hideSessionFeedbackExpanded() {
    const expanded = document.getElementById('sessionFeedbackExpanded');
    if (expanded) {
        expanded.classList.add('hidden');
    }
}

async function submitSessionFeedback(success) {
    // Collect session info
    const sessionCommands = commandHistory.map(h => h.command).join(', ').substring(0, 500);

    try {
        await apiCall('/api/v1/solution-feedback', {
            method: 'POST',
            body: JSON.stringify({
                solution_type: 'session',
                solution_reference: sessionCommands || 'No commands executed',
                success: success,
                session_id: currentSessionId,
                problem_description: `Session started at ${new Date().toISOString()}`
            })
        });

        // Visual feedback
        const btn = document.getElementById('sessionFeedbackBtn');
        if (btn) {
            btn.innerHTML = `
                <div class="fixed bottom-20 left-4 z-50">
                    <div class="bg-${success ? 'green' : 'yellow'}-600 text-white px-4 py-2 rounded-lg shadow-lg">
                        <i class="fas fa-${success ? 'check' : 'times'} mr-2"></i>
                        ${success ? 'Thanks! Feedback recorded.' : 'Thanks for letting us know.'}
                    </div>
                </div>
            `;
            // Hide after 3 seconds
            setTimeout(() => {
                btn.remove();
                sessionFeedbackButtonVisible = false;
            }, 3000);
        }
    } catch (error) {
        console.error('Failed to submit session feedback:', error);
        showToast('Failed to submit feedback', 'error');
    }
}

// WinRM: Simple Execution with Timeout Warning
async function executeWinRmWithTimeout(cardId, command) {
    const card = document.getElementById(cardId);
    const actionsDiv = card.querySelector('.cmd-actions');
    actionsDiv.innerHTML = '<div class="flex-1 flex items-center justify-center text-blue-400 text-sm py-2"><i class="fas fa-spinner fa-spin mr-2"></i>Executing via WinRM...</div>';

    try {
        // Standard execute endpoint
        const response = await apiCall(`/api/servers/${currentServerId}/execute`, {
            method: 'POST',
            body: JSON.stringify({ command: command, timeout: 60 })
        });
        const result = await response.json();

        const isSuccess = (result.exit_code === 0) || (result.success === true);

        let output = result.stdout || result.stderr;

        if (result.error && result.error.includes('timed out')) {
            // Fallback for timeout
            showWinRMFallback(cardId, command);
            return;
        }

        output = output || (isSuccess ? 'Command completed successfully' : (result.error || 'Command failed'));

        showCommandOutputInCard(cardId, command, output, isSuccess, result.exit_code);
        await autoSendCommandOutputToAgent(command, output, isSuccess, result.exit_code);

    } catch (error) {
        showToast('WinRM Execution failed: ' + error.message, 'error');
    }
}

function showInteractivePrompt(cardId, command, partialOutput, processId) {
    const card = document.getElementById(cardId);
    if (!card) return;

    // Ensure we don't have duplicates
    const existingPrompt = card.querySelector('.interactive-prompt');
    if (existingPrompt) existingPrompt.remove();

    const promptId = `prompt-${processId}`;
    const outputPreview = partialOutput ? `
        <div class="bg-black rounded p-2 text-xs font-mono text-gray-300 mb-3 max-h-32 overflow-y-auto border border-gray-700">
            ${escapeHtml(partialOutput)}
        </div>
    ` : '';

    const actionsDiv = card.querySelector('.cmd-actions');
    actionsDiv.innerHTML = `
        <div class="interactive-prompt bg-yellow-900/20 border-t border-yellow-500/30 p-3 w-full rounded">
            <div class="text-yellow-400 text-sm mb-2 flex items-center">
                <i class="fas fa-keyboard mr-2 animate-pulse"></i>
                <span>Command is waiting for input...</span>
            </div>
            
            ${outputPreview}
            
            <input type="text" 
                   class="bg-gray-800 border border-gray-600 text-white px-3 py-2 rounded w-full mb-2 focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm" 
                   placeholder="Type input and press Enter..." 
                   id="input-${promptId}">
            
            <div class="flex space-x-2">
                <button class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm px-3 py-1.5 rounded transition-colors flex items-center justify-center" 
                        onclick="sendInteractiveInput('${cardId}', '${promptId}', '${processId}', '${escapeHtml(command).replace(/'/g, "\\'")}')">
                    <i class="fas fa-paper-plane mr-2"></i>Send
                </button>
                <button class="bg-red-600/80 hover:bg-red-500 text-white text-sm px-3 py-1.5 rounded transition-colors" 
                        onclick="cancelInteractiveCommand('${cardId}', '${processId}')">
                    Cancel
                </button>
            </div>
        </div>
    `;

    // Focus input
    setTimeout(() => {
        const input = document.getElementById(`input-${promptId}`);
        if (input) {
            input.focus();
            // Handle Enter key
            input.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    sendInteractiveInput(cardId, promptId, processId, command);
                }
            };
        }
    }, 100);
}

async function sendInteractiveInput(cardId, promptId, processId, command) {
    const inputEl = document.getElementById(`input-${promptId}`);
    if (!inputEl) return;

    const userInput = inputEl.value;
    inputEl.disabled = true;

    // Show spinner on button
    const btn = inputEl.parentElement.querySelector('button');
    if (btn) btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const response = await apiCall(`/api/servers/${currentServerId}/send-input`, {
            method: 'POST',
            body: JSON.stringify({
                process_id: processId,
                user_input: userInput,
                wait_timeout: 3
            })
        });
        const result = await response.json();

        if (result.completed) {
            // Finished!
            const isSuccess = (result.exit_code === 0);
            // Combine previous output if we tracked it, but here we just show what returned
            // Actually, for better UX we might want to append to terminal

            showCommandOutputInCard(cardId, command, result.output, isSuccess, result.exit_code);
            await autoSendCommandOutputToAgent(command, result.output, isSuccess, result.exit_code);

        } else {
            // Still waiting - clear input and show more output
            inputEl.disabled = false;
            inputEl.value = '';
            inputEl.focus();
            if (btn) btn.innerHTML = '<i class="fas fa-paper-plane mr-2"></i>Send';

            // Append output to preview if possible, for now just update
            if (result.output) {
                const preview = document.querySelector(`#${cardId} .interactive-prompt .bg-black`);
                if (preview) {
                    preview.innerHTML += escapeHtml(result.output);
                    preview.scrollTop = preview.scrollHeight;
                }
            }
        }
    } catch (error) {
        showToast('Failed to send input: ' + error.message, 'error');
        inputEl.disabled = false;
        if (btn) btn.innerHTML = '<i class="fas fa-paper-plane mr-2"></i>Send';
    }
}

async function cancelInteractiveCommand(cardId, processId) {
    try {
        const url = `/api/servers/${currentServerId}/cancel-process?process_id=${processId}`;
        await apiCall(url, { method: 'POST' });

        const card = document.getElementById(cardId);
        if (card) {
            const actionsDiv = card.querySelector('.cmd-actions');
            actionsDiv.innerHTML = '<div class="text-red-400 text-sm p-2"><i class="fas fa-ban mr-2"></i>Command cancelled by user.</div>';
        }
    } catch (error) {
        showToast('Failed to cancel: ' + error.message, 'error');
    }
}

function showWinRMFallback(cardId, command) {
    const card = document.getElementById(cardId);
    const actionsDiv = card.querySelector('.cmd-actions');
    actionsDiv.innerHTML = `
        <div class="bg-yellow-900/30 p-3 rounded text-sm mb-2">
            <p class="text-yellow-400 mb-1"><i class="fas fa-exclamation-triangle mr-2"></i>Timeout (WinRM)</p>
            <p class="text-gray-400 mb-2">Command may be waiting for input, which isn't supported via WinRM.</p>
            <div class="flex space-x-2">
                <button class="text-blue-400 hover:text-blue-300 underline" onclick="copyToClipboard('${escapeHtml(command).replace(/'/g, "\\'")}')">Copy Command</button>
                <span class="text-gray-600">|</span>
                <span class="text-gray-500">Run via RDP instead</span>
            </div>
        </div>
    `;
}

async function autoSendCommandOutputToAgent(command, output, isSuccess, exitCode) {
    // Wait 2 seconds for terminal buffer to update
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Build automatic message to Agent
    const statusEmoji = isSuccess ? '✅' : '❌';
    const autoMessage = `${statusEmoji} Command executed:\n\`\`\`\n${command}\n\`\`\`\n\nExit code: ${exitCode}\n\nOutput:\n\`\`\`\n${output.substring(0, 1000)}${output.length > 1000 ? '\n...(truncated)' : ''}\n\`\`\`\n\nWhat should I do next?`;

    // Add to UI as user message, but visually distinct (auto)
    appendUserMessage(`[Auto-Report] Command execution complete.`);

    // Show typing indicator
    showTypingIndicator();

    // Send to Agent via SSE streaming (same as regular messages)
    const termContent = getTerminalContent();
    let finalMessage = autoMessage;
    if (termContent) {
        finalMessage += `\n\n[TERMINAL CONTEXT]\n\`\`\`\n${termContent}\n\`\`\``;
    }

    // Use streaming for auto-send as well
    await sendStreamingMessage(finalMessage);
    console.log('✅ Auto-sent command output to Agent via SSE stream');
}

function showCommandOutputInCard(cardId, command, output, success, exitCode) {
    const card = document.getElementById(cardId);
    if (!card) return;
    const isSuccess = success && (exitCode === null || exitCode === 0);
    const statusText = isSuccess ? (exitCode !== null ? `Executed (exit code: ${exitCode})` : 'Executed successfully') : `Failed (exit code: ${exitCode !== null ? exitCode : 'unknown'})`;
    const statusColor = isSuccess ? 'text-green-400' : 'text-red-400';
    const statusIcon = isSuccess ? 'fa-check-circle' : 'fa-times-circle';
    const actionsDiv = card.querySelector('.cmd-actions');
    actionsDiv.innerHTML = `<div class="flex-1 flex items-center ${statusColor} text-sm py-2"><i class="fas ${statusIcon} mr-2"></i>${statusText}</div><button class="toggle-output-btn text-gray-400 hover:text-white text-sm px-3 py-2 transition-colors" title="Toggle output"><i class="fas fa-chevron-down"></i></button>`;
    const outputDiv = card.querySelector('.cmd-output');
    if (outputDiv && output) {
        let displayOutput = output;
        if (displayOutput.length > 3000) {
            displayOutput = displayOutput.substring(0, 1500) + '\n... [truncated] ...\n' + displayOutput.substring(displayOutput.length - 1500);
        }
        outputDiv.innerHTML = `<div class="border-t border-gray-700 p-3 bg-gray-900/50"><div class="text-xs text-gray-400 mb-2"><i class="fas fa-terminal mr-1"></i>Output</div><pre class="bg-gray-950 rounded p-3 text-xs text-gray-300 overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap">${escapeHtml(displayOutput)}</pre></div>`;
        outputDiv.classList.remove('hidden');
    }
    const toggleBtn = card.querySelector('.toggle-output-btn');
    if (toggleBtn && outputDiv) {
        toggleBtn.onclick = () => {
            outputDiv.classList.toggle('hidden');
            const icon = toggleBtn.querySelector('i');
            icon.className = outputDiv.classList.contains('hidden') ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
        };
    }
    addToCommandHistory(command, output, exitCode, isSuccess);
}

function rerunCommand(command) {
    if (!currentServerId) {
        showToast('Connect to a server first', 'error');
        return;
    }
    showToast('Re-running: ' + command.substring(0, 30) + '...', 'success');
    if (terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
        terminalSocket.send(command + '\r');
        term.focus();
    }
}

// Command Card Functions (for AI-suggested commands)
function addRunButtons(element) {
    const blocks = element.querySelectorAll('pre code');
    let commandCount = 0;  // Track how many commands we've found

    blocks.forEach(block => {
        const pre = block.parentElement;
        if (pre.querySelector('.code-actions') || pre.closest('.command-card')) return;

        // Get language class
        const lang = block.className.match(/language-(\w+)/)?.[1] || '';
        const content = block.innerText.trim();

        // Detect bash/shell commands
        const isExplicitShell = ['shell', 'bash', 'sh', 'zsh', 'fish'].includes(lang);
        const isUnmarked = lang === '';

        // Enhanced detection: if it looks like a command, create a button
        const looksLikeCommand = isActualCommand(content);

        if (isExplicitShell || (looksLikeCommand && (isUnmarked || lang === 'bash'))) {
            commandCount++;

            // ONLY show the FIRST command with a Run button
            if (commandCount === 1) {
                createCommandCard(pre, content);
            } else {
                // Just add copy button for extra commands (no Run button)
                addCopyButton(pre, block, lang || 'bash');
            }
        } else {
            addCopyButton(pre, block, lang || 'text');
        }
    });
}

function isActualCommand(content) {
    if (!content || content.length < 2) return false;
    if (content.includes('?')) return false;
    if (/^\d+\.\s/.test(content)) return false;
    if (/^[\*\-]\s/.test(content)) return false;
    const commandPatterns = [/^(sudo\s+)?[a-z_][a-z0-9_-]*\s/i, /^\$\s/, /^cd\s/, /^ls(\s|$)/, /^cat\s/, /^echo\s/, /^grep\s/, /^docker\s/, /^kubectl\s/, /^systemctl\s/, /^journalctl\s/, /^tail\s/, /^ps\s/, /^df\s/, /^du\s/, /^free(\s|$)/];
    for (const pattern of commandPatterns) {
        if (pattern.test(content)) return true;
    }
    if (!content.includes('\n') && content.length < 50 && /^[a-z_][a-z0-9_-]*$/i.test(content)) return true;
    return false;
}

function createCommandCard(pre, command) {
    const cardId = 'cmd-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    const card = document.createElement('div');
    card.id = cardId;
    card.className = 'command-card bg-gradient-to-r from-gray-800 to-gray-800/80 rounded-lg border border-purple-500/30 my-3 overflow-hidden';
    card.innerHTML = `<div class="flex items-center justify-between px-3 py-2 bg-gray-900/50 border-b border-gray-700"><div class="flex items-center text-xs text-gray-400"><i class="fas fa-terminal text-green-400 mr-2"></i><span>Command</span></div><div class="flex space-x-1"><button class="copy-cmd-btn bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded transition-colors" title="Copy"><i class="fas fa-copy"></i></button></div></div><div class="p-3"><div class="bg-gray-900 rounded p-3 font-mono text-sm text-green-400 whitespace-pre-wrap break-all">${escapeHtml(command)}</div></div><div class="cmd-actions flex space-x-2 px-3 pb-3"><button class="run-cmd-btn flex-1 bg-green-600 hover:bg-green-500 text-white text-sm px-4 py-2 rounded font-medium transition-colors flex items-center justify-center"><i class="fas fa-play mr-2"></i>Run in Terminal</button><button class="skip-cmd-btn bg-gray-600 hover:bg-gray-500 text-white text-sm px-3 py-2 rounded font-medium transition-colors" title="Skip this command"><i class="fas fa-forward"></i></button></div><div class="cmd-output hidden"></div>`;
    pre.parentNode.replaceChild(card, pre);
    card.querySelector('.copy-cmd-btn').onclick = () => {
        copyToClipboard(command).then(() => {
            card.querySelector('.copy-cmd-btn').innerHTML = '<i class="fas fa-check text-green-400"></i>';
            setTimeout(() => { card.querySelector('.copy-cmd-btn').innerHTML = '<i class="fas fa-copy"></i>'; }, 2000);
        });
    };
    card.querySelector('.run-cmd-btn').onclick = () => executeCommandWithOutput(cardId, command);
    card.querySelector('.skip-cmd-btn').onclick = () => {
        const actionsDiv = card.querySelector('.cmd-actions');
        actionsDiv.innerHTML = '<div class="flex-1 flex items-center text-gray-500 text-sm py-2"><i class="fas fa-forward mr-2"></i>Skipped</div>';
        card.style.opacity = '0.6';
    };
}

function addCopyButton(pre, block, lang) {
    const btnContainer = document.createElement('div');
    btnContainer.className = 'code-actions absolute top-1 right-1 flex space-x-1 z-10';
    const langBadge = document.createElement('span');
    langBadge.className = 'bg-gray-800 text-gray-400 text-[10px] px-1.5 py-0.5 rounded';
    langBadge.textContent = lang;
    btnContainer.appendChild(langBadge);
    const copyBtn = document.createElement('button');
    copyBtn.className = 'bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded transition-colors';
    copyBtn.innerHTML = '<i class="fas fa-copy"></i>';
    copyBtn.title = 'Copy code';
    copyBtn.onclick = () => {
        copyToClipboard(block.innerText.trim()).then(() => {
            copyBtn.innerHTML = '<i class="fas fa-check text-green-400"></i>';
            setTimeout(() => { copyBtn.innerHTML = '<i class="fas fa-copy"></i>'; }, 2000);
        });
    };
    btnContainer.appendChild(copyBtn);
    pre.className += ' relative bg-gray-900 rounded-md p-3 my-2 border border-gray-700 whitespace-pre-wrap break-words overflow-x-auto';
    pre.appendChild(btnContainer);
}

// Inline Chat Functions
function toggleInlineChat() {
    const overlay = document.getElementById('inlineChatOverlay');
    if (!overlay) return;
    inlineChatVisible = !inlineChatVisible;
    overlay.classList.toggle('hidden', !inlineChatVisible);
    if (inlineChatVisible) {
        const input = document.getElementById('inlineChatInput');
        if (input) { input.focus(); input.value = ''; }
    } else {
        if (term) term.focus();
    }
}

function closeInlineChat() {
    const overlay = document.getElementById('inlineChatOverlay');
    if (overlay) {
        overlay.classList.add('hidden');
        inlineChatVisible = false;
        if (term) term.focus();
    }
}

function handleInlineChatKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendInlineChat();
    } else if (event.key === 'Escape') {
        closeInlineChat();
    }
}

function getTerminalContext(numLines = 30) {
    if (!term) return '';
    const buffer = term.buffer.active;
    const lines = [];
    const startRow = Math.max(0, buffer.baseY + buffer.cursorY - numLines);
    const endRow = buffer.baseY + buffer.cursorY;
    for (let i = startRow; i <= endRow; i++) {
        const line = buffer.getLine(i);
        if (line) lines.push(line.translateToString(true));
    }
    return lines.join('\n').trim();
}

function sendInlineChat() {
    const input = document.getElementById('inlineChatInput');
    if (!input || !input.value.trim()) return;
    const question = input.value.trim();
    const terminalContext = getTerminalContext();
    const message = `[TERMINAL CONTEXT - Current terminal output]\n\`\`\`\n${terminalContext}\n\`\`\`\n\n[USER QUESTION]\n${question}`;
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(message);
        const container = document.getElementById('chatMessages');
        const msgDiv = document.createElement('div');
        msgDiv.className = 'flex justify-end mb-2';
        msgDiv.innerHTML = `<div class="bg-gradient-to-r from-blue-600 to-blue-500 rounded-2xl rounded-br-sm px-4 py-2 max-w-[75%] shadow-lg"><p class="text-sm text-white whitespace-pre-wrap break-words">${escapeHtml(question)}</p><div class="text-[10px] text-blue-200 mt-1 opacity-70"><i class="fas fa-terminal mr-1"></i>from terminal</div></div>`;
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
        showTypingIndicator();
    } else {
        showToast('Chat not connected', 'error');
    }
    closeInlineChat();
}

function sendQuickInlineChat(question) {
    document.getElementById('inlineChatInput').value = question;
    sendInlineChat();
}

// Explain Selection
function showExplainButton(selectedText) {
    currentSelection = selectedText;
    const btn = document.getElementById('explainSelectionBtn');
    if (!btn) return;
    btn.style.top = '8px';
    btn.style.right = '8px';
    btn.classList.remove('hidden');
}

function hideExplainButton() {
    const btn = document.getElementById('explainSelectionBtn');
    if (btn) btn.classList.add('hidden');
    currentSelection = '';
}

function explainSelectedText() {
    if (!currentSelection || !currentSelection.trim()) {
        showToast('No text selected', 'error');
        return;
    }
    const message = `[EXPLAIN TERMINAL OUTPUT]\nPlease explain the following terminal output:\n\n\`\`\`\n${currentSelection}\n\`\`\`\n\nWhat does this mean? Is there an error? What action should I take?`;
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(message);
        showTypingIndicator();
        showToast('Asking AI to explain...', 'success');
    } else {
        showToast('Chat not connected', 'error');
    }
    hideExplainButton();
    term.clearSelection();
}

// Agent Mode Functions
function openAgentModal() {
    if (!terminalSocket || terminalSocket.readyState !== WebSocket.OPEN) {
        showToast('Please connect to a server first', 'error');
        return;
    }
    const modal = document.getElementById('agentModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.getElementById('agentGoal').focus();
}

function closeAgentModal() {
    const modal = document.getElementById('agentModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.getElementById('agentGoal').value = '';
    document.getElementById('autoApprove').checked = false;
}

async function startAgent() {
    const goal = document.getElementById('agentGoal').value.trim();
    const autoApprove = document.getElementById('autoApprove').checked;
    if (!goal) { showToast('Please enter a goal for the agent', 'error'); return; }
    if (!currentServerId) { showToast('Please connect to a server first', 'error'); return; }
    try {
        const response = await apiCall('/api/agent/start', {
            method: 'POST',
            body: JSON.stringify({ chat_session_id: currentSessionId, server_id: currentServerId, goal: goal, auto_approve: autoApprove })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start agent');
        }
        currentAgentSession = await response.json();
        closeAgentModal();
        enterAgentMode(goal);
        connectAgentWebSocket(currentAgentSession.id);
    } catch (error) {
        console.error('Failed to start agent:', error);
        showToast(error.message || 'Failed to start agent', 'error');
    }
}

function enterAgentMode(goal) {
    isAgentMode = true;
    const container = document.getElementById('chatMessages');
    container.innerHTML = `<div id="agentHeader" class="agent-header-banner rounded-lg p-4 mb-4"><div class="flex items-center justify-between"><div class="flex items-center"><div class="w-8 h-8 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center mr-3 animate-pulse"><i class="fas fa-robot text-white text-sm"></i></div><div><div class="agent-header-title">Agent Mode Active</div><div class="agent-header-goal truncate max-w-xs" title="${escapeHtml(goal)}">${escapeHtml(goal)}</div></div></div><button id="agentStopBtn" onclick="stopAgent()" class="text-red-400 hover:text-red-300 text-xs px-3 py-1 border border-red-500/30 rounded hover:bg-red-500/10 transition-colors"><i class="fas fa-stop mr-1"></i>Stop</button></div><div class="mt-3 flex items-center text-xs"><span id="agentStatusBadge" class="px-2 py-1 rounded bg-purple-600/50 text-purple-200 mr-2"><i class="fas fa-spinner fa-spin mr-1"></i>Starting...</span><span class="text-gray-400">Step <span id="agentStepNum">0</span> of <span id="agentMaxSteps">20</span></span></div></div><div id="agentSteps" class="space-y-4"></div><div id="agentApprovalPanel" class="hidden"></div>`;
    document.getElementById('chatForm').style.display = 'none';
    const agentBtn = document.getElementById('agentModeBtn');
    if (agentBtn) {
        agentBtn.classList.remove('text-gray-400', 'hover:text-purple-400');
        agentBtn.classList.add('text-purple-400', 'animate-pulse');
    }
}

function exitAgentMode() {
    isAgentMode = false;
    currentAgentSession = null;
    if (agentSocket) { agentSocket.close(); agentSocket = null; }
    document.getElementById('chatForm').style.display = 'flex';
    const agentBtn = document.getElementById('agentModeBtn');
    if (agentBtn) {
        agentBtn.classList.remove('text-purple-400', 'animate-pulse');
        agentBtn.classList.add('text-gray-400', 'hover:text-purple-400');
    }
    if (currentSessionId) loadMessageHistory(currentSessionId);
}

function connectAgentWebSocket(sessionId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('token');
    if (agentSocket) agentSocket.close();
    agentSocket = new WebSocket(`${protocol}//${window.location.host}/ws/agent/${sessionId}?token=${token}`);
    agentSocket.onopen = () => { console.log('Agent WebSocket connected'); updateAgentStatus('thinking', 'Analyzing...'); };
    agentSocket.onmessage = (event) => { try { handleAgentMessage(JSON.parse(event.data)); } catch (e) { console.error('Failed to parse agent message:', e); } };
    agentSocket.onclose = () => console.log('Agent WebSocket closed');
    agentSocket.onerror = (error) => { console.error('Agent WebSocket error:', error); showToast('Agent connection error', 'error'); };
}

function handleAgentMessage(data) {
    console.log('Agent message:', data.type, data);
    switch (data.type) {
        case 'connected': updateAgentStatus('thinking', 'Analyzing goal...'); break;
        case 'status_changed': updateAgentStatus(data.status); break;
        case 'step_created': addAgentStep(data.step, data.auto_approve === true); break;
        case 'step_updated': updateAgentStep(data.step); break;
        case 'complete': handleAgentComplete(data); break;
        case 'error': showToast(data.message || 'Agent error', 'error'); break;
    }
}

function updateAgentStatus(status, text) {
    const badge = document.getElementById('agentStatusBadge');
    if (!badge) return;
    const statusMap = {
        'thinking': { icon: 'fa-brain', color: 'bg-purple-600/50 text-purple-200', text: text || 'Thinking...' },
        'awaiting_approval': { icon: 'fa-pause-circle', color: 'bg-yellow-600/50 text-yellow-200', text: 'Awaiting approval' },
        'executing': { icon: 'fa-cog fa-spin', color: 'bg-blue-600/50 text-blue-200', text: 'Executing...' },
        'completed': { icon: 'fa-check-circle', color: 'bg-green-600/50 text-green-200', text: 'Completed' },
        'failed': { icon: 'fa-times-circle', color: 'bg-red-600/50 text-red-200', text: 'Failed' },
        'stopped': { icon: 'fa-stop-circle', color: 'bg-gray-600/50 text-gray-200', text: 'Stopped' }
    };
    const config = statusMap[status] || statusMap.thinking;
    badge.className = `px-2 py-1 rounded ${config.color} mr-2`;
    badge.innerHTML = `<i class="fas ${config.icon} mr-1"></i>${config.text}`;
}

function addAgentStep(step, autoApproveEnabled = false) {
    const container = document.getElementById('agentSteps');
    if (!container) return;
    const stepNum = document.getElementById('agentStepNum');
    if (stepNum) stepNum.textContent = step.step_number;
    const stepEl = document.createElement('div');
    stepEl.id = `agent-step-${step.id}`;
    stepEl.className = 'bg-gray-800 rounded-lg p-4 border border-gray-700';
    if (step.step_type === 'command') {
        stepEl.innerHTML = `<div class="flex items-start"><div class="w-6 h-6 rounded-full bg-blue-600/30 flex items-center justify-center mr-3 mt-0.5 flex-shrink-0"><i class="fas fa-terminal text-blue-400 text-xs"></i></div><div class="flex-grow min-w-0"><div class="text-xs text-gray-400 mb-1">Step ${step.step_number} - Command</div><div class="bg-gray-900 rounded p-2 font-mono text-sm text-green-400 break-all">${escapeHtml(step.content)}</div>${step.reasoning ? `<div class="text-xs text-gray-500 mt-2"><i class="fas fa-lightbulb text-yellow-500 mr-1"></i>${escapeHtml(step.reasoning)}</div>` : ''}<div id="step-output-${step.id}" class="mt-2 hidden"><div class="text-xs text-gray-400 mb-1">Output:</div><pre class="bg-gray-900 rounded p-2 text-xs text-gray-300 overflow-x-auto max-h-40 overflow-y-auto"></pre></div><div id="step-status-${step.id}" class="mt-2 flex items-center text-xs text-gray-400"><i class="fas fa-clock mr-1"></i>Pending...</div></div></div>`;
        if (step.status === 'pending' && !autoApproveEnabled) {
            showApprovalPanel(step);
        } else if (step.status === 'pending' && autoApproveEnabled) {
            // Auto-approve: run immediately in the user's terminal
            executeAgentStepInTerminal(step);
        }
    } else if (step.step_type === 'complete') {
        stepEl.className = 'agent-step-complete rounded-lg p-4';
        stepEl.innerHTML = `<div class="flex items-start"><div class="w-6 h-6 rounded-full agent-step-complete-icon flex items-center justify-center mr-3 mt-0.5 flex-shrink-0"><i class="fas fa-check text-xs"></i></div><div class="flex-grow"><div class="text-xs mb-1 font-semibold agent-step-complete-title">Goal Achieved!</div><div class="text-sm agent-step-complete-body">${marked.parse(step.content)}</div></div></div>`;
    } else if (step.step_type === 'failed') {
        stepEl.className = 'agent-step-failed rounded-lg p-4';
        stepEl.innerHTML = `<div class="flex items-start"><div class="w-6 h-6 rounded-full agent-step-failed-icon flex items-center justify-center mr-3 mt-0.5 flex-shrink-0"><i class="fas fa-times text-xs"></i></div><div class="flex-grow"><div class="text-xs agent-step-failed-title mb-1 font-semibold">Agent Failed</div><div class="text-sm agent-step-failed-body">${escapeHtml(step.content)}</div></div></div>`;
    }
    container.appendChild(stepEl);
    container.scrollTop = container.scrollHeight;
}

function updateAgentStep(step) {
    const outputDiv = document.getElementById(`step-output-${step.id}`);
    const statusDiv = document.getElementById(`step-status-${step.id}`);
    if (step.output && outputDiv) {
        outputDiv.classList.remove('hidden');
        const pre = outputDiv.querySelector('pre');
        if (pre) {
            let output = step.output;
            if (output.length > 5000) output = output.substring(0, 2500) + '\n... [truncated] ...\n' + output.substring(output.length - 2500);
            pre.textContent = output;
        }
    }
    if (statusDiv) {
        if (step.status === 'executed') {
            const exitCode = step.exit_code || 0;
            statusDiv.innerHTML = exitCode === 0 ? '<i class="fas fa-check-circle text-green-400 mr-1"></i>Executed successfully' : `<i class="fas fa-exclamation-circle text-yellow-400 mr-1"></i>Exited with code ${exitCode}`;
            statusDiv.className = `mt-2 flex items-center text-xs ${exitCode === 0 ? 'text-green-400' : 'text-yellow-400'}`;
        } else if (step.status === 'rejected') {
            statusDiv.innerHTML = '<i class="fas fa-ban text-gray-400 mr-1"></i>Skipped by user';
            statusDiv.className = 'mt-2 flex items-center text-xs text-gray-400';
        } else if (step.status === 'failed') {
            statusDiv.innerHTML = '<i class="fas fa-times-circle text-red-400 mr-1"></i>Failed';
            statusDiv.className = 'mt-2 flex items-center text-xs text-red-400';
        }
    }
    hideApprovalPanel();
}

function showApprovalPanel(step) {
    updateAgentStatus('awaiting_approval');
    currentApprovalStep = step;
    const panel = document.getElementById('agentApprovalPanel');
    if (!panel) return;
    panel.className = 'bg-gradient-to-r from-yellow-900/30 to-orange-900/30 rounded-lg p-4 mt-4 border border-yellow-500/30';
    panel.innerHTML = `<div class="flex items-center mb-3"><i class="fas fa-shield-alt text-yellow-400 mr-2"></i><span class="text-sm font-semibold text-yellow-200">Approval Required</span></div><div class="text-xs text-gray-400 mb-2">The agent wants to execute:</div><div class="bg-gray-900 rounded p-3 font-mono text-sm text-green-400 mb-3 break-all">${escapeHtml(step.content)}</div>${step.reasoning ? `<div class="text-xs text-gray-400 mb-3"><i class="fas fa-lightbulb text-yellow-500 mr-1"></i>${escapeHtml(step.reasoning)}</div>` : ''}<div class="flex space-x-2"><button onclick="approveAgentStep()" class="flex-1 bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded font-medium transition-colors"><i class="fas fa-check mr-2"></i>Approve & Run</button><button onclick="rejectAgentStep()" class="bg-gray-600 hover:bg-gray-500 text-white px-4 py-2 rounded font-medium transition-colors"><i class="fas fa-forward mr-2"></i>Skip</button></div>`;
    const container = document.getElementById('chatMessages');
    if (container) container.scrollTop = container.scrollHeight;
}

function hideApprovalPanel() {
    const panel = document.getElementById('agentApprovalPanel');
    if (panel) { panel.className = 'hidden'; panel.innerHTML = ''; }
    currentApprovalStep = null;
}

async function approveAgentStep() {
    if (!currentAgentSession) return;
    try {
        const stepToRun = currentApprovalStep;
        if (agentSocket && agentSocket.readyState === WebSocket.OPEN) {
            agentSocket.send(JSON.stringify({ type: 'approve' }));
        } else {
            await apiCall(`/api/agent/${currentAgentSession.id}/approve`, { method: 'POST' });
        }
        hideApprovalPanel();
        updateAgentStatus('executing', 'Running command...');
        // Execute the approved step in the connected terminal.
        await executeAgentStepInTerminal(stepToRun);
    } catch (error) {
        console.error('Failed to approve step:', error);
        showToast('Failed to approve step', 'error');
    }
}

async function rejectAgentStep() {
    if (!currentAgentSession) return;
    try {
        if (agentSocket && agentSocket.readyState === WebSocket.OPEN) {
            agentSocket.send(JSON.stringify({ type: 'reject' }));
        } else {
            await apiCall(`/api/agent/${currentAgentSession.id}/reject`, { method: 'POST' });
        }
        hideApprovalPanel();
        updateAgentStatus('thinking', 'Agent is reconsidering...');
    } catch (error) {
        console.error('Failed to reject step:', error);
        showToast('Failed to skip step', 'error');
    }
}

async function stopAgent() {
    if (!currentAgentSession) { exitAgentMode(); return; }
    try {
        if (agentSocket && agentSocket.readyState === WebSocket.OPEN) {
            agentSocket.send(JSON.stringify({ type: 'stop' }));
        }
        await apiCall(`/api/agent/${currentAgentSession.id}/stop`, { method: 'POST' });
        updateAgentStatus('stopped');
        showToast('Agent stopped', 'info');
        const container = document.getElementById('agentSteps');
        if (container) {
            const exitBtn = document.createElement('div');
            exitBtn.className = 'text-center mt-4';
            exitBtn.innerHTML = '<button onclick="exitAgentMode()" class="btn-secondary px-4 py-2 rounded"><i class="fas fa-arrow-left mr-2"></i>Return to Chat</button>';
            container.appendChild(exitBtn);
        }
    } catch (error) {
        console.error('Failed to stop agent:', error);
        showToast('Failed to stop agent', 'error');
    }
}

function handleAgentComplete(data) {
    updateAgentStatus(data.status, data.status === 'completed' ? 'Goal achieved!' : 'Failed');
    const robotIcon = document.querySelector('#agentHeader .animate-pulse');
    if (robotIcon) robotIcon.classList.remove('animate-pulse');
    const stopBtn = document.getElementById('agentStopBtn');
    if (stopBtn) {
        stopBtn.id = 'agentReturnBtn';
        stopBtn.className = 'text-blue-400 hover:text-blue-300 text-xs px-3 py-1 border border-blue-500/30 rounded hover:bg-blue-500/10 transition-colors';
        stopBtn.onclick = exitAgentMode;
        stopBtn.innerHTML = '<i class="fas fa-arrow-left mr-1"></i>Return to Chat';
    }
    const container = document.getElementById('agentSteps');
    if (container) {
        const exitBtn = document.createElement('div');
        exitBtn.className = 'text-center mt-4';
        exitBtn.innerHTML = '<button onclick="exitAgentMode()" class="btn-primary px-4 py-2 rounded"><i class="fas fa-arrow-left mr-2"></i>Return to Chat</button>';
        container.appendChild(exitBtn);
    }
    if (data.status === 'completed') showToast('Agent completed the goal!', 'success');
    else showToast(data.message || 'Agent failed', 'error');
}

/* ==========================================================================
   File Operations & Diff View Extensions (Phase 2 Preview-First Workflow)
   ========================================================================== */

// Removed duplicate declaration - already declared in ai_chat.html template
// let currentRightPane = 'terminal';
let currentFile = { path: null, content: null, version: null };
let currentChangeSet = null;

/**
 * Switch between Terminal, Data Output, File Editor, and Diff View panes
 */
function switchRightPane(pane) {
    currentRightPane = pane;

    // Defined containers
    const containers = {
        'terminal': document.getElementById('terminalContainer'),
        'data': document.getElementById('dataOutputContainer'),
        'file': document.getElementById('fileEditorContainer'),
        'diff': document.getElementById('diffViewContainer'),
        'agentHQ': document.getElementById('agentHQContainer')
    };

    // Defined tabs
    const tabs = {
        'terminal': document.getElementById('terminalTabBtn'),
        'data': document.getElementById('dataOutputTabBtn'),
        'file': document.getElementById('fileEditorTabBtn'),
        'diff': document.getElementById('diffViewTabBtn'),
        'agentHQ': document.getElementById('agentHQTabBtn')
    };

    // Defined controls
    const controls = {
        'terminal': [document.getElementById('terminalControls'), document.getElementById('terminalStatus')],
        'data': [document.getElementById('dataOutputControls')],
        'file': [document.getElementById('fileEditorControls')],
        'diff': [], // No specific header controls for diff yet
        'agentHQ': [document.getElementById('agentHQControls')]
    };

    // Toggle Container Visibility
    Object.keys(containers).forEach(key => {
        if (containers[key]) {
            if (key === pane) containers[key].classList.remove('hidden');
            else containers[key].classList.add('hidden');
        }
    });

    // Toggle Tab Styling
    Object.keys(tabs).forEach(key => {
        const btn = tabs[key];
        if (!btn) return;

        // Reset to base inactive style
        btn.className = 'px-3 py-1 text-xs font-medium bg-transparent text-gray-400 border-r border-gray-600 hover:text-white hover:bg-gray-800 transition-colors relative';

        // Apply active style
        if (key === pane) {
            btn.classList.remove('bg-transparent', 'text-gray-400', 'hover:bg-gray-800');
            if (key === 'terminal') btn.classList.add('bg-green-600', 'text-white');
            else if (key === 'data') btn.classList.add('bg-blue-600', 'text-white');
            else if (key === 'file') btn.classList.add('bg-purple-600', 'text-white');
            else if (key === 'diff') btn.classList.add('bg-amber-600', 'text-white');
            else if (key === 'agentHQ') btn.classList.add('bg-blue-600', 'text-white');
        }
    });

    // Toggle Control Visibility
    ['terminal', 'data', 'file', 'diff', 'agentHQ'].forEach(key => {
        const elements = controls[key] || [];
        elements.forEach(el => {
            if (el) el.classList.add('hidden');
        });

        if (key === pane) {
            elements.forEach(el => {
                if (el) el.classList.remove('hidden');
            });
        }
    });

    // Trigger data load if needed
    if (pane === 'diff') {
        refreshDiffView();
    } else if (pane === 'file' && currentFile.path && !currentFile.content) {
        refreshCurrentFile();
    } else if (pane === 'agentHQ') {
        refreshAgentHQ();
    }
}

async function openFile(path) {
    currentFile.path = path;
    const label = document.getElementById('currentFileLabel');
    if (label) {
        label.textContent = path;
        label.title = path;
    }
    await refreshCurrentFile();
    switchRightPane('file');
}

async function refreshCurrentFile() {
    if (!currentFile.path) return;

    // Show loading state
    const container = document.getElementById('fileEditorContent');
    if (container) {
        container.innerHTML = '<div class="flex items-center justify-center h-full text-gray-500"><i class="fas fa-spinner fa-spin text-2xl mb-2"></i><span class="block text-xs">Loading file...</span></div>';
    }

    try {
        const session_id = currentSessionId || (currentSession ? currentSession.id : null);
        const response = await apiCall('/api/v1/files/read', {
            method: 'POST',
            body: JSON.stringify({
                path: currentFile.path,
                session_id: session_id
            })
        });

        if (!response.ok) throw new Error('Failed to read file');

        const data = await response.json();
        currentFile.content = data.content;
        currentFile.version = data.version;

        renderFileContent(data.content, currentFile.path);
    } catch (error) {
        console.error('File read error:', error);
        if (container) {
            container.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-red-400">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Failed to load file</p>
                <div class="text-xs text-gray-500 mt-1">${escapeHtml(error.message)}</div>
                <button onclick="refreshCurrentFile()" class="mt-4 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs">Retry</button>
            </div>`;
        }
        showToast(`Error opening file: ${error.message}`, 'error');
    }
}

function renderFileContent(content, path) {
    const container = document.getElementById('fileEditorContent');
    if (!container) return;

    // Detect language extension
    const ext = path.split('.').pop().toLowerCase();
    const langClass = `language-${ext}`;

    container.innerHTML = `<pre class="m-0 p-4 h-full overflow-auto text-sm"><code class="${langClass} font-mono">${escapeHtml(content)}</code></pre>`;

    // Apply syntax highlighting
    if (window.hljs) {
        window.hljs.highlightElement(container.querySelector('code'));
    }
}

async function refreshDiffView() {
    const summary = document.getElementById('diffChangeSummary');
    const content = document.getElementById('diffListContent');
    const emptyState = document.getElementById('diffEmptyState');
    const badge = document.getElementById('diffBadge');

    if (summary) summary.textContent = 'Checking...';

    // Check if `currentChangeSet` is set in memory

    if (!currentChangeSet || !currentChangeSet.items || currentChangeSet.items.length === 0) {
        if (content) content.innerHTML = '';
        if (content) content.classList.add('hidden');
        if (emptyState) emptyState.classList.remove('hidden');
        if (summary) summary.textContent = 'No pending changes';
        if (badge) badge.classList.add('hidden');
        const list = document.getElementById('pendingChangesList');
        if (list) list.classList.add('hidden');
        return;
    }

    // We have changes
    if (emptyState) emptyState.classList.add('hidden');
    const list = document.getElementById('pendingChangesList');
    if (list) list.classList.remove('hidden');
    if (content) content.classList.remove('hidden');
    if (summary) summary.textContent = `${currentChangeSet.items.length} file(s) changed`;
    if (badge) badge.classList.remove('hidden');

    renderDiffList(currentChangeSet.items);
}

function renderDiffList(items) {
    const container = document.getElementById('diffListContent');
    if (!container) return;

    container.innerHTML = items.map((item, index) => {
        let icon = 'fa-file';
        let color = 'text-gray-400';
        let label = 'MODIFIED';
        let badgeColor = 'bg-blue-900 text-blue-200';

        if (item.change_type === 'create') {
            icon = 'fa-plus-circle';
            color = 'text-green-400';
            label = 'NEW';
            badgeColor = 'bg-green-900 text-green-200';
        } else if (item.change_type === 'delete') {
            icon = 'fa-minus-circle';
            color = 'text-red-400';
            label = 'DELETED';
            badgeColor = 'bg-red-900 text-red-200';
        }

        return `
        <div class="bg-gray-900 border border-gray-700 rounded overflow-hidden shadow-sm">
            <div class="px-3 py-2 bg-gray-800 border-b border-gray-700 flex justify-between items-center">
                <div class="flex items-center space-x-2">
                    <span class="text-[10px] font-bold px-1.5 py-0.5 rounded ${badgeColor}">${label}</span>
                    <span class="text-xs text-gray-300 font-mono">${escapeHtml(item.path)}</span>
                </div>
                <div class="flex space-x-1">
                     <!-- Individual actions could go here -->
                </div>
            </div>
            <div class="p-0 overflow-x-auto">
                <pre class="text-[10px] leading-4 font-mono p-2"><code class="language-diff">${escapeHtml(item.diff || 'No diff content available')}</code></pre>
            </div>
        </div>
        `;
    }).join('');

    // Highlight all diff blocks
    if (window.hljs) {
        container.querySelectorAll('pre code').forEach(block => {
            window.hljs.highlightElement(block);
        });
    }
}

async function applyAllChanges() {
    if (!currentChangeSet || !currentChangeSet.id) return;

    try {
        const btn = document.getElementById('btnApplyAll');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Applying...';
            btn.disabled = true;
        }

        const response = await apiCall(`/api/v1/changesets/${currentChangeSet.id}/apply`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to apply changes');

        showToast('Changes applied successfully', 'success');

        // Clear state
        currentChangeSet = null;
        refreshDiffView();

        // Switch back to terminal or notify
        switchRightPane('terminal');
        appendAIMessage('✅ **Changes applied successfully.** You can now verify the functionality.');

    } catch (error) {
        console.error('Apply error:', error);
        showToast(`Failed to apply: ${error.message}`, 'error');
    } finally {
        const btn = document.getElementById('btnApplyAll');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-check mr-2"></i>Apply All Changes';
            btn.disabled = false;
        }
    }
}

async function discardAllChanges() {
    if (!currentChangeSet) return;

    if (!confirm('Are you sure you want to discard all pending changes?')) return;

    currentChangeSet = null;
    refreshDiffView();
    showToast('Changes discarded', 'info');
    switchRightPane('terminal');
}

async function loadChangeSet(id) {
    try {
        const response = await apiCall(`/api/v1/changesets/${id}`);
        if (!response.ok) throw new Error('Failed to load changeset');
        currentChangeSet = await response.json();
        switchRightPane('diff');
    } catch (error) {
        console.error('Failed to load changeset:', error);
        showToast('Failed to load pending changes', 'error');
    }
}

// Agent HQ Functions

async function refreshAgentHQ() {
    if (!currentSessionId) return;

    const label = document.getElementById('agentHQStatusLabel');
    if (label) label.textContent = 'Refreshing...';
    try {
        const cleanSessionId = currentSessionId.replace('session-', '');
        const response = await apiCall(`/api/agents/hq/${cleanSessionId}`);

        if (!response.ok) throw new Error('Failed to fetch Agent HQ status');

        const data = await response.json();
        renderAgentHQ(data);
        if (label) label.textContent = 'Live';
    } catch (error) {
        console.error('Agent HQ Error:', error);
        if (label) label.textContent = 'Error';
    }
}

function renderAgentHQ(data) {
    const info = document.getElementById('hqPoolInfo');
    if (info) info.textContent = `${data.pool.name} (Max: ${data.pool.max_concurrent})`;

    // Render Active Agents
    const activeList = document.getElementById('activeAgentsList');
    if (activeList) {
        if (data.tasks.active.length === 0) {
            activeList.innerHTML = '<div class="text-center text-gray-500 py-4">No active agents running</div>';
        } else {
            activeList.innerHTML = data.tasks.active.map(task => `
                <div class="bg-gray-800 p-3 rounded border border-blue-500/30 flex justify-between items-start">
                    <div>
                        <div class="flex items-center space-x-2 mb-1">
                            <span class="text-xs font-bold text-blue-400 uppercase">${task.agent_type}</span>
                            <span class="text-xs text-gray-500">${new Date(task.started_at).toLocaleTimeString()}</span>
                            ${task.iteration_count > 0 ? `<span class="text-[10px] text-yellow-400 ml-2"><i class="fas fa-sync-alt fa-spin mr-1"></i>Iter: ${task.iteration_count}/${task.max_iterations}</span>` : ''}
                        </div>
                        <div class="text-sm text-gray-200">${task.goal}</div>
                    </div>
                    <button onclick="stopAgentTask('${task.id}')" class="text-red-400 hover:text-red-300 px-2" title="Stop Task">
                        <i class="fas fa-stop-circle"></i>
                    </button>
                </div>
            `).join('');
        }
    }

    // Render Queued Tasks
    const queuedList = document.getElementById('queuedTasksList');
    if (queuedList) {
        if (data.tasks.queued.length === 0) {
            queuedList.innerHTML = '<span class="text-xs text-gray-600">Queue is empty</span>';
        } else {
            queuedList.innerHTML = data.tasks.queued.map(task => `
                <div class="bg-gray-800/50 p-2 rounded border border-gray-700 flex justify-between items-center">
                    <div>
                        <span class="text-xs font-bold text-gray-400 uppercase mr-2">${task.agent_type}</span>
                        <span class="text-xs text-gray-300 truncate max-w-[200px] inline-block align-bottom">${task.goal}</span>
                    </div>
                    <span class="text-[10px] text-gray-500">Priority: ${task.priority || 10}</span>
                </div>
            `).join('');
        }
    }

    // Render Completed
    const completedList = document.getElementById('completedTasksList');
    if (completedList) {
        completedList.innerHTML = data.tasks.completed.slice(0, 5).map(task => `
             <div class="bg-gray-800/30 p-2 rounded border border-gray-800 flex justify-between items-center opacity-75">
                 <div>
                    <span class="text-xs font-bold ${task.status === 'completed' ? 'text-green-500' : 'text-red-500'} uppercase mr-2">${task.status}</span>
                    <span class="text-xs text-gray-400 truncate max-w-[200px] inline-block align-bottom">${task.goal}</span>
                 </div>
                 <span class="text-[10px] text-gray-600">${new Date(task.completed_at).toLocaleTimeString()}</span>
             </div>
        `).join('');
    }
}

async function stopAgentTask(taskId) {
    if (!confirm('Stop this agent task?')) return;
    try {
        await apiCall(`/api/agents/tasks/${taskId}/stop`, {
            method: 'POST'
        });
        refreshAgentHQ();
    } catch (e) {
        showToast('Failed to stop task', 'error');
    }
}

function showSpawnAgentModal() {
    const goal = prompt("Enter goal for background agent:");
    if (goal) {
        spawnAgent(goal);
    }
}

async function spawnAgent(goal) {
    if (!currentSessionId) {
        showToast('No active session', 'error');
        return;
    }

    try {
        let poolId = null;
        // Fetch HQ first to get pool ID.
        const response = await apiCall(`/api/agents/hq/${currentSessionId}`);
        const data = await response.json();
        poolId = data.pool.id;

        const spawnResp = await apiCall('/api/agents/spawn', {
            method: 'POST',
            body: JSON.stringify({
                pool_id: poolId,
                goal: goal,
                agent_type: 'background',
                priority: 10,
                auto_iterate: true,
                max_iterations: 10
            })
        });

        if (spawnResp.ok) {
            showToast('Agent spawned locally', 'success');
            refreshAgentHQ();
            switchRightPane('agentHQ');
        } else {
            showToast('Failed to spawn agent', 'error');
        }

    } catch (e) {
        console.error(e);
        showToast('Error spawning agent', 'error');
    }
}

// Auto-refresh Agent HQ if visible
setInterval(() => {
    const container = document.getElementById('agentHQContainer');
    if (container && !container.classList.contains('hidden')) {
        refreshAgentHQ();
    }
}, 5000);


// ==========================================
// UI Helper Functions (Dropdowns, Sessions)
// ==========================================

function toggleSessionDropdown() {
    const dropdown = document.getElementById('sessionDropdown');
    const btn = document.getElementById('sessionDropdownBtn');
    const wrapper = btn ? btn.closest('.ts-session-dropdown-wrapper') : null;
    if (!dropdown) return;

    dropdown.classList.toggle('hidden');

    // Toggle open class on wrapper for chevron animation
    if (wrapper) {
        wrapper.classList.toggle('open', !dropdown.classList.contains('hidden'));
    }

    // Refresh session list when opening
    if (!dropdown.classList.contains('hidden')) {
        loadSessions();
    }
}

function toggleModelDropdown() {
    const list = document.getElementById('modelListContainer');
    const selector = document.getElementById('llmSelector');
    if (list) {
        const isHidden = list.classList.contains('hidden');
        list.classList.toggle('hidden', !isHidden);
        if (selector) {
            if (isHidden) selector.classList.add('open');
            else selector.classList.remove('open');
        }
    }
}

// Close dropdowns when clicking outside
window.addEventListener('click', function (e) {
    const sessionDropdown = document.getElementById('sessionDropdown');
    const sessionBtn = document.getElementById('sessionDropdownBtn');
    if (sessionDropdown && !sessionDropdown.classList.contains('hidden')) {
        if (!sessionDropdown.contains(e.target) && (!sessionBtn || !sessionBtn.contains(e.target))) {
            sessionDropdown.classList.add('hidden');
            const wrapper = sessionBtn ? sessionBtn.closest('.ts-session-dropdown-wrapper') : null;
            if (wrapper) wrapper.classList.remove('open');
        }
    }

    const llmSelector = document.getElementById('llmSelector');
    const modelListContainer = document.getElementById('modelListContainer');
    if (llmSelector && !llmSelector.contains(e.target)) {
        if (modelListContainer) modelListContainer.classList.add('hidden');
        llmSelector.classList.remove('open');
    }
});

async function loadSessions() {
    try {
        const response = await apiCall('/api/troubleshoot/sessions');
        if (!response.ok) return;

        const data = await response.json();
        const sessions = data.sessions || [];
        populateSessionDropdown(sessions);
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

function populateSessionDropdown(sessions) {
    const container = document.getElementById('sessionListContainer');
    if (!container) return;

    if (sessions.length === 0) {
        container.innerHTML = '<div class="ts-session-empty">No previous sessions</div>';
    } else {
        container.innerHTML = sessions.map(session => {
            const isActive = session.id === currentSessionId;
            const title = AIChatBase.escapeHtml(session.title || 'Untitled Session');
            const date = new Date(session.created_at).toLocaleDateString();
            const time = new Date(session.created_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
            return `
            <div class="ts-session-item ${isActive ? 'active' : ''}" onclick="switchSession('${session.id}')">
                <div class="ts-session-item-title">${title}</div>
                <div class="ts-session-item-date">${date} ${time}</div>
            </div>`;
        }).join('');
    }
}

async function createNewSession() {
    try {
        const response = await apiCall('/api/troubleshoot/sessions', {
            method: 'POST',
            body: JSON.stringify({})
        });

        if (response.ok) {
            const session = await response.json();
            switchSession(session.id);
            showToast('New session created', 'success');
        } else {
            showToast('Failed to create session', 'error');
        }
    } catch (error) {
        console.error('Create session failed:', error);
        showToast('Error creating session', 'error');
    }
}

async function switchSession(sessionId) {
    if (sessionId === currentSessionId) return;

    currentSessionId = sessionId;
    const dropdown = document.getElementById('sessionDropdown');
    if (dropdown) {
        dropdown.classList.add('hidden');
        const wrapper = dropdown.closest('.ts-session-dropdown-wrapper');
        if (wrapper) wrapper.classList.remove('open');
    }

    // Update UI title
    const titleEl = document.getElementById('currentSessionTitle');
    if (titleEl) titleEl.textContent = 'Loading...';

    // Load messages
    await loadMessageHistory(sessionId);

    // Reconnect WebSocket to the new session
    if (typeof connectChatWebSocket === 'function') {
        connectChatWebSocket(sessionId);
    }

    if (titleEl) titleEl.textContent = 'Active Session';
    showToast('Session switched', 'info');
}

// Populate Model Dropdown
function populateModelDropdown(providers) {
    const list = document.getElementById('llmProviderList');
    if (!list) return;

    if (!providers || providers.length === 0) {
        list.innerHTML = '<div class="px-3 py-2 text-xs text-gray-500">No providers available</div>';
        updateModelStatusIcon('disconnected');
        return;
    }

    // Determine which provider is currently selected
    const selectedId = (currentSession && currentSession.llm_provider_id) 
        ? currentSession.llm_provider_id 
        : (providers.find(p => p.is_default)?.id || '');

    list.innerHTML = providers.map(p => {
        const isSelected = p.id === selectedId;
        const name = p.provider_name || p.name || 'Unknown';
        return `
        <div class="ts-llm-option ${isSelected ? 'selected' : ''}" 
             data-provider-id="${p.id}" onclick="selectModel('${p.id}'); toggleModelDropdown();">
            <i data-feather="${p.is_enabled !== false ? 'check-circle' : 'x-circle'}" style="width: 14px; height: 14px; color: ${p.is_enabled !== false ? '#4ade80' : '#f87171'}"></i>
            <span class="ml-2">${AIChatBase.escapeHtml(name)}${p.is_default ? ' ⭐' : ''}</span>
        </div>
    `}).join('');

    if (typeof feather !== 'undefined') feather.replace();
    updateModelStatusIcon('connected');
}

async function selectModel(providerId) {
    if (!currentSessionId) return;

    try {
        const response = await apiCall(`/api/troubleshoot/sessions/${currentSessionId}/provider`, {
            method: 'PATCH',
            body: JSON.stringify({ provider_id: providerId })
        });

        if (response.ok) {
            const result = await response.json();
            
            // Update session tracking FIRST
            if (currentSession) {
                currentSession.llm_provider_id = providerId;
            } else {
                currentSession = { llm_provider_id: providerId };
            }
            
            // Re-render dropdown with new selection
            populateModelDropdown(availableProviders);
            
            // Update the model icon tooltip
            const provider = availableProviders.find(p => p.id === providerId);
            if (provider) {
                const btn = document.getElementById('llmIconBtn');
                if (btn) btn.title = `LLM: ${provider.provider_name || provider.name}`;
            }
            
            // Add system message to chat
            const container = document.getElementById('chatMessages');
            const msg = document.createElement('div');
            msg.className = 'text-center text-xs text-gray-500 my-2 italic';
            msg.innerHTML = `<i class="fas fa-sync-alt mr-1"></i>Now using: ${result.provider_name} - ${result.model_name}`;
            container.appendChild(msg);
            container.scrollTop = container.scrollHeight;
            
            const list = document.getElementById('modelListContainer');
            if (list) list.classList.add('hidden');
            const sel = document.getElementById('llmSelector');
            if (sel) sel.classList.remove('open');
            showToast(`Switched to ${result.provider_name}`, 'success');
        }
    } catch (error) {
        console.error('Switch model failed:', error);
        showToast('Failed to switch model', 'error');
    }
}


// Expose to window for inline onclicks
window.toggleSessionDropdown = toggleSessionDropdown;
window.toggleModelDropdown = toggleModelDropdown;
window.createNewSession = createNewSession;
window.switchSession = switchSession;
window.selectModel = selectModel;
