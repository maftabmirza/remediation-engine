/**
 * PII False Positive Feedback UI
 * 
 * Provides interactive highlighting of detected PII with ability to report false positives.
 */

class PIIFeedbackUI {
    constructor() {
        this.detections = [];
        this.sessionId = null;
        this.handleReportClick = this.handleReportClick.bind(this);
        document.addEventListener('click', this.handleReportClick);
        this.modal = null;
    }

    /**
     * Highlight PII detections in a message with clickable badges
     * @param {HTMLElement} messageElement - The message element to highlight
     * @param {Array} detections - Array of detection objects
     * @param {string} originalText - Original message text before redaction
     */
    highlightDetections(messageElement, detections, originalText) {
        if (!detections || detections.length === 0) return;
        
        console.log('🔍 PII UI: Highlighting', detections.length, 'detections');

        // Store detections for this message
        this.detections = detections;
        
        // Get the text content element (might be nested in divs)
        let textElement = messageElement;
        const contentDiv = messageElement.querySelector('.message-content');
        if (contentDiv) {
            textElement = contentDiv;
        }
        
        let html = originalText;
        
        // Sort detections by position (descending) to replace from end to start
        // This prevents position shifting when inserting HTML
        const sorted = [...detections].sort((a, b) => b.start - a.start);
        
        for (const detection of sorted) {
            const original = detection.original_text;
            const placeholder = detection.placeholder;
            const entityType = detection.entity_type;
            const detectionEngine = detection.detection_engine || detection.engine || 'presidio';
            const confidence = Math.round((detection.confidence || 0) * 100);
            
            // Create highlighted span with detailed hover dialog
            const highlighted = `<span class="pii-highlight" 
                      data-placeholder="${encodeURIComponent(placeholder)}"
                      data-original="${encodeURIComponent(original)}"
                      data-entity="${encodeURIComponent(entityType)}"
                      data-confidence="${confidence}"
                      data-engine="${encodeURIComponent(detectionEngine)}">
                    <span class="pii-text">${this.escapeHtml(original)}</span>
                    <div class="pii-hover-dialog">
                        <div class="pii-dialog-header">
                            <span class="pii-entity-badge">${this.escapeHtml(entityType)}</span>
                            <span class="pii-confidence-badge">${confidence}% confidence</span>
                        </div>
                        <button class="pii-report-btn" 
                                data-original="${encodeURIComponent(original)}"
                                data-entity="${encodeURIComponent(entityType)}"
                            data-placeholder="${encodeURIComponent(placeholder)}"
                            data-engine="${encodeURIComponent(detectionEngine)}"
                            data-confidence="${detection.confidence || 0}">
                            <svg class="w-3 h-3 inline-block mr-1" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                            </svg>
                            Report as Not PII
                        </button>
                    </div>
                </span>`;
            
            // Replace the original text with highlighted version
            const before = html.substring(0, detection.start);
            const after = html.substring(detection.end);
            html = before + highlighted + after;
        }
        
        textElement.innerHTML = html;
        console.log('✅ PII UI: Highlighted', sorted.length, 'items in message');
    }

