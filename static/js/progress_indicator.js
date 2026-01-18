/**
 * Progress Indicator Component for AI Troubleshooting
 * 
 * Displays a visual progress bar showing the current phase,
 * completed phases, elapsed time, and tool call count.
 */

const PHASES = [
    { key: 'identify', icon: '🔍', label: 'Identify' },
    { key: 'verify', icon: '✅', label: 'Verify' },
    { key: 'investigate', icon: '📊', label: 'Investigate' },
    { key: 'plan', icon: '🧠', label: 'Plan' },
    { key: 'act', icon: '🛠️', label: 'Act' }
];

let progressState = {
    currentPhase: null,
    completedPhases: [],
    toolsCalled: 0,
    startTime: null,
    visible: false,
    elapsedInterval: null
};

/**
 * Initialize the progress indicator component
 */
function initProgressIndicator() {
    // Check if already exists
    if (document.getElementById('progressIndicator')) {
        return;
    }
    
    const indicator = document.createElement('div');
    indicator.id = 'progressIndicator';
    indicator.className = 'progress-indicator hidden bg-gray-900/95 border border-gray-700 rounded-lg p-3 mb-4';
    indicator.innerHTML = getProgressHTML();
    
    // Insert before chat messages
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages && chatMessages.parentElement) {
        chatMessages.parentElement.insertBefore(indicator, chatMessages);
    }
}

/**
 * Generate the HTML for the progress indicator
 */
function getProgressHTML() {
    const currentIndex = PHASES.findIndex(p => p.key === progressState.currentPhase);
    const percentage = currentIndex >= 0 ? ((currentIndex + 1) / PHASES.length * 100) : 0;
    const elapsed = progressState.startTime ? 
        Math.floor((Date.now() - progressState.startTime) / 1000) : 0;
    
    return `
        <div class="flex justify-between items-center mb-2">
            <span class="text-sm font-medium text-gray-300">
                ${progressState.currentPhase ? 
                    `Phase ${currentIndex + 1} of ${PHASES.length} - ${PHASES[currentIndex]?.label || ''}` : 
                    'Starting investigation...'}
            </span>
            <span class="text-xs text-gray-500">${Math.round(percentage)}%</span>
        </div>
        
        <div class="progress-bar h-2 bg-gray-700 rounded-full mb-3 overflow-hidden">
            <div class="progress-fill h-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-500"
                 style="width: ${percentage}%"></div>
        </div>
        
        <div class="phase-steps flex justify-between items-center mb-2">
            ${PHASES.map((phase, i) => {
                const isCompleted = progressState.completedPhases.includes(phase.key);
                const isCurrent = phase.key === progressState.currentPhase;
                const isPending = !isCompleted && !isCurrent;
                
                let stepHTML = `
                    <div class="phase-step flex flex-col items-center ${isCurrent ? 'current' : ''} ${isCompleted ? 'completed' : ''} ${isPending ? 'pending' : ''}">
                        <div class="phase-icon text-lg ${isCompleted ? 'text-green-400' : isCurrent ? 'text-blue-400' : 'text-gray-600'}">
                            ${isCompleted ? '✓' : phase.icon}
                        </div>
                        <div class="phase-label text-[10px] ${isCurrent ? 'text-blue-400 font-medium' : 'text-gray-500'}">
                            ${phase.label}
                        </div>
                        ${isCurrent ? '<div class="text-[9px] text-blue-400">(current)</div>' : ''}
                    </div>
                `;
                
                // Add connector between phases
                if (i < PHASES.length - 1) {
                    stepHTML += `
                        <div class="phase-connector flex-1 h-0.5 mx-1 ${isCompleted ? 'bg-green-400' : 'bg-gray-700'}"></div>
                    `;
                }
                
                return stepHTML;
            }).join('')}
        </div>
        
        <div class="flex justify-between text-xs text-gray-500">
            <span><i class="fas fa-clock mr-1"></i>Elapsed: ${elapsed}s</span>
            <span><i class="fas fa-wrench mr-1"></i>Tools: ${progressState.toolsCalled}/2 minimum</span>
        </div>
    `;
}

/**
 * Show the progress indicator
 */
function showProgress() {
    const indicator = document.getElementById('progressIndicator');
    if (indicator) {
        indicator.classList.remove('hidden');
        progressState.visible = true;
        progressState.startTime = Date.now();
        
        // Start elapsed time updater
        if (progressState.elapsedInterval) {
            clearInterval(progressState.elapsedInterval);
        }
        progressState.elapsedInterval = setInterval(updateProgressDisplay, 1000);
    }
}

/**
 * Hide the progress indicator
 */
function hideProgress() {
    const indicator = document.getElementById('progressIndicator');
    if (indicator) {
        indicator.classList.add('hidden');
        progressState.visible = false;
        if (progressState.elapsedInterval) {
            clearInterval(progressState.elapsedInterval);
            progressState.elapsedInterval = null;
        }
    }
}

/**
 * Update the progress state
 */
function updateProgress(phase, toolsCalled = null) {
    const prevPhase = progressState.currentPhase;
    
    // Mark previous phase as completed if moving to a new phase
    if (prevPhase && prevPhase !== phase && !progressState.completedPhases.includes(prevPhase)) {
        progressState.completedPhases.push(prevPhase);
    }
    
    progressState.currentPhase = phase;
    
    if (toolsCalled !== null) {
        progressState.toolsCalled = toolsCalled;
    }
    
    updateProgressDisplay();
}

/**
 * Update the progress display
 */
function updateProgressDisplay() {
    const indicator = document.getElementById('progressIndicator');
    if (indicator && progressState.visible) {
        indicator.innerHTML = getProgressHTML();
    }
}

/**
 * Complete the progress (all phases done)
 */
function completeProgress() {
    // Mark all phases as completed
    progressState.completedPhases = PHASES.map(p => p.key);
    progressState.currentPhase = null;
    updateProgressDisplay();
    
    // Hide after animation
    setTimeout(hideProgress, 2000);
}

/**
 * Reset progress for new investigation
 */
function resetProgress() {
    if (progressState.elapsedInterval) {
        clearInterval(progressState.elapsedInterval);
    }
    
    progressState = {
        currentPhase: null,
        completedPhases: [],
        toolsCalled: 0,
        startTime: null,
        visible: false,
        elapsedInterval: null
    };
    
    hideProgress();
}

/**
 * Handle progress event from backend
 */
function handleProgressEvent(data) {
    if (!progressState.visible) {
        showProgress();
    }
    
    if (data.phase) {
        updateProgress(data.phase, data.tools_called || null);
    }
}
