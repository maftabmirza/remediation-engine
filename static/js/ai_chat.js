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
let chatFontSize = 14;
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
                    <button onclick="rerunCommand('${escapeHtml(entry.command).replace(/'/g, "\\'")}')" class="text-blue-400 hover:text-blue-300 text-xs px-1" title="Re-run"><i class="fas fa-redo"></i></button>
                    <button onclick="copyToClipboard('${escapeHtml(entry.command).replace(/'/g, "\\'")}')" class="text-gray-400 hover:text-white text-xs px-1" title="Copy"><i class="fas fa-copy"></i></button>
                </div>
            </div>
            <div class="text-[10px] text-gray-500 mt-1">${entry.displayTime} • exit ${entry.exitCode}</div>
        </div>
    `).join('');
}

// Font Size Controls
function adjustChatFont(delta) {
    chatFontSize = Math.max(10, Math.min(24, chatFontSize + delta));
    document.getElementById('chatMessages').style.fontSize = `${chatFontSize}px`;
}

function adjustTermFont(delta) {
    if (!term) return;
    const newSize = Math.max(8, Math.min(24, term.options.fontSize + delta));
    term.options.fontSize = newSize;
    fitAddon.fit();
}

// Chat Session Management
async function initChatSession() {
    try {
        await loadAvailableProviders();

        // Get or create standalone session
        let response = await apiCall('/api/chat/sessions/standalone');

        if (response.ok) {
            currentSession = await response.json();
            currentSessionId = currentSession.id;
            console.log('Using chat session:', currentSessionId);
        } else {
            // Fallback: create new session
            const createResponse = await apiCall('/api/chat/sessions', {
                method: 'POST',
                body: JSON.stringify({})
            });
            if (!createResponse.ok) throw new Error('Failed to create chat session');
            currentSession = await createResponse.json();
            currentSessionId = currentSession.id;
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
    } catch (error) {
        console.error('Chat init failed:', error);
        showToast('Failed to initialize chat', 'error');
    }
}

async function loadAvailableProviders() {
    try {
        // Show connecting status
        if (typeof updateModelStatusIcon === 'function') {
            updateModelStatusIcon('connecting');
        }

        const response = await apiCall('/api/chat/providers');
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
    } catch (error) {
        console.error('Failed to load providers:', error);
        if (typeof updateModelStatusIcon === 'function') {
            updateModelStatusIcon('disconnected');
        }
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
            const btn = document.getElementById('modelIconBtn');
            if (btn) btn.title = `LLM: ${provider.provider_name}`;
        }
    } else {
        const defaultProvider = availableProviders.find(p => p.is_default);
        if (defaultProvider) {
            if (typeof selectedModelId !== 'undefined') {
                selectedModelId = defaultProvider.id;
            }
            const btn = document.getElementById('modelIconBtn');
            if (btn) btn.title = `LLM: ${defaultProvider.provider_name}`;
        }
    }
}

async function switchModel(providerId) {
    if (!currentSessionId || !providerId) return;
    try {
        const response = await apiCall(`/api/chat/sessions/${currentSessionId}/provider`, {
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
        const response = await apiCall(`/api/chat/sessions/${sessionId}/messages`);
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
                const wrapper = document.createElement('div');
                const hasCodeBlock = msg.content.includes('```') || msg.content.includes('[TERMINAL') || msg.content.includes('[ERROR') || msg.content.includes('[SYSTEM');
                wrapper.className = hasCodeBlock ? 'flex justify-start w-full pr-2 mb-3' : 'flex justify-end mb-3';
                wrapper.innerHTML = `
                    <div class="bg-gray-700/80 border border-gray-700 rounded-lg p-3 ${hasCodeBlock ? 'w-full' : 'max-w-xs lg:max-w-md'} text-sm text-white shadow-md" style="word-break: break-word;">
                        <div class="user-message-content ${hasCodeBlock ? 'overflow-x-auto max-h-80 overflow-y-auto' : ''}">
                            ${hasCodeBlock ? marked.parse(msg.content) : escapeHtml(msg.content)}
                        </div>
                    </div>
                `;
                container.appendChild(wrapper);
                lastMessageRole = 'user';
            } else if (msg.role === 'assistant') {
                const wrapper = document.createElement('div');
                wrapper.className = 'flex justify-start w-full pr-2 mb-3';
                wrapper.innerHTML = `
                    <div class="ai-message-wrapper w-full">
                        <div class="flex items-center mb-2">
                            <div class="w-6 h-6 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center mr-2">
                                <i class="fas fa-robot text-white text-xs"></i>
                            </div>
                            <span class="text-xs text-gray-400">AI Assistant</span>
                        </div>
                        <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700 text-sm ai-message-content shadow-lg">
                            ${marked.parse(msg.content)}
                        </div>
                    </div>
                `;
                container.appendChild(wrapper);
                addRunButtons(wrapper);
                lastMessageRole = 'assistant';
            }
        });
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Failed to load chat history:', error);
        showWelcomeScreen();
    }
}