    /**
     * Show modal/prompt to report false positive
     */
    async reportFalsePositive(originalText, entityType, placeholder, detectionEngine = 'presidio', originalConfidence = null) {
        console.log('🔍 PII UI: Reporting false positive:', originalText, entityType, detectionEngine);

        const comment = await this.showReportModal(originalText);
        if (comment === null) {
            console.log('🔍 PII UI: User cancelled report');
            return;
        }
        
        try {
            const response = await fetch('/api/v1/pii/feedback/false-positive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    detected_text: originalText,
                    detected_entity_type: entityType,
                    detection_engine: detectionEngine,
                    user_comment: comment || undefined,
                    whitelist_scope: 'organization',
                    session_id: this.sessionId || undefined,
                    agent_mode: 'troubleshoot',
                    original_confidence: typeof originalConfidence === 'number' ? originalConfidence : undefined
                })
            });
            
            if (!response.ok) {
                let errorMessage = 'Failed to submit feedback';
                try {
                    const error = await response.json();
                    if (typeof error.detail === 'string') {
                        errorMessage = error.detail;
                    } else if (Array.isArray(error.detail)) {
                        errorMessage = error.detail.map(item => item.msg || JSON.stringify(item)).join('; ');
                    } else if (error.detail) {
                        errorMessage = JSON.stringify(error.detail);
                    } else if (error.message) {
                        errorMessage = error.message;
                    }
                } catch (_) {
                    // Fallback to default message
                }
                throw new Error(errorMessage);
            }
            
            const result = await response.json();
            console.log('✅ PII UI: Feedback submitted:', result);
            
            // Show success message
            this.showToast(
                `✅ Reported as false positive. "${originalText}" will not be detected in future sessions.`,
                'success'
            );
            
            // Remove highlight from this detection
            this.removeHighlight(placeholder);
            
        } catch (error) {
            console.error('❌ PII UI: Failed to submit feedback:', error);
            this.showToast(
                `❌ Failed to submit feedback: ${error.message}`,
                'error'
            );
        }
    }

    /**
     * Show themed modal for false positive reporting.
     * Returns comment string or null if cancelled.
     */
    showReportModal(originalText) {
        return new Promise((resolve) => {
            if (!this.modal) {
                this.modal = document.createElement('div');
                this.modal.className = 'pii-modal-backdrop hidden';
                this.modal.innerHTML = `
                    <div class="pii-modal">
                        <div class="pii-modal-header">
                            <span class="pii-modal-title">Report as Not PII</span>
                            <button class="pii-modal-close" aria-label="Close">×</button>
                        </div>
                        <div class="pii-modal-body">
                            <div class="pii-modal-text"></div>
                            <label class="pii-modal-label">Optional: Why is this not PII?</label>
                            <textarea class="pii-modal-input" rows="3" placeholder="Add a short reason (optional)"></textarea>
                        </div>
                        <div class="pii-modal-actions">
                            <button class="pii-modal-cancel">Cancel</button>
                            <button class="pii-modal-confirm">Report</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(this.modal);
            }

            const textEl = this.modal.querySelector('.pii-modal-text');
            const inputEl = this.modal.querySelector('.pii-modal-input');
            const closeBtn = this.modal.querySelector('.pii-modal-close');
            const cancelBtn = this.modal.querySelector('.pii-modal-cancel');
            const confirmBtn = this.modal.querySelector('.pii-modal-confirm');

            textEl.textContent = `Report "${originalText}" as NOT sensitive data? This will whitelist it for your organization.`;
            inputEl.value = '';

            const cleanup = (result) => {
                this.modal.classList.add('hidden');
                closeBtn.removeEventListener('click', onCancel);
                cancelBtn.removeEventListener('click', onCancel);
                confirmBtn.removeEventListener('click', onConfirm);
                this.modal.removeEventListener('click', onBackdrop);
                resolve(result);
            };

            const onCancel = () => cleanup(null);
            const onConfirm = () => cleanup(inputEl.value.trim());
            const onBackdrop = (e) => {
                if (e.target === this.modal) onCancel();
            };

            closeBtn.addEventListener('click', onCancel);
            cancelBtn.addEventListener('click', onCancel);
            confirmBtn.addEventListener('click', onConfirm);
            this.modal.addEventListener('click', onBackdrop);

            this.modal.classList.remove('hidden');
            inputEl.focus();
        });
    }

    /**
     * Remove highlight after successful feedback
     */
    removeHighlight(placeholder) {
        const encodedPlaceholder = encodeURIComponent(placeholder);
        const elements = document.querySelectorAll(`[data-placeholder="${encodedPlaceholder}"]`);
        elements.forEach(element => {
            const textElement = element.querySelector('.pii-text');
            const text = textElement ? textElement.textContent : element.textContent;
            element.replaceWith(document.createTextNode(text));
        });
        console.log('🔍 PII UI: Removed highlight for', placeholder);
    }

    /**
     * Handle report button clicks (avoids inline handlers)
     */
    handleReportClick(event) {
        const button = event.target.closest('.pii-report-btn');
        if (!button) return;
        event.preventDefault();

        const original = decodeURIComponent(button.getAttribute('data-original') || '');
        const entityType = decodeURIComponent(button.getAttribute('data-entity') || '');
        const placeholder = decodeURIComponent(button.getAttribute('data-placeholder') || '');
        const detectionEngine = decodeURIComponent(button.getAttribute('data-engine') || 'presidio');
        const confidenceValue = parseFloat(button.getAttribute('data-confidence'));

        if (!original || !entityType || !placeholder) {
            console.warn('🔍 PII UI: Missing report button data attributes');
            return;
        }

        this.reportFalsePositive(original, entityType, placeholder, detectionEngine, Number.isFinite(confidenceValue) ? confidenceValue : null);
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // Remove existing toasts
        const existingToasts = document.querySelectorAll('.pii-toast');
        existingToasts.forEach(toast => toast.remove());
        
        const toast = document.createElement('div');
        toast.className = `pii-toast pii-toast-${type}`;
        toast.innerHTML = `
            <div class="pii-toast-content">
                ${this.escapeHtml(message)}
            </div>
        `;
        document.body.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
        
        console.log('🔍 PII UI: Toast shown:', type, message);
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Set current session ID for feedback context
     */
    setSessionId(sessionId) {
        this.sessionId = sessionId;
        console.log('🔍 PII UI: Session ID set:', sessionId);
    }
}

// Global instance
window.piiFeedbackUI = new PIIFeedbackUI();

console.log('✅ PII Feedback UI initialized');
