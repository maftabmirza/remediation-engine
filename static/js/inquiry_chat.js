/**
 * AI Inquiry Page JavaScript
 * Dedicated Q&A interface with Artifacts Panel (Claude-inspired)
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

// Artifacts state
let artifacts = [];
let activeArtifactId = null;
let pinnedArtifacts = new Set();
let currentArtifactTab = 'recent';

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
        updateModelStatusIcon('connecting');
        const response = await apiCall('/api/v1/inquiry/providers');
        if (!response.ok) throw new Error('Failed to load providers');
        availableProviders = await response.json();

        if (typeof populateModelDropdown === 'function') {
            populateModelDropdown(availableProviders);
        }
        updateModelStatusIcon('connected');
    } catch (error) {
        console.error('Failed to load providers:', error);
        updateModelStatusIcon('disconnected');
    }
}

function updateModelSelector() {
    if (currentSession && currentSession.llm_provider_id) {
        if (typeof selectedModelId !== 'undefined') {
            selectedModelId = currentSession.llm_provider_id;
        }
    }
}

function updateModelStatusIcon(status) {
    const icon = document.getElementById('modelStatusIcon');
    if (!icon) return;
    
    // Remove all status classes
    icon.classList.remove('text-green-400', 'text-red-400', 'text-yellow-400', 'text-gray-400');
    
    switch(status) {
        case 'connected':
            icon.classList.add('text-green-400');
            break;
        case 'disconnected':
            icon.classList.add('text-red-400');
            break;
        case 'connecting':
            icon.classList.add('text-yellow-400');
            break;
        default:
            icon.classList.add('text-gray-400');
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
        let firstChunkReceived = false;

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
                        } else if (data.type === 'chunk') {
                            // Remove typing indicator on first content chunk
                            if (!firstChunkReceived) {
                                removeTypingIndicator();
                                firstChunkReceived = true;
                            }
                            fullResponse += data.content;
                            appendStreamingChunk(data.content);
                        } else if (data.type === 'artifact') {
                            // Handle explicit artifact events from backend
                            if (data.artifact) {
                                addArtifact({
                                    id: data.artifact.id || generateArtifactId(),
                                    type: data.artifact.type || 'markdown',
                                    title: data.artifact.title || 'Data',
                                    content: data.artifact.content,
                                    rawContent: data.artifact.content,
                                    timestamp: new Date().toISOString()
                                });
                            }
                        } else if (data.type === 'tools_used') {
                            handleToolsUsedEvent(data.content);
                        } else if (data.type === 'done') {
                            finalizeStreamingMessage(fullResponse, data.tool_calls || []);
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

        // Extract and process artifacts from the stream
        const artifactRegex = /\[ARTIFACT\]([\s\S]*?)\[\/ARTIFACT\]/g;
        let match;
        while ((match = artifactRegex.exec(newText)) !== null) {
            try {
                const artifactData = JSON.parse(match[1]);
                // Validate artifact: content must be a string (real tool results are strings)
                // Hallucinated artifacts often have object content (like chart configs)
                if (typeof artifactData.content !== 'string') {
                    console.warn('Skipping hallucinated artifact with non-string content');
                    continue;
                }
                // Also validate that ID starts with 'tool-' (our real artifacts do)
                if (artifactData.id && !artifactData.id.startsWith('tool-')) {
                    console.warn('Skipping artifact with suspicious ID:', artifactData.id);
                    continue;
                }
                // Check if we already added this artifact
                if (!artifacts.find(a => a.id === artifactData.id)) {
                    addArtifact({
                        id: artifactData.id || generateArtifactId(),
                        type: artifactData.type || 'markdown',
                        title: artifactData.title || 'Tool Result',
                        content: artifactData.content,
                        rawContent: artifactData.content,
                        timestamp: new Date().toISOString()
                    });
                }
            } catch (e) {
                console.error('Error parsing artifact:', e);
            }
        }

        // Remove artifact markers and suggestions from display text
        let displayText = newText
            .replace(/\[\s*ARTIFACT\s*\][\s\S]*?\[\s*\/ARTIFACT\s*\]/gi, '')
            .replace(/\[\s*SUGGESTIONS\s*\]([\s\S]*?)\[\s*\/SUGGESTIONS\s*\]/gi, '');
        currentMessageDiv.innerHTML = marked.parse(displayText);
    }
    container.scrollTop = container.scrollHeight;
}

function finalizeStreamingMessage(fullText, toolCalls = []) {
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
    
    // Extract artifacts from the full text
    const artifactRegex = /\[ARTIFACT\]([\s\S]*?)\[\/ARTIFACT\]/g;
    let match;
    while ((match = artifactRegex.exec(fullText)) !== null) {
        try {
            const artifactData = JSON.parse(match[1]);
            // Validate artifact: content must be a string (real tool results are strings)
            // Hallucinated artifacts often have object content (like chart configs)
            if (typeof artifactData.content !== 'string') {
                console.warn('Skipping hallucinated artifact with non-string content');
                continue;
            }
            // Also validate that ID starts with 'tool-' (our real artifacts do)
            if (artifactData.id && !artifactData.id.startsWith('tool-')) {
                console.warn('Skipping artifact with suspicious ID:', artifactData.id);
                continue;
            }
            // Check if we already added this artifact
            if (!artifacts.find(a => a.id === artifactData.id)) {
                addArtifact({
                    id: artifactData.id || generateArtifactId(),
                    type: artifactData.type || 'markdown',
                    title: artifactData.title || 'Tool Result',
                    content: artifactData.content,
                    rawContent: artifactData.content,
                    timestamp: new Date().toISOString()
                });
            }
        } catch (e) {
            console.error('Error parsing artifact:', e);
        }
    }
    
    // Remove artifact markers from display text
    const cleanText = fullText.replace(/\[\s*ARTIFACT\s*\][\s\S]*?\[\s*\/ARTIFACT\s*\]/gi, '');
    appendAIMessage(cleanText);
    
    // Detect and create additional artifacts from the cleaned response
    const detectedArtifacts = detectArtifacts(cleanText);
    detectedArtifacts.forEach(artifact => {
        addArtifact(artifact);
    });
    
    // If tools were used but no artifacts detected, create a summary artifact
    if (toolCalls && toolCalls.length > 0 && detectedArtifacts.length === 0 && artifacts.length === 0) {
        addArtifact({
            id: generateArtifactId(),
            type: 'markdown',
            title: 'Query Summary',
            content: `**Tools Used:** ${toolCalls.join(', ')}\n\n${cleanText}`,
            rawContent: cleanText,
            timestamp: new Date().toISOString()
        });
    }
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

    // Determine which provider is currently selected
    const selectedId = (currentSession && currentSession.llm_provider_id) 
        ? currentSession.llm_provider_id 
        : (providers.find(p => p.is_default)?.id || '');

    list.innerHTML = providers.map(p => {
        const isSelected = p.id === selectedId;
        return `
        <div class="model-item px-3 py-2 hover:bg-gray-700 cursor-pointer flex items-center ${isSelected ? 'bg-blue-900/40 border-l-2 border-blue-400' : 'border-l-2 border-transparent'}" 
             data-provider-id="${p.id}" onclick="selectModel('${p.id}')">
            <div class="w-2 h-2 rounded-full ${p.is_enabled ? 'bg-green-400' : 'bg-red-400'} mr-2" title="${p.is_enabled ? 'Enabled' : 'Disabled'}"></div>
            <div class="text-xs text-gray-300 flex-grow">
                <div class="font-bold ${isSelected ? 'text-blue-300' : ''}">${AIChatBase.escapeHtml(p.name)}${p.is_default ? ' <span class="text-yellow-400">⭐</span>' : ''}</div>
                <div class="text-[10px] text-gray-500">${AIChatBase.escapeHtml(p.model_id)}</div>
            </div>
            ${isSelected ? '<i class="fas fa-check ml-2 text-blue-400 text-sm"></i>' : ''}
        </div>
    `}).join('');
}

async function selectModel(providerId) {
    if (!currentSessionId) return;
    
    try {
        const response = await apiCall(`/api/v1/inquiry/sessions/${currentSessionId}/provider`, {
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
            
            // Update model icon tooltip
            const provider = availableProviders.find(p => p.id === providerId);
            if (provider) {
                const btn = document.getElementById('modelIconBtn');
                if (btn) btn.title = `LLM: ${provider.provider_name || provider.name}`;
            }
            
            // Add system message to chat
            const container = document.getElementById('chatMessages');
            const msg = document.createElement('div');
            msg.className = 'text-center text-xs text-gray-500 my-2 italic';
            msg.innerHTML = `<i class="fas fa-sync-alt mr-1"></i>Now using: ${result.provider_name} - ${result.model_name}`;
            container.appendChild(msg);
            container.scrollTop = container.scrollHeight;
            
            showToast(`Switched to ${result.provider_name}`, 'success');
        }
    } catch (error) {
        console.error('Failed to switch model:', error);
        showToast('Failed to switch model', 'error');
    }
    
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
    AIChatBase.showTypingIndicator('Analyzing data...');
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

// ============= ARTIFACTS SYSTEM =============

/**
 * Artifact type definitions with icons and colors
 */
