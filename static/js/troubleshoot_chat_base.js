/**
 * AI Chat Base Module
 * 
 * Shared utilities, rendering functions, and base components used by
 * both Inquiry and Troubleshooting modes on the AI chat page.
 * 
 * Dependencies: marked.js (for markdown rendering)
 */

const AIChatBase = {
    // Current font sizes
    chatFontSize: 14,
    termFontSize: 14,

    // Session state
    currentSessionId: null,

    // Configurable UI elements
    config: {
        chatContainerSelector: '#chatMessages',
        aiIconClass: 'fas fa-robot',
        aiGradientClass: 'from-purple-600 to-blue-600',
        aiName: 'AI Assistant',
        userIconClass: 'fas fa-user',
        userGradientClass: 'bg-blue-900/40',
        suggestionIconClass: 'fas fa-lightbulb'
    },

    /**
     * Initialize with custom configuration
     */
    init(config = {}) {
        this.config = { ...this.config, ...config };
    },

    /**
     * Get the chat messages container element
     */
    getChatContainer() {
        return document.querySelector(this.config.chatContainerSelector);
    },

    // ========================================================================
    // Utility Functions
    // ========================================================================

    /**
     * Escape HTML special characters to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    },

    /**
     * Copy text to clipboard with user feedback
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            if (typeof showToast === 'function') {
                showToast('Copied to clipboard!', 'success');
            }
            return true;
        } catch (err) {
            console.error('Failed to copy:', err);
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                if (typeof showToast === 'function') {
                    showToast('Copied to clipboard!', 'success');
                }
                return true;
            } catch (err2) {
                if (typeof showToast === 'function') {
                    showToast('Failed to copy to clipboard', 'error');
                }
                return false;
            } finally {
                document.body.removeChild(textArea);
            }
        }
    },

    /**
     * Format a timestamp for display
     */
    formatTimestamp(date = new Date()) {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // ========================================================================
    // Typing Indicator
    // ========================================================================

    /**
     * Show the typing indicator in chat
     */
    showTypingIndicator(text = "Thinking...") {
        const container = this.getChatContainer();
        if (!container) return;

        // Remove existing indicator
        this.removeTypingIndicator();

        const indicator = document.createElement('div');
        indicator.className = 'message ai-message typing-indicator flex justify-start my-2';
        indicator.id = 'typingIndicator';
        indicator.innerHTML = `
            <div class="bg-gray-700/80 rounded-lg px-4 py-3 flex items-center space-x-3 border border-gray-600 shadow-md">
                <div class="flex space-x-1">
                    <div class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                    <div class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                    <div class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
                </div>
                <span class="text-gray-400 text-xs">${this.escapeHtml(text)}</span>
            </div>
        `;
        container.appendChild(indicator);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Remove the typing indicator from chat
     */
    removeTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) indicator.remove();
    },

    // ========================================================================
    // Message Rendering
    // ========================================================================

    /**
     * Append a user message to the chat
     */
    appendUserMessage(text) {
        const container = this.getChatContainer();
        if (!container) return;

        const msgDiv = document.createElement('div');
        msgDiv.className = 'flex justify-end mb-3';
        msgDiv.innerHTML = `
            <div class="${this.config.userGradientClass} border border-blue-800 rounded-lg p-3 max-w-xs lg:max-w-md text-sm text-white shadow-md" style="word-break: break-word;">
                ${this.escapeHtml(text)}
            </div>
        `;
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Append an AI message to the chat with markdown rendering
     */
    appendAIMessage(text, options = {}) {
        const container = this.getChatContainer();
        if (!container) return;

        const {
            skipRunButtons = false,
            suggestions = [],
            messageId = 'msg-' + Date.now()
        } = options;

        // Remove typing indicator first
        this.removeTypingIndicator();

        // Process markers
        let cleanText = text;

        // 1. Suggestions
        const suggestionsRegex = /\[\s*SUGGESTIONS\s*\]\s*(?:```json)?\s*([\s\S]*?)\s*(?:```)?\s*\[\s*\/SUGGESTIONS\s*\]/gi;
        let extractedSuggestions = [...suggestions];

        cleanText = cleanText.replace(suggestionsRegex, (match, jsonStr) => {
            try {
                // Normalize JSON
                let normalized = jsonStr.trim().replace(/\n/g, '').replace(/\s+/g, ' ');
                if (normalized.includes("'") && !normalized.includes('"')) {
                    normalized = normalized.replace(/'/g, '"');
                }
                const parsed = JSON.parse(normalized);
                if (Array.isArray(parsed)) extractedSuggestions = extractedSuggestions.concat(parsed);
            } catch (e) {
                console.error("Failed to parse suggestions in-text:", e);
            }
            return '';
        });

        // 2. CMD_CARDs (JSON format)
        const cmdCardRegex = /\[CMD_CARD\](.*?)\[\/CMD_CARD\]/g;
        let cardDataList = [];
        cleanText = cleanText.replace(cmdCardRegex, (match, jsonStr) => {
            try {
                const cardData = JSON.parse(jsonStr);
                cardDataList.push(cardData);
            } catch (e) {
                console.error('Failed to parse CMD_CARD:', e);
            }
            return '';
        });

        // 3. Misc Tags (FILE_OPEN, CHANGESET, REASONING, PROGRESS)
        // These are usually handled by specific event handlers in the main controller,
        // but we clean them from the text here for rendering.
        cleanText = cleanText.replace(/\[FILE_OPEN\].*?\[\/FILE_OPEN\]/g, '');
        cleanText = cleanText.replace(/\[CHANGESET_ID\].*?\[\/CHANGESET_ID\]/g, '');
        cleanText = cleanText.replace(/\[REASONING\].*?\[\/REASONING\]/g, '');
        cleanText = cleanText.replace(/\[PROGRESS\].*?\[\/PROGRESS\]/g, '');

        // Render markdown
        let htmlContent = '';
        if (typeof marked !== 'undefined') {
            try {
                htmlContent = marked.parse(cleanText);
            } catch (e) {
                htmlContent = this.escapeHtml(cleanText);
            }
        } else {
            htmlContent = this.escapeHtml(cleanText);
        }

        const msgDiv = document.createElement('div');
        msgDiv.className = 'flex justify-start w-full pr-2 mb-3';
        msgDiv.innerHTML = `
            <div class="ai-message-wrapper w-full">
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center">
                        <div class="w-6 h-6 rounded-full bg-gradient-to-r ${this.config.aiGradientClass} flex items-center justify-center mr-2 shadow-sm">
                            <i class="${this.config.aiIconClass} text-white text-xs"></i>
                        </div>
                        <span class="text-xs text-gray-400 font-medium">${this.config.aiName}</span>
                    </div>
                </div>
                <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700 text-sm ai-message-content shadow-lg">
                    <div class="message-text">${htmlContent}</div>
                    <div class="cmd-cards-container mt-3 space-y-3"></div>
                    <div class="suggestions-container mt-4 pt-3 border-t border-gray-700/50 hidden">
                        <div class="text-[10px] uppercase tracking-wider text-gray-500 mb-2 flex items-center">
                            <i class="${this.config.suggestionIconClass} mr-1.5"></i> Suggested Actions
                        </div>
                        <div class="flex flex-wrap gap-2 suggestion-buttons"></div>
                    </div>
                </div>
            </div>
        `;

        container.appendChild(msgDiv);

        // Render CMD_CARDs
        const cardsContainer = msgDiv.querySelector('.cmd-cards-container');
        cardDataList.forEach((cardData, idx) => {
            const card = this.renderCommandCard(
                cardData.command,
                cardData.server || 'local',
                cardData.explanation || '',
                `${messageId}-card-${idx}`
            );
            cardsContainer.appendChild(card);
        });

        // Render Suggestions
        if (extractedSuggestions.length > 0) {
            const suggestionsWrapper = msgDiv.querySelector('.suggestions-container');
            const buttonsContainer = msgDiv.querySelector('.suggestion-buttons');
            suggestionsWrapper.classList.remove('hidden');

            extractedSuggestions.forEach(s => {
                const text = typeof s === 'string' ? s : (s.text || s.label || '');
                if (!text) return;

                const btn = document.createElement('button');
                btn.className = 'bg-gray-700/50 hover:bg-gray-700 text-gray-300 text-xs px-3 py-1.5 rounded-full border border-gray-600 hover:border-blue-500 transition-all';
                btn.innerHTML = this.escapeHtml(text);
                btn.onclick = () => {
                    if (typeof sendSuggestion === 'function') sendSuggestion(text);
                };
                buttonsContainer.appendChild(btn);
            });
        }

        // Add syntax highlighting and copy buttons to code blocks
        const codeBlocks = msgDiv.querySelectorAll('pre code');
        codeBlocks.forEach(block => {
            const pre = block.parentElement;
            const lang = block.className.replace('language-', '');

            this.addCopyButton(pre, block, lang);

            // Add run buttons for shell commands if not skipped
            if (!skipRunButtons) {
                const content = block.textContent.trim();
                if (this.isActualCommand(content)) {
                    this.addRunButtonToCodeBlock(pre, content);
                }
            }
        });

        container.scrollTop = container.scrollHeight;
        return msgDiv;
    },

    /**
     * Render a structured command card with run/skip buttons
     */
    renderCommandCard(command, server, explanation, cardId) {
        const card = document.createElement('div');
        card.className = 'command-card bg-gray-900 border border-gray-700 rounded-lg overflow-hidden shadow-md';
        card.id = cardId;

        const safeCmd = this.escapeHtml(command).replace(/'/g, "\\'");

        card.innerHTML = `
            <div class="command-card-header bg-gray-800/50 px-3 py-2 border-b border-gray-700 flex justify-between items-center">
                <span class="text-[10px] font-mono text-blue-400">
                    <i class="fas fa-server mr-1.5"></i>${this.escapeHtml(server)}
                </span>
                <span class="command-card-status text-[10px] text-gray-500 italic">
                    <i class="fas fa-history mr-1"></i>Pending
                </span>
            </div>
            <div class="px-3 py-2">
                <div class="text-xs text-gray-300 mb-2 truncate" title="${this.escapeHtml(explanation)}">${this.escapeHtml(explanation)}</div>
                <pre class="bg-black/40 p-2 rounded text-xs font-mono text-green-400 overflow-x-auto"><code>${this.escapeHtml(command)}</code></pre>
            </div>
            <div class="bg-gray-800/30 px-3 py-2 flex gap-2">
                <button class="btn btn-xs bg-blue-600 hover:bg-blue-500 text-white flex items-center gap-1.5 rounded py-1 px-2 text-[10px] font-medium" 
                        onclick="if(window.executeCommandWithOutput) executeCommandWithOutput('${cardId}', '${safeCmd}')">
                    <i class="fas fa-play text-[8px]"></i> Run
                </button>
                <button class="btn btn-xs bg-gray-700 hover:bg-gray-600 text-gray-300 flex items-center gap-1.5 rounded py-1 px-2 text-[10px] font-medium"
                        onclick="AIChatBase.copyToClipboard('${safeCmd}')">
                    <i class="fas fa-copy text-[8px]"></i> Copy
                </button>
                <button class="btn btn-xs border border-gray-600 hover:bg-gray-700 text-gray-400 flex items-center gap-1.5 rounded py-1 px-2 text-[10px]"
                        onclick="if(window.skipCommand) skipCommand('${cardId}', '${safeCmd}')">
                    <i class="fas fa-forward text-[8px]"></i> Skip
                </button>
            </div>
        `;

        return card;
    },

    /**
     * Check if text content looks like an executable command
     */
    isActualCommand(content) {
        // Skip yaml/json/config content
        if (content.includes(': ') && content.includes('\n')) return false;
        if (content.startsWith('{') || content.startsWith('[')) return false;

        // Common command patterns
        const commandPatterns = [
            /^(sudo\s+)?/i,
            /^(ssh|scp|rsync)\s+/i,
            /^(docker|kubectl|helm)\s+/i,
            /^(systemctl|service|journalctl)\s+/i,
            /^(cat|grep|awk|sed|tail|head)\s+/i,
            /^(curl|wget|nc)\s+/i,
            /^(ls|cd|pwd|mkdir|rm|cp|mv)\s+/i,
            /^(ps|top|htop|free|df)\s+/i,
            /^(apt|yum|dnf|pip|npm)\s+/i,
            /^(git|make|cmake)\s+/i
        ];

        return commandPatterns.some(pattern => pattern.test(content));
    },

    /**
     * Add a run button to a code block
     */
    addRunButtonToCodeBlock(pre, command) {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'absolute top-2 right-10';
        const safeCmd = this.escapeHtml(command).replace(/'/g, "\\'");

        actionsDiv.innerHTML = `
            <button class="bg-blue-600/80 hover:bg-blue-500 text-white text-[10px] py-1 px-2 rounded backdrop-blur-sm transition-all flex items-center gap-1 shadow-lg" 
                    onclick="if(window.executeCommandWithOutput) executeCommandWithOutput('auto-${Date.now()}', '${safeCmd}')">
                <i class="fas fa-play text-[8px]"></i> Run
            </button>
        `;

        pre.style.position = 'relative';
        pre.appendChild(actionsDiv);
    },

    /**
     * Add copy button to a code block
     */
    addCopyButton(pre, block, lang) {
        const btn = document.createElement('button');
        btn.className = 'absolute top-2 right-2 text-gray-400 hover:text-white bg-gray-800/50 hover:bg-gray-700 p-1 rounded backdrop-blur-sm transition-all';
        btn.innerHTML = '<i class="fas fa-copy text-xs"></i>';
        btn.title = 'Copy to clipboard';
        btn.onclick = () => this.copyToClipboard(block.textContent);

        pre.style.position = 'relative';
        pre.appendChild(btn);
    },

    // ========================================================================
    // Font Size Controls
    // ========================================================================

    /**
     * Adjust chat font size
     */
    adjustChatFont(delta) {
        this.chatFontSize = Math.max(10, Math.min(24, this.chatFontSize + delta));
        const container = this.getChatContainer();
        if (container) {
            container.style.fontSize = `${this.chatFontSize}px`;
        }
    },

    // ========================================================================
    // Welcome Screen
    // ========================================================================

    /**
     * Show the welcome screen with suggestions
     */
    showWelcomeScreen(title = "Welcome", subtitle = "How can I help you?", suggestions = []) {
        const container = this.getChatContainer();
        if (!container) return;

        container.innerHTML = `
            <div class="welcome-screen flex flex-col items-center justify-center p-8 text-center mt-10">
                <div class="w-16 h-16 rounded-2xl bg-gradient-to-br ${this.config.aiGradientClass} flex items-center justify-center mb-6 shadow-xl transform rotate-3 hover:rotate-0 transition-transform duration-300">
                    <i class="${this.config.aiIconClass} text-white text-3xl"></i>
                </div>
                <h2 class="text-2xl font-bold text-white mb-2">${this.escapeHtml(title)}</h2>
                <p class="text-gray-400 text-sm mb-8 max-w-sm">${this.escapeHtml(subtitle)}</p>
                <div class="grid grid-cols-1 gap-3 w-full max-w-md">
                    ${suggestions.map(s => `
                        <button onclick="if(typeof sendSuggestion === 'function') sendSuggestion('${this.escapeHtml(s.text || s).replace(/'/g, "\\'")}')" 
                                class="flex items-center gap-3 p-3 bg-gray-800/50 hover:bg-gray-800 border border-gray-700 rounded-xl text-left text-sm text-gray-300 hover:text-white hover:border-blue-500/50 transition-all group">
                            <i class="${s.icon || 'fas fa-arrow-right'} text-gray-500 group-hover:text-blue-400 transition-colors"></i>
                            <span>${this.escapeHtml(s.text || s)}</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    },

    // ========================================================================
    // Clear Chat
    // ========================================================================

    /**
     * Clear all messages from the chat
     */
    clearAllMessages() {
        const container = this.getChatContainer();
        if (container) {
            container.innerHTML = '';
        }
    }
};

// Export for use as module and global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AIChatBase;
}
window.AIChatBase = AIChatBase;
