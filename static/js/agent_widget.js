/**
 * AI Helper Agent Widget
 * Handles floating chat interface and context-aware messaging
 */

const AgentWidget = {
    state: {
        isOpen: false,
        isTyping: false,
        messages: []
    },

    elements: {
        fab: null,
        window: null,
        messages: null,
        input: null,
        sendBtn: null,
        closeBtn: null
    },

    init() {
        // Create elements if they don't exist (in case we want to inject via JS)
        // For now, we assume HTML is in layout.html, we just bind
        this.elements.fab = document.getElementById('agent-fab');
        this.elements.window = document.getElementById('agent-chat-window');
        this.elements.messages = document.getElementById('agent-messages');
        this.elements.input = document.getElementById('agent-input');
        this.elements.sendBtn = document.getElementById('agent-send-btn');
        this.elements.closeBtn = document.getElementById('agent-close-btn');

        if (!this.elements.fab) return; // Widget not present

        this.bindEvents();
        this.addWelcomeMessage();
        console.log('[AgentWidget DEBUG] Widget initialized successfully. window.codeMirrorInstances:', window.codeMirrorInstances);
    },

    bindEvents() {
        this.elements.fab.addEventListener('click', () => this.toggleChat());
        this.elements.closeBtn?.addEventListener('click', () => this.toggleChat());

        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());

        this.elements.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea and toggle button
        this.elements.input.addEventListener('input', () => {
            this.elements.input.style.height = 'auto';
            this.elements.input.style.height = (this.elements.input.scrollHeight) + 'px';
            this.updateButtonState();
        });

        // Initial state
        this.updateButtonState();
    },

    updateButtonState() {
        if (!this.elements.input || !this.elements.sendBtn) return;
        const text = this.elements.input.value.trim();
        this.elements.sendBtn.disabled = text.length === 0 || this.state.isTyping;

    },

    toggleChat() {
        this.state.isOpen = !this.state.isOpen;

        if (this.state.isOpen) {
            this.elements.window.classList.add('visible');
            this.elements.fab.style.transform = 'scale(0.8) rotate(45deg)';
            this.elements.input.focus();
            this.scrollToBottom();
        } else {
            this.elements.window.classList.remove('visible');
            this.elements.fab.style.transform = 'scale(1) rotate(0deg)';
        }
    },

    addWelcomeMessage() {
        if (this.state.messages.length === 0) {
            const welcome = "Hi! I'm Antigravity, your AI assistant. I can help you understand this page, debug alerts, or explain the codebase. How can I help?";
            this.appendMessage('agent', welcome);
        }
    },

    async sendMessage() {
        const text = this.elements.input.value.trim();
        if (!text || this.state.isTyping) return;

        // Clear input
        this.elements.input.value = '';
        this.elements.input.style.height = 'auto';

        // User message
        this.appendMessage('user', text);

        // API Call
        this.setTyping(true);

        try {
            const context = this.getPageContext();

            const response = await fetch('/api/agent/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // Add auth token if needed, usually handled by cookie/browser
                },
                body: JSON.stringify({
                    message: text,
                    context: context
                })
            });

            if (!response.ok) {
                throw new Error('Failed to get response');
            }

            const data = await response.json();
            this.appendMessage('agent', data.response, data.citations);

        } catch (error) {
            console.error('Agent Error:', error);
            this.appendMessage('agent', 'Sorry, I encountered an error regarding your request. Please try again.');
        } finally {
            this.setTyping(false);
        }
    },

    appendMessage(role, text, citations = []) {
        this.state.messages.push({ role, text });

        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        let contentHtml = this.formatText(text);

        // Add citations if any
        if (citations && citations.length > 0) {
            const citationsHtml = citations.map(c =>
                `<div class="mt-1 text-xs opacity-75 border-l-2 border-blue-500 pl-2">
                    <i class="fas fa-book-open mr-1"></i> ${c}
                 </div>`
            ).join('');
            contentHtml += `<div class="mt-2 text-xs pt-2 border-t border-gray-700/50">${citationsHtml}</div>`;
        }

        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        msgDiv.innerHTML = `
            <div class="message-bubble">${contentHtml}</div>
            <div class="message-meta">
                ${role === 'agent' ? 'Antigravity' : 'You'} • ${timestamp}
            </div>
        `;

        this.elements.messages.appendChild(msgDiv);
        this.scrollToBottom();
    },

    setTyping(isTyping) {
        this.state.isTyping = isTyping;
        this.elements.sendBtn.disabled = isTyping;

        // Handle visual typing indicator
        let indicator = document.getElementById('agent-typing');
        if (isTyping) {
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.id = 'agent-typing';
                indicator.className = 'typing-indicator message agent';
                indicator.innerHTML = `
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                `;
                this.elements.messages.appendChild(indicator);
            }
            this.scrollToBottom();
        } else {
            if (indicator) indicator.remove();
        }
    },

    getPageContext() {
        // Basic context
        const context = {
            url: window.location.href,
            path: window.location.pathname,
            title: document.title
        };

        // DOM Content extraction (limited to main content to save tokens)
        const mainContent = document.querySelector('main') || document.body;
        // Clean up script and style tags
        const clone = mainContent.cloneNode(true);
        const scripts = clone.querySelectorAll('script, style, noscript');
        scripts.forEach(s => s.remove());

        // NOISE REDUCTION (keep meaningful placeholders)
        // Remove navigation sidebars, tooltips, and other UI chrome
        const noiseSelectors = [
            '.form-sidebar',           // Sidebar navigation
            '.info-tooltip',           // Tooltip popups
            '.info-tooltip-text',      // Tooltip text
            'nav',                      // Navigation elements
            '.typing-indicator',        // Chat typing indicator
            '#agent-chat-window',       // Agent widget itself
            '#agent-fab',               // Agent button
            '.CodeMirror',              // We handle these separately
        ];
        noiseSelectors.forEach(sel => {
            clone.querySelectorAll(sel).forEach(el => el.remove());
        });

        // Inject Values for Inputs/Textareas
        const originalInputs = mainContent.querySelectorAll('input, textarea, select');
        const cloneInputs = clone.querySelectorAll('input, textarea, select');

        for (let i = 0; i < originalInputs.length && i < cloneInputs.length; i++) {
            const original = originalInputs[i];
            const originalValue = original.value;
            const cloned = cloneInputs[i];

            // For text inputs/textareas, add representation (including empty ones)
            if (original.tagName === 'INPUT' || original.tagName === 'TEXTAREA') {
                if (original.type !== 'hidden' && original.type !== 'password') {
                    const label = original.name || original.id || 'field';
                    const displayValue = originalValue.trim() || '(empty)';
                    const textSpan = document.createElement('span');
                    textSpan.innerText = `[${label}: ${displayValue}] `;
                    if (cloned && cloned.parentNode) cloned.parentNode.replaceChild(textSpan, cloned);
                }
            } else if (original.tagName === 'SELECT') {
                const selectedText = original.options[original.selectedIndex]?.text || original.value;
                const label = original.name || original.id || 'select';
                const textSpan = document.createElement('span');
                textSpan.innerText = `[${label}: ${selectedText}] `;
                if (cloned && cloned.parentNode) cloned.parentNode.replaceChild(textSpan, cloned);
            }
        }

        // Remove hidden elements (Tailwind .hidden)
        clone.querySelectorAll('.hidden').forEach(el => el.remove());


        // Handle CodeMirror if present (it's often not in a textarea value until submit)
        // We look for CodeMirror styling in original and try to grab text
        const codeMirrors = mainContent.querySelectorAll('.CodeMirror');
        console.log('[AgentWidget DEBUG] Found CodeMirror elements:', codeMirrors.length);
        console.log('[AgentWidget DEBUG] window.codeMirrorInstances:', window.codeMirrorInstances);

        // Collect CodeMirror content FIRST (will prepend to text)
        let cmText = "";
        if (codeMirrors.length > 0 && window.codeMirrorInstances && Object.keys(window.codeMirrorInstances).length > 0) {
            cmText = "--- CODE EDITORS CONTENT (IMPORTANT) ---\n";
            for (const [key, cm] of Object.entries(window.codeMirrorInstances)) {
                const value = cm.getValue();
                if (value && value.trim()) {
                    console.log(`[AgentWidget DEBUG] Editor ${key}:`, value);
                    cmText += `[${key}]:\n${value}\n\n`;
                }
            }
            cmText += "--- END CODE EDITORS ---\n\n";
        } else {
            console.log('[AgentWidget DEBUG] No codeMirrorInstances found or empty');
        }

        // Get text content
        let text = clone.innerText || "";
        console.log('[AgentWidget DEBUG] Page text length:', text.length);
        console.log('[AgentWidget DEBUG] CodeMirror text length:', cmText.length);

        // PREPEND code editor content so it's never truncated
        text = cmText + text;
        console.log('[AgentWidget DEBUG] Total context length before truncation:', text.length);

        // Truncation limit
        if (text.length > 30000) {
            text = text.substring(0, 30000) + '... (truncated)';
        }

        console.log('[AgentWidget DEBUG] Final context length:', text.length);

        context.page_content = text;

        return context;
    },


    scrollToBottom() {
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    },

    formatText(text) {
        if (!text) return '';

        // Basic Markdown Support
        // Bold
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Italic
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // Code blocks
        text = text.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        // Inline code
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Newlines
        text = text.replace(/\n/g, '<br>');

        return text;
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    AgentWidget.init();
});
