/**
 * Theme Manager for AIOps Platform
 * Manages Light and Jackson themes
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
        let savedTheme = localStorage.getItem('aiops-theme') || 'light';

        // Fall back to light if saved theme no longer exists
        if (!this.themes[savedTheme]) {
            savedTheme = 'light';
            localStorage.setItem('aiops-theme', 'light');
        }

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
                themeLink.href = `/static/css/themes/${themeName}.css?v=20260228d`;
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

// Ensure inline-style recolor runs after DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    const currentTheme = window.themeManager.getCurrentTheme();
    if (currentTheme === 'jackson') {
        window.themeManager._recolorInlineBlue();
    }
});