const ARTIFACT_TYPES = {
    table: { icon: 'fa-table', color: 'text-blue-400', bgColor: 'bg-blue-900/30', label: 'Table' },
    code: { icon: 'fa-code', color: 'text-green-400', bgColor: 'bg-green-900/30', label: 'Code' },
    json: { icon: 'fa-brackets-curly', color: 'text-yellow-400', bgColor: 'bg-yellow-900/30', label: 'JSON' },
    yaml: { icon: 'fa-file-code', color: 'text-purple-400', bgColor: 'bg-purple-900/30', label: 'YAML' },
    markdown: { icon: 'fa-file-alt', color: 'text-gray-400', bgColor: 'bg-gray-800', label: 'Document' },
    list: { icon: 'fa-list', color: 'text-cyan-400', bgColor: 'bg-cyan-900/30', label: 'List' },
    alert: { icon: 'fa-bell', color: 'text-red-400', bgColor: 'bg-red-900/30', label: 'Alerts' },
    metrics: { icon: 'fa-chart-line', color: 'text-emerald-400', bgColor: 'bg-emerald-900/30', label: 'Metrics' }
};

/**
 * Detect artifacts from AI response content
 */
function detectArtifacts(content) {
    const detectedArtifacts = [];
    
    // 1. Detect Markdown tables
    const tableRegex = /(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)/g;
    let match;
    while ((match = tableRegex.exec(content)) !== null) {
        const tableContent = match[1];
        const lines = tableContent.trim().split('\n');
        const title = extractTableTitle(content, match.index) || `Data Table`;
        detectedArtifacts.push({
            id: generateArtifactId(),
            type: 'table',
            title: title,
            content: tableContent,
            rawContent: tableContent,
            timestamp: new Date().toISOString()
        });
    }
    
    // 2. Detect code blocks
    const codeRegex = /```(\w+)?\n([\s\S]*?)```/g;
    while ((match = codeRegex.exec(content)) !== null) {
        const lang = match[1] || 'text';
        const codeContent = match[2];
        
        // Skip if it's just a small inline code
        if (codeContent.trim().split('\n').length < 3) continue;
        
        let artifactType = 'code';
        if (lang === 'json') artifactType = 'json';
        if (lang === 'yaml' || lang === 'yml') artifactType = 'yaml';
        
        detectedArtifacts.push({
            id: generateArtifactId(),
            type: artifactType,
            title: `${lang.toUpperCase()} Snippet`,
            content: codeContent,
            language: lang,
            rawContent: match[0],
            timestamp: new Date().toISOString()
        });
    }
    
    // 3. Detect alert lists (common pattern: bullet points with alert names)
    const alertListRegex = /(?:Found \d+ alerts?|Alerts?:)\s*\n((?:[-*•]\s*.+\n?)+)/gi;
    while ((match = alertListRegex.exec(content)) !== null) {
        const listContent = match[1];
        const alertCount = (listContent.match(/[-*•]\s/g) || []).length;
        if (alertCount >= 2) {
            detectedArtifacts.push({
                id: generateArtifactId(),
                type: 'alert',
                title: `${alertCount} Alerts`,
                content: listContent,
                rawContent: match[0],
                timestamp: new Date().toISOString()
            });
        }
    }
    
    // 4. Detect numbered/bulleted lists (5+ items)
    const listRegex = /(?:^|\n)((?:(?:\d+\.|[-*•])\s+.+\n?){5,})/g;
    while ((match = listRegex.exec(content)) !== null) {
        // Skip if already captured as alert list
        if (detectedArtifacts.some(a => a.rawContent && match[0].includes(a.rawContent))) continue;
        
        const listContent = match[1];
        const itemCount = (listContent.match(/(?:\d+\.|[-*•])\s/g) || []).length;
        detectedArtifacts.push({
            id: generateArtifactId(),
            type: 'list',
            title: `List (${itemCount} items)`,
            content: listContent,
            rawContent: match[0],
            timestamp: new Date().toISOString()
        });
    }
    
    return detectedArtifacts;
}

