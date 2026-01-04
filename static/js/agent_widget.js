
document.addEventListener('DOMContentLoaded', () => {
    // Inject Widget HTML if not present
    if (!document.getElementById('agent-widget')) {
        const widgetHTML = `
            <div id="agent-widget">
                <div id="agent-window">
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

    async function sendMessage() {
        const text = input.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        input.value = '';
        showTyping();

        try {
            const payload = {
                query: text,
                page_context: {
                    url: window.location.href,
                    title: document.title
                }
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

            if (data.warning) {
                aiText = `> [!WARNING]\n> ${data.warning}\n\n` + aiText;
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
});
