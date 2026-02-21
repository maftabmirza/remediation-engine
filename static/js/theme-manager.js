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
                    // Ocean Breeze - Teal-Blue Enterprise theme
                    '--bg-app': '#FFFFFF',
                    '--bg-sidebar': '#caf0f8',
                    '--bg-header': '#FFFFFF',

                    '--bg-panel': 'rgba(255, 255, 255, 0.95)',
                    '--bg-surface': '#FFFFFF',
                    '--bg-surface-raised': '#FFFFFF',
                    '--glass-border': '1px solid #90e0ef',
                    '--glass-shadow': '0 4px 12px rgba(3, 4, 94, 0.05)',

                    '--border-subtle': '1px solid #dbeafe',
                    '--border-dark': '1px solid #03045e',

                    '--text-primary': '#03045e',
                    '--text-secondary': '#334155',
                    '--text-on-dark': '#03045e',
                    '--text-header': '#03045e',
                    '--text-muted-dark': '#64748b',

                    '--border-header': 'rgba(0, 119, 182, 0.1)',
                    '--header-btn-bg': 'rgba(0, 0, 0, 0.05)',
                    '--header-btn-border': 'rgba(0, 0, 0, 0.1)',
                    '--header-btn-hover': 'rgba(0, 0, 0, 0.08)',
                    '--header-btn-color': '#334155',

                    '--accent-blue': '#0077b6',
                    '--accent-purple': '#03045e',
                    '--accent-cyan': '#00b4d8',
                    '--accent-selected-bg': 'rgba(0, 119, 182, 0.08)',

                    '--status-success': '#059669',
                    '--status-warning': '#D97706',
                    '--status-error': '#DC2626',

                    '--shadow-card': '0 1px 3px rgba(3, 4, 94, 0.06), 0 1px 2px rgba(3, 4, 94, 0.04)',
                    '--shadow-hover': '0 8px 20px -4px rgba(3, 4, 94, 0.10), 0 4px 8px -2px rgba(3, 4, 94, 0.06)',
                    '--shadow-levitate': '0 16px 32px -6px rgba(3, 4, 94, 0.12), 0 8px 16px -4px rgba(3, 4, 94, 0.06)'
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
            olive_leaf: {
                name: 'Olive Leaf',
                icon: 'feather',
                colors: {
                    // Olive Leaf Theme
                    // Palette: Olive Leaf #606c38 | Black Forest #283618 | Cornsilk #fefae0 | Light Caramel #dda15e | Copper #bc6c25
                    '--bg-app': '#fefae0',
                    '--bg-sidebar': '#283618',
                    '--bg-header': '#283618',

                    '--bg-panel': 'rgba(254, 250, 224, 0.92)',
                    '--bg-surface': '#f7f3df',
                    '--bg-surface-raised': '#fefae0',
                    '--glass-border': '1px solid rgba(188, 108, 37, 0.25)',
                    '--glass-shadow': '0 4px 6px -1px rgba(40, 54, 24, 0.08), 0 2px 4px -1px rgba(40, 54, 24, 0.05)',

                    '--border-subtle': '1px solid rgba(96, 108, 56, 0.22)',
                    '--border-dark': '1px solid #283618',

                    '--text-primary': '#283618',
                    '--text-secondary': '#606c38',
                    '--text-on-dark': '#fefae0',
                    '--text-header': '#fefae0',
                    '--text-muted-dark': '#9aaf82',

                    '--border-header': 'rgba(254, 250, 224, 0.15)',
                    '--header-btn-bg': 'rgba(254, 250, 224, 0.1)',
                    '--header-btn-border': 'rgba(254, 250, 224, 0.2)',
                    '--header-btn-hover': 'rgba(254, 250, 224, 0.18)',
                    '--header-btn-color': '#fefae0',

                    '--accent-blue': '#bc6c25',
                    '--accent-purple': '#606c38',
                    '--accent-cyan': '#dda15e',
                    '--accent-selected-bg': 'rgba(188, 108, 37, 0.08)',

                    '--status-success': '#16a34a',
                    '--status-warning': '#d97706',
                    '--status-error': '#ef4444',

                    '--shadow-card': '0 1px 3px rgba(40, 54, 24, 0.08), 0 1px 2px rgba(40, 54, 24, 0.04)',
                    '--shadow-hover': '0 8px 20px -4px rgba(40, 54, 24, 0.10), 0 4px 8px -2px rgba(40, 54, 24, 0.05)',
                    '--shadow-levitate': '0 16px 32px -6px rgba(40, 54, 24, 0.12), 0 8px 16px -4px rgba(40, 54, 24, 0.06)',

                    // Olive Leaf theme-specific extras
                    '--olive-brand-copper': '#bc6c25',
                    '--olive-cornsilk': '#fefae0',
                    '--olive-forest': '#283618',
                    '--olive-leaf-color': '#606c38',
                    '--olive-caramel': '#dda15e',

                    '--radius-sm': '8px',
                    '--radius-md': '12px',
                    '--radius-lg': '16px'
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
        } else if (themeName === 'olive_leaf') {
            this._recolorInlineBlueToCopper();
            this._startOliveObserver();
            this._stopJacksonObserver();
        } else {
            this._stopJacksonObserver();
            this._stopOliveObserver();
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

    /**
     * Rewrite inline style="" attributes that contain hardcoded blue
     * to Olive Leaf Copper (#bc6c25) for the olive_leaf theme.
     */
    _recolorInlineBlueToCopper() {
        const BLUE_RE = /#3b82f6|#2563eb|#1d4ed8|rgba\(\s*59\s*,\s*130\s*,\s*246/gi;
        document.querySelectorAll('[style]').forEach(el => {
            const raw = el.getAttribute('style');
            if (!BLUE_RE.test(raw)) return;
            BLUE_RE.lastIndex = 0;

            let updated = raw;
            updated = updated.replace(/#3b82f6/gi, '#bc6c25');
            updated = updated.replace(/#2563eb/gi, '#9a5720');
            updated = updated.replace(/#1d4ed8/gi, '#7a4415');
            updated = updated.replace(
                /rgba\(\s*59\s*,\s*130\s*,\s*246/gi,
                'rgba(188, 108, 37'
            );
            if (updated.includes('linear-gradient') && updated.includes('#bc6c25')) {
                updated = updated.replace(/linear-gradient\([^)]*\)/gi, '#bc6c25');
            }
            el.setAttribute('style', updated);
        });
    }

    _startOliveObserver() {
        if (this._oliveObs) return;
        const startObserving = () => {
            if (!document.body) return;
            this._oliveObs = new MutationObserver((mutations) => {
                let needsRecolor = false;
                for (const m of mutations) {
                    if (m.addedNodes.length) { needsRecolor = true; break; }
                }
                if (needsRecolor) this._recolorInlineBlueToCopper();
            });
            this._oliveObs.observe(document.body, { childList: true, subtree: true });
        };
        if (document.body) {
            startObserving();
        } else {
            document.addEventListener('DOMContentLoaded', startObserving, { once: true });
        }
    }

    _stopOliveObserver() {
        if (this._oliveObs) {
            this._oliveObs.disconnect();
            this._oliveObs = null;
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

// Ensure inline-style recolor runs after DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    const currentTheme = window.themeManager.getCurrentTheme();
    if (currentTheme === 'jackson') {
        window.themeManager._recolorInlineBlue();
    } else if (currentTheme === 'olive_leaf') {
        window.themeManager._recolorInlineBlueToCopper();
    }
});
