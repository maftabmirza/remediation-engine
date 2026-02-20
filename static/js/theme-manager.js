/**
 * Theme Manager for AIOps Platform
 * Manages Light, Aftab, and Jackson themes
 * Use browser zoom (Ctrl+/Ctrl-) for interface scaling
 */

class ThemeManager {
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
                    // Jackson Theme — matches reference image (light sidebar)
                    // Primary Brand: #722f37 (maroon)
                    // Sidebar: #dbcfc7 | Active item: Deep Maroon #722f37
                    '--bg-app': '#FFFFFF',          // Clean white main background
                    '--bg-sidebar': '#dbcfc7',
                    '--bg-header': '#FFFFFF',       // White header per reference

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

                    '--accent-blue': '#722f37',     // Jackson maroon — primary CTA
                    '--accent-purple': '#5a252c',  // Darker maroon for hover/active states
                    '--accent-cyan': '#722f37',     // Same maroon for consistency
                    '--accent-selected-bg': 'rgba(114, 47, 55, 0.06)',

                    '--status-success': '#059669',
                    '--status-warning': '#D97706',
                    '--status-error': '#DC2626',

                    '--shadow-card': '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
                    '--shadow-hover': '0 8px 20px -4px rgba(0, 0, 0, 0.10), 0 4px 8px -2px rgba(0, 0, 0, 0.06)',
                    '--shadow-levitate': '0 16px 32px -6px rgba(0, 0, 0, 0.12), 0 8px 16px -4px rgba(0, 0, 0, 0.06)',

                    // Jackson-specific extra variables
                    '--jackson-brand-red': '#722f37',
                    '--jackson-warm-beige': '#E8E3D9',
                    '--jackson-dark-text': '#333333',
                    '--jackson-light-gray': '#767676',

                    '--radius-sm': '4px',           // Subtle rounding per Jackson spec
                    '--radius-md': '6px',
                    '--radius-lg': '8px'
                }
            }
        };

        this.init();
    }

    init() {
        // Load saved theme preference
        const savedTheme = localStorage.getItem('aiops-theme') || 'light';

        // Apply saved theme
        this.applyTheme(savedTheme);

        // Add data attribute for current theme
        document.documentElement.setAttribute('data-theme', savedTheme);

        console.log('✓ Theme Manager initialized');
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

        // Update Theme CSS File
        const themeLink = document.getElementById('theme-css');
        if (themeLink) {
            // Check if href needs update to avoid reload flash if same
            if (!themeLink.href.includes(`/${themeName}.css`)) {
                themeLink.href = `/static/css/themes/${themeName}.css?v=20260219a`;
            }
        }

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
     * (#3b82f6, #2563eb, #1d4ed8) to Jackson maroon (#722f37).
     */
    _recolorInlineBlue() {
        const BLUE_RE = /#3b82f6|#2563eb|#1d4ed8|rgba\(\s*59\s*,\s*130\s*,\s*246/gi;
        const replacements = {
            '#3b82f6': '#722f37',
            '#2563eb': '#722f37',
            '#1d4ed8': '#5a252c',
        };

        document.querySelectorAll('[style]').forEach(el => {
            const raw = el.getAttribute('style');
            if (!BLUE_RE.test(raw)) return;
            BLUE_RE.lastIndex = 0; // reset regex state

            let updated = raw;
            // Replace hex colors
            updated = updated.replace(/#3b82f6/gi, '#722f37');
            updated = updated.replace(/#2563eb/gi, '#722f37');
            updated = updated.replace(/#1d4ed8/gi, '#5a252c');
            // Replace rgba blue
            updated = updated.replace(
                /rgba\(\s*59\s*,\s*130\s*,\s*246/gi,
                'rgba(114, 47, 55'
            );
            // Replace linear-gradient blue combos
            updated = updated.replace(
                /linear-gradient\([^)]*#722f37[^)]*#722f37[^)]*\)/gi,
                (match) => match.replace(/linear-gradient\([^,]+,/, 'linear-gradient(135deg,')
            );
            // Flatten double-maroon gradients to solid
            if (updated.includes('linear-gradient') && updated.includes('#722f37')) {
                updated = updated.replace(
                    /linear-gradient\([^)]*\)/gi,
                    '#722f37'
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

    updateThemeSelector(themeName) {
        const themeButtons = document.querySelectorAll('[data-theme-btn]');
        themeButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.themeBtn === themeName);
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
}

// Initialize globally - maintain backward compatibility with old variable name
window.themeZoomManager = new ThemeManager();
window.themeManager = window.themeZoomManager;

// Ensure Jackson inline-style recolor runs after DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    const currentTheme = window.themeManager.getCurrentTheme();
    if (currentTheme === 'jackson') {
        window.themeManager._recolorInlineBlue();
    }
});