function showWelcomeScreen() {
    const container = document.getElementById('chatMessages');
    container.innerHTML = `
        <div class="text-center text-gray-400 mt-10">
            <i class="fas fa-robot text-4xl mb-3 text-purple-400"></i>
            <p class="mb-2 text-lg">👋 Hi! I'm your AI assistant.</p>
            <p class="text-sm text-gray-500 mb-4">Connect to a server and ask me anything:</p>
            <div class="mt-3 space-y-2 text-left max-w-sm mx-auto">
                <button onclick="sendSuggestion('What can you help me with?')" class="w-full text-left bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded text-sm border border-gray-700 transition-colors">
                    <i class="fas fa-question-circle text-purple-400 mr-2"></i>What can you help me with?
                </button>
                <button onclick="sendSuggestion('How do I check disk space on a Linux server?')" class="w-full text-left bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded text-sm border border-gray-700 transition-colors">
                    <i class="fas fa-terminal text-green-400 mr-2"></i>How do I check disk space?
                </button>
                <button onclick="sendSuggestion('Show me common troubleshooting commands')" class="w-full text-left bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded text-sm border border-gray-700 transition-colors">
                    <i class="fas fa-wrench text-yellow-400 mr-2"></i>Common troubleshooting commands
                </button>
                <button onclick="sendSuggestion('Explain how to analyze server logs')" class="w-full text-left bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded text-sm border border-gray-700 transition-colors">
                    <i class="fas fa-file-alt text-blue-400 mr-2"></i>How to analyze server logs
                </button>
            </div>
        </div>
    `;
}

function sendSuggestion(text) {
    const input = document.getElementById('chatInput');
    input.value = text;
    sendMessage(new Event('submit'));
}

// WebSocket Chat Connection
function connectChatWebSocket(sessionId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('token');
    if (!token) {
        document.getElementById('chatMessages').innerHTML = '<div class="text-red-400 text-center">Authentication error. Please login again.</div>';
        return;
    }
    chatSocket = new WebSocket(`${protocol}//${window.location.host}/ws/chat/${sessionId}?token=${token}`);
    chatSocket.onopen = () => {
        if (typeof updateModelStatusIcon === 'function') {
            updateModelStatusIcon('connected');
        }
    };
    chatSocket.onmessage = (event) => {
        const msg = event.data;
        if (msg === '[DONE]') return;
        appendAIMessage(msg);
    };
    chatSocket.onclose = () => {
        if (typeof updateModelStatusIcon === 'function') {
            updateModelStatusIcon('disconnected');
        }
        setTimeout(() => {
            if (currentSessionId) {
                if (typeof updateModelStatusIcon === 'function') {
                    updateModelStatusIcon('connecting');
                }
                connectChatWebSocket(currentSessionId);
            }
        }, 3000);
    };
}

