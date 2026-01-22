/**
 * Runbook-specific client-side tools
 * Extract runbook details from DOM on runbook pages
 */

(function () {
    'use strict';

    const DEBUG = true;

    function log(...args) {
        if (DEBUG) {
            console.log('%c[RunbookTools]', 'color: #9C27B0; font-weight: bold', ...args);
        }
    }

    function error(...args) {
        console.error('%c[RunbookTools]', 'color: #F44336; font-weight: bold', ...args);
    }

    /**
     * Extract runbook ID from URL
     */
    function extractRunbookId() {
        const match = window.location.pathname.match(/\/runbooks\/([a-f0-9-]+)/);
        const id = match ? match[1] : null;
        log('Extracted runbook ID:', id);
        return id;
    }

    /**
     * Detect if we're on edit or view page
     */
    function detectRunbookMode() {
        const path = window.location.pathname;
        if (path.includes('/edit')) return 'edit';
        if (path.includes('/view')) return 'view';
        return 'list';
    }

    /**
     * Extract runbook metadata (name, description, etc.)
     */
    function extractRunbookMetadata() {
        const metadata = {
            name: null,
            description: null,
            category: null,
            status: null,
            auto_execute: null,
            approval_required: null,
            tags: []
        };

        // Try to find runbook name
        const nameSelectors = [
            'h1',
            '.runbook-name',
            'input[name="name"]',
            '#runbook_name'
        ];

        for (const selector of nameSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                metadata.name = element.innerText || element.value;
                if (metadata.name) {
                    log('Found runbook name:', metadata.name);
                    break;
                }
            }
        }

        // Try to find description
        const descSelectors = [
            '.runbook-description',
            'textarea[name="description"]',
            'p.text-secondary'
        ];

        for (const selector of descSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                metadata.description = element.innerText || element.value;
                if (metadata.description && metadata.description.length > 10) {
                    log('Found description:', metadata.description.substring(0, 50) + '...');
                    break;
                }
            }
        }

        // Extract tags
        const tagElements = document.querySelectorAll('.px-2.py-1.rounded.text-xs.bg-gray-800');
        metadata.tags = Array.from(tagElements).map(el => el.innerText.trim());
        if (metadata.tags.length > 0) {
            log('Found tags:', metadata.tags);
        }

        // Extract status badges
        const statusBadge = document.querySelector('.bg-green-900, .bg-gray-700');
        if (statusBadge) {
            metadata.status = statusBadge.innerText.toLowerCase();
            log('Found status:', metadata.status);
        }

        return metadata;
    }

    /**
     * Extract runbook steps from DOM
     * Works for both edit mode (.step-card) and view mode (.border-gray-700)
     */
    function extractRunbookSteps() {
        log('Extracting runbook steps...');
        const steps = [];

        // Strategy 1: Edit mode - .step-card elements
        const editModeCards = document.querySelectorAll('.step-card');
        if (editModeCards.length > 0) {
            log(`Found ${editModeCards.length} steps in EDIT mode`);

            editModeCards.forEach((card, idx) => {
                const step = {
                    order: idx + 1,
                    name: null,
                    description: null,
                    command_linux: null,
                    command_windows: null,
                    target_os: null,
                    timeout: null
                };

                // Extract step name
                const nameInput = card.querySelector('.step-name, input[name*="name"]');
                if (nameInput) {
                    step.name = nameInput.value || nameInput.innerText;
                }

                // Extract description
                const descTextarea = card.querySelector('textarea[placeholder*="description"]');
                if (descTextarea) {
                    step.description = descTextarea.value;
                }

                // Extract command from CodeMirror
                const codeMirror = card.querySelector('.CodeMirror');
                if (codeMirror && codeMirror.CodeMirror) {
                    step.command_linux = codeMirror.CodeMirror.getValue();
                } else {
                    // Fallback to textarea
                    const cmdTextarea = card.querySelector('textarea[name*="command"]');
                    if (cmdTextarea) {
                        step.command_linux = cmdTextarea.value;
                    }
                }

                // Extract OS type
                const osSelect = card.querySelector('select[name*="os"]');
                if (osSelect) {
                    step.target_os = osSelect.value;
                }

                steps.push(step);
                log(`Step ${step.order}:`, step.name || 'Unnamed', `(${step.command_linux ? step.command_linux.substring(0, 30) + '...' : 'no command'})`);
            });

            return steps;
        }

        // Strategy 2: View mode - .border-gray-700 container elements
        const viewModeContainers = document.querySelectorAll('.border.border-gray-700.rounded-lg.p-4.bg-gray-800');
        if (viewModeContainers.length > 0) {
            log(`Found ${viewModeContainers.length} steps in VIEW mode`);

            viewModeContainers.forEach((container, idx) => {
                const step = {
                    order: idx + 1,
                    name: null,
                    description: null,
                    command_linux: null,
                    command_windows: null,
                    target_os: null
                };

                // Extract step name (h4 tag)
                const nameElement = container.querySelector('h4');
                if (nameElement) {
                    step.name = nameElement.innerText.trim();
                }

                // Extract description
                const descElement = container.querySelector('p.text-sm.text-secondary');
                if (descElement) {
                    step.description = descElement.innerText.trim();
                }

                // Extract Linux command
                const linuxCmd = container.querySelector('pre code');
                if (linuxCmd) {
                    step.command_linux = linuxCmd.innerText.trim();
                }

                // Extract OS badge
                const osBadge = container.querySelector('.px-2.py-1.rounded.text-xs.bg-gray-700');
                if (osBadge) {
                    step.target_os = osBadge.innerText.toLowerCase();
                }

                steps.push(step);
                log(`Step ${step.order}:`, step.name || 'Unnamed');
            });

            return steps;
        }

        log('No steps found on page');
        return steps;
    }

    /**
     * Main tool: Read current runbook page
     */
    async function readRunbookPage(args = {}) {
        log('readRunbookPage called with args:', args);

        const mode = detectRunbookMode();
        const runbookId = extractRunbookId();

        if (!runbookId) {
            throw new Error('Not on a specific runbook page (no ID found in URL)');
        }

        const metadata = extractRunbookMetadata();
        const steps = extractRunbookSteps();

        const result = {
            runbook_id: runbookId,
            mode: mode,
            metadata: metadata,
            steps: steps,
            step_count: steps.length,
            url: window.location.href,
            extracted_at: new Date().toISOString()
        };

        log('Extraction complete:', result);

        return {
            type: 'runbook',
            data: result,
            summary: `Found runbook "${metadata.name || 'Unnamed'}" with ${steps.length} steps`
        };
    }

    /**
     * Tool: Get specific runbook step
     */
    async function getRunbookStep(args = {}) {
        log('getRunbookStep called with args:', args);

        const stepNumber = args.step_number || args.step || 1;
        const steps = extractRunbookSteps();

        if (stepNumber < 1 || stepNumber > steps.length) {
            throw new Error(`Invalid step number ${stepNumber}. Runbook has ${steps.length} steps.`);
        }

        const step = steps[stepNumber - 1];
        log(`Returning step ${stepNumber}:`, step);

        return {
            type: 'runbook_step',
            data: step,
            summary: `Step ${stepNumber}: ${step.name || 'Unnamed'}`
        };
    }

    /**
     * Tool: Search steps by keyword
     */
    async function searchRunbookSteps(args = {}) {
        log('searchRunbookSteps called with args:', args);

        const keyword = args.keyword || args.query;
        if (!keyword) {
            throw new Error('keyword parameter is required');
        }

        const steps = extractRunbookSteps();
        const matches = steps.filter(step => {
            const searchText = [
                step.name,
                step.description,
                step.command_linux,
                step.command_windows
            ].join(' ').toLowerCase();

            return searchText.includes(keyword.toLowerCase());
        });

        log(`Found ${matches.length} steps matching "${keyword}"`);

        return {
            type: 'runbook_step_search',
            data: {
                keyword,
                matches,
                match_count: matches.length,
                total_steps: steps.length
            },
            summary: `Found ${matches.length} steps containing "${keyword}"`
        };
    }

    // Register tools
    if (window.reviveToolRegistry) {
        window.reviveToolRegistry.register('read_runbook_page', {
            description: 'Extract complete runbook details from the current page, including all steps, metadata, and configuration',
            category: 'runbook',
            pageTypes: ['runbooks'],
            parameters: [],
            handler: readRunbookPage
        });

        window.reviveToolRegistry.register('get_runbook_step', {
            description: 'Get details of a specific runbook step by step number',
            category: 'runbook',
            pageTypes: ['runbooks'],
            parameters: [
                {
                    name: 'step_number',
                    type: 'integer',
                    description: 'The step number to retrieve (1-based index)',
                    required: true
                }
            ],
            handler: getRunbookStep
        });

        window.reviveToolRegistry.register('search_runbook_steps', {
            description: 'Search runbook steps by keyword in name, description, or commands',
            category: 'runbook',
            pageTypes: ['runbooks'],
            parameters: [
                {
                    name: 'keyword',
                    type: 'string',
                    description: 'Keyword to search for in steps',
                    required: true
                }
            ],
            handler: searchRunbookSteps
        });

        log('Registered 3 runbook tools');
    } else {
        error('Tool registry not found! Make sure registry.js is loaded first.');
    }
})();