function extractTableTitle(content, tableIndex) {
    // Look for heading or bold text before the table
    const beforeTable = content.substring(Math.max(0, tableIndex - 200), tableIndex);
    
    // Check for markdown heading
    const headingMatch = beforeTable.match(/#{1,3}\s+(.+?)(?:\n|$)/);
    if (headingMatch) return headingMatch[1].trim();
    
    // Check for bold text
    const boldMatch = beforeTable.match(/\*\*(.+?)\*\*(?:\s*:)?/);
    if (boldMatch) return boldMatch[1].trim();
    
    return null;
}

function generateArtifactId() {
    return 'artifact-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

/**
 * Add artifact to the panel
 */
function addArtifact(artifact) {
    // Add to global list
    artifacts.unshift(artifact);
    
    // Update count
    updateArtifactCount();
    
    // Hide empty state
    const emptyState = document.getElementById('artifactsEmpty');
    if (emptyState) emptyState.classList.add('hidden');
    
    // Set as active and render
    setActiveArtifact(artifact.id);
    
    // Add to history grid
    addArtifactToHistory(artifact);
    
    // Add link in chat
    addArtifactLinkToChat(artifact);
}

function updateArtifactCount() {
    const countEl = document.getElementById('artifactCount');
    if (countEl) countEl.textContent = artifacts.length;
}

/**
 * Set active artifact (shows in large view)
 */
function setActiveArtifact(artifactId) {
    const artifact = artifacts.find(a => a.id === artifactId);
    if (!artifact) return;
    
    activeArtifactId = artifactId;
    
    const container = document.getElementById('activeArtifact');
    const titleEl = document.getElementById('activeArtifactTitle');
    const typeEl = document.getElementById('activeArtifactType');
    const iconEl = document.getElementById('activeArtifactIcon');
    const contentEl = document.getElementById('activeArtifactContent');
    const pinBtn = document.getElementById('pinArtifactBtn');
    
    if (!container) return;
    
    // Show container
    container.classList.remove('hidden');
    
    // Update header
    const typeInfo = ARTIFACT_TYPES[artifact.type] || ARTIFACT_TYPES.markdown;
    titleEl.textContent = artifact.title;
    typeEl.textContent = typeInfo.label;
    typeEl.className = `ml-2 px-2 py-0.5 text-[10px] ${typeInfo.bgColor} ${typeInfo.color} rounded`;
    iconEl.className = `fas ${typeInfo.icon} ${typeInfo.color} mr-2`;
    
    // Update pin button state
    if (pinBtn) {
        pinBtn.classList.toggle('text-yellow-400', pinnedArtifacts.has(artifactId));
    }
    
    // Render content based on type
    contentEl.innerHTML = renderArtifactContent(artifact);
    
    // Highlight code if needed
    if (artifact.type === 'code' || artifact.type === 'json' || artifact.type === 'yaml') {
        contentEl.querySelectorAll('pre code').forEach(block => {
            if (typeof hljs !== 'undefined') hljs.highlightElement(block);
        });
    }
    
    // Mark as active in history
    document.querySelectorAll('.artifact-thumb').forEach(el => {
        el.classList.toggle('ring-2', el.dataset.artifactId === artifactId);
        el.classList.toggle('ring-blue-500', el.dataset.artifactId === artifactId);
    });
}

/**
 * Render artifact content based on type
 */
function renderArtifactContent(artifact) {
    // Check if content contains chart data
    if (artifact.content && artifact.content.includes('[CHART]')) {
        return renderChartArtifact(artifact);
    }
    
    switch (artifact.type) {
        case 'table':
            return renderTableArtifact(artifact);
        case 'code':
        case 'json':
        case 'yaml':
            return renderCodeArtifact(artifact);
        case 'alert':
            return renderAlertArtifact(artifact);
        case 'list':
            return renderListArtifact(artifact);
        case 'chart':
            return renderChartArtifact(artifact);
        default:
            return `<div class="prose prose-invert max-w-none text-sm">${marked.parse(artifact.content)}</div>`;
    }
}

/**
 * Render chart artifact using Chart.js
 */
function renderChartArtifact(artifact) {
    const content = artifact.content;
    
    // Extract chart data from [CHART]...[/CHART] markers
    const chartMatch = content.match(/\[CHART\]([\s\S]*?)\[\/CHART\]/);
    if (!chartMatch) {
        // No chart data, render as markdown
        return `<div class="prose prose-invert max-w-none text-sm">${marked.parse(content)}</div>`;
    }
    
    try {
        const chartData = JSON.parse(chartMatch[1]);
        const chartId = 'chart-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        
        // Extract text content (before chart marker)
        const textContent = content.replace(/\[CHART\][\s\S]*?\[\/CHART\]/, '').trim();
        
        // Schedule chart rendering after DOM update
        setTimeout(() => {
            const canvas = document.getElementById(chartId);
            if (canvas && typeof Chart !== 'undefined') {
                new Chart(canvas, {
                    type: chartData.type || 'bar',
                    data: {
                        labels: chartData.labels || [],
                        datasets: chartData.datasets || []
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                labels: { color: '#9ca3af' }
                            }
                        },
                        scales: chartData.type !== 'doughnut' && chartData.type !== 'pie' ? {
                            x: {
                                ticks: { color: '#9ca3af' },
                                grid: { color: '#374151' }
                            },
                            y: {
                                ticks: { color: '#9ca3af' },
                                grid: { color: '#374151' },
                                beginAtZero: true
                            }
                        } : undefined
                    }
                });
            }
        }, 100);
        
        return `
            <div class="space-y-4">
                ${textContent ? `<div class="prose prose-invert max-w-none text-sm">${marked.parse(textContent)}</div>` : ''}
                <div class="bg-gray-800 rounded-lg p-4" style="height: 300px;">
                    <canvas id="${chartId}"></canvas>
                </div>
            </div>
        `;
    } catch (e) {
        console.error('Error rendering chart:', e);
        return `<div class="prose prose-invert max-w-none text-sm">${marked.parse(content.replace(/\[CHART\][\s\S]*?\[\/CHART\]/, ''))}</div>`;
    }
}