function appendAIMessage(text, skipRunButtons = false) {
    removeTypingIndicator();
    const container = document.getElementById('chatMessages');

    // Check for CMD_CARD markers and extract them
    const cmdCardRegex = /\[CMD_CARD\](.*?)\[\/CMD_CARD\]/g;
    let match;
    let hasCards = false;
    let extractedCommands = [];

    while ((match = cmdCardRegex.exec(text)) !== null) {
        hasCards = true;
        try {
            const cardData = JSON.parse(match[1]);
            extractedCommands.push(cardData.command);
            renderCommandCard(cardData.command, cardData.server, cardData.explanation);
        } catch (e) {
            console.error('Failed to parse CMD_CARD:', e);
        }
    }

    // Remove CMD_CARD markers from text for display
    let cleanText = text.replace(cmdCardRegex, '');

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

    // If only CMD_CARD (no meaningful text), skip normal message rendering
    if (hasCards && cleanText.trim() === '') {
        return;
    }

    if (lastMessageRole !== 'assistant' || !currentMessageDiv) {
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
                <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700 text-sm ai-message-content shadow-lg" data-full-text=""></div>
            </div>
        `;
        container.appendChild(wrapper);
        currentMessageDiv = wrapper.querySelector('.ai-message-content');
        lastMessageRole = 'assistant';
    }
    if (!currentMessageDiv) {
        console.error('Failed to create message container');
        return;
    }
    const currentText = currentMessageDiv.getAttribute('data-full-text') || '';
    const newText = currentText + cleanText;
    currentMessageDiv.setAttribute('data-full-text', newText);
    currentMessageDiv.innerHTML = marked.parse(newText);
    // Only add "Run in Terminal" buttons in Inquiry mode (troubleshoot uses CMD_CARDs)
    const chatMode = typeof currentChatMode !== 'undefined' ? currentChatMode : 'troubleshoot';
    if (!skipRunButtons && !hasCards && chatMode === 'general') {
        addRunButtons(currentMessageDiv);
    }
    container.scrollTop = container.scrollHeight;
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
                    <button onclick="executeCommandWithOutput('${cardId}', '${escapeHtml(command).replace(/'/g, "\\'")}')" 
                            class="flex-1 bg-green-600 hover:bg-green-500 text-white text-sm px-4 py-2 rounded font-medium transition-colors flex items-center justify-center">
                        <i class="fas fa-play mr-2"></i>Run in Terminal
                    </button>
                    <button onclick="skipCommand('${cardId}', '${escapeHtml(command).replace(/'/g, "\\'")}')" 
                            class="bg-yellow-600 hover:bg-yellow-500 text-white text-sm px-3 py-2 rounded font-medium transition-colors"
                            title="Skip this command">
                        <i class="fas fa-forward"></i>
                    </button>
                    <button onclick="copyToClipboard('${escapeHtml(command).replace(/'/g, "\\'")}')" 
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

function appendUserMessage(text) {
    const container = document.getElementById('chatMessages');
    const wrapper = document.createElement('div');
    wrapper.className = 'flex justify-end';
    wrapper.innerHTML = `
        <div class="bg-gray-700/80 border border-gray-700 rounded-lg p-3 max-w-xs lg:max-w-md text-sm text-white shadow-md">
            ${text}
        </div>
    `;
    container.appendChild(wrapper);
    container.scrollTop = container.scrollHeight;
    lastMessageRole = 'user';
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

function sendMessage(e) {
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

    // Check which mode we're in (defined in ai_chat.html)
    const chatMode = typeof currentChatMode !== 'undefined' ? currentChatMode : 'troubleshoot';

    appendUserMessage(escapeHtml(text));
    showTypingIndicator();

    if (chatMode === 'general') {
        // General Inquiry mode: Use observability API
        // The handleObservabilityQuery function is defined in ai_chat.html
        if (typeof handleObservabilityQuery === 'function') {
            handleObservabilityQuery(text);
        } else {
            removeTypingIndicator();
            appendAIMessage('Error: Observability query handler not available.');
        }
        input.value = '';
        return;
    }

    // Troubleshooting mode: Use WebSocket chat (original behavior)
    if (!chatSocket) {
        removeTypingIndicator();
        appendAIMessage('Chat not connected. Please refresh the page.');
        return;
    }

    const termContent = getTerminalContent();
    let finalMessage = text;
    if (termContent) {
        finalMessage += `\n\n[SYSTEM: The user has the following active terminal output. Use it if relevant to the query.]\n\`\`\`\n${termContent}\n\`\`\``;
    }
    chatSocket.send(finalMessage);
    input.value = '';
}

