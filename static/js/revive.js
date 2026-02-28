/**
 * RE-VIVE WebSocket Client
 * 
 * Handles real-time communication with the RE-VIVE unified assistant.
 * Manages connection, message protocols, and UI updates.
 */

class ReviveClient {
    constructor() {
        this.ws = null;
        this.sessionId = 'new';
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.isConnecting = false;
        this.currentMode = 'auto';
        this.messageQueue = [];

        // UI Elements
        this.messagesContainer = document.getElementById('messages-container');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.stopButton = document.getElementById('stop-button');
        this.modeBadge = document.getElementById('mode-badge');
        this.connectionStatus = document.getElementById('connection-status');
        this.sessionSelector = document.getElementById('session-selector');
        this.charCount = document.getElementById('char-count');

        this.setupEventListeners();
        this.loadSessions();
    }

    setupEventListeners() {
        // Send message on Enter (Shift+Enter for new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
            this.charCount.textContent = `${this.messageInput.value.length} / 2000`;
        });

        // Send button
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // Stop button
        this.stopButton.addEventListener('click', () => this.stopGeneration());

        // Session selector
        this.sessionSelector.addEventListener('change', (e) => {
            this.sessionId = e.target.value;
            if (this.sessionId !== 'new') {
                this.loadSessionHistory();
            } else {
                this.clearMessages();
            }
        });
    }

    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            return;
        }

        this.isConnecting = true;
        this.updateConnectionStatus('connecting', 'Connecting...');

        // Get auth token from cookie or localStorage
        const token = this.getAuthToken();
        if (!token) {
            this.updateConnectionStatus('error', 'Not authenticated');
            return;
        }

        // Get current page context
        const currentPage = window.location.pathname;

        // Build WebSocket URL
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/revive/${this.sessionId}?token=${encodeURIComponent(token)}&current_page=${encodeURIComponent(currentPage)}`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.isConnecting = false;
            this.reconnectAttempts = 0;
            this.updateConnectionStatus('connected', 'Connected');

            // Process queued messages
            while (this.messageQueue.length > 0) {
                const msg = this.messageQueue.shift();
                this.ws.send(JSON.stringify(msg));
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('error', 'Connection error');
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed');
            this.isConnecting = false;
            this.updateConnectionStatus('disconnected', 'Disconnected');
            this.attemptReconnect();
        };
    }

    handleMessage(data) {
        console.log('Received message:', data);

        switch (data.type) {
            case 'connected':
                if (data.session_id && data.session_id !== this.sessionId) {
                    this.sessionId = data.session_id;
                    this.updateSessionSelector();
                }
                break;

            case 'mode':
                this.updateMode(data.mode || 'auto');
                break;

            case 'chunk':
                this.appendToCurrentMessage(data.content || '');
                break;

            case 'tool_call':
                this.showToolCall(data.tool_name, data.arguments);
                break;

            case 'done':
                this.finishMessage(data.tool_calls || []);
                break;

            case 'error':
                this.showError(data.message || 'An error occurred');
                break;

            case 'cancelled':
                this.finishMessage([], true);
                break;
        }
    }

    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Add user message to UI
        this.addUserMessage(message);

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.charCount.textContent = '0 / 2000';

        // Show typing indicator
        this.showTypingIndicator();

        // Send via WebSocket
        const payload = {
            type: 'message',
            content: message,
            current_page: window.location.pathname
        };

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(payload));
        } else {
            this.messageQueue.push(payload);
            this.connect();
        }

        // Toggle buttons
        this.sendButton.classList.add('hidden');
        this.stopButton.classList.remove('hidden');
    }

    stopGeneration() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'stop' }));
        }

        this.sendButton.classList.remove('hidden');
        this.stopButton.classList.add('hidden');
    }

    addUserMessage(content) {
        const template = document.getElementById('user-message-template');
        const clone = template.content.cloneNode(true);

        const messageContent = clone.querySelector('.message-content');
        messageContent.textContent = content;

        this.messagesContainer.appendChild(clone);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const template = document.getElementById('typing-indicator-template');
        const clone = template.content.cloneNode(true);
        this.messagesContainer.appendChild(clone);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    appendToCurrentMessage(content) {
        this.removeTypingIndicator();

        let currentMessage = this.messagesContainer.querySelector('.assistant-message.active');

        if (!currentMessage) {
            const template = document.getElementById('assistant-message-template');
            const clone = template.content.cloneNode(true);
            this.messagesContainer.appendChild(clone);

            currentMessage = this.messagesContainer.lastElementChild;
            currentMessage.classList.add('assistant-message', 'active');
            currentMessage.dataset.content = '';
        }

        // Append content
        currentMessage.dataset.content += content;

        // Render markdown
        const messageContent = currentMessage.querySelector('.message-content');
        if (typeof marked !== 'undefined') {
            messageContent.innerHTML = marked.parse(currentMessage.dataset.content);
        } else {
            messageContent.textContent = currentMessage.dataset.content;
        }

        this.scrollToBottom();
    }

    finishMessage(toolCalls = [], cancelled = false) {
        const currentMessage = this.messagesContainer.querySelector('.assistant-message.active');

        if (currentMessage) {
            currentMessage.classList.remove('active');

            // Show tool calls
            if (toolCalls.length > 0) {
                const toolCallsContainer = currentMessage.querySelector('.tool-calls');
                toolCallsContainer.classList.remove('hidden');

                toolCalls.forEach(tool => {
                    const badge = document.createElement('span');
                    badge.className = 'inline-block px-2 py-1 text-xs bg-purple-800 text-purple-200 rounded';
                    badge.textContent = `🔧 ${tool}`;
                    toolCallsContainer.appendChild(badge);
                });
            }

            if (cancelled) {
                const messageContent = currentMessage.querySelector('.message-content');
                messageContent.innerHTML += '<p class="text-gray-400 italic">Generation cancelled</p>';
            }
        }

        this.removeTypingIndicator();

        // Toggle buttons
        this.sendButton.classList.remove('hidden');
        this.stopButton.classList.add('hidden');

        this.scrollToBottom();
    }

    showToolCall(toolName, args) {
        console.log(`Tool call: ${toolName}`, args);

        // Visual feedback for tool execution
        const currentMessage = this.messagesContainer.querySelector('.assistant-message.active');
        if (currentMessage) {
            const toolCallsContainer = currentMessage.querySelector('.tool-calls');
            toolCallsContainer.classList.remove('hidden');

            const template = document.getElementById('tool-call-template');
            const clone = template.content.cloneNode(true);
            clone.querySelector('.tool-name').textContent = toolName;
            toolCallsContainer.appendChild(clone);
        }
    }

    showError(message) {
        this.removeTypingIndicator();

        const errorDiv = document.createElement('div');
        errorDiv.className = 'message-bubble flex justify-start';
        errorDiv.innerHTML = `
            <div class="max-w-2xl bg-red-900 border border-red-700 text-white rounded-lg px-4 py-3">
                <div class="flex items-start gap-3">
                    <i class="fas fa-exclamation-triangle text-red-400"></i>
                    <div>
                        <strong>Error:</strong> ${this.escapeHtml(message)}
                    </div>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(errorDiv);

        this.sendButton.classList.remove('hidden');
        this.stopButton.classList.add('hidden');
        this.scrollToBottom();
    }

    updateMode(mode) {
        this.currentMode = mode;

        // Update badge
        this.modeBadge.className = 'mode-badge px-3 py-1 rounded-full text-xs font-semibold text-white';

        switch (mode) {
            case 'grafana':
                this.modeBadge.classList.add('mode-grafana');
                this.modeBadge.innerHTML = '<i class="fas fa-chart-line mr-1"></i> Grafana Mode';
                break;
            case 'aiops':
                this.modeBadge.classList.add('mode-aiops');
                this.modeBadge.innerHTML = '<i class="fas fa-cogs mr-1"></i> AIOps Mode';
                break;
            default:
                this.modeBadge.classList.add('mode-auto');
                this.modeBadge.innerHTML = '<i class="fas fa-magic mr-1"></i> Auto Mode';
        }
    }

    updateConnectionStatus(status, text) {
        const dot = this.connectionStatus.querySelector('.w-2');
        const label = this.connectionStatus.querySelector('span:last-child');

        dot.className = 'w-2 h-2 rounded-full';

        switch (status) {
            case 'connected':
                dot.classList.add('bg-green-500');
                break;
            case 'connecting':
                dot.classList.add('bg-yellow-500');
                break;
            case 'error':
                dot.classList.add('bg-red-500');
                break;
            default:
                dot.classList.add('bg-gray-500');
        }

        label.textContent = text;
        label.className = status === 'connected' ? 'text-green-400' : 'text-gray-400';
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.updateConnectionStatus('error', 'Connection failed');
            return;
        }

        this.reconnectAttempts++;
        this.updateConnectionStatus('connecting', `Reconnecting (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

        setTimeout(() => {
            this.connect();
        }, this.reconnectDelay * this.reconnectAttempts);
    }

    loadSessions() {
        // Load session list from API
        fetch('/api/revive/sessions')
            .then(res => res.json())
            .then(data => {
                if (data.sessions) {
                    data.sessions.forEach(session => {
                        const option = document.createElement('option');
                        option.value = session.id;
                        option.textContent = session.title || 'Untitled Session';
                        this.sessionSelector.appendChild(option);
                    });
                }
            })
            .catch(err => console.error('Failed to load sessions:', err));
    }

    updateSessionSelector() {
        // Add current session if not in list
        const exists = Array.from(this.sessionSelector.options).some(opt => opt.value === this.sessionId);
        if (!exists && this.sessionId !== 'new') {
            const option = document.createElement('option');
            option.value = this.sessionId;
            option.textContent = 'Current Session';
            option.selected = true;
            this.sessionSelector.insertBefore(option, this.sessionSelector.options[1]);
        }
    }

    loadSessionHistory() {
        // TODO: Load message history for selected session
        this.clearMessages();
    }

    clearMessages() {
        this.messagesContainer.innerHTML = `
            <div class="message-bubble max-w-2xl mx-auto text-center py-8">
                <i class="fas fa-brain text-6xl text-purple-400 mb-4"></i>
                <h2 class="text-2xl font-bold text-white mb-2">Welcome to RE-VIVE</h2>
                <p class="text-gray-400">
                    Your unified assistant for Grafana observability and AIOps remediation.
                </p>
                <p class="text-sm text-gray-500 mt-2">
                    Ask about metrics, dashboards, or execute runbooks - I'll automatically determine the best approach.
                </p>
            </div>
        `;
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    getAuthToken() {
        // Try to get token from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'access_token') {
                return value;
            }
        }

        // Fallback to localStorage
        return localStorage.getItem('auth_token');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for global use
window.ReviveClient = ReviveClient;