function renderTableArtifact(artifact) {
    // Parse markdown table and render as HTML table with styling
    const lines = artifact.content.trim().split('\n');
    if (lines.length < 2) return `<pre>${escapeHtml(artifact.content)}</pre>`;
    
    const headers = lines[0].split('|').filter(c => c.trim()).map(c => c.trim());
    const rows = lines.slice(2).map(line => 
        line.split('|').filter(c => c.trim()).map(c => c.trim())
    );
    
    return `
        <div class="overflow-x-auto">
            <table class="w-full text-sm text-left">
                <thead class="text-xs text-gray-400 uppercase bg-gray-800">
                    <tr>
                        ${headers.map(h => `<th class="px-4 py-3 font-medium">${escapeHtml(h)}</th>`).join('')}
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-700">
                    ${rows.map(row => `
                        <tr class="hover:bg-gray-800/50">
                            ${row.map(cell => `<td class="px-4 py-3 text-gray-300">${escapeHtml(cell)}</td>`).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        <div class="mt-3 text-xs text-gray-500">${rows.length} rows</div>
    `;
}

function renderCodeArtifact(artifact) {
    const lang = artifact.language || 'text';
    return `
        <div class="relative">
            <div class="absolute top-2 right-2 text-xs text-gray-500 bg-gray-900 px-2 py-1 rounded">${lang}</div>
            <pre class="bg-gray-900 rounded-lg p-4 overflow-x-auto"><code class="language-${lang} text-sm">${escapeHtml(artifact.content)}</code></pre>
        </div>
    `;
}

function renderAlertArtifact(artifact) {
    const items = artifact.content.split('\n').filter(l => l.trim().match(/^[-*•]/));
    return `
        <div class="space-y-2">
            ${items.map(item => {
                const text = item.replace(/^[-*•]\s*/, '').trim();
                const severity = detectAlertSeverity(text);
                const severityColors = {
                    critical: 'bg-red-900/30 border-red-700 text-red-300',
                    warning: 'bg-yellow-900/30 border-yellow-700 text-yellow-300',
                    info: 'bg-blue-900/30 border-blue-700 text-blue-300'
                };
                return `
                    <div class="flex items-center p-3 rounded border ${severityColors[severity] || severityColors.info}">
                        <i class="fas fa-exclamation-circle mr-3"></i>
                        <span class="text-sm">${escapeHtml(text)}</span>
                    </div>
                `;
            }).join('')}
        </div>
        <div class="mt-3 text-xs text-gray-500">${items.length} alerts</div>
    `;
}

function detectAlertSeverity(text) {
    const lower = text.toLowerCase();
    if (lower.includes('critical') || lower.includes('error') || lower.includes('down')) return 'critical';
    if (lower.includes('warning') || lower.includes('warn') || lower.includes('high')) return 'warning';
    return 'info';
}

function renderListArtifact(artifact) {
    return `<div class="prose prose-invert max-w-none text-sm">${marked.parse(artifact.content)}</div>`;
}

/**
 * Add thumbnail to history grid
 */
function addArtifactToHistory(artifact) {
    const history = document.getElementById('artifactHistory');
    if (!history) return;
    
    const typeInfo = ARTIFACT_TYPES[artifact.type] || ARTIFACT_TYPES.markdown;
    
    const thumb = document.createElement('div');
    thumb.className = `artifact-thumb cursor-pointer p-3 bg-gray-800 rounded-lg border border-gray-700 hover:border-gray-500 transition-all ${artifact.id === activeArtifactId ? 'ring-2 ring-blue-500' : ''}`;
    thumb.dataset.artifactId = artifact.id;
    thumb.onclick = () => setActiveArtifact(artifact.id);
    
    thumb.innerHTML = `
        <div class="flex items-center justify-between mb-2">
            <div class="flex items-center">
                <i class="fas ${typeInfo.icon} ${typeInfo.color} mr-2 text-sm"></i>
                <span class="text-xs font-medium text-white truncate max-w-[120px]">${escapeHtml(artifact.title)}</span>
            </div>
            ${pinnedArtifacts.has(artifact.id) ? '<i class="fas fa-thumbtack text-yellow-400 text-xs"></i>' : ''}
        </div>
        <div class="text-[10px] text-gray-500">${new Date(artifact.timestamp).toLocaleTimeString()}</div>
        <div class="mt-2 text-xs text-gray-400 line-clamp-2 h-8 overflow-hidden">${getArtifactPreview(artifact)}</div>
    `;
    
    // Insert at beginning
    history.insertBefore(thumb, history.firstChild);
}

function getArtifactPreview(artifact) {
    const text = artifact.content.replace(/[#*`|]/g, '').trim();
    return escapeHtml(text.substring(0, 80)) + (text.length > 80 ? '...' : '');
}

