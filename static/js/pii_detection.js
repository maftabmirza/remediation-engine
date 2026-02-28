/**
 * PII Detection Configuration UI
 */

let currentConfig = null;
let entities = [];
let plugins = [];
let whitelistItems = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadConfiguration();
    loadEntities();
    loadPlugins();
    loadWhitelist();
});

/**
 * Switch between tabs
 */
function switchTab(tabName, button) {
    // Update buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeButton = button || document.querySelector(`.tab-button[data-tab="${tabName}"]`);
    if (activeButton) {
        activeButton.classList.add('active');
    }
    
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
 * Build auth headers (if token is available)
 */
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
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
        updateExceptionEntityOptions();
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
    
    // Presidio built-in PII entity types
    // Secrets (passwords, API keys, tokens) are detected by detect-secrets library
    const defaultEntities = [
        { name: 'EMAIL_ADDRESS', description: 'Email addresses', built_in: true, threshold: 0.7, enabled: true, redaction: 'mask' },
        { name: 'PHONE_NUMBER', description: 'Phone numbers', built_in: true, threshold: 0.6, enabled: true, redaction: 'mask' },
        { name: 'US_SSN', description: 'US Social Security Numbers', built_in: true, threshold: 0.8, enabled: true, redaction: 'hash' },
        { name: 'CREDIT_CARD', description: 'Credit card numbers', built_in: true, threshold: 0.8, enabled: true, redaction: 'mask' },
        { name: 'PERSON', description: 'Person names', built_in: true, threshold: 0.5, enabled: false, redaction: 'tag' },
        { name: 'IP_ADDRESS', description: 'IP addresses', built_in: true, threshold: 0.7, enabled: true, redaction: 'mask' },
        { name: 'US_PASSPORT', description: 'US passport numbers', built_in: true, threshold: 0.8, enabled: true, redaction: 'mask' },
        { name: 'US_DRIVER_LICENSE', description: 'US driver license numbers', built_in: true, threshold: 0.8, enabled: true, redaction: 'mask' },
        { name: 'IBAN_CODE', description: 'IBAN bank codes', built_in: true, threshold: 0.8, enabled: true, redaction: 'mask' }
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
        updateExceptionEntityOptions();
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
    
    // detect-secrets plugins - optimized for low false positives
    // High entropy detectors are DISABLED by default
    const defaultPlugins = [
        { name: 'KeywordDetector', description: 'Detects secrets by context (password=, secret=, api_key=, token=)', enabled: true },
        { name: 'AWSKeyDetector', description: 'AWS access keys and secret keys', enabled: true },
        { name: 'GitHubTokenDetector', description: 'GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)', enabled: true },
        { name: 'GitLabTokenDetector', description: 'GitLab tokens (glpat-)', enabled: true },
        { name: 'OpenAIDetector', description: 'OpenAI API keys (sk-)', enabled: true },
        { name: 'JwtTokenDetector', description: 'JSON Web Tokens (JWT)', enabled: true },
        { name: 'PrivateKeyDetector', description: 'RSA/SSH/EC private keys', enabled: true },
        { name: 'SlackDetector', description: 'Slack tokens (xoxb-, xoxp-)', enabled: true },
        { name: 'StripeDetector', description: 'Stripe API keys (sk_live_, sk_test_)', enabled: true },
        { name: 'BasicAuthDetector', description: 'Basic auth in URLs (user:pass@host)', enabled: true },
        { name: 'AzureStorageKeyDetector', description: 'Azure storage account keys', enabled: true },
        { name: 'TwilioKeyDetector', description: 'Twilio API keys', enabled: true },
        { name: 'SendGridDetector', description: 'SendGrid API keys', enabled: true },
        { name: 'DiscordBotTokenDetector', description: 'Discord bot tokens', enabled: true },
        { name: 'TelegramBotTokenDetector', description: 'Telegram bot tokens', enabled: true },
        { name: 'Base64HighEntropyString', description: 'High entropy base64 (⚠️ causes false positives)', enabled: false },
        { name: 'HexHighEntropyString', description: 'High entropy hex (⚠️ causes false positives)', enabled: false }
    ];
    
    // Merge with current config if available
    const configPlugins = currentConfig?.detect_secrets?.plugins || [];
    const mergedPlugins = defaultPlugins.map(plugin => {
        const configPlugin = configPlugins.find(p => p.plugin_name === plugin.name);
        return configPlugin ? { ...plugin, ...configPlugin } : plugin;
    });
    
    mergedPlugins.forEach(plugin => {
        const isWarning = plugin.name.includes('HighEntropy');
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <strong>${plugin.name}</strong>
            </td>
            <td>
                <input type="checkbox" ${plugin.enabled ? 'checked' : ''} 
                    onchange="updatePluginEnabled('${plugin.name}', this.checked)">
            </td>
            <td style="color: ${isWarning ? '#FFD54F' : 'var(--text-secondary)'}; font-size: 13px;">
                ${plugin.description}
            </td>
            <td>
                <span style="color: ${plugin.enabled ? '#4CAF50' : '#9E9E9E'}; font-size: 12px;">
                    ${plugin.enabled ? '● Active' : '○ Disabled'}
                </span>
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
    setTimeout(() => runTest(), 100);
}

/**
 * Load whitelist entries
 */
async function loadWhitelist() {
    try {
        const showInactive = document.getElementById('showInactiveWhitelist');
        const activeOnly = showInactive ? !showInactive.checked : true;
        const response = await fetch(`/api/v1/pii/feedback/whitelist?active_only=${activeOnly}`, {
            headers: {
                ...getAuthHeaders()
            },
            credentials: 'same-origin'
        });
        if (!response.ok) throw new Error('Failed to load whitelist');
        const data = await response.json();
        whitelistItems = data.items || [];
        renderWhitelistTable();
    } catch (error) {
        showAlert('Error loading exceptions: ' + error.message, 'error');
    }
}

/**
 * Render whitelist table
 */
function renderWhitelistTable() {
    const tbody = document.getElementById('whitelistTable');
    tbody.innerHTML = '';

    if (!whitelistItems.length) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td colspan="5" style="color: var(--text-secondary);">
                No exceptions added yet.
            </td>
        `;
        tbody.appendChild(row);
        return;
    }

    whitelistItems.forEach(item => {
        const row = document.createElement('tr');
        const addedAt = item.added_at ? new Date(item.added_at).toLocaleString() : 'N/A';
        const statusLabel = item.active ? 'Active' : 'Inactive';
        const statusColor = item.active ? 'var(--accent-green)' : 'var(--text-secondary)';
        const reporter = item.reported_by || 'N/A';
        const sessionId = item.session_id || 'N/A';
        row.innerHTML = `
            <td>${item.text}</td>
            <td>${item.entity_type}</td>
            <td>${item.scope}</td>
            <td>${addedAt}</td>
            <td>${reporter}</td>
            <td>${sessionId}</td>
            <td style="color: ${statusColor}; font-weight: 600;">${statusLabel}</td>
            <td>
                <button class="btn-secondary" onclick="deleteWhitelistEntry('${item.id}')">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * Add a whitelist entry
 */
async function addWhitelistEntry() {
    const detectedText = document.getElementById('exceptionText').value.trim();
    const entityType = document.getElementById('exceptionEntityType').value.trim();
    const detectionEngine = document.getElementById('exceptionEngine').value;
    const userComment = document.getElementById('exceptionComment').value.trim();

    if (!detectedText) {
        showAlert('Please enter the detected text to whitelist', 'error');
        return;
    }
    if (!entityType) {
        showAlert('Please enter the entity type', 'error');
        return;
    }

    try {
        const response = await fetch('/api/v1/pii/feedback/false-positive', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                detected_text: detectedText,
                detected_entity_type: entityType,
                detection_engine: detectionEngine,
                user_comment: userComment || null
            })
        });

        if (!response.ok) throw new Error('Failed to add exception');

        document.getElementById('exceptionText').value = '';
        document.getElementById('exceptionEntityType').value = '';
        document.getElementById('exceptionComment').value = '';

        showAlert('Exception added successfully.', 'success');
        await loadWhitelist();
    } catch (error) {
        showAlert('Error adding exception: ' + error.message, 'error');
    }
}

/**
 * Delete whitelist entry
 */
async function deleteWhitelistEntry(entryId) {
    if (!confirm('Delete this exception?')) return;

    try {
        const response = await fetch(`/api/v1/pii/feedback/${entryId}`, {
            method: 'DELETE',
            headers: {
                ...getAuthHeaders()
            },
            credentials: 'same-origin'
        });
        if (!response.ok) throw new Error('Failed to delete exception');

        showAlert('Exception deleted successfully.', 'success');
        await loadWhitelist();
    } catch (error) {
        showAlert('Error deleting exception: ' + error.message, 'error');
    }
}

/**
 * Update exception entity options
 */
function updateExceptionEntityOptions() {
    const datalist = document.getElementById('exceptionEntityList');
    if (!datalist) return;

    const options = new Set();
    (entities || []).forEach(entity => {
        if (entity && entity.name) options.add(entity.name);
    });
    (plugins || []).forEach(plugin => {
        if (plugin && plugin.name) options.add(plugin.name);
    });
    options.add('SECRET');
    options.add('UNKNOWN');

    datalist.innerHTML = '';
    Array.from(options).sort().forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        datalist.appendChild(option);
    });
}

