/**
 * Alert-specific client-side tools
 * Extract alert details from DOM on alert pages
 */

(function () {
    'use strict';

    const DEBUG = true;

    function log(...args) {
        if (DEBUG) {
            console.log('%c[AlertTools]', 'color: #FF5722; font-weight: bold', ...args);
        }
    }

    function error(...args) {
        console.error('%c[AlertTools]', 'color: #F44336; font-weight: bold', ...args);
    }

    /**
     * Extract alert ID from URL
     */
    function extractAlertId() {
        const match = window.location.pathname.match(/\/alerts\/([a-f0-9-]+)/);
        const id = match ? match[1] : null;
        log('Extracted alert ID:', id);
        return id;
    }

    /**
     * Extract alert labels from DOM
     */
    function extractLabels() {
        const labels = {};

        // Look for label containers
        const labelElements = document.querySelectorAll('.label, [data-label], .badge');

        labelElements.forEach(el => {
            const text = el.innerText || el.textContent;
            // Try to parse "key=value" or "key: value" format
            const match = text.match(/(\w+)\s*[:=]\s*(.+)/);
            if (match) {
                labels[match[1]] = match[2];
            }
        });

        log('Extracted labels:', labels);
        return labels;
    }

    /**
     * Extract alert annotations
     */
    function extractAnnotations() {
        const annotations = {};

        // Look for annotation sections
        const annotationSection = document.querySelector('.annotations, [data-annotations]');
        if (annotationSection) {
            const items = annotationSection.querySelectorAll('dt, dd');
            for (let i = 0; i < items.length; i += 2) {
                if (items[i] && items[i + 1]) {
                    const key = items[i].innerText.trim();
                    const value = items[i + 1].innerText.trim();
                    annotations[key] = value;
                }
            }
        }

        log('Extracted annotations:', annotations);
        return annotations;
    }

    /**
     * Main tool: Read alert page
     */
    async function readAlertPage(args = {}) {
        log('readAlertPage called with args:', args);

        const alertId = extractAlertId();

        const alertData = {
            alert_id: alertId,
            alert_name: null,
            severity: null,
            status: null,
            description: null,
            started_at: null,
            labels: extractLabels(),
            annotations: extractAnnotations(),
            url: window.location.href
        };

        // Extract alert name
        const nameSelectors = ['h1', '.alert-name', '.alert-title'];
        for (const selector of nameSelectors) {
            const el = document.querySelector(selector);
            if (el) {
                alertData.alert_name = el.innerText.trim();
                if (alertData.alert_name) break;
            }
        }

        // Extract severity
        const severityBadges = document.querySelectorAll('.severity, .badge-critical, .badge-warning, .badge-info');
        if (severityBadges.length > 0) {
            alertData.severity = severityBadges[0].innerText.trim().toLowerCase();
        }

        // Extract status
        const statusBadges = document.querySelectorAll('.status, .alert-status');
        if (statusBadges.length > 0) {
            alertData.status = statusBadges[0].innerText.trim().toLowerCase();
        }

        // Extract description
        const descSelectors = ['.description', '.alert-description', 'p.text-secondary'];
        for (const selector of descSelectors) {
            const el = document.querySelector(selector);
            if (el) {
                alertData.description = el.innerText.trim();
                if (alertData.description && alertData.description.length > 10) break;
            }
        }

        // Extract timestamp
        const timeElements = document.querySelectorAll('time, .timestamp, [data-timestamp]');
        if (timeElements.length > 0) {
            alertData.started_at = timeElements[0].getAttribute('datetime') || timeElements[0].innerText;
        }

        log('Alert extraction complete:', alertData);

        return {
            type: 'alert',
            data: alertData,
            summary: `Alert: ${alertData.alert_name || 'Unnamed'} (${alertData.severity || 'unknown severity'})`
        };
    }

    /**
     * Tool: Get alert timeline
     */
    async function getAlertTimeline(args = {}) {
        log('getAlertTimeline called');

        const events = [];

        // Look for timeline or history section
        const timelineItems = document.querySelectorAll('.timeline-item, .history-item, .event-item');

        timelineItems.forEach((item, idx) => {
            const event = {
                order: idx + 1,
                timestamp: null,
                event_type: null,
                description: null
            };

            const timeEl = item.querySelector('time, .timestamp');
            if (timeEl) {
                event.timestamp = timeEl.getAttribute('datetime') || timeEl.innerText;
            }

            const typeEl = item.querySelector('.event-type, .badge');
            if (typeEl) {
                event.event_type = typeEl.innerText.trim();
            }

            const descEl = item.querySelector('.event-description, p');
            if (descEl) {
                event.description = descEl.innerText.trim();
            }

            events.push(event);
        });

        log(`Found ${events.length} timeline events`);

        return {
            type: 'alert_timeline',
            data: {
                events,
                count: events.length
            },
            summary: `Found ${events.length} events in alert timeline`
        };
    }

    // Register tools
    if (window.reviveToolRegistry) {
        window.reviveToolRegistry.register('read_alert_page', {
            description: 'Extract alert details from the current alert page, including severity, status, labels, and annotations',
            category: 'alert',
            pageTypes: ['alerts'],
            parameters: [],
            handler: readAlertPage
        });

        window.reviveToolRegistry.register('get_alert_timeline', {
            description: 'Extract alert event timeline showing state changes and actions taken',
            category: 'alert',
            pageTypes: ['alerts'],
            parameters: [],
            handler: getAlertTimeline
        });

        log('Registered 2 alert tools');
    } else {
        error('Tool registry not found!');
    }
})();
