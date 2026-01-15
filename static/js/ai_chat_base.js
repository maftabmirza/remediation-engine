/**
 * AI Chat Base Module
 * 
 * Shared utilities, rendering functions, and base components used by
 * both Inquiry and Troubleshooting modes on the AI chat page.
 * 
 * Dependencies: marked.js (for markdown rendering)
 */

// ============================================================================
// Configuration
// ============================================================================

const AIChatBase = {
    // Current font sizes
    chatFontSize: 14,
    termFontSize: 14,

    // Session state
    currentSessionId: null,

    // Chat container selector
    chatContainerSelector: '#chatMessages',

    /**
     * Get the chat messages container element
     */
    getChatContainer() {
        return document.querySelector(this.chatContainerSelector);
    },

    // ========================================================================
    // Utility Functions
    // ========================================================================

    /**
     * Escape HTML special characters to prevent XSS
     */
    escapeHtml(text) {
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
    showTypingIndicator() {
        const container = this.getChatContainer();
        if (!container) return;

        // Remove existing indicator
        this.removeTypingIndicator();

        const indicator = document.createElement('div');
        indicator.className = 'message ai-message typing-indicator';
        indicator.id = 'typingIndicator';
        indicator.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
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
        msgDiv.className = 'message user-message';
        msgDiv.innerHTML = `
            <div class="message-content">
                <div class="message-text">${this.escapeHtml(text)}</div>
            </div>
            <div class="message-avatar">
                <i class="fas fa-user"></i>
            </div>
        `;
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Append an AI message to the chat with markdown rendering
     * @param {string} text - The message text (supports markdown)
     * @param {boolean} skipRunButtons - If true, don't add run buttons to code blocks
     */
    appendAIMessage(text, skipRunButtons = false) {
        const container = this.getChatContainer();
        if (!container) return;

        // Remove typing indicator first
        this.removeTypingIndicator();

        const msgDiv = document.createElement('div');
        msgDiv.className = 'message ai-message';

        // Process CMD_CARD markers first
        let processedText = text;
        const cmdCardRegex = /\[CMD_CARD\]\s*server:\s*([^\n]+)\s*command:\s*([^\n]+)\s*explanation:\s*([^\[]*)\[\/CMD_CARD\]/g;
        let cardIndex = 0;

        processedText = processedText.replace(cmdCardRegex, (match, server, command, explanation) => {
            const cardId = `cmd-card-${Date.now()}-${cardIndex++}`;
            // Return a placeholder that we'll replace with the actual card
            return `<div id="${cardId}" class="cmd-card-placeholder" data-server="${this.escapeHtml(server.trim())}" data-command="${this.escapeHtml(command.trim())}" data-explanation="${this.escapeHtml(explanation.trim())}"></div>`;
        });

        // Render markdown
        let htmlContent = '';
        if (typeof marked !== 'undefined') {
            try {
                htmlContent = marked.parse(processedText);
            } catch (e) {
                console.error('Markdown parsing error:', e);
                htmlContent = this.escapeHtml(processedText);
            }
        } else {
            htmlContent = this.escapeHtml(processedText);
        }

        msgDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="message-text">${htmlContent}</div>
            </div>
        `;

        container.appendChild(msgDiv);

        // Replace CMD_CARD placeholders with actual cards
        const placeholders = msgDiv.querySelectorAll('.cmd-card-placeholder');
        placeholders.forEach(placeholder => {
            const server = placeholder.dataset.server;
            const command = placeholder.dataset.command;
            const explanation = placeholder.dataset.explanation;
            const cardId = placeholder.id;

            const card = this.renderCommandCard(command, server, explanation, cardId);
            placeholder.replaceWith(card);
        });

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
                    this.createCommandCard(pre, content);
                }
            }
        });

        container.scrollTop = container.scrollHeight;
    },

    /**
     * Render a structured command card with run/skip buttons
     */
    renderCommandCard(command, server, explanation, cardId) {
        const card = document.createElement('div');
        card.className = 'command-card';
        card.id = cardId;

        card.innerHTML = `
            <div class="command-card-header">
                <span class="command-card-server">
                    <i class="fas fa-server"></i> ${this.escapeHtml(server)}
                </span>
                <span class="command-card-status pending">
                    <i class="fas fa-clock"></i> Pending
                </span>
            </div>
            <div class="command-card-body">
                <div class="command-card-explanation">${this.escapeHtml(explanation)}</div>
                <pre class="command-card-code"><code>${this.escapeHtml(command)}</code></pre>
            </div>
            <div class="command-card-actions">
                <button class="btn btn-primary btn-sm run-cmd-btn" onclick="executeCommandWithOutput('${cardId}', '${this.escapeHtml(command).replace(/'/g, "\\'")}')">
                    <i class="fas fa-play"></i> Run
                </button>
                <button class="btn btn-secondary btn-sm" onclick="AIChatBase.copyToClipboard('${this.escapeHtml(command).replace(/'/g, "\\'")}')">
                    <i class="fas fa-copy"></i> Copy
                </button>
                <button class="btn btn-outline btn-sm skip-cmd-btn" onclick="skipCommand('${cardId}', '${this.escapeHtml(command).replace(/'/g, "\\'")}')">
                    <i class="fas fa-forward"></i> Skip
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
     * Create a command card wrapper around a code block
     */
    createCommandCard(pre, command) {
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-with-actions';

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'code-actions';
        actionsDiv.innerHTML = `
            <button class="btn btn-xs btn-primary" onclick="executeCommandWithOutput('auto-${Date.now()}', '${this.escapeHtml(command).replace(/'/g, "\\'")}')">
                <i class="fas fa-play"></i> Run
            </button>
        `;

        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
        wrapper.appendChild(actionsDiv);
    },

    /**
     * Add copy button to a code block
     */
    addCopyButton(pre, block, lang) {
        const btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.innerHTML = '<i class="fas fa-copy"></i>';
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
    showWelcomeScreen() {
        const container = this.getChatContainer();
        if (!container) return;

        container.innerHTML = `
            <div class="welcome-screen">
                <div class="welcome-icon">
                    <i class="fas fa-robot"></i>
                </div>
                <h2>Welcome to AI Assistant</h2>
                <p>How can I help you today?</p>
                <div class="suggestions">
                    <div class="suggestion-chips">
                        <button class="suggestion-chip" onclick="sendSuggestion('What alerts are currently firing?')">
                            <i class="fas fa-bell"></i> What alerts are firing?
                        </button>
                        <button class="suggestion-chip" onclick="sendSuggestion('Show me the system health status')">
                            <i class="fas fa-heartbeat"></i> System health
                        </button>
                        <button class="suggestion-chip" onclick="sendSuggestion('Help me troubleshoot a slow application')">
                            <i class="fas fa-search"></i> Troubleshoot performance
                        </button>
                    </div>
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