/**
 * Get test text for entity
 */
function getTestText(entityName) {
    const testTexts = {
        'EMAIL_ADDRESS': 'Contact support@example.com for help',
        'PHONE_NUMBER': 'Call us at (555) 123-4567',
        'US_SSN': 'SSN: 123-45-6789',
        'CREDIT_CARD': 'Card: 4532-1234-5678-9010',
        'PERSON': 'John Doe submitted the report',
        'IP_ADDRESS': 'Server at 8.8.8.8',
        'US_PASSPORT': 'Passport: 123456789',
        'US_DRIVER_LICENSE': 'License: A1234567',
        'IBAN_CODE': 'IBAN: DE89370400440532013000'
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
        detectionsDiv.innerHTML = result.detections.map(detection => {
            const confidenceRaw = (detection.confidence ?? detection.confidence_score);
            const confidencePct = (typeof confidenceRaw === 'number' && Number.isFinite(confidenceRaw))
                ? `${(confidenceRaw * 100).toFixed(1)}%`
                : 'N/A';

            const start = (typeof detection.start === 'number') ? detection.start : detection.position_start;
            const end = (typeof detection.end === 'number') ? detection.end : detection.position_end;
            const position = (typeof start === 'number' && typeof end === 'number')
                ? `${start}-${end}`
                : 'N/A';

            const engine = detection.engine || 'unknown';
            const entityType = detection.entity_type || detection.entity || 'UNKNOWN';

            return `
                <div class="detection-item ${engine}">
                    <strong>${entityType}</strong> (${engine})
                    <br>
                    <small>Confidence: ${confidencePct}</small>
                    <br>
                    <small>Position: ${position}</small>
                </div>
            `;
        }).join('');
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
