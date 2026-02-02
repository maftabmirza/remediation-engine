# PII False Positive UI - Implementation TODO

## Current Situation

### What Works ✅
- Backend PII detection (Presidio + detect-secrets)
- Database schema for false positive feedback
- API endpoints for submitting feedback
- Whitelist service with caching
- Generic notification: "🔒 PII redacted before sending to AI"

### What's Missing ❌
- **No visual highlighting** of redacted PII in chat messages
- **No "Not PII" button** for users to report false positives
- **No feedback modal** to collect user comments
- **No visual indication** of which specific text was redacted

## User Request

> "I want to report Aftab as not a PII, there is no option. Intention was PII will be highlighted and we can report in UI by mouse pointer."

## Required Implementation

### 1. Modify Backend Response

**File:** `app/routers/troubleshoot_api.py`

The endpoint needs to return which specific text pieces were detected and redacted:

```python
# Current: Only returns redacted message
return {
    "response": ai_response,
    "session_id": session_id,
    "tool_calls": tool_calls,
    "pii_mapping": pii_mapping  # ✅ This exists
}

# Need to add:
return {
    "response": ai_response,
    "session_id": session_id,
    "tool_calls": tool_calls,
    "pii_mapping": pii_mapping,
    "pii_detections": [  # ❌ ADD THIS
        {
            "original_text": "aftab@gmail.com",
            "placeholder": "[EMAIL_ADDRESS_1]",
            "entity_type": "EMAIL_ADDRESS",
            "confidence": 0.95,
            "start": 28,
            "end": 43
        }
    ]
}
```

### 2. Create Frontend UI Component

**File:** `static/js/pii_feedback_ui.js` (NEW FILE)

```javascript
/**
 * PII False Positive Feedback UI
 */

class PIIFeedbackUI {
    constructor() {
        this.detections = [];
    }

    /**
     * Highlight PII detections in a message with clickable badges
     */
    highlightDetections(messageElement, detections, originalText) {
        if (!detections || detections.length === 0) return;

        let html = originalText;
        
        // Sort detections by position (descending) to replace from end to start
        const sorted = [...detections].sort((a, b) => b.start - a.start);
        
        for (const detection of sorted) {
            const original = detection.original_text;
            const placeholder = detection.placeholder;
            const entityType = detection.entity_type;
            
            // Create highlighted span with "Not PII" button
            const highlighted = `
                <span class="pii-highlight" 
                      data-placeholder="${placeholder}"
                      data-original="${original}"
                      data-entity="${entityType}"
                      title="${entityType} (confidence: ${(detection.confidence * 100).toFixed(0)}%)">
                    <span class="pii-text">${original}</span>
                    <button class="pii-report-btn" 
                            onclick="piiFeedbackUI.reportFalsePositive('${original}', '${entityType}', '${placeholder}')">
                        Not PII
                    </button>
                </span>
            `;
            
            html = html.substring(0, detection.start) + 
                   highlighted + 
                   html.substring(detection.end);
        }
        
        messageElement.innerHTML = html;
    }

    /**
     * Show modal to report false positive
     */
    async reportFalsePositive(originalText, entityType, placeholder) {
        const comment = prompt(
            `Report "${originalText}" as not PII?\n\nOptional: Add a comment explaining why this is not sensitive data:`,
            ''
        );
        
        if (comment === null) return; // User cancelled
        
        try {
            const response = await fetch('/api/v1/pii/feedback/false-positive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    detected_text: originalText,
                    detected_entity_type: entityType,
                    user_comment: comment,
                    whitelist_scope: 'organization'
                })
            });
            
            if (!response.ok) throw new Error('Failed to submit feedback');
            
            const result = await response.json();
            
            // Show success message
            this.showToast(
                `✅ Reported as false positive. "${originalText}" will not be detected in future sessions.`,
                'success'
            );
            
            // Remove highlight from this detection
            this.removeHighlight(placeholder);
            
        } catch (error) {
            console.error('Failed to submit PII feedback:', error);
            this.showToast('❌ Failed to submit feedback. Please try again.', 'error');
        }
    }

    /**
     * Remove highlight after successful feedback
     */
    removeHighlight(placeholder) {
        const element = document.querySelector(`[data-placeholder="${placeholder}"]`);
        if (element) {
            const text = element.querySelector('.pii-text').textContent;
            element.replaceWith(document.createTextNode(text));
        }
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `pii-toast pii-toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }
}

