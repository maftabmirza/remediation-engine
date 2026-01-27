/**
 * PII Detection Configuration UI
 */

let currentConfig = null;
let entities = [];
let plugins = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadConfiguration();
    loadEntities();
    loadPlugins();
});

/**
 * Switch between tabs
 */
function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

/**
 * Load current configuration
 */
async function loadConfiguration() {
    try {
        const response = await fetch('/api/v1/pii/config');
        if (!response.ok) throw new Error('Failed to load configuration');
        
        currentConfig = await response.json();
        applyConfigToUI(currentConfig);
    } catch (error) {
        showAlert('Error loading configuration: ' + error.message, 'error');
    }
}

/**
 * Apply configuration to UI
 */
function applyConfigToUI(config) {
    if (config.global_settings) {
        document.getElementById('enablePresidio').checked = config.presidio?.enabled ?? true;
        document.getElementById('enableSecrets').checked = config.detect_secrets?.enabled ?? true;
        document.getElementById('autoRedact').checked = config.global_settings.auto_redact ?? true;
        document.getElementById('logDetections').checked = config.global_settings.log_detections ?? true;
        document.getElementById('defaultRedaction').value = config.global_settings.default_redaction_type ?? 'mask';
    }
}

/**
 * Load available entities
 */
async function loadEntities() {
    try {
        const response = await fetch('/api/v1/pii/entities');
        if (!response.ok) throw new Error('Failed to load entities');
        
        const data = await response.json();
        entities = data.presidio_entities || [];
        renderEntitiesTable();
    } catch (error) {
        showAlert('Error loading entities: ' + error.message, 'error');
    }
}

/**
 * Render entities table
 */
