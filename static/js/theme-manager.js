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
                icon: 'disc',
                colors: {
                    // Jackson Theme — matches jackson.com brand design
                    // Primary Brand Red (Torch Red): #EB0028
                    // Secondary Background (warm beige): #E8E3D9
                    '--bg-app': '#FFFFFF',          // Clean white main background
                    '--bg-sidebar': '#1A1A1A',      // Near-black sidebar (softer than pure black)
                    '--bg-header': '#1A1A1A',       // Near-black header to match sidebar

                    '--bg-panel': '#FFFFFF',        // Pure white panels/cards
                    '--bg-surface': '#F7F6F3',      // Warm light surface (jackson warm gray)
                    '--bg-surface-raised': '#FFFFFF',
                    '--glass-border': '1px solid #E0DDD6',  // Warm subtle border
                    '--glass-shadow': '0 2px 8px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04)',

                    '--border-subtle': '1px solid #E0DDD6',
                    '--border-dark': '1px solid #333333',

                    '--text-primary': '#000000',    // Black for high-impact headings
                    '--text-secondary': '#767676',  // Gray for secondary text/accents
                    '--text-on-dark': '#FFFFFF',
                    '--text-header': '#FFFFFF',
                    '--text-muted-dark': '#9CA3AF',

                    '--border-header': 'rgba(255, 255, 255, 0.08)',
                    '--header-btn-bg': 'rgba(255, 255, 255, 0.08)',
                    '--header-btn-border': 'rgba(255, 255, 255, 0.15)',
                    '--header-btn-hover': 'rgba(255, 255, 255, 0.15)',
                    '--header-btn-color': '#FFFFFF',

                    '--accent-blue': '#EB0028',     // Jackson Torch Red — primary CTA
                    '--accent-purple': '#B80020',   // Darker red for hover/active states
                    '--accent-cyan': '#EB0028',     // Same brand red for consistency
                    '--accent-selected-bg': 'rgba(235, 0, 40, 0.06)',

                    '--status-success': '#059669',
                    '--status-warning': '#D97706',
                    '--status-error': '#DC2626',

                    '--shadow-card': '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
                    '--shadow-hover': '0 8px 20px -4px rgba(0, 0, 0, 0.10), 0 4px 8px -2px rgba(0, 0, 0, 0.06)',
                    '--shadow-levitate': '0 16px 32px -6px rgba(0, 0, 0, 0.12), 0 8px 16px -4px rgba(0, 0, 0, 0.06)',

                    // Jackson-specific extra variables
                    '--jackson-brand-red': '#EB0028',
                    '--jackson-warm-beige': '#E8E3D9',
                    '--jackson-dark-text': '#333333',
                    '--jackson-light-gray': '#767676',

                    '--radius-sm': '4px',           // Subtle rounding per Jackson spec
                    '--radius-md': '6px',
                    '--radius-lg': '8px'
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
        const savedZoom = localStorage.getItem('aiops-zoom');

        // Apply saved theme
        this.applyTheme(savedTheme);

        // Auto-detect large screen on first visit (no saved zoom)
        if (savedZoom === null) {
            const detectedZoom = this.detectOptimalZoom();
            const zoomIndex = this.zoomLevels.indexOf(detectedZoom);
            if (zoomIndex !== -1) {
                this.currentZoomIndex = zoomIndex;
            }
            console.log(`✓ Auto-detected screen ${window.screen.width}×${window.screen.height} → zoom ${Math.round(detectedZoom * 100)}%`);
        } else {
            // Apply previously saved zoom
            const zoom = parseFloat(savedZoom) || 1.0;
            const zoomIndex = this.zoomLevels.indexOf(zoom);
            if (zoomIndex !== -1) {
                this.currentZoomIndex = zoomIndex;
            }
        }
        this.applyZoom();

        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();

        // Add data attribute for current theme
        document.documentElement.setAttribute('data-theme', savedTheme);

        console.log('✓ Theme & Zoom Manager initialized');
    }

    /**
     * Detect optimal zoom level based on screen resolution.
     * On high-res monitors (2K/QHD/4K) the default 100% makes
     * everything physically tiny — bump zoom so the UI stays
     * comfortable. Uses window.screen (physical pixels).
     */
    detectOptimalZoom() {
        const screenWidth = window.screen.width;
        const screenHeight = window.screen.height;
        const dpr = window.devicePixelRatio || 1;

        // Effective resolution (CSS pixels available)
        const effectiveWidth = screenWidth;

        // 4K / UHD (≥ 3000 CSS pixels wide, or high DPR on large screen)
        if (effectiveWidth >= 3000) {
            return 1.5;
        }
        // QHD / 2K / 1440p (≥ 2400 CSS px)
        if (effectiveWidth >= 2400) {
            return 1.25;
        }
        // Wide QHD or high-density (≥ 1800 CSS px)
        if (effectiveWidth >= 1800) {
            return 1.1;
        }

        // Standard laptop / FHD — keep default
        return 1.0;
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

        // Jackson: recolor hardcoded inline blue styles to brand red
        if (themeName === 'jackson') {
            this._recolorInlineBlue();
            // Also observe DOM changes for dynamically-added elements
            this._startJacksonObserver();
        } else {
            this._stopJacksonObserver();
        }

        // Update Logo Icon (A -> J for Jackson)
        this._updateLogoIcon(themeName);

        // Update UI if theme selector exists
        this.updateThemeSelector(themeName);

        // Dispatch custom event for other components
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: themeName, name: theme.name }
        }));

        console.log(`✓ Theme applied: ${theme.name}`);
    }

    /**
     * Rewrite inline style="" attributes that contain hardcoded blue
     * (#3b82f6, #2563eb, #1d4ed8) to Jackson red (#EB0028).
     */
    _recolorInlineBlue() {
        const BLUE_RE = /#3b82f6|#2563eb|#1d4ed8|rgba\(\s*59\s*,\s*130\s*,\s*246/gi;
        const replacements = {
            '#3b82f6': '#EB0028',
            '#2563eb': '#EB0028',
            '#1d4ed8': '#C50022',
        };

        document.querySelectorAll('[style]').forEach(el => {
            const raw = el.getAttribute('style');
            if (!BLUE_RE.test(raw)) return;
            BLUE_RE.lastIndex = 0; // reset regex state

            let updated = raw;
            // Replace hex colors
            updated = updated.replace(/#3b82f6/gi, '#EB0028');
            updated = updated.replace(/#2563eb/gi, '#EB0028');
            updated = updated.replace(/#1d4ed8/gi, '#C50022');
            // Replace rgba blue
            updated = updated.replace(
                /rgba\(\s*59\s*,\s*130\s*,\s*246/gi,
                'rgba(235, 0, 40'
            );
            // Replace linear-gradient blue combos
            updated = updated.replace(
                /linear-gradient\([^)]*#EB0028[^)]*#EB0028[^)]*\)/gi,
                (match) => match.replace(/linear-gradient\([^,]+,/, 'linear-gradient(135deg,')
            );
            // Flatten double-red gradients to solid
            if (updated.includes('linear-gradient') && updated.includes('#EB0028')) {
                updated = updated.replace(
                    /linear-gradient\([^)]*\)/gi,
                    '#EB0028'
                );
            }

            el.setAttribute('style', updated);
        });
    }

    _startJacksonObserver() {
        if (this._jacksonObs) return;
        const startObserving = () => {
            if (!document.body) return;
            this._jacksonObs = new MutationObserver((mutations) => {
                let needsRecolor = false;
                for (const m of mutations) {
                    if (m.addedNodes.length) { needsRecolor = true; break; }
                }
                if (needsRecolor) this._recolorInlineBlue();
            });
            this._jacksonObs.observe(document.body, { childList: true, subtree: true });
        };
        if (document.body) {
            startObserving();
        } else {
            document.addEventListener('DOMContentLoaded', startObserving, { once: true });
        }
    }

    _stopJacksonObserver() {
        if (this._jacksonObs) {
            this._jacksonObs.disconnect();
            this._jacksonObs = null;
        }
    }

    _updateLogoIcon(themeName) {
        const logoSpan = document.querySelector('.sidebar-logo-icon span');
        if (logoSpan) {
            logoSpan.textContent = (themeName === 'jackson') ? 'J' : 'A';
        }
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

// Ensure Jackson inline-style recolor runs after DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    if (window.themeZoomManager && window.themeZoomManager.getCurrentTheme() === 'jackson') {
        window.themeZoomManager._recolorInlineBlue();
    }
});