// Global instance
const piiFeedbackUI = new PIIFeedbackUI();
```

### 3. Add CSS Styles

**File:** `static/css/troubleshoot.css` or `static/css/main.css`

```css
/* PII Highlighting */
.pii-highlight {
    position: relative;
    display: inline-block;
    background: rgba(255, 193, 7, 0.2);
    border-bottom: 2px solid #ffc107;
    padding: 2px 4px;
    border-radius: 3px;
    cursor: help;
}

.pii-highlight:hover {
    background: rgba(255, 193, 7, 0.3);
}

.pii-text {
    font-weight: 500;
    color: #ffc107;
}

.pii-report-btn {
    display: none;
    position: absolute;
    top: -25px;
    right: 0;
    background: #dc3545;
    color: white;
    border: none;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    cursor: pointer;
    white-space: nowrap;
    z-index: 10;
}

.pii-highlight:hover .pii-report-btn {
    display: block;
}

.pii-report-btn:hover {
    background: #c82333;
}

/* Toast notifications */
.pii-toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #333;
    color: white;
    padding: 12px 20px;
    border-radius: 5px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    opacity: 0;
    transform: translateY(20px);
    transition: all 0.3s ease;
    z-index: 1000;
    max-width: 400px;
}

.pii-toast.show {
    opacity: 1;
    transform: translateY(0);
}

.pii-toast-success {
    background: #28a745;
}

.pii-toast-error {
    background: #dc3545;
}
```

### 4. Integrate into Chat Interface

**File:** `static/js/troubleshoot_chat.js`

Modify the message handling to include PII detection info:

```javascript
// After receiving message from backend
async function sendMessage(message) {
    // ... existing code ...
    
    const response = await fetch('/api/troubleshoot/chat', {
        method: 'POST',
        body: JSON.stringify({
            message: message,
            session_id: currentSessionId
        })
    });
    
    const data = await response.json();
    
    // NEW: If PII was detected, highlight it in the user message
    if (data.pii_detections && data.pii_detections.length > 0) {
        const userMsgElement = document.querySelector('.user-message:last-child');
        if (userMsgElement) {
            piiFeedbackUI.highlightDetections(
                userMsgElement, 
                data.pii_detections, 
                message  // Original user input
            );
        }
    }
    
    // ... rest of existing code ...
}
```

### 5. Include Script in HTML

**File:** `templates/ai.html` or relevant template

```html
<!-- Add before closing </body> tag -->
<script src="/static/js/pii_feedback_ui.js"></script>
```

## Implementation Steps

1. ✅ Update backend to include `pii_detections` array in response
2. ✅ Create `pii_feedback_ui.js` with highlighting and feedback logic
3. ✅ Add CSS styles for highlighting and buttons
4. ✅ Integrate into `troubleshoot_chat.js`
5. ✅ Test with various PII types (email, phone, SSN, etc.)
6. ✅ Add admin review dashboard for feedback queue

## Testing Checklist

- [ ] Email detection: `test@example.com` should show "Not PII" button
- [ ] Person name detection: `John Smith` should show "Not PII" button
- [ ] Click "Not PII" → Submit feedback successfully
- [ ] Same text in next message → Should NOT be detected again
- [ ] Toast notification appears on success/failure
- [ ] Highlight removed after successful feedback
- [ ] Multiple detections in same message all highlighted
- [ ] Works across all chat interfaces (troubleshoot, alert, revive)

## Expected User Experience

### Before Implementation (Current)
```
User: Hello, I am Aftab and email is aftab@gmail.com
[Generic notification: 🔒 PII redacted before sending to AI]
AI: Hello Aftab! ...
```
No way to report false positives.

### After Implementation
```
User: Hello, I am Aftab and email is aftab@gmail.com
       [Message shows with aftab@gmail.com highlighted in yellow]
       [Hover over highlight → "Not PII" button appears]
       [Click "Not PII" → Modal asks for optional comment]
       [Submit → Toast: "✅ Reported as false positive"]
AI: Hello Aftab! ...
```

In next session, `aftab@gmail.com` will NOT be detected/highlighted.

## Priority

**HIGH** - This is a core usability feature for the PII detection system. Without it, users cannot correct false positives, leading to frustration when legitimate business data is unnecessarily redacted.
