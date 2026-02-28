# UI/UX Requirements

This document defines the user interface and experience specifications for the AIOps Remediation Engine.

## 1. General Interface

| Req ID | Requirement | Description |
| :--- | :--- | :--- |
| **UI-GN-01** | **Responsive Layout** | The application must be fully responsive, scaling correctly from desktop monitors (1920x1080) down to tablet sizes. |
| **UI-GN-02** | **Dark Mode Default** | The interface should strictly adhere to a dark theme (NOC/SOC style) to reduce eye strain during long operations. |
| **UI-GN-04** | **Builder Mode Hint** | If `context.form_data.builder_mode_detected` is true, UI should show a tip: "You're in Builder mode. Switch to Code mode...". |

## 2. Interaction & Controls

| Req ID | Requirement | Description |
| :--- | :--- | :--- |
| **UI-CT-01** | **Dropdown Selection State** | **Critical**: Any dropdown menu used for selecting a state, action, or filter (e.g., Quick Links, Action Selectors) must visually indicate the currently active or selected option using a **tick mark** (✓) or distinct visual highlight. |
| **UI-CT-03** | **Smart Suggestions** | Chat interface must render `[SUGGESTIONS]` blocks as clickable chips/buttons for quick user action. |

## 3. Terminal Interface

| Req ID | Requirement | Description |
| :--- | :--- | :--- |
| **UI-TR-01** | **Web Terminal (xterm.js)** | The terminal must render correctly using a standard web-based emulator (xterm.js), supporting standard keyboard shortcuts (Ctrl+C, etc.). |
| **UI-TR-02** | **No Hidden Execution** | As per AI Rules, the terminal must display *everything* happening on the connection. No hidden channels. |
| **UI-TR-03** | **Inline Chat Overlay** | Users must be able to invoke an inline chat (Ctrl+I) over the terminal to ask questions about the current screen content. |

## 4. Alert Visualization

| Req ID | Requirement | Description |
| :--- | :--- | :--- |
| **UI-AL-01** | **Severity Color Coding** | Alerts must use standard color codes: Critical (Red), Warning (Orange/Yellow), Info (Blue). |
| **UI-AL-02** | **Metadata Popovers** | Detailed metadata (long labels/annotations) should be tucked away in popovers or expandable sections to keep the main view clean. |