/**
 * Add artifact link to the chat message
 */
function addArtifactLinkToChat(artifact) {
    const typeInfo = ARTIFACT_TYPES[artifact.type] || ARTIFACT_TYPES.markdown;
    
    // Find the current streaming message or last AI message
    const messages = document.querySelectorAll('.ai-message-content');
    const lastMessage = messages[messages.length - 1];
    
    if (lastMessage) {
        // Check if link container exists, if not create it
        let linkContainer = lastMessage.querySelector('.artifact-links');
        if (!linkContainer) {
            linkContainer = document.createElement('div');
            linkContainer.className = 'artifact-links mt-3 pt-3 border-t border-gray-700 flex flex-wrap gap-2';
            lastMessage.appendChild(linkContainer);
        }
        
        const link = document.createElement('button');
        link.className = `inline-flex items-center px-3 py-1.5 text-xs ${typeInfo.bgColor} ${typeInfo.color} rounded-full hover:opacity-80 transition-opacity`;
        link.onclick = (e) => { e.stopPropagation(); setActiveArtifact(artifact.id); };
        link.innerHTML = `<i class="fas ${typeInfo.icon} mr-1.5"></i>${escapeHtml(artifact.title)} <i class="fas fa-arrow-right ml-2 text-[10px]"></i>`;
        
        linkContainer.appendChild(link);
    }
}

