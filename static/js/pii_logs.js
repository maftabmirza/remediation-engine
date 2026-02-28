/**
 * PII Detection Logs Viewer
 * Loads one page at a time for better UI/UX performance
 */

let currentPage = 1;
let pageSize = 25;  // Smaller default for faster initial load
let totalPages = 1;
let totalLogs = 0;
let currentFilters = {};
let searchMode = false;  // When true, pagination uses search endpoint
let currentSearchQuery = '';  // Stored search query for pagination
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Set default date range (last 7 days) BEFORE first load to scope the query
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 7);
    
    document.getElementById('endDate').valueAsDate = endDate;
    document.getElementById('startDate').valueAsDate = startDate;
    
    // Apply default date filter so we don't load all records
    currentFilters.start_date = startDate.toISOString().split('T')[0];
    currentFilters.end_date = endDate.toISOString().split('T')[0];
    
    loadLogs();
    loadStatistics();
    
    // Initialize page size selector if present
    const pageSizeSelect = document.getElementById('pageSizeSelect');
    if (pageSizeSelect) {
        pageSizeSelect.value = pageSize;
        pageSizeSelect.addEventListener('change', (e) => {
            pageSize = parseInt(e.target.value, 10);
            currentPage = 1;
            loadLogs();
        });
    }
});

/**
 * Load logs with current filters and pagination.
 * Uses search endpoint when in search mode, otherwise regular logs endpoint.
 */