function showTypingIndicator() {
    const container = document.getElementById('chatMessages');
    const indicator = document.createElement('div');
    indicator.id = 'typingIndicator';
    indicator.className = 'flex justify-start my-2';
    indicator.innerHTML = `
        <div class="bg-gray-700 rounded-lg px-4 py-3 flex items-center space-x-2">
            <div class="flex space-x-1">
                <div class="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                <div class="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                <div class="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
            </div>
            <span class="text-gray-400 text-xs">AI is thinking...</span>
        </div>
    `;
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
    } else {
        return new Promise((resolve, reject) => {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.top = '-9999px';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            try {
                const successful = document.execCommand('copy');
                document.body.removeChild(textarea);
                if (successful) resolve();
                else reject(new Error('Copy command failed'));
            } catch (err) {
                document.body.removeChild(textarea);
                reject(err);
            }
        });
    }
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
async function submitFeedback(feedbackId, command, success) {
    const feedbackDiv = document.getElementById(feedbackId);
    if (feedbackDiv) {
        feedbackDiv.innerHTML = `
            <div class="text-${success ? 'green' : 'yellow'}-400 text-sm p-2">
                <i class="fas fa-${success ? 'check' : 'times'} mr-2"></i>
                ${success ? 'Great! Feedback recorded.' : 'Thanks for letting us know.'}
            </div>
            `;
    }

    // Save feedback to backend
    try {
        await apiCall('/api/v1/solution-feedback', {
            method: 'POST',
            body: JSON.stringify({
                solution_type: 'command',
                solution_reference: command,
                success: success,
                session_id: currentSessionId
            })
        });
    } catch (error) {
        console.error('Failed to save feedback:', error);
    }
}

// ============================================================================
// Session-Level Feedback (Floating Button)
// ============================================================================

let sessionFeedbackButtonVisible = false;

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

    // Auto-send to chat WebSocket
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        // Add to UI as user message, but visually distinct (auto)
        // Using appendUserMessage but maybe prefixed
        appendUserMessage(`[Auto-Report] Command execution complete.`);

        // Show typing indicator
        showTypingIndicator();

        // Send to Agent with terminal context
        const termContent = getTerminalContent();
        let finalMessage = autoMessage;
        if (termContent) {
            finalMessage += `\n\n[TERMINAL CONTEXT]\n\`\`\`\n${termContent}\n\`\`\``;
        }

        chatSocket.send(finalMessage);
        console.log('✅ Auto-sent command output to Agent');
    } else {
        console.warn('Chat WebSocket not connected - cannot auto-send');
        showToast('Please type "Done" to have AI analyze the output', 'info');
    }
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
    container.innerHTML = `<div id="agentHeader" class="bg-gradient-to-r from-purple-900/50 to-blue-900/50 rounded-lg p-4 mb-4 border border-purple-500/30"><div class="flex items-center justify-between"><div class="flex items-center"><div class="w-8 h-8 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center mr-3 animate-pulse"><i class="fas fa-robot text-white text-sm"></i></div><div><div class="text-sm font-semibold text-white">Agent Mode Active</div><div class="text-xs text-gray-400 truncate max-w-xs" title="${escapeHtml(goal)}">${escapeHtml(goal)}</div></div></div><button id="agentStopBtn" onclick="stopAgent()" class="text-red-400 hover:text-red-300 text-xs px-3 py-1 border border-red-500/30 rounded hover:bg-red-500/10 transition-colors"><i class="fas fa-stop mr-1"></i>Stop</button></div><div class="mt-3 flex items-center text-xs"><span id="agentStatusBadge" class="px-2 py-1 rounded bg-purple-600/50 text-purple-200 mr-2"><i class="fas fa-spinner fa-spin mr-1"></i>Starting...</span><span class="text-gray-400">Step <span id="agentStepNum">0</span> of <span id="agentMaxSteps">20</span></span></div></div><div id="agentSteps" class="space-y-4"></div><div id="agentApprovalPanel" class="hidden"></div>`;
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
        case 'step_created': addAgentStep(data.step); break;
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

