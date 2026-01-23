/**
 * AI Inquiry Page JavaScript
 * Dedicated Q&A interface for the AI Inquiry feature.
 * Removes terminal/command execution logic.
 */

// Global state
let chatSocket = null;
var currentSessionId = null;
let currentSession = null;
let availableProviders = [];
let lastMessageRole = null;
let currentMessageDiv = null;
let chatFontSize = 14;
let pendingCommandCancelled = false;  // Flag to cancel pending command polling
let currentStreamController = null;   // AbortController for streaming requests
let isStreaming = false;              // Flag to track if streaming is active

// Reasoning panel state
let reasoningHistory = [];
let reasoningPanelVisible = true;

// Font Size Controls
function adjustChatFont(delta) {
    AIChatBase.adjustChatFont(delta);
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
                <i class="fas fa-brain mr-2 text-purple-400"></i>AI Analysis
            </span>
            <i class="fas fa-chevron-down text-gray-500" id="reasoningToggleIcon"></i>
        </div>
        <div class="reasoning-body p-3 max-h-64 overflow-y-auto" id="reasoningBody">
            <div class="text-gray-500 text-sm">Waiting for analysis...</div>
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

    // Simplified phases for Inquiry
    const phaseIcons = {
        'identify': '🔍',
        'verify': '✅',
        'investigate': '📊',
        'plan': '🧠',
        'act': '💡' // Changed from tool to bulb
    };

    body.innerHTML = reasoningHistory.map((step, i) => {
        const icon = phaseIcons[step.phase] || '❓';
        // Only render known phases or generic info to avoid noise
        return `
            <div class="reasoning-step mb-3 pl-4 border-l-2 border-gray-600">
                <div class="flex items-center text-xs font-medium mb-1">
                    <span class="mr-2">${icon}</span>
                    <span>${step.phase || 'Info'}</span>
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

    body.scrollTop = body.scrollHeight;
}

function resetReasoningPanel() {
    reasoningHistory = [];
    const body = document.getElementById('reasoningBody');
    if (body) {
        body.innerHTML = '<div class="text-gray-500 text-sm">Waiting for analysis...</div>';
    }
    const panel = document.getElementById('reasoningPanel');
    if (panel) {
        panel.classList.add('hidden');
    }
}

// Chat Session Management
async function initChatSession() {
    try {
        await loadAvailableProviders();

        // Get available sessions
        let response = await apiCall('/api/v1/inquiry/sessions');

        if (response.ok) {
            const data = await response.json();
            if (data.sessions && data.sessions.length > 0) {
                currentSessionId = data.sessions[0].id;
                currentSession = data.sessions[0];
            }
        }

        if (!currentSessionId) {
            response = await apiCall('/api/v1/inquiry/sessions', {
                method: 'POST'
            });

            if (response.ok) {
                currentSession = await response.json();
                currentSessionId = currentSession.id;
            } else {
                throw new Error('Failed to create session');
            }
        }

        updateModelSelector();
        await loadMessageHistory(currentSessionId);

        // No WebSocket for Inquiry - it's purely REST/Streaming for now to allow simple scaling
        // connectChatWebSocket(currentSession.id); 

    } catch (error) {
        console.error('Chat init failed:', error);
        showToast('Failed to initialize chat', 'error');
    }
}

async function loadAvailableProviders() {
    try {
        const response = await apiCall('/api/v1/inquiry/providers');
        if (!response.ok) throw new Error('Failed to load providers');
        availableProviders = await response.json();

        if (typeof populateModelDropdown === 'function') {
            populateModelDropdown(availableProviders);
        }
    } catch (error) {
        console.error('Failed to load providers:', error);
    }
}

function updateModelSelector() {
    if (currentSession && currentSession.llm_provider_id) {
        if (typeof selectedModelId !== 'undefined') {
            selectedModelId = currentSession.llm_provider_id;
        }
    }
}

async function switchModel(providerId) {
    if (!currentSessionId || !providerId) return;
    try {
        const response = await apiCall(`/api/v1/inquiry/sessions/${currentSessionId}/provider`, {
            method: 'PATCH',
            body: JSON.stringify({ provider_id: providerId })
        });
        if (!response.ok) throw new Error('Failed to switch model');
        showToast('Model switched', 'success');
        currentSession.llm_provider_id = providerId;
    } catch (error) {
        console.error('Failed to switch model:', error);
        showToast('Failed to switch model', 'error');
    }
}

async function loadMessageHistory(sessionId) {
    try {
        const response = await apiCall(`/api/v1/inquiry/sessions/${sessionId}/messages`);
        if (!response.ok) throw new Error('Failed to load history');
        const messages = await response.json();
        const container = document.getElementById('chatMessages');
        container.innerHTML = '';
        if (messages.length === 0) {
            showWelcomeScreen();
            return;
        }
        messages.forEach(msg => {
            if (msg.role === 'user') {
                appendUserMessage(msg.content);
            } else if (msg.role === 'assistant') {
                appendAIMessage(msg.content);
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
        "AI Analyst",
        "Ask me about infrastructure, metrics, or logs.",
        [
            { text: "What alerts are currently firing?", icon: "fas fa-bell" },
            { text: "Show me system health status", icon: "fas fa-heartbeat" },
            { text: "Explain recent errors in logs", icon: "fas fa-file-alt" }
        ]
    );
}

function sendSuggestion(text) {
    const input = document.getElementById('chatInput');
    input.value = text;
    sendMessage(new Event('submit'));
}

function appendUserMessage(text) {
    AIChatBase.appendUserMessage(text);
    lastMessageRole = 'user';
}

function appendAIMessage(text) {
    AIChatBase.appendAIMessage(text, {
        skipRunButtons: true, // Inquiry doesn't run terminal commands
        messageId: 'inquiry-' + Date.now()
    });
    lastMessageRole = 'assistant';
}

// Redundant, handled by AIChatBase

// Chat Interaction
async function sendMessage(e) {
    e.preventDefault();

    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    if (typeof resetReasoningPanel === 'function') resetReasoningPanel();

    appendUserMessage(text);
    input.value = '';
    showTypingIndicator();

    await sendStreamingMessage(text);
}

async function sendStreamingMessage(message) {
    currentStreamController = new AbortController();
    isStreaming = true;

    try {
        const token = localStorage.getItem('token');
        // Pointing to INQUIRY endpoint
        const response = await fetch('/api/v1/inquiry/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                query: message,
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

        removeTypingIndicator();

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
                        } else if (data.type === 'chunk') {
                            fullResponse += data.content;
                            appendStreamingChunk(data.content);
                        } else if (data.type === 'tools_used') {
                            handleToolsUsedEvent(data.content);
                        } else if (data.type === 'done') {
                            finalizeStreamingMessage(fullResponse);
                        } else if (data.type === 'error') {
                            appendAIMessage(`Error: ${data.content}`);
                        }
                    } catch (e) {
                        console.error("Error parsing SSE data:", e);
                    }
                }
            }
        }
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.error('Streaming error:', error);
            removeTypingIndicator();
            appendAIMessage('Error communicating with AI service.');
        }
    } finally {
        isStreaming = false;
        currentStreamController = null;
        removeTypingIndicator();
    }
}


// --- Missing Reasoning Panel Functions ---

function handleReasoningEvent(data) {
    // Attempt to find the reasoning panel container
    // Common IDs from ai_chat.js: reasoningActionList or similar
    // HTML uses 'dataOutputResults' for the right pane
    const container = document.getElementById('reasoningActionList') ||
        document.getElementById('reasoningPanel') ||
        document.getElementById('dataOutputResults');

    if (!container) {
        // If panel doesn't exist, just log it and return to avoid crashing
        console.log('Reasoning event (panel not found):', data);
        return;
    }

    const item = document.createElement('div');
    item.className = 'reasoning-item mb-2 p-2 bg-gray-800 rounded border border-gray-700 text-xs';

    let icon = 'fa-cog';
    let color = 'text-gray-400';

    if (data.phase === 'plan') { icon = 'fa-map'; color = 'text-blue-400'; }
    else if (data.phase === 'act') { icon = 'fa-bolt'; color = 'text-yellow-400'; }
    else if (data.phase === 'observe') { icon = 'fa-eye'; color = 'text-purple-400'; }

    item.innerHTML = `
        <div class="flex items-start">
            <i class="fas ${icon} ${color} mt-1 mr-2 width-4"></i>
            <div>
                <div class="font-semibold text-gray-300">${data.tool || data.phase}</div>
                <div class="text-gray-400">${escapeHtml(data.thought || '')}</div>
            </div>
        </div>
    `;
    container.appendChild(item);
    container.scrollTop = container.scrollHeight;
}

function resetReasoningPanel() {
    const container = document.getElementById('reasoningActionList') || document.getElementById('reasoningPanel');
    if (container) {
        container.innerHTML = '';
    }
}

function handleToolsUsedEvent(tools) {
    if (!tools || tools.length === 0) return;

    // Add to reasoning history
    const toolValidation = {
        phase: 'act',
        tool: tools.join(', '),
        thought: 'Tools executed successfully.'
    };
    handleReasoningEvent(toolValidation);

    // Also show a small indicator in the chat if reasoning panel is closed
    const container = document.getElementById('chatMessages');
    if (lastMessageRole === 'assistant' && currentMessageDiv) {
        // We are streaming, so maybe just append a marker? 
        // Or better, let reasoning panel handle it.
        // We can add a "Tools Used" badge to the message wrapper
    }
}

function appendStreamingChunk(chunk) {
    const container = document.getElementById('chatMessages');
    if (lastMessageRole !== 'assistant' || !currentMessageDiv) {
        const wrapper = document.createElement('div');
        wrapper.className = 'flex justify-start w-full pr-2 mb-3'; // Added mb-3 for spacing
        wrapper.innerHTML = `
            <div class="ai-message-wrapper w-full">
                <div class="flex items-center mb-2">
                     <div class="w-6 h-6 rounded-full bg-gradient-to-r from-blue-600 to-cyan-600 flex items-center justify-center mr-2">
                        <i class="fas fa-search text-white text-xs"></i>
                    </div>
                    <span class="text-xs text-gray-400">AI Analyst</span>
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

        let displayText = newText.replace(/\[\s*SUGGESTIONS\s*\]([\s\S]*?)\[\s*\/SUGGESTIONS\s*\]/gi, '');
        currentMessageDiv.innerHTML = marked.parse(displayText);
    }
    container.scrollTop = container.scrollHeight;
}

function finalizeStreamingMessage(fullText) {
    // Re-render full message to handle any formatting properly
    if (currentMessageDiv) {
        // Safer removal: traverse up to the main wrapper
        const wrapper = currentMessageDiv.closest('.flex.justify-start');
        if (wrapper && wrapper.parentNode) {
            wrapper.parentNode.removeChild(wrapper);
        } else {
            currentMessageDiv.remove();
        }
        currentMessageDiv = null;
    }
    appendAIMessage(fullText);
}

// --- UI Helpers ---

function toggleSessionDropdown() {
    const dropdown = document.getElementById('sessionDropdown');
    const btn = document.getElementById('sessionDropdownBtn');
    if (!dropdown) return;

    dropdown.classList.toggle('hidden');

    if (!dropdown.classList.contains('hidden')) {
        // Refresh session list
        loadSessions();
    }

    // Explicitly positioning if it's absolute global
    const rect = btn.getBoundingClientRect();
    dropdown.style.top = (rect.bottom + 5) + 'px';
    dropdown.style.left = rect.left + 'px';
}

async function loadSessions() {
    try {
        const response = await apiCall('/api/v1/inquiry/sessions');
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
        container.innerHTML = '<div class="px-3 py-2 text-xs text-gray-500">No previous sessions</div>';
    } else {
        container.innerHTML = sessions.map(session => `
            <div class="px-3 py-2 hover:bg-gray-700 cursor-pointer flex justify-between items-center group" onclick="switchSession('${session.id}')">
                <div class="truncate max-w-[180px] text-xs ${session.id === currentSessionId ? 'text-blue-400 font-bold' : 'text-gray-300'}">
                    ${AIChatBase.escapeHtml(session.title || 'Untitled Session')}
                </div>
                <div class="text-[10px] text-gray-500">
                    ${new Date(session.created_at).toLocaleDateString()}
                </div>
            </div>
        `).join('');
    }

    const newSessionHtml = `
        <div class="px-3 py-2 hover:bg-gray-700 cursor-pointer text-blue-400 border-b border-gray-700 flex items-center" onclick="createNewSession()">
            <i class="fas fa-plus mr-2 text-xs"></i> <span class="text-xs font-bold">New Session</span>
        </div>
    `;
    container.innerHTML = newSessionHtml + container.innerHTML;
}

async function createNewSession() {
    try {
        const response = await apiCall('/api/v1/inquiry/sessions', {
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
    document.getElementById('sessionDropdown').classList.add('hidden');

    // Update UI title
    const titleEl = document.getElementById('currentSessionTitle');
    if (titleEl) titleEl.textContent = 'Loading...';

    // Load messages
    await loadMessageHistory(sessionId);

    // Fetch session details to update title properly if we want title to persist
    // For now:
    if (titleEl) titleEl.textContent = 'Active Session';
    showToast('Session switched', 'info');
}

// Populate Model Dropdown helper (needed if loadAvailableProviders calls it)
function populateModelDropdown(providers) {
    const list = document.getElementById('modelListContainer');
    if (!list) return;

    if (!providers || providers.length === 0) {
        list.innerHTML = '<div class="px-3 py-2 text-xs text-gray-500">No providers available</div>';
        return;
    }

    list.innerHTML = providers.map(p => `
        <div class="px-3 py-2 hover:bg-gray-700 cursor-pointer flex items-center" onclick="selectModel('${p.id}')">
            <div class="w-2 h-2 rounded-full ${p.is_enabled ? 'bg-green-400' : 'bg-red-400'} mr-2"></div>
            <div class="text-xs text-gray-300">
                <div class="font-bold">${AIChatBase.escapeHtml(p.name)}</div>
                <div class="text-[10px] text-gray-500">${AIChatBase.escapeHtml(p.model_id)}</div>
            </div>
            ${p.is_default ? '<i class="fas fa-check ml-auto text-blue-400 text-xs"></i>' : ''}
        </div>
    `).join('');
}

async function selectModel(providerId) {
    if (!currentSessionId) return;
    // Inquiry calls switchModel, let's keep it consistent or redirect selectModel to switchModel
    switchModel(providerId);
    document.getElementById('modelDropdown').classList.add('hidden');
}

// Expose these new functions
window.createNewSession = createNewSession;
window.switchSession = switchSession;
window.selectModel = selectModel;

function toggleModelDropdown() {
    const dropdown = document.getElementById('modelDropdown');
    if (dropdown) {
        dropdown.classList.toggle('hidden');
    }
}

// Close dropdowns when clicking outside
window.addEventListener('click', function (e) {
    const sessionDropdown = document.getElementById('sessionDropdown');
    const sessionBtn = document.getElementById('sessionDropdownBtn');
    if (sessionDropdown && !sessionDropdown.classList.contains('hidden') &&
        !sessionDropdown.contains(e.target) && (!sessionBtn || !sessionBtn.contains(e.target))) {
        sessionDropdown.classList.add('hidden');
    }

    const modelDropdown = document.getElementById('modelDropdown');
    const modelBtn = document.getElementById('modelIconBtn');
    if (modelDropdown && !modelDropdown.classList.contains('hidden') &&
        !modelDropdown.contains(e.target) && (!modelBtn || !modelBtn.contains(e.target))) {
        modelDropdown.classList.add('hidden');
    }
});

function showTypingIndicator() {
    AIChatBase.showTypingIndicator('Analyzing system data...');
}

function removeTypingIndicator() {
    AIChatBase.removeTypingIndicator();
}

function cancelStreaming() {
    if (currentStreamController && isStreaming) {
        currentStreamController.abort();
        showToast('Cancelled', 'info');
    }
}

// Utils
function escapeHtml(text) {
    return AIChatBase.escapeHtml(text);
}

function clearChat() {
    // Simple clear, no modal for inquiry to keep it fast
    if (confirm('Clear conversation history?')) {
        document.getElementById('chatMessages').innerHTML = '';
        showWelcomeScreen();
        lastMessageRole = null;
    }
}

// Event Listeners
document.addEventListener('keydown', function (e) {
    if (e.target && e.target.id === 'chatInput') {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(e);
        }
    }
    if (e.ctrlKey && e.key === 'l') { e.preventDefault(); clearChat(); }
});

window.addEventListener('load', function () {
    if (typeof marked === 'undefined') {
        console.error('marked.js failed to load');
        showToast('Failed to load chat library', 'error');
        return;
    }
    console.log('Initializing AI Inquiry...');

    // Explicitly bind UI toggles to window to ensure visibility
    window.toggleSessionDropdown = toggleSessionDropdown;
    window.toggleModelDropdown = toggleModelDropdown;

    // Also bind directly to elements as fallback
    const sBtn = document.getElementById('sessionDropdownBtn');
    if (sBtn) sBtn.onclick = toggleSessionDropdown;

    const mBtn = document.getElementById('modelIconBtn');
    if (mBtn) mBtn.onclick = toggleModelDropdown;

    AIChatBase.init({
        aiIconClass: 'fas fa-search',
        aiGradientClass: 'from-blue-600 to-cyan-600',
        aiName: 'AI Analyst',
        userGradientClass: 'bg-blue-900/40'
    });
    initChatSession();
});