async function loadLogs() {
    const tbody = document.getElementById('logsTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center"><div class="loading-spinner mx-auto mb-2"></div><p class="text-slate-500">Loading logs...</p></td></tr>';
    
    try {
        const params = new URLSearchParams();
        params.set('page', String(currentPage));
        params.set('limit', String(pageSize));
        if (searchMode && currentSearchQuery) params.set('q', currentSearchQuery);
        Object.entries(currentFilters).forEach(([k, v]) => {
            if (v != null && v !== '') params.set(k, String(v));
        });
        
        const url = searchMode
            ? `/api/v1/pii/logs/search?${params}`
            : `/api/v1/pii/logs?${params}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load logs');
        
        const data = await response.json();
        if (searchMode) {
            displaySearchResults(data);
        } else {
            displayLogs(data);
        }
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="6" class="no-results">Error loading logs: ${error.message}</td></tr>`;
    }
}

/**
 * Display logs in table
 */
function displayLogs(data) {
    const tbody = document.getElementById('logsTableBody');
    
    if (!data.logs || data.logs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="no-results">
                    <div class="no-results-icon">📋</div>
                    <div>No detection logs found</div>
                </td>
            </tr>
        `;
        return;
    }
    
    totalLogs = data.total;
    totalPages = data.pages;
    
    tbody.innerHTML = data.logs.map(log => `
        <tr onclick="viewDetail('${log.id}')">
            <td>${formatTimestamp(log.detected_at)}</td>
            <td>
                <span class="entity-badge ${getEntityClass(log.entity_type)}">
                    ${log.entity_type}
                </span>
            </td>
            <td>
                <span class="engine-label">${log.detection_engine}</span>
            </td>
            <td>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${log.confidence_score * 100}%"></div>
                </div>
                <small>${(log.confidence_score * 100).toFixed(0)}%</small>
            </td>
            <td>${log.source_type}</td>
            <td>
                <button class="icon-button" onclick="event.stopPropagation(); viewDetail('${log.id}')">
                    👁️
                </button>
            </td>
        </tr>
    `).join('');
    
    updatePagination();
}

/**
 * Format timestamp
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Get entity badge class
 */
function getEntityClass(entityType) {
    const type = entityType.toLowerCase();
    if (type.includes('email')) return 'email';
    if (type.includes('api') || type.includes('key')) return 'api_key';
    if (type.includes('password')) return 'password';
    if (type.includes('phone')) return 'phone';
    return 'default';
}

/**
 * Update pagination controls
 */
function updatePagination() {
    const start = (currentPage - 1) * pageSize + 1;
    const end = Math.min(currentPage * pageSize, totalLogs);
    
    document.getElementById('pageStart').textContent = start;
    document.getElementById('pageEnd').textContent = end;
    document.getElementById('totalLogs').textContent = totalLogs;
    document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
    
    document.getElementById('prevButton').disabled = currentPage === 1;
    document.getElementById('nextButton').disabled = currentPage === totalPages;
}

/**
 * Go to previous page
 */
function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        loadLogs();
    }
}

/**
 * Go to next page
 */
function nextPage() {
    if (currentPage < totalPages) {
        currentPage++;
        loadLogs();
    }
}

/**
 * Apply filters
 */
function applyFilters() {
    currentFilters = {};
    currentPage = 1;
    searchMode = false;
    currentSearchQuery = '';
    
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    const entityType = document.getElementById('entityTypeFilter').value;
    const engine = document.getElementById('engineFilter').value;
    const sourceType = document.getElementById('sourceFilter').value;
    
    if (startDate) currentFilters.start_date = startDate;
    if (endDate) currentFilters.end_date = endDate;
    if (entityType) currentFilters.entity_type = entityType;
    if (engine) currentFilters.engine = engine;
    if (sourceType) currentFilters.source_type = sourceType;
    
    loadLogs();
}

/**
 * Clear filters
 */
function clearFilters() {
    document.getElementById('startDate').value = '';
    document.getElementById('endDate').value = '';
    document.getElementById('entityTypeFilter').value = '';
    document.getElementById('engineFilter').value = '';
    document.getElementById('sourceFilter').value = '';
    document.getElementById('searchQuery').value = '';
    
    currentFilters = {};
    currentPage = 1;
    searchMode = false;
    currentSearchQuery = '';
    // Restore default date range
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 7);
    document.getElementById('endDate').valueAsDate = endDate;
    document.getElementById('startDate').valueAsDate = startDate;
    currentFilters.start_date = startDate.toISOString().split('T')[0];
    currentFilters.end_date = endDate.toISOString().split('T')[0];
    loadLogs();
}

/**
 * Search logs (paginated - one page at a time)
 */
async function searchLogs() {
    const query = document.getElementById('searchQuery').value;
    if (!query.trim()) {
        applyFilters();
        return;
    }
    
    searchMode = true;
    currentSearchQuery = query;
    currentPage = 1;
    
    try {
        const params = new URLSearchParams();
        params.set('q', query);
        params.set('page', String(currentPage));
        params.set('limit', String(pageSize));
        Object.entries(currentFilters).forEach(([k, v]) => {
            if (v != null && v !== '') params.set(k, String(v));
        });
        
        const response = await fetch(`/api/v1/pii/logs/search?${params}`);
        if (!response.ok) throw new Error('Search failed');
        
        const data = await response.json();
        displaySearchResults(data);
    } catch (error) {
        alert('Search error: ' + error.message);
    }
}

/**
 * Display search results (paginated)
 */
function displaySearchResults(data) {
    const tbody = document.getElementById('logsTableBody');
    
    if (!data.results || data.results.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="no-results">
                    No results found for "${data.query}"
                </td>
            </tr>
        `;
        return;
    }
    
    // Search API returns paginated results - calculate pages from total
    const pages = Math.ceil(data.total / pageSize) || 1;
    displayLogs({ logs: data.results, total: data.total, pages });
}

/**
 * View log detail
 */
async function viewDetail(logId) {
    try {
        const response = await fetch(`/api/v1/pii/logs/${logId}`);
        if (!response.ok) throw new Error('Failed to load log detail');
        
        const log = await response.json();
        displayLogDetail(log);
    } catch (error) {
        alert('Error loading detail: ' + error.message);
    }
}

/**
 * Display log detail in modal
 */
function displayLogDetail(log) {
    const modalBody = document.getElementById('modalBody');
    
    modalBody.innerHTML = `
        <div class="detail-row">
            <div class="detail-label">Detection ID</div>
            <div class="detail-value">${log.id}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Detected At</div>
            <div class="detail-value">${new Date(log.detected_at).toLocaleString()}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Entity Type</div>
            <div class="detail-value">
                <span class="entity-badge ${getEntityClass(log.entity_type)}">${log.entity_type}</span>
            </div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Detection Engine</div>
            <div class="detail-value">${log.detection_engine}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Confidence Score</div>
            <div class="detail-value">${(log.confidence_score * 100).toFixed(1)}%</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Source Type</div>
            <div class="detail-value">${log.source_type}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Source ID</div>
            <div class="detail-value">${log.source_id || 'N/A'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Context</div>
            <div class="context-box">${log.context_snippet || 'No context available'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Position</div>
            <div class="detail-value">${log.position_start}-${log.position_end}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Was Redacted</div>
            <div class="detail-value">${log.was_redacted ? '✅ Yes' : '❌ No'}</div>
        </div>
        ${log.was_redacted ? `
            <div class="detail-row">
                <div class="detail-label">Redaction Type</div>
                <div class="detail-value">${log.redaction_type || 'N/A'}</div>
            </div>
        ` : ''}
    `;
    
    document.getElementById('detailModal').classList.add('active');
}

/**
 * Close modal
 */
function closeModal() {
    document.getElementById('detailModal').classList.remove('active');
}

/**
 * Load statistics
 */
async function loadStatistics() {
    try {
        const response = await fetch('/api/v1/pii/logs/stats?period=7d');
        if (!response.ok) throw new Error('Failed to load statistics');
        
        const stats = await response.json();
        displayStatistics(stats);
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

/**
 * Display statistics
 */
function displayStatistics(stats) {
    document.getElementById('statTotal').textContent = stats.total_detections || 0;
    
    // Calculate today's count
    const today = new Date().toISOString().split('T')[0];
    const todayTrend = stats.trend?.find(t => t.date === today);
    document.getElementById('statToday').textContent = todayTrend?.count || 0;
    
    // Get top entity type
    const byType = stats.by_entity_type || {};
    const topType = Object.entries(byType).sort((a, b) => b[1] - a[1])[0];
    document.getElementById('statTopType').textContent = topType ? `${topType[0]} (${topType[1]})` : '-';
    
    // Calculate redaction percentage
    const redactedPercent = stats.total_detections > 0 
        ? ((stats.total_detections - 100) / stats.total_detections * 100).toFixed(1)
        : 0;
    document.getElementById('statRedacted').textContent = `${redactedPercent}%`;
}

/**
 * Export logs to CSV
 */
async function exportLogs() {
    try {
        const params = new URLSearchParams(currentFilters);
        const response = await fetch(`/api/v1/pii/logs/export?format=csv&${params}`);
        
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pii_detection_logs_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert('Export error: ' + error.message);
    }
}

// Close modal on outside click
document.getElementById('detailModal').addEventListener('click', (e) => {
    if (e.target.id === 'detailModal') {
        closeModal();
    }
});
