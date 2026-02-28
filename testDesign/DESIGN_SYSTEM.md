# Enterprise AIOps Design System

This document serves as the single source of truth for the Enterprise AIOps Command Center design. Refer to these guidelines to maintain consistency across the application.

## 1. Design Philosophy
- **Theme**: Light Glassmorphism with Enterprise Cleanliness.
- **Visual Style**: Premium, clean, and data-dense but readable.
- **Key Characteristics**: Subtle gradients, blur effects (`backdrop-filter`), and refined shadows.

## 2. Color Palette (CSS Variables)

### Backgrounds
| Variable | Value | Description |
| :--- | :--- | :--- |
| `--bg-app` | `#f4f6f8` | Main application background (Light greyish-blue) |
| `--bg-sidebar` | `#0f172a` | Dark Sidebar background (Deep Navy) |
| `--bg-header` | `#0f172a` | Header background (Deep Navy) |
| `--bg-panel` | `rgba(255, 255, 255, 0.75)` | Glassmorphic panel background |

### Text Colors
| Variable | Value | Usage |
| :--- | :--- | :--- |
| `--text-primary` | `#1e293b` | Primary headings and body text |
| `--text-secondary` | `#64748b` | Secondary information, subtitles |
| `--text-on-dark` | `#f1f5f9` | Text on dark backgrounds (Sidebar/Header) |
| `--text-muted-dark` | `#94a3b8` | Muted text on dark backgrounds |

### Accent Colors
| Variable | Value | Usage |
| :--- | :--- | :--- |
| `--accent-blue` | `#3b82f6` | Primary Actions, Links, Info |
| `--accent-purple` | `#8b5cf6` | AI/Magic features |
| `--accent-cyan` | `#06b6d4` | Analytics/Data |
| `--accent-selected-bg`| `rgba(59, 130, 246, 0.08)` | Selected item background |

### Functional / Status Colors
| Variable | Value | Usage |
| :--- | :--- | :--- |
| `--status-success` | `#10b981` | Healthy, On, Success |
| `--status-warning` | `#f59e0b` | Warning, Degraded, Caution |
| `--status-error` | `#ef4444` | Critical, Offline, Error |

## 3. Typography
**Font Family**: `'Adobe Clean', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`
**Monospace**: `'Inter', monospace` (Used for numbers and data alignment)

| Type | Weight | Size | Usage |
| :--- | :--- | :--- | :--- |
| **Page Title** | 600 | `20px` | Main page headers |
| **Section Header** | 700 | `15px` | Card headers (h3) |
| **Body Default** | 400 | `14px` | Standard text |
| **Label/Small** | 500 | `11px-13px` | Badges, metadata |
| **Numbers** | 600 | Variable | Metric values (uses Monospace) |

## 4. UI Components

### Cards (Glassmorphism)
- **Base Style**: `background: linear-gradient(145deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.6))`
- **Blur**: `backdrop-filter: blur(12px)`
- **Border**: `1px solid rgba(255, 255, 255, 0.6)`
- **Radius**: `--radius-md` (12px)
- **Shadow**: `--shadow-card`
- **Hover Effect**: Lifts up (`translateY(-4px)`), increased shadow (`--shadow-levitate`), and whiter background.

### Buttons
- **Small Button (`.btn-sm`)**:
  - Padding: `4px 10px`
  - Radius: `4px`
  - Border: `1px solid var(--border-subtle)`
  - Hover: Border and text become `--accent-blue`.
- **Icon Button (`.icon-btn`)**:
  - Transparent background, changes to `rgba(255, 255, 255, 0.1)` on hover.

### Badges & Pills
- **Badge**: Colored background, white text (or dark text depending on contrast).
- **Label Pill (`.label-pill`)**: Used for tags (e.g., `severity=critical`).

### Navigation Items (`.nav-item`)
- **Default**: Transparent background, `--text-muted-dark` color.
- **Hover**: `rgba(255, 255, 255, 0.1)` background, `--text-on-dark` color.
- **Active**: Semi-transparent blue background (15% opacity), White text, Subtle glow shadow.
- **Icons**: 18x18px (Feather icons).

## 5. Effects & Utilities

### Borders
- `--border-subtle`: `1px solid rgba(226, 232, 240, 0.8)`
- `--border-dark`: `1px solid #334155`

### Shadows
- `--shadow-card`: `0 1px 3px rgba(0, 0, 0, 0.05), ...`
- `--shadow-levitate`: Stronger shadow for floating elements.

### Border Radius
- `--radius-sm`: `8px`
- `--radius-md`: `12px`
- `--radius-lg`: `16px`

## 6. Layout Grid
- **Global Grid**: `170px` (Sidebar) | `1fr` (Main) | `0px` (Chat)
- **Dashboard Grid**: 4 Columns.
- **Gap**: `24px`

## 7. Iconography
- **Library**: Feather Icons (`<i data-feather="icon-name"></i>`)
- **Style**: Stroke `currentColor`, Fill `none`.
- **Colors**: Icons often match their specific function (e.g., Activity = Green, Alert = Red).

## 8. Navigation Behavior
- **Locked Mode**: Sidebar stays expanded (Width: 170px).
- **Auto-Close Mode**: Sidebar collapses to icons (Width: 48px). **Does not expand on hover** (Click to toggle).
