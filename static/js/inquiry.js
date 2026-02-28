
// Inquiry Pillar JS

let currentSessionId = null;
let artifactSequence = 0;

document.addEventListener('DOMContentLoaded', () => {
    createNewSession();
});

function createNewSession() {
    currentSessionId = crypto.randomUUID();
    artifactSequence = 0;
    document.getElementById('sessionIdDisplay').textContent = currentSessionId.substring(0, 8);
    document.getElementById('chatMessages').innerHTML = `
        <div class="text-center inq-empty-hint mt-10">
            <i class="fas fa-robot text-4xl mb-4 inq-empty-icon"></i>
            <p>Ask me anything about your infrastructure, alerts, or logs.</p>
        </div>
    `;
    const panel = document.getElementById('detailsPanel');
    panel.innerHTML = `
        <div id="artifactPlaceholder" class="flex flex-col items-center justify-center h-full inq-empty-hint">
            <i class="fas fa-layer-group text-3xl mb-3 inq-empty-icon"></i>
            <p class="text-sm">Artifacts will appear here as you run queries.</p>
        </div>
    `;
    document.getElementById('artifactCount').textContent = '';
}

function clearChat() {
    createNewSession();
}

async function sendInquiry(event) {
    event.preventDefault();
    const input = document.getElementById('inquiryInput');
    const query = input.value.trim();
    if (!query) return;

    appendMessage('user', query);
    input.value = '';

    const loadingId = appendLoadingMessage();
    const artifactLoadingId = appendArtifactLoading(query);

    try {
        const response = await fetch('/api/v1/inquiry/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, session_id: currentSessionId })
        });

        const data = await response.json();
        removeMessage(loadingId);
        removeArtifactLoading(artifactLoadingId);

        if (response.ok) {
            appendMessage('assistant', data.answer);
            appendArtifact(data, query);
        } else {
            appendMessage('error', `Error: ${data.detail || 'Unknown error'}`);
            removeArtifactLoading(artifactLoadingId);
        }

    } catch (error) {
        removeMessage(loadingId);
        removeArtifactLoading(artifactLoadingId);
        appendMessage('error', `Network Error: ${error.message}`);
    }
}

function appendMessage(role, text) {
    const container = document.getElementById('chatMessages');
    if (container.querySelector('.text-center')) {
        container.innerHTML = '';
    }

    const div = document.createElement('div');
    div.className = `flex flex-col ${role === 'user' ? 'items-end' : 'items-start'}`;

    const bubble = document.createElement('div');
    bubble.className = `max-w-[90%] rounded-lg px-4 py-2 mb-1 ${
        role === 'user'
            ? 'inq-bubble-user'
            : role === 'error'
                ? 'inq-bubble-error'
                : 'inq-bubble-assistant'
        }`;
    bubble.innerHTML = formatMarkdown(text);
    div.appendChild(bubble);

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
        <div class="inq-bubble-assistant rounded-lg px-4 py-2 mb-2">
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

// ─── Artifact Feed ────────────────────────────────────────────────────────────

function appendArtifactLoading(query) {
    const panel = document.getElementById('detailsPanel');
    // Remove placeholder if present
    const placeholder = panel.querySelector('#artifactPlaceholder');
    if (placeholder) placeholder.remove();

    artifactSequence++;
    const id = 'artifact-loading-' + Date.now();
    const el = document.createElement('div');
    el.id = id;
    el.className = 'inq-artifact-card animate-pulse';
    el.innerHTML = `
        <div class="inq-artifact-header">
            <span class="inq-artifact-seq">#${artifactSequence}</span>
            <span class="inq-artifact-query truncate">${escapeHtml(query)}</span>
            <span class="ml-auto"><i class="fas fa-circle-notch fa-spin inq-spinner-color text-xs"></i></span>
        </div>
    `;
    panel.appendChild(el);
    panel.scrollTop = panel.scrollHeight;
    updateArtifactCount();
    return id;
}

function removeArtifactLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
    // Decrement so appendArtifact uses the same seq number
    artifactSequence--;
}

