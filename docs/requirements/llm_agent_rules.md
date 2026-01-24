# LLM Agent Rules & Implementation Requirements

This document outlines the strict behavioral rules and implementation details for the AI Agent (Troubleshoot Native Agent). These rules are critical for security, usability, and auditability.

## 1. Safety & Approval

| Rule ID | Rule | Notes / Implementation Details |
| :--- | :--- | :--- |
| **AR-01** | **Approval Required** | AI should never run a command on a remote server without user approval. The UI must show an Approval Panel. <br>**Implementation**: `suggest_ssh_command` tool triggers this. Blocks dangerous commands like `rm -rf /`, `mkfs`, `dd`, `fork bombs` (Linux) and `Format-Volume`, `Clear-Disk`, `IEX` (Windows) via `CommandValidator`. |
| **AR-02** | **Audit Trail** | The system must track: `command_proposed` → `command_approved` → `command_executed`. Logged to `command_history` table and `ai_audit_service`. |
| **AR-03** | **Agent Mode Constraints** | Only "Agent Mode" steps can auto-execute if "Auto-approve" is checked. Default `max_iterations` is 20 (Code default is 7, needs config adj). |

## 2. Terminal & Execution

| Rule ID | Rule | Notes / Implementation Details |
| :--- | :--- | :--- |
| **AR-04** | **Read Output** | The AI must read the command output. This is captured via WebSocket PTY (`xterm.js`) and sent back to the AI context. |
| **AR-05** | **Suggest Next Action** | After reading command output, the Agent must analyze it and suggest the next logical step via the `suggest_ssh_command` tool. This suggestion should be visible in the audit trail. |
| **AR-06** | **Cross-Platform Support** | Support Linux/Unix and Windows. Detect prompts (`$`, `#`, `C:>`, `PS C:>`). Use `CommandValidator` to enforce OS-specific safety (`DEFAULT_LINUX_BLOCKLIST`, `DEFAULT_WINDOWS_BLOCKLIST`). |
| **AR-07** | **Pager Handling** | The system must automatically detect pager prompts (e.g., `(END)`, `--More--`) and auto-send `q` to exit them, preventing the Agent from hanging. |
| **AR-08** | **Step Visibility** | All commands executed by the Agent must be visible in the terminal. No hidden background execution is allowed. |
| **AR-09** | **ANSI Stripping** | Terminal escape codes (ANSI colors/formatting) must be stripped from the output before being sent to the AI to ensure clean analysis. |

## 3. Feedback & Learning

| Rule ID | Rule | Notes / Implementation Details |
| :--- | :--- | :--- |
| **AR-10** | **Feedback Mechanism** | UI Thumbs Up/Down. AI considers `get_feedback_history` tool results to avoid repeating past failures. |
| **AR-11** | **Stored Database** | Feedback must be stored in the database to improve future Agent performance (Session-level feedback). |

## 4. Session & Constraints

| Rule ID | Rule | Notes / Implementation Details |
| :--- | :--- | :--- |
| **AR-12** | **Timeout Handling** | User control for timeouts is required. After 2 minutes of execution/waiting, show a "Read Output & Continue" button instead of failing outright. |
| **AR-13** | **Q&A Support** | The Agent can ask questions to the user. Supported user responses: `Yes`, `No`, `Skip`, `Custom`. |
| **AR-14** | **Output Truncation** | Large outputs must be truncated to prevent UI/LLM context overload. Threshold: **5000 characters**. |
| **AR-15** | **Error Detection** | Detect keywords: "error", "failed", "denied". Agent must analyze these returns and suggest fixes, not ignore them. |
| **AR-16** | **Session Isolation** | Sessions identified by UUID. `AISession` table tracks `user_id` and `pillar` (troubleshoot/revive). |
| **AR-17** | **Max Steps Limit** | Strict limit of **20 steps** (System Prompt requirement) to prevent loop. (Note: Code implementation uses `max_iterations=7` default, must be configured to 20). |

## 5. Agent Protocol (System Prompt)

| Rule ID | Rule | Implementation Details |
| :--- | :--- | :--- |
| **AR-18** | **5-Phase Protocol** | Agent MUST follow: 1. Identify, 2. Verify (OS/target), 3. Investigate (Tools), 4. Plan, 5. Act. |
| **AR-19** | **Anti-Hallucination** | System Prompt strictly forbids inventing tool outputs. "YOU MUST CALL TOOLS". |
| **AR-20** | **Runbook Linking** | Regex `\[Open runbook\]\(([^)]+)\)` used to capture and append `📖 Runbook Links` section to final response. |
| **AR-21** | **Suggestions** | Response may include `[SUGGESTIONS]` block with 2-4 short follow-up actions (e.g., "Check logs", "Restart"). |
