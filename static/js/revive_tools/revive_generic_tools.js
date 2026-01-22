/**
 * Generic client-side tools
 * Available on all pages
 */

(function () {
    'use strict';

    const DEBUG = true;

    function log(...args) {
        if (DEBUG) {
            console.log('%c[GenericTools]', 'color: #607D8B; font-weight: bold', ...args);
        }
    }

    function error(...args) {
        console.error('%c[GenericTools]', 'color: #F44336; font-weight: bold', ...args);
    }

    /**
     * Detect page type from URL
     */
    function detectPageType() {
        const path = window.location.pathname;

        if (path.includes('/runbooks')) return 'runbooks';
        if (path.includes('/alerts')) return 'alerts';
        if (path.includes('/panels')) return 'panels';
        if (path.includes('/knowledge')) return 'knowledge';
        if (path.includes('/dashboards')) return 'dashboards';
        if (path.includes('/grafana')) return 'grafana';
        if (path.includes('/prometheus')) return 'prometheus';

        return 'unknown';
    }

    /**
     * Detect available actions on page
     */
    function detectAvailableActions() {
        const actions = [];

        // Check for common action buttons/links using valid CSS selectors
        // Note: :contains() is not valid CSS, it's jQuery-specific
        if (document.querySelector('[onclick*="execute"]') ||
            Array.from(document.querySelectorAll('button')).some(btn => btn.textContent.toLowerCase().includes('execute'))) {
            actions.push('execute_runbook');
        }
        if (document.querySelector('form[method="post"]')) {
            actions.push('submit_form');
        }
        if (document.querySelector('.edit-button, [href*="edit"]') ||
            Array.from(document.querySelectorAll('button')).some(btn => btn.textContent.toLowerCase().includes('edit'))) {
            actions.push('edit');
        }
        if (document.querySelector('.delete-button, [data-action="delete"]')) {
            actions.push('delete');
        }
        if (document.querySelector('[href*="create"]') ||
            Array.from(document.querySelectorAll('button')).some(btn => btn.textContent.toLowerCase().includes('create'))) {
            actions.push('create');
        }

        log('Available actions:', actions);
        return actions;
    }

    /**
     * Get visible buttons and their labels
     */
    function getVisibleButtons() {
        const buttons = document.querySelectorAll('button:not(.hidden):not([style*="display: none"])');
        const buttonLabels = Array.from(buttons)
            .map(btn => btn.innerText.trim())
            .filter(text => text.length > 0);

        log('Visible buttons:', buttonLabels);
        return buttonLabels;
    }

    /**
     * Main tool: Get basic page context
     */
    async function getPageContext(args = {}) {
        log('getPageContext called');

        const context = {
            url: window.location.href,
            pathname: window.location.pathname,
            search: window.location.search,
            hash: window.location.hash,
            title: document.title,
            page_type: detectPageType(),
            has_forms: document.querySelectorAll('form').length > 0,
            has_tables: document.querySelectorAll('table').length > 0,
            has_modals: document.querySelectorAll('.modal, .fixed').length > 0,
            visible_buttons: getVisibleButtons(),
            available_actions: detectAvailableActions(),
            page_summary: document.body.innerText.substring(0, 500),
            extracted_at: new Date().toISOString()
        };

        log('Page context:', context);

        return {
            type: 'page_context',
            data: context,
            summary: `Page: ${context.title} (${context.page_type})`
        };
    }

    /**
     * Tool: Read page forms
     */
    async function readPageForms(args = {}) {
        log('readPageForms called');

        const forms = [];
        const formElements = document.querySelectorAll('form');

        formElements.forEach((form, idx) => {
            const formData = {
                order: idx + 1,
                action: form.action,
                method: form.method,
                fields: []
            };

            // Extract form fields
            const inputs = form.querySelectorAll('input:not([type="hidden"]), textarea, select');
            inputs.forEach(input => {
                const field = {
                    name: input.name || input.id,
                    type: input.type || input.tagName.toLowerCase(),
                    value: input.value,
                    label: null,
                    required: input.required
                };

                // Try to find label
                const label = input.labels?.[0] ||
                    form.querySelector(`label[for="${input.id}"]`);
                if (label) {
                    field.label = label.innerText.trim();
                }

                if (field.name) {
                    formData.fields.push(field);
                }
            });

            forms.push(formData);
        });

        log(`Found ${forms.length} forms with ${forms.reduce((sum, f) => sum + f.fields.length, 0)} fields`);

        return {
            type: 'page_forms',
            data: {
                forms,
                count: forms.length
            },
            summary: `Found ${forms.length} forms on page`
        };
    }

    /**
     * Tool: Extract all visible text
     */
    async function extractPageText(args = {}) {
        log('extractPageText called');

        const maxLength = args.max_length || 5000;

        // Get main content areas, excluding navigation/footer
        const mainContent = document.querySelector('main, .main-content, #content, article');
        const textSource = mainContent || document.body;

        let text = textSource.innerText;

        if (text.length > maxLength) {
            text = text.substring(0, maxLength) + '... (truncated)';
        }

        log(`Extracted ${text.length} characters of page text`);

        return {
            type: 'page_text',
            data: {
                text,
                length: text.length,
                truncated: text.includes('(truncated)')
            },
            summary: `Extracted ${text.length} characters of text`
        };
    }

    /**
     * Tool: Take page screenshot (metadata only, actual screenshot via backend)
     */
    async function getPageScreenshot(args = {}) {
        log('getPageScreenshot called');

        // Return page dimensions and viewport info
        const viewport = {
            width: window.innerWidth,
            height: window.innerHeight,
            scroll_y: window.scrollY,
            scroll_x: window.scrollX,
            device_pixel_ratio: window.devicePixelRatio
        };

        const document_size = {
            width: document.documentElement.scrollWidth,
            height: document.documentElement.scrollHeight
        };

        return {
            type: 'page_screenshot_info',
            data: {
                viewport,
                document_size,
                url: window.location.href,
                note: 'Actual screenshot capture requires server-side tool'
            },
            summary: `Page dimensions: ${viewport.width}x${viewport.height}`
        };
    }

    // Register tools
    if (window.reviveToolRegistry) {
        window.reviveToolRegistry.register('get_page_context', {
            description: 'Get basic information about the current page including URL, title, type, and available actions',
            category: 'generic',
            pageTypes: null, // Available on all pages
            parameters: [],
            handler: getPageContext
        });

        window.reviveToolRegistry.register('read_page_forms', {
            description: 'Extract all forms and their fields from the current page',
            category: 'generic',
            pageTypes: null,
            parameters: [],
            handler: readPageForms
        });

        window.reviveToolRegistry.register('extract_page_text', {
            description: 'Extract all visible text content from the page',
            category: 'generic',
            pageTypes: null,
            parameters: [
                {
                    name: 'max_length',
                    type: 'integer',
                    description: 'Maximum length of text to extract (default: 5000)',
                    required: false
                }
            ],
            handler: extractPageText
        });

        window.reviveToolRegistry.register('get_page_screenshot_info', {
            description: 'Get page dimensions and viewport information for screenshot capture',
            category: 'generic',
            pageTypes: null,
            parameters: [],
            handler: getPageScreenshot
        });

        log('Registered 4 generic tools');
    } else {
        error('Tool registry not found!');
    }
})();