function appendArtifact(data, userQuery) {
    const panel = document.getElementById('detailsPanel');
    if (!data) return;

    // Remove placeholder
    const placeholder = panel.querySelector('#artifactPlaceholder');
    if (placeholder) placeholder.remove();

    artifactSequence++;
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const artifactId = 'artifact-' + Date.now();

    const toolsUsed = data.tools_used || [];
    const toolResults = data.tool_results || [];

    // ── Header ──
    let html = `
    <div id="${artifactId}" class="inq-artifact-card">

        <!-- Artifact header -->
        <div class="inq-artifact-header">
            <span class="inq-artifact-seq">#${artifactSequence}</span>
            <span class="inq-artifact-query flex-1">${escapeHtml(userQuery)}</span>
            <span class="inq-artifact-time">${now}</span>
        </div>
    `;

    // ── Tools Used badges ──
    if (toolsUsed.length > 0) {
        html += `
        <div class="inq-artifact-tools-row">
            ${toolsUsed.map(t => `
                <span class="inq-tool-badge">
                    <i class="fas fa-wrench mr-1"></i>${escapeHtml(t)}
                </span>`).join('')}
        </div>
        `;
    }

    // ── Tool Results (sequential) ──
    if (toolResults.length > 0) {
        html += `<div class="inq-artifact-results">`;
        toolResults.forEach((tr, idx) => {
            const execTime = tr.execution_time_ms
                ? `<span class="inq-exec-time">${tr.execution_time_ms}ms</span>`
                : '';
            const argsStr = (tr.arguments && Object.keys(tr.arguments).length > 0)
                ? `<div class="inq-args-text truncate" title="${escapeHtml(JSON.stringify(tr.arguments))}">↳ ${escapeHtml(JSON.stringify(tr.arguments))}</div>`
                : '';

            let resultHtml = '';
            if (tr.result) {
                const formatted = escapeHtml(tr.result)
                    .replace(/\*\*([^*]+)\*\*/g, '<strong class="inq-bold">$1</strong>')
                    .replace(/\n/g, '<br>');
                resultHtml = `
                    <div class="inq-code-box">
                        <pre class="inq-code-pre">${formatted}</pre>
                    </div>
                `;
            }

            html += `
            <div class="inq-result-row">
                <div class="inq-result-title">
                    <span class="inq-result-idx">${idx + 1}.</span>
                    <span class="inq-tool-name">${escapeHtml(tr.tool_name)}</span>
                    ${execTime}
                </div>
                ${argsStr ? `<div class="inq-args">${argsStr}</div>` : ''}
                ${resultHtml}
            </div>
            `;
        });
        html += `</div>`;
    }

    // ── Answer / Summary ──
    if (data.answer) {
        html += `
        <div class="inq-artifact-answer">
            <div class="inq-answer-label">
                <i class="fas fa-check-circle mr-1"></i>Answer
            </div>
            <div class="inq-answer-text">${formatMarkdown(data.answer)}</div>
        </div>
        `;
    }

    html += `</div>`; // close artifact card

    const el = document.createElement('div');
    el.innerHTML = html;
    panel.appendChild(el.firstElementChild);
    panel.scrollTop = panel.scrollHeight;
    updateArtifactCount();
}

function updateArtifactCount() {
    const cnt = document.getElementById('artifactCount');
    if (cnt && artifactSequence > 0) {
        cnt.textContent = `${artifactSequence} artifact${artifactSequence !== 1 ? 's' : ''}`;
    }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    if (typeof str !== 'string') str = String(str);
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatMarkdown(text) {
    if (!text) return '';
    return escapeHtml(text)
        .replace(/\*\*([^*]+)\*\*/g, '<strong class="inq-bold font-semibold">$1</strong>')
        .replace(/`([^`]+)`/g, '<code class="inq-inline-code">$1</code>')
        .replace(/\n/g, '<br>');
}