/**
 * Artifact Actions
 */
function copyArtifact() {
    const artifact = artifacts.find(a => a.id === activeArtifactId);
    if (!artifact) return;
    
    navigator.clipboard.writeText(artifact.content).then(() => {
        showToast('Copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'error');
    });
}

function exportArtifact() {
    const artifact = artifacts.find(a => a.id === activeArtifactId);
    if (!artifact) return;
    
    let filename, content, mimeType;
    
    switch (artifact.type) {
        case 'json':
            filename = 'artifact.json';
            content = artifact.content;
            mimeType = 'application/json';
            break;
        case 'yaml':
            filename = 'artifact.yaml';
            content = artifact.content;
            mimeType = 'text/yaml';
            break;
        case 'table':
            filename = 'artifact.csv';
            content = convertTableToCSV(artifact.content);
            mimeType = 'text/csv';
            break;
        default:
            filename = 'artifact.txt';
            content = artifact.content;
            mimeType = 'text/plain';
    }
    
    downloadFile(content, filename, mimeType);
}

function convertTableToCSV(tableContent) {
    const lines = tableContent.trim().split('\n');
    return lines
        .filter((_, i) => i !== 1) // Skip separator line
        .map(line => 
            line.split('|')
                .filter(c => c.trim())
                .map(c => `"${c.trim().replace(/"/g, '""')}"`)
                .join(',')
        )
        .join('\n');
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function pinArtifact() {
    if (!activeArtifactId) return;
    
    if (pinnedArtifacts.has(activeArtifactId)) {
        pinnedArtifacts.delete(activeArtifactId);
        showToast('Unpinned', 'info');
    } else {
        pinnedArtifacts.add(activeArtifactId);
        showToast('Pinned', 'success');
    }
    
    // Update UI
    const pinBtn = document.getElementById('pinArtifactBtn');
    if (pinBtn) {
        pinBtn.classList.toggle('text-yellow-400', pinnedArtifacts.has(activeArtifactId));
    }
    
    // Update thumbnail
    const thumb = document.querySelector(`.artifact-thumb[data-artifact-id="${activeArtifactId}"]`);
    if (thumb) {
        const pinIcon = thumb.querySelector('.fa-thumbtack');
        if (pinnedArtifacts.has(activeArtifactId) && !pinIcon) {
            const headerDiv = thumb.querySelector('.flex');
            headerDiv.insertAdjacentHTML('beforeend', '<i class="fas fa-thumbtack text-yellow-400 text-xs"></i>');
        } else if (!pinnedArtifacts.has(activeArtifactId) && pinIcon) {
            pinIcon.remove();
        }
    }
}

function minimizeArtifact() {
    const container = document.getElementById('activeArtifact');
    if (container) container.classList.add('hidden');
    activeArtifactId = null;
    
    // Remove active ring from thumbnails
    document.querySelectorAll('.artifact-thumb').forEach(el => {
        el.classList.remove('ring-2', 'ring-blue-500');
    });
}

function clearArtifacts() {
    if (!confirm('Clear all artifacts?')) return;
    
    artifacts = [];
    pinnedArtifacts.clear();
    activeArtifactId = null;
    
    const history = document.getElementById('artifactHistory');
    if (history) history.innerHTML = '';
    
    const active = document.getElementById('activeArtifact');
    if (active) active.classList.add('hidden');
    
    const empty = document.getElementById('artifactsEmpty');
    if (empty) empty.classList.remove('hidden');
    
    updateArtifactCount();
}

function exportAllArtifacts() {
    if (artifacts.length === 0) {
        showToast('No artifacts to export', 'info');
        return;
    }
    
    let content = `# AI Inquiry Artifacts Report\n`;
    content += `Generated: ${new Date().toLocaleString()}\n\n`;
    
    artifacts.forEach((artifact, i) => {
        content += `---\n\n## ${i + 1}. ${artifact.title}\n`;
        content += `Type: ${artifact.type} | Time: ${new Date(artifact.timestamp).toLocaleString()}\n\n`;
        content += artifact.content + '\n\n';
    });
    
    downloadFile(content, 'inquiry-artifacts.md', 'text/markdown');
}

function switchArtifactTab(tab) {
    currentArtifactTab = tab;
    
    // Update tab styles
    document.querySelectorAll('.artifact-tab').forEach(el => {
        el.classList.remove('border-blue-500', 'text-blue-400', 'bg-gray-800');
        el.classList.add('border-transparent', 'text-gray-400');
    });
    
    const activeTab = document.getElementById(`artifactTab${tab.charAt(0).toUpperCase() + tab.slice(1)}`);
    if (activeTab) {
        activeTab.classList.add('border-blue-500', 'text-blue-400', 'bg-gray-800');
        activeTab.classList.remove('border-transparent');
    }
    
    // Filter displayed artifacts
    const history = document.getElementById('artifactHistory');
    if (!history) return;
    
    if (tab === 'all') {
        history.querySelectorAll('.artifact-thumb').forEach(el => el.style.display = '');
    } else {
        // Show only recent (last 5) or pinned
        const thumbs = history.querySelectorAll('.artifact-thumb');
        thumbs.forEach((el, i) => {
            const isPinned = pinnedArtifacts.has(el.dataset.artifactId);
            el.style.display = (i < 5 || isPinned) ? '' : 'none';
        });
    }
}

// Expose artifact functions globally
window.setActiveArtifact = setActiveArtifact;
window.copyArtifact = copyArtifact;
window.exportArtifact = exportArtifact;
window.pinArtifact = pinArtifact;
window.minimizeArtifact = minimizeArtifact;
window.clearArtifacts = clearArtifacts;
window.exportAllArtifacts = exportAllArtifacts;
window.switchArtifactTab = switchArtifactTab;

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
