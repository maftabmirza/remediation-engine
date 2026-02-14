# Reset Theme to Light (Default)

## Quick Fix: Clear Saved Theme

If your browser has 'aftab' theme saved from testing and you want to reset to 'light', follow these steps:

### Option 1: Browser Console (Fastest)

1. Open browser DevTools (F12 or Right-click → Inspect)
2. Go to **Console** tab
3. Paste and run:
```javascript
localStorage.removeItem('aiops-theme');
localStorage.removeItem('aiops-zoom');
location.reload();
```

### Option 2: Application Storage

1. Open browser DevTools (F12)
2. Go to **Application** tab (Chrome/Edge) or **Storage** tab (Firefox)
3. Expand **Local Storage**
4. Click on `http://localhost:8080`
5. Find and delete:
   - `aiops-theme`
   - `aiops-zoom` (optional)
6. Refresh page (F5)

### Option 3: Manually Set Light Theme

In browser console:
```javascript
localStorage.setItem('aiops-theme', 'light');
location.reload();
```

## Verification

After clearing, you should see in console:
```
✓ Theme applied: Light
✓ Zoom level: 100%
✓ Theme & Zoom Manager initialized
```

## About the Themes

- **Light**: Your current/existing design (DEFAULT) ✅
  - All original colors preserved
  - Navy sidebar (#0f0e47)
  - Light background (#f4f6f8)
  
- **Aftab**: New custom theme (to be designed later)
  - Currently has placeholder colors
  - Will be customized per your requirements

## The Code is Correct

The Light theme in `theme-manager.js` has the EXACT same colors as your original `style.css`:

```javascript
light: {
    name: 'Light',
    icon: 'sun',
    colors: {
        '--bg-app': '#f4f6f8',           // Same as original
        '--bg-sidebar': '#0f0e47',       // Same as original
        '--bg-header': '#0f0e47',        // Same as original
        // ... all other colors match exactly
    }
}
```

**Your current theme has NOT been changed** - it's just that localStorage had 'aftab' saved from when you clicked the theme toggle button to test it.

---

**After clearing localStorage, the default theme will be Light** (your original design).
