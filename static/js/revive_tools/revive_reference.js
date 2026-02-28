/**
 * CLIENT-SIDE TOOLS QUICK REFERENCE
 * 
 * Open browser console (F12) and try these commands:
 */

// ====================
// BASIC USAGE
// ====================

// 1. Check if registry is loaded
console.log(window.reviveToolRegistry);

// 2. See all available tools
const pageType = window.reviveToolRegistry.detectPageType();
const tools = window.reviveToolRegistry.getAvailableTools(pageType);
console.log('Available Tools:', tools.map(t => t.name));

// 3. Execute a tool
const result = await window.reviveToolRegistry.execute('get_page_context');
console.log(result);

// ====================
// RUNBOOK PAGE TOOLS
// ====================

// Read entire runbook
const runbook = await window.reviveToolRegistry.execute('read_runbook_page');
console.log(runbook);
// Returns: {runbook_id, mode, metadata: {name, description, tags}, steps: [...]}

// Get specific step
const step1 = await window.reviveToolRegistry.execute('get_runbook_step', {
    step_number: 1
});
console.log(step1);
// Returns: {order, name, description, command_linux, target_os, ...}

// Search steps
const searchResults = await window.reviveToolRegistry.execute('search_runbook_steps', {
    keyword: 'apache'
});
console.log(searchResults);
// Returns: {keyword, matches: [...], match_count, total_steps}

// ====================
// ALERT PAGE TOOLS
// ====================

// Read alert details
const alert = await window.reviveToolRegistry.execute('read_alert_page');
console.log(alert);
// Returns: {alert_id, alert_name, severity, status, labels, annotations}

// Get alert timeline
const timeline = await window.reviveToolRegistry.execute('get_alert_timeline');
console.log(timeline);
// Returns: {events: [...], count}

// ====================
// PROMETHEUS/GRAFANA TOOLS
// ====================

// Extract PromQL query
const query = await window.reviveToolRegistry.execute('extract_promql_query');
console.log(query);
// Returns: {query, data_source, query_language, extraction_method}

// Get dashboard panels
const panels = await window.reviveToolRegistry.execute('get_dashboard_panels');
console.log(panels);
// Returns: {panels: [...], count}

// ====================
// GENERIC TOOLS (All Pages)
// ====================

// Get page context
const context = await window.reviveToolRegistry.execute('get_page_context');
console.log(context);
// Returns: {url, title, page_type, visible_buttons, available_actions, ...}

// Read all forms
const forms = await window.reviveToolRegistry.execute('read_page_forms');
console.log(forms);
// Returns: {forms: [{action, method, fields: [...]}], count}

// Extract page text
const text = await window.reviveToolRegistry.execute('extract_page_text', {
    max_length: 1000
});
console.log(text);
// Returns: {text, length, truncated}

// ====================
// DEBUGGING
// ====================

// Enable verbose logging
window.reviveToolRegistry.debug = true;

// Test a tool and see detailed logs
const testResult = await window.reviveToolRegistry.execute('read_runbook_page');

// Check pending requests
console.log(window.reviveToolRegistry.pendingRequests);

// Get all registered tools
console.log(window.reviveToolRegistry.tools);

// ====================
// ERROR HANDLING
// ====================

try {
    const result = await window.reviveToolRegistry.execute('some_tool');
    if (result.success) {
        console.log('Success:', result.result);
    } else {
        console.error('Error:', result.error);
        console.error('Stack:', result.error_stack);
    }
} catch (err) {
    console.error('Execution failed:', err);
}

// ====================
// PERFORMANCE TESTING
// ====================

// Time a tool execution
console.time('Tool Execution');
const data = await window.reviveToolRegistry.execute('read_runbook_page');
console.timeEnd('Tool Execution');
console.log('Duration:', data.duration_ms, 'ms');

// Batch testing
async function testAllTools() {
    const pageType = window.reviveToolRegistry.detectPageType();
    const tools = window.reviveToolRegistry.getAvailableTools(pageType);

    for (const tool of tools) {
        console.group(`Testing: ${tool.name}`);
        try {
            const result = await window.reviveToolRegistry.execute(tool.name);
            console.log('✓ Success:', result);
        } catch (err) {
            console.error('✗ Failed:', err);
        }
        console.groupEnd();
    }
}

// Run batch test
await testAllTools();

// ====================
// EXPECTED CONSOLE OUTPUT
// ====================

/*
When page loads, you should see:

[RE-VIVE] Client Tool Registry initialized
[ClientToolRegistry] Registry initialized
[GenericTools] Registered 4 generic tools
[RunbookTools] Registered 3 runbook tools (on runbook pages)
[AlertTools] Registered 2 alert tools (on alert pages)
[PrometheusTools] Registered 2 Prometheus/Grafana tools (on those pages)

When tool executes:

[ClientToolRegistry] Executing tool: read_runbook_page {}
[RunbookTools] readRunbookPage called with args: {}
[RunbookTools] Extracted runbook ID: 9b650e1a-b0a0-4e01-9d39-074fc3e27cd7
[RunbookTools] Extracting runbook steps...
[RunbookTools] Found 5 steps in EDIT mode
[RunbookTools] Step 1: Install Apache (sudo apt-get install apache2...)
[RunbookTools] Extraction complete: {runbook_id: '...', ...}
[ClientToolRegistry] Tool "read_runbook_page" completed in 15ms
*/