function addAgentStep(step) {
    const container = document.getElementById('agentSteps');
    if (!container) return;
    const stepNum = document.getElementById('agentStepNum');
    if (stepNum) stepNum.textContent = step.step_number;
    const stepEl = document.createElement('div');
    stepEl.id = `agent-step-${step.id}`;
    stepEl.className = 'bg-gray-800 rounded-lg p-4 border border-gray-700';
    if (step.step_type === 'command') {
        stepEl.innerHTML = `<div class="flex items-start"><div class="w-6 h-6 rounded-full bg-blue-600/30 flex items-center justify-center mr-3 mt-0.5 flex-shrink-0"><i class="fas fa-terminal text-blue-400 text-xs"></i></div><div class="flex-grow min-w-0"><div class="text-xs text-gray-400 mb-1">Step ${step.step_number} - Command</div><div class="bg-gray-900 rounded p-2 font-mono text-sm text-green-400 break-all">${escapeHtml(step.content)}</div>${step.reasoning ? `<div class="text-xs text-gray-500 mt-2"><i class="fas fa-lightbulb text-yellow-500 mr-1"></i>${escapeHtml(step.reasoning)}</div>` : ''}<div id="step-output-${step.id}" class="mt-2 hidden"><div class="text-xs text-gray-400 mb-1">Output:</div><pre class="bg-gray-900 rounded p-2 text-xs text-gray-300 overflow-x-auto max-h-40 overflow-y-auto"></pre></div><div id="step-status-${step.id}" class="mt-2 flex items-center text-xs text-gray-400"><i class="fas fa-clock mr-1"></i>Pending...</div></div></div>`;
        if (step.status === 'pending') showApprovalPanel(step);
    } else if (step.step_type === 'complete') {
        stepEl.className = 'bg-green-900/30 rounded-lg p-4 border border-green-500/30';
        stepEl.innerHTML = `<div class="flex items-start"><div class="w-6 h-6 rounded-full bg-green-600/30 flex items-center justify-center mr-3 mt-0.5 flex-shrink-0"><i class="fas fa-check text-green-400 text-xs"></i></div><div class="flex-grow"><div class="text-xs text-green-400 mb-1 font-semibold">Goal Achieved!</div><div class="text-sm text-gray-300">${marked.parse(step.content)}</div></div></div>`;
    } else if (step.step_type === 'failed') {
        stepEl.className = 'bg-red-900/30 rounded-lg p-4 border border-red-500/30';
        stepEl.innerHTML = `<div class="flex items-start"><div class="w-6 h-6 rounded-full bg-red-600/30 flex items-center justify-center mr-3 mt-0.5 flex-shrink-0"><i class="fas fa-times text-red-400 text-xs"></i></div><div class="flex-grow"><div class="text-xs text-red-400 mb-1 font-semibold">Agent Failed</div><div class="text-sm text-gray-300">${escapeHtml(step.content)}</div></div></div>`;
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
}

async function approveAgentStep() {
    if (!currentAgentSession) return;
    try {
        if (agentSocket && agentSocket.readyState === WebSocket.OPEN) {
            agentSocket.send(JSON.stringify({ type: 'approve' }));
        } else {
            await apiCall(`/api/agent/${currentAgentSession.id}/approve`, { method: 'POST' });
        }
        hideApprovalPanel();
        updateAgentStatus('executing', 'Running command...');
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