function renderEntitiesTable() {
    const tbody = document.getElementById('presidioEntitiesTable');
    tbody.innerHTML = '';
    
    const defaultEntities = [
        { name: 'EMAIL', description: 'Email addresses', built_in: true, threshold: 0.7, enabled: true, redaction: 'mask' },
        { name: 'PHONE_NUMBER', description: 'Phone numbers', built_in: true, threshold: 0.6, enabled: true, redaction: 'mask' },
        { name: 'US_SSN', description: 'Social Security Numbers', built_in: true, threshold: 0.8, enabled: true, redaction: 'hash' },
        { name: 'CREDIT_CARD', description: 'Credit card numbers', built_in: true, threshold: 0.8, enabled: true, redaction: 'mask' },
        { name: 'PERSON', description: 'Person names', built_in: true, threshold: 0.5, enabled: false, redaction: 'tag' },
        { name: 'HIGH_ENTROPY', description: 'High entropy strings', built_in: false, threshold: 0.7, enabled: true, redaction: 'mask' },
        { name: 'INTERNAL_HOSTNAME', description: 'Internal hostnames', built_in: false, threshold: 0.7, enabled: true, redaction: 'mask' },
        { name: 'PRIVATE_IP', description: 'Private IP addresses', built_in: false, threshold: 0.7, enabled: true, redaction: 'mask' }
    ];
    
    // Merge with current config if available
    const configEntities = currentConfig?.presidio?.entities || [];
    const mergedEntities = defaultEntities.map(entity => {
        const configEntity = configEntities.find(e => e.entity_type === entity.name);
        return configEntity ? { ...entity, ...configEntity } : entity;
    });
    
    mergedEntities.forEach(entity => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                ${entity.name}
                ${!entity.built_in ? '<span class="custom-badge">CUSTOM</span>' : ''}
            </td>
            <td>
                <input type="checkbox" ${entity.enabled ? 'checked' : ''} 
                    onchange="updateEntityEnabled('${entity.name}', this.checked)">
            </td>
            <td>
                <input type="range" class="slider" min="0" max="1" step="0.05" 
                    value="${entity.threshold}" 
                    onchange="updateEntityThreshold('${entity.name}', this.value)">
                <span class="threshold-display" id="threshold-${entity.name}">${entity.threshold}</span>
            </td>
            <td>
                <select onchange="updateEntityRedaction('${entity.name}', this.value)">
                    <option value="mask" ${entity.redaction === 'mask' ? 'selected' : ''}>Mask</option>
                    <option value="hash" ${entity.redaction === 'hash' ? 'selected' : ''}>Hash</option>
                    <option value="remove" ${entity.redaction === 'remove' ? 'selected' : ''}>Remove</option>
                    <option value="tag" ${entity.redaction === 'tag' ? 'selected' : ''}>Tag</option>
                </select>
            </td>
            <td>
                <button class="btn-secondary" onclick="testEntity('${entity.name}')">Test</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * Load available plugins
 */
async function loadPlugins() {
    try {
        const response = await fetch('/api/v1/pii/plugins');
        if (!response.ok) throw new Error('Failed to load plugins');
        
        const data = await response.json();
        plugins = data.detect_secrets_plugins || [];
        renderPluginsTable();
    } catch (error) {
        showAlert('Error loading plugins: ' + error.message, 'error');
    }
}

/**
 * Render plugins table
 */
function renderPluginsTable() {
    const tbody = document.getElementById('pluginsTable');
    tbody.innerHTML = '';
    
    const defaultPlugins = [
        { name: 'HighEntropyString', description: 'Detects high entropy strings', configurable: true, settings: 'Base64: 4.5, Hex: 3.0', enabled: true },
        { name: 'KeywordDetector', description: 'Detects keywords like password', configurable: true, settings: 'Keywords: password, secret', enabled: true },
        { name: 'AWSKeyDetector', description: 'Detects AWS access keys', configurable: false, settings: '-', enabled: true },
        { name: 'GitHubTokenDetector', description: 'Detects GitHub tokens', configurable: false, settings: '-', enabled: true },
        { name: 'PrivateKeyDetector', description: 'Detects private keys', configurable: false, settings: '-', enabled: true },
        { name: 'JwtTokenDetector', description: 'Detects JWT tokens', configurable: false, settings: '-', enabled: true },
        { name: 'SlackDetector', description: 'Detects Slack tokens', configurable: false, settings: '-', enabled: true },
        { name: 'StripeDetector', description: 'Detects Stripe API keys', configurable: false, settings: '-', enabled: true }
    ];
    
    // Merge with current config if available
    const configPlugins = currentConfig?.detect_secrets?.plugins || [];
    const mergedPlugins = defaultPlugins.map(plugin => {
        const configPlugin = configPlugins.find(p => p.plugin_name === plugin.name);
        return configPlugin ? { ...plugin, ...configPlugin } : plugin;
    });
    
    mergedPlugins.forEach(plugin => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${plugin.name}</td>
            <td>
                <input type="checkbox" ${plugin.enabled ? 'checked' : ''} 
                    onchange="updatePluginEnabled('${plugin.name}', this.checked)">
            </td>
            <td>${plugin.settings}</td>
            <td>
                ${plugin.configurable ? 
                    `<button class="btn-secondary" onclick="configurePlugin('${plugin.name}')">Configure</button>` : 
                    '-'
                }
            </td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * Update entity enabled state
 */
function updateEntityEnabled(entityName, enabled) {
    if (!currentConfig.presidio) currentConfig.presidio = { entities: [] };
    if (!currentConfig.presidio.entities) currentConfig.presidio.entities = [];
    
    const entity = currentConfig.presidio.entities.find(e => e.entity_type === entityName);
    if (entity) {
        entity.enabled = enabled;
    } else {
        currentConfig.presidio.entities.push({ entity_type: entityName, enabled });
    }
}

/**
 * Update entity threshold
 */
function updateEntityThreshold(entityName, threshold) {
    document.getElementById(`threshold-${entityName}`).textContent = threshold;
    
    if (!currentConfig.presidio) currentConfig.presidio = { entities: [] };
    if (!currentConfig.presidio.entities) currentConfig.presidio.entities = [];
    
    const entity = currentConfig.presidio.entities.find(e => e.entity_type === entityName);
    if (entity) {
        entity.threshold = parseFloat(threshold);
    } else {
        currentConfig.presidio.entities.push({ entity_type: entityName, threshold: parseFloat(threshold) });
    }
}

/**
 * Update entity redaction type
 */
function updateEntityRedaction(entityName, redaction) {
    if (!currentConfig.presidio) currentConfig.presidio = { entities: [] };
    if (!currentConfig.presidio.entities) currentConfig.presidio.entities = [];
    
    const entity = currentConfig.presidio.entities.find(e => e.entity_type === entityName);
    if (entity) {
        entity.redaction_type = redaction;
    } else {
        currentConfig.presidio.entities.push({ entity_type: entityName, redaction_type: redaction });
    }
}

/**
 * Update plugin enabled state
 */
function updatePluginEnabled(pluginName, enabled) {
    if (!currentConfig.detect_secrets) currentConfig.detect_secrets = { plugins: [] };
    if (!currentConfig.detect_secrets.plugins) currentConfig.detect_secrets.plugins = [];
    
    const plugin = currentConfig.detect_secrets.plugins.find(p => p.plugin_name === pluginName);
    if (plugin) {
        plugin.enabled = enabled;
    } else {
        currentConfig.detect_secrets.plugins.push({ plugin_name: pluginName, enabled });
    }
}

/**
 * Test specific entity
 */
function testEntity(entityName) {
    document.getElementById('testInput').value = getTestText(entityName);
    switchTab('test');
    document.querySelectorAll('.tab-button')[2].click();
    setTimeout(() => runTest(), 100);
}

/**
 * Get test text for entity
 */
function getTestText(entityName) {
    const testTexts = {
        'EMAIL': 'Contact support@example.com for help',
        'PHONE_NUMBER': 'Call us at 555-123-4567',
        'US_SSN': 'SSN: 123-45-6789',
        'CREDIT_CARD': 'Card: 4532-1234-5678-9010',
        'PERSON': 'John Doe submitted the report',
        'HIGH_ENTROPY': 'Token: aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Q=',
        'INTERNAL_HOSTNAME': 'Connect to server.internal.local',
        'PRIVATE_IP': 'Database at 192.168.1.100'
    };
    return testTexts[entityName] || 'Enter test text here';
}

/**
 * Configure plugin
 */
function configurePlugin(pluginName) {
    alert(`Configuration dialog for ${pluginName} would open here`);
}

/**
 * Run test detection
 */
async function runTest() {
    const testInput = document.getElementById('testInput').value;
    if (!testInput.trim()) {
        showAlert('Please enter text to test', 'error');
        return;
    }
    
    const loading = document.getElementById('testLoading');
    loading.style.display = 'inline-block';
    
    try {
        const response = await fetch('/api/v1/pii/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: testInput,
                engines: ['presidio', 'detect_secrets']
            })
        });
        
        if (!response.ok) throw new Error('Test failed');
        
        const result = await response.json();
        displayTestResults(result);
    } catch (error) {
        showAlert('Error running test: ' + error.message, 'error');
    } finally {
        loading.style.display = 'none';
    }
}

/**
 * Display test results
 */
function displayTestResults(result) {
    const resultsDiv = document.getElementById('testResults');
    const detectionsDiv = document.getElementById('detectionsResults');
    const previewDiv = document.getElementById('redactedPreview');
    
    resultsDiv.style.display = 'block';
    
    // Display detections
    if (result.detections && result.detections.length > 0) {
        detectionsDiv.innerHTML = result.detections.map(detection => `
            <div class="detection-item ${detection.engine}">
                <strong>${detection.entity_type}</strong> (${detection.engine})
                <br>
                <small>Confidence: ${(detection.confidence_score * 100).toFixed(1)}%</small>
                <br>
                <small>Position: ${detection.position_start}-${detection.position_end}</small>
            </div>
        `).join('');
    } else {
        detectionsDiv.innerHTML = '<p>No detections found</p>';
    }
    
    // Display redacted preview
    previewDiv.textContent = result.redacted_preview || 'No redactions';
}

/**
 * Save configuration
 */
async function saveConfiguration() {
    try {
        // Collect global settings
        const config = {
            presidio: {
                enabled: document.getElementById('enablePresidio').checked,
                entities: currentConfig.presidio?.entities || []
            },
            detect_secrets: {
                enabled: document.getElementById('enableSecrets').checked,
                plugins: currentConfig.detect_secrets?.plugins || []
            },
            global_settings: {
                auto_redact: document.getElementById('autoRedact').checked,
                log_detections: document.getElementById('logDetections').checked,
                default_redaction_type: document.getElementById('defaultRedaction').value
            }
        };
        
        const response = await fetch('/api/v1/pii/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) throw new Error('Failed to save configuration');
        
        const result = await response.json();
        currentConfig = result;
        showAlert('Configuration saved successfully!', 'success');
    } catch (error) {
        showAlert('Error saving configuration: ' + error.message, 'error');
    }
}

/**
 * Show alert message
 */
function showAlert(message, type) {
    const alertDiv = document.getElementById('alertMessage');
    alertDiv.innerHTML = `
        <div class="alert alert-${type}">
            ${message}
        </div>
    `;
    
    setTimeout(() => {
        alertDiv.innerHTML = '';
    }, 5000);
}
