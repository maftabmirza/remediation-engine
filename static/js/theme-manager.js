/**
 * Theme & Zoom Manager for AIOps Platform
 * Manages Light and Aftab themes with zoom functionality
 */

class ThemeZoomManager {
    constructor() {
        this.themes = {
            light: {
                name: 'Light',
                icon: 'sun',
                colors: {
                    // Current theme colors - keeping existing design
                    '--bg-app': '#f4f6f8',
                    '--bg-sidebar': '#0f0e47',
                    '--bg-header': '#0f0e47',

                    '--bg-panel': 'rgba(255, 255, 255, 0.75)',
                    '--glass-border': '1px solid rgba(255, 255, 255, 0.8)',
                    '--glass-shadow': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',

                    '--border-subtle': '1px solid rgba(226, 232, 240, 0.8)',
                    '--border-dark': '1px solid #334155',

                    '--text-primary': '#1e293b',
                    '--text-secondary': '#64748b',
                    '--text-primary': '#1e293b',
                    '--text-secondary': '#64748b',
                    '--text-on-dark': '#f1f5f9',
                    '--text-on-dark': '#f1f5f9',
                    '--text-header': '#f1f5f9', // Header text color (same as on-dark for Light theme)
                    '--text-muted-dark': '#94a3b8',

                    '--border-header': 'rgba(255, 255, 255, 0.1)',
                    '--header-btn-bg': 'rgba(255, 255, 255, 0.1)',
                    '--header-btn-border': 'rgba(255, 255, 255, 0.2)',
                    '--header-btn-hover': 'rgba(255, 255, 255, 0.18)',
                    '--header-btn-color': '#f1f5f9',

                    '--accent-blue': '#3b82f6',
                    '--accent-purple': '#8b5cf6',
                    '--accent-cyan': '#06b6d4',
                    '--accent-selected-bg': 'rgba(59, 130, 246, 0.08)',

                    '--status-success': '#10b981',
                    '--status-warning': '#f59e0b',
                    '--status-error': '#ef4444',

                    '--shadow-card': '0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03)',
                    '--shadow-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025)',
                    '--shadow-levitate': '0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02)'
                }
            },
            aftab: {
                name: 'Aftab',
                icon: 'zap',
                colors: {
                    // Placeholder - Aftab theme to be designed later
                    // Using temporary colors for now
                    '--bg-app': '#f0f0f0',
                    '--bg-sidebar': '#1a1a1a',
                    '--bg-header': '#2a2a2a',

                    '--bg-panel': 'rgba(255, 255, 255, 0.8)',
                    '--glass-border': '1px solid rgba(255, 255, 255, 0.9)',
                    '--glass-shadow': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',

                    '--border-subtle': '1px solid rgba(200, 200, 200, 0.8)',
                    '--border-dark': '1px solid #444444',

                    '--text-primary': '#1a1a1a',
                    '--text-secondary': '#666666',
                    '--text-primary': '#1a1a1a',
                    '--text-secondary': '#666666',
                    '--text-on-dark': '#ffffff',
                    '--text-on-dark': '#ffffff',
                    '--text-header': '#ffffff', // Header text color
                    '--text-muted-dark': '#aaaaaa',

                    '--border-header': 'rgba(255, 255, 255, 0.1)',
                    '--header-btn-bg': 'rgba(255, 255, 255, 0.1)',
                    '--header-btn-border': 'rgba(255, 255, 255, 0.2)',
                    '--header-btn-hover': 'rgba(255, 255, 255, 0.18)',
                    '--header-btn-color': '#ffffff',

                    '--accent-blue': '#4a90e2',
                    '--accent-purple': '#9b59b6',
                    '--accent-cyan': '#1abc9c',
                    '--accent-selected-bg': 'rgba(74, 144, 226, 0.1)',

                    '--status-success': '#27ae60',
                    '--status-warning': '#f39c12',
                    '--status-error': '#e74c3c',

                    '--shadow-card': '0 2px 4px rgba(0, 0, 0, 0.1)',
                    '--shadow-hover': '0 8px 16px rgba(0, 0, 0, 0.1)',
                    '--shadow-levitate': '0 12px 24px rgba(0, 0, 0, 0.15)'
                }
            },
            jackson: {
                name: 'Jackson',
                icon: 'disc', // Changed to disc for the red dot feel, or could use 'target'
                colors: {
                    // Jackson Theme - Brand Red & Black
                    '--bg-app': '#F9FAFB',     // Very light gray/white background
                    '--bg-sidebar': '#000000', // Pure Black Sidebar
                    '--bg-header': '#000000',  // Pure Black Header (Matches matches Sidebar)

                    '--bg-panel': 'rgba(255, 255, 255, 0.95)',
                    '--glass-border': '1px solid #e5e7eb',
                    '--glass-shadow': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',

                    '--border-subtle': '1px solid #e5e7eb',
                    '--border-dark': '1px solid #1f2937',

                    '--text-primary': '#111827',   // Almost black
                    '--text-secondary': '#4b5563', // Gray 600
                    '--text-on-dark': '#ffffff',
                    '--text-on-dark': '#ffffff',
                    '--text-header': '#ffffff',    // White text for black header
                    '--text-muted-dark': '#9ca3af',

                    '--border-header': 'rgba(255, 255, 255, 0.1)',
                    '--header-btn-bg': 'rgba(255, 255, 255, 0.1)',
                    '--header-btn-border': 'rgba(255, 255, 255, 0.2)',
                    '--header-btn-hover': 'rgba(255, 255, 255, 0.18)',
                    '--header-btn-color': '#ffffff',

                    '--accent-blue': '#CE1126',    // Jackson Corporate Red
                    '--accent-purple': '#991b1b',  // Darker Red
                    '--accent-cyan': '#ef4444',    // Lighter Red
                    '--accent-selected-bg': 'rgba(206, 17, 38, 0.08)', // Red tint

                    '--status-success': '#059669',
                    '--status-warning': '#d97706',
                    '--status-error': '#dc2626',

                    '--shadow-card': '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
                    '--shadow-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                    '--shadow-levitate': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                }
            }
        };

        this.zoomLevels = [0.75, 0.85, 0.9, 1.0, 1.1, 1.25, 1.5];
        this.currentZoomIndex = 3; // Default to 1.0 (100%)

        this.init();
    }

    init() {
        // Load saved preferences
        const savedTheme = localStorage.getItem('aiops-theme') || 'light';
        const savedZoom = parseFloat(localStorage.getItem('aiops-zoom')) || 1.0;

        // Apply saved theme
        this.applyTheme(savedTheme);

        // Apply saved zoom
        const zoomIndex = this.zoomLevels.indexOf(savedZoom);
        if (zoomIndex !== -1) {
            this.currentZoomIndex = zoomIndex;
        }
        this.applyZoom();

        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();

        // Add data attribute for current theme
        document.documentElement.setAttribute('data-theme', savedTheme);

        console.log('✓ Theme & Zoom Manager initialized');
    }

    applyTheme(themeName) {
        const theme = this.themes[themeName];
        if (!theme) {
            console.error(`Theme '${themeName}' not found`);
            return;
        }

        const root = document.documentElement;

        // Apply all color variables
        Object.entries(theme.colors).forEach(([key, value]) => {
            root.style.setProperty(key, value);
        });

        // Save preference
        localStorage.setItem('aiops-theme', themeName);
        document.documentElement.setAttribute('data-theme', themeName);

        // Update UI if theme selector exists
        this.updateThemeSelector(themeName);

        // Dispatch custom event for other components
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: themeName, name: theme.name }
        }));

        console.log(`✓ Theme applied: ${theme.name}`);
    }

    updateThemeSelector(themeName) {
        // Update theme toggle button
        const themeButtons = document.querySelectorAll('[data-theme-btn]');
        themeButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.themeBtn === themeName);
        });
    }

    zoomIn() {
        if (this.currentZoomIndex < this.zoomLevels.length - 1) {
            this.currentZoomIndex++;
            this.applyZoom();
        }
    }

    zoomOut() {
        if (this.currentZoomIndex > 0) {
            this.currentZoomIndex--;
            this.applyZoom();
        }
    }

    resetZoom() {
        this.currentZoomIndex = 3; // Reset to 1.0 (100%)
        this.applyZoom();
    }

    applyZoom() {
        const zoomLevel = this.zoomLevels[this.currentZoomIndex];

        // Check if body exists before applying zoom
        if (document.body) {
            document.body.style.zoom = zoomLevel;

            // Save preference
            localStorage.setItem('aiops-zoom', zoomLevel);

            // Update UI
            this.updateZoomDisplay();

            // Dispatch event
            window.dispatchEvent(new CustomEvent('zoomChanged', {
                detail: {
                    zoom: zoomLevel,
                    percent: Math.round(zoomLevel * 100),
                    index: this.currentZoomIndex,
                    isMin: this.currentZoomIndex === 0,
                    isMax: this.currentZoomIndex === this.zoomLevels.length - 1
                }
            }));

            console.log(`✓ Zoom level: ${Math.round(zoomLevel * 100)}%`);
        } else {
            // Body not ready yet, will apply when DOM is fully loaded
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => {
                    this.applyZoom();
                }, { once: true });
            }
        }
    }

    updateZoomDisplay() {
        const display = document.getElementById('zoom-level-display');
        if (display) {
            const percent = Math.round(this.zoomLevels[this.currentZoomIndex] * 100);
            display.textContent = `${percent}%`;
        }
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + Plus/Equals for zoom in
            if ((e.ctrlKey || e.metaKey) && (e.key === '+' || e.key === '=')) {
                e.preventDefault();
                this.zoomIn();
            }

            // Ctrl/Cmd + Minus for zoom out
            if ((e.ctrlKey || e.metaKey) && e.key === '-') {
                e.preventDefault();
                this.zoomOut();
            }

            // Ctrl/Cmd + 0 for reset zoom
            if ((e.ctrlKey || e.metaKey) && e.key === '0') {
                e.preventDefault();
                this.resetZoom();
            }
        });
    }

    getAvailableThemes() {
        return Object.keys(this.themes).map(key => ({
            id: key,
            name: this.themes[key].name,
            icon: this.themes[key].icon
        }));
    }

    getCurrentTheme() {
        return localStorage.getItem('aiops-theme') || 'light';
    }

    getCurrentZoom() {
        return this.zoomLevels[this.currentZoomIndex];
    }
}

// Initialize globally
window.themeZoomManager = new ThemeZoomManager();
