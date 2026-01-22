
// Inquiry Pillar JS

let currentSessionId = null;

document.addEventListener('DOMContentLoaded', () => {
    createNewSession();
    // Focus, etc
});

function createNewSession() {
    currentSessionId = crypto.randomUUID();
    document.getElementById('sessionIdDisplay').textContent = currentSessionId.substring(0, 8);
    document.getElementById('chatMessages').innerHTML = `
        <div class="text-center text-gray-500 mt-10">
            <i class="fas fa-robot text-4xl mb-4 text-gray-700"></i>
            <p>Ask me anything about your infrastructure, alerts, or logs.</p>
        </div>
    `;
    document.getElementById('detailsPanel').innerHTML = `
        <div class="flex flex-col items-center justify-center h-full text-gray-500">
            <p>Select a message or run a query to see details here.</p>
        </div>
    `;
}

function clearChat() {
    createNewSession();
}

async function sendInquiry(event) {
    event.preventDefault();
    const input = document.getElementById('inquiryInput');
    const query = input.value.trim();
    if (!query) return;

    // Append User Message
    appendMessage('user', query);
    input.value = '';

    // Show Loading
    const loadingId = appendLoadingMessage();

    try {
        const response = await fetch('/api/v1/inquiry/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId
            })
        });

        const data = await response.json();
        removeMessage(loadingId);

        if (response.ok) {
            appendMessage('assistant', data.answer, data);
            showDetails(data);
        } else {
            appendMessage('error', `Error: ${data.detail || 'Unknown error'}`);
        }

    } catch (error) {
        removeMessage(loadingId);
        appendMessage('error', `Network Error: ${error.message}`);
    }
}

function appendMessage(role, text, data = null) {
    const container = document.getElementById('chatMessages');
    // Remove welcome message if exists
    if (container.querySelector('.text-center')) {
        container.innerHTML = '';
    }

    const div = document.createElement('div');
    div.className = `flex flex-col ${role === 'user' ? 'items-end' : 'items-start'}`;

    const bubble = document.createElement('div');
    bubble.className = `max-w-[90%] rounded-lg px-4 py-2 mb-1 ${role === 'user'
            ? 'bg-blue-600 text-white'
            : role === 'error'
                ? 'bg-red-900/50 text-red-200 border border-red-700'
                : 'bg-gray-700 text-gray-200 border border-gray-600'
        }`;

    // Markdown/HTML formatting (simple)
    bubble.innerHTML = text.replace(/\n/g, '<br>');

    div.appendChild(bubble);

    if (data) {
        const toolsUsed = data.tools_used || [];
        if (toolsUsed.length > 0) {
            const status = document.createElement('div');
            status.className = 'text-[10px] text-gray-500 mb-2 px-1';
            status.textContent = `Used tools: ${toolsUsed.join(', ')}`;
            div.appendChild(status);
        }

        // Add click handler to show details again
        bubble.classList.add('cursor-pointer', 'hover:opacity-90');
        bubble.onclick = () => showDetails(data);
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    return div.id = 'msg-' + Date.now();
}

function appendLoadingMessage() {
    const container = document.getElementById('chatMessages');
    const id = 'loading-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'flex flex-col items-start';
    div.innerHTML = `
        <div class="bg-gray-700/50 text-gray-400 rounded-lg px-4 py-2 mb-2 border border-gray-700">
            <i class="fas fa-circle-notch fa-spin mr-2"></i> Thinking...
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function showDetails(data) {
    const panel = document.getElementById('detailsPanel');
    if (!data) return;

    let html = `<div class="space-y-4">`;

    // Summary
    html += `
        <div class="bg-gray-800 p-3 rounded border border-gray-700">
            <h4 class="text-xs font-semibold text-gray-400 uppercase mb-2">Result Summary</h4>
            <div class="text-sm text-gray-300">${data.answer.replace(/\n/g, '<br>')}</div>
        </div>
    `;

    // Tools Used
    if (data.tools_used && data.tools_used.length > 0) {
        html += `
            <div class="bg-gray-800 p-3 rounded border border-gray-700">
               <h4 class="text-xs font-semibold text-gray-400 uppercase mb-2">Tools Executed</h4>
               <ul class="list-disc list-inside text-sm text-blue-300">
                  ${data.tools_used.map(t => `<li>${t}</li>`).join('')}
               </ul>
            </div>
        `;
    }

    // Raw Tools Execution (if available in future, mocked here)
    // We expect the server response might carry more detailed logs later

    html += `</div>`;
    panel.innerHTML = html;
}
