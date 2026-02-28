# Theme & Zoom System Guide

## Overview

The AIOps Platform includes a flexible theme and zoom system that allows users to customize their viewing experience.

## Features

### 🎨 Themes

The application supports two themes:

1. **Light Theme** (Default)
   - Clean, modern light interface
   - Current production design
   - Icon: Sun ☀️

2. **Aftab Theme**
   - Custom theme (placeholder design)
   - To be fully designed and customized
   - Icon: Zap ⚡

### 🔍 Zoom Functionality

- **7 Zoom Levels**: 75%, 85%, 90%, 100%, 110%, 125%, 150%
- **Default**: 100%
- **Smooth transitions** between zoom levels
- **Persistent**: Zoom level is saved and restored on page reload

## Usage

### Switching Themes

**Via UI:**
- Click the theme toggle button in the header (shows current theme name and icon)
- Themes toggle between Light and Aftab

**Keyboard Shortcuts:**
- None (theme switching is UI-only)

### Zoom Controls

**Via UI:**
- Click the **+** button to zoom in
- Click the **-** button to zoom out
- Click the **⊡** button to reset to 100%
- Current zoom level is displayed in the middle

**Keyboard Shortcuts:**
- `Ctrl/Cmd + Plus (+)` - Zoom in
- `Ctrl/Cmd + Minus (-)` - Zoom out
- `Ctrl/Cmd + 0` - Reset to 100%

## Technical Details

### Files

- **JavaScript**: `/static/js/theme-manager.js`
- **CSS**: `/static/css/theme-controls.css`
- **Template**: Integrated in `/templates/base.html`

### Storage

User preferences are stored in browser `localStorage`:
- `aiops-theme`: Current theme name ('light' or 'aftab')
- `aiops-zoom`: Current zoom level (0.75 to 1.5)

### Custom Events

The theme manager dispatches custom events:

```javascript
// Listen for theme changes
window.addEventListener('themeChanged', function(e) {
    console.log('New theme:', e.detail.theme);
});

// Listen for zoom changes
window.addEventListener('zoomChanged', function(e) {
    console.log('Zoom percent:', e.detail.percent);
    console.log('Is min zoom:', e.detail.isMin);
    console.log('Is max zoom:', e.detail.isMax);
});
```

### API

Access the theme/zoom manager globally:

```javascript
// Get current theme
window.themeZoomManager.getCurrentTheme(); // 'light' or 'aftab'

// Switch theme
window.themeZoomManager.applyTheme('aftab');

// Zoom controls
window.themeZoomManager.zoomIn();
window.themeZoomManager.zoomOut();
window.themeZoomManager.resetZoom();

// Get current zoom
window.themeZoomManager.getCurrentZoom(); // e.g., 1.0
```

## Customizing the Aftab Theme

To design the Aftab theme, edit the colors in `/static/js/theme-manager.js`:

```javascript
aftab: {
    name: 'Aftab',
    icon: 'zap',
    colors: {
        '--bg-app': '#your-color',
        '--bg-sidebar': '#your-color',
        '--bg-header': '#your-color',
        // ... more CSS variables
    }
}
```

### Available CSS Variables

All CSS variables that can be customized:

```css
--bg-app              /* Main app background */
--bg-sidebar          /* Sidebar background */
--bg-header           /* Header background */
--bg-panel            /* Glass panel background */
--glass-border        /* Glass panel border */
--glass-shadow        /* Glass panel shadow */
--border-subtle       /* Subtle borders */
--border-dark         /* Dark borders */
--text-primary        /* Primary text color */
--text-secondary      /* Secondary text color */
--text-on-dark        /* Text on dark backgrounds */
--text-muted-dark     /* Muted text on dark */
--accent-blue         /* Blue accent color */
--accent-purple       /* Purple accent color */
--accent-cyan         /* Cyan accent color */
--accent-selected-bg  /* Selected item background */
--status-success      /* Success status color */
--status-warning      /* Warning status color */
--status-error        /* Error status color */
--shadow-card         /* Card shadow */
--shadow-hover        /* Hover shadow */
--shadow-levitate     /* Elevated shadow */
```

## Browser Compatibility

- ✅ Chrome/Edge (Chromium-based)
- ✅ Firefox
- ✅ Safari
- ⚠️ Note: `zoom` CSS property has varying support; consider using `transform: scale()` for better cross-browser support if needed

## Notifications

When theme or zoom changes, a toast notification appears in the bottom-right corner showing:
- Theme name when switching themes
- Zoom percentage when adjusting zoom

Notifications auto-dismiss after 2 seconds.

## Responsive Behavior

- **Desktop**: Shows theme name + icon, zoom percentage
- **Tablet**: Shows icon only, hides zoom percentage
- **Mobile**: Compact controls, essential buttons only
