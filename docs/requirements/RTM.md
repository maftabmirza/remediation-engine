# Requirements Traceability Matrix (RTM)

This matrix maps user requirements to their implementation status and location.

## 1. LLM Agent Rules (Behavioral)
*Reference: `docs/requirements/llm_agent_rules.md`*

| Rule ID | Requirement | Status | Verification | Implemented In |
| :--- | :--- | :--- | :--- | :--- |
| **AR-01** | **Approval Required** | [x] Implemented | Manual Test | `app/services/agentic/troubleshoot_native_agent.py` |
| **AR-02** | **Audit Trail** | [x] Implemented | DB Check | `app/models_revive.py` (CommandHistory) |
| **AR-03** | **Agent Mode Constraints** | [x] Implemented | UI Test | `templates/alert_detail.html` (Agent Modal) |
| **AR-04** | **Read Output** | [x] Implemented | E2E Test | `app/services/ssh_service.py` |
| **AR-05** | **Suggest Next Action** | [x] Implemented | Unit Test | `app/services/agentic/tools/` |
| **AR-06** | **Cross-Platform** | [/] Partial | Integration | `app/services/agentic/tools/ssh_tools.py` |
| **AR-07** | **Pager Handling** | [x] Implemented | Unit Test | `app/services/ssh_service.py` (Output Processor) |
| **AR-08** | **Step Visibility** | [x] Implemented | Visual | `templates/alert_detail.html` |
| **AR-09** | **ANSI Stripping** | [x] Implemented | Unit Test | `app/utils/text_processing.py` |
| **AR-10** | **Feedback Mechanism** | [x] Implemented | API Test | `app/routers/feedback.py` |
| **AR-11** | **Stored Database** | [x] Implemented | DB Check | `app/models_revive.py` |
| **AR-12** | **Timeout Handling** | [ ] Pending | Manual | `app/services/agentic/troubleshoot_native_agent.py` |
| **AR-13** | **Q&A Support** | [x] Implemented | Unit Test | `app/services/agentic/troubleshoot_native_agent.py` |
| **AR-14** | **Output Truncation** | [x] Implemented | Unit Test | `app/services/ssh_service.py` |
| **AR-15** | **Error Detection** | [x] Implemented | Unit Test | `app/services/agentic/troubleshoot_native_agent.py` |
| **AR-16** | **Session Isolation** | [x] Implemented | Security Test | `app/routers/troubleshoot_api.py` |
| **AR-17** | **Max Steps Limit** | [x] Implemented | Unit Test | `app/services/agentic/troubleshoot_native_agent.py` |
| **AR-18** | **5-Phase Protocol** | [x] Implemented | System Prompt | `troubleshoot_native_agent.py` (System Prompt) |
| **AR-19** | **Anti-Hallucination** | [x] Implemented | System Prompt | `troubleshoot_native_agent.py` |
| **AR-20** | **Runbook Linking** | [x] Implemented | Unit Test | `troubleshoot_native_agent.py` (`_extract_runbook_view_links`) |
| **AR-21** | **Suggestions** | [x] Implemented | UI Test | `troubleshoot_native_agent.py` & `alert_detail.html` |

## 2. UI/UX Requirements
*Reference: `docs/requirements/ui_ux_requirements.md`*

| Req ID | Requirement | Status | Implemented In |
| :--- | :--- | :--- | :--- |
| **UI-GN-01** | Responsive Layout | [x] Implemented | `static/css/index.css` |
| **UI-GN-02** | Dark Mode Default | [x] Implemented | `static/css/colors.css` |
| **UI-GN-03** | Loading Indicators | [x] Implemented | `static/js/common.js` |
| **UI-CT-01** | **Dropdown Tick Mark** | [ ] Pending | `templates/` (Needs Update) |
| **UI-TR-01** | Web Terminal (xterm) | [x] Implemented | `static/js/terminal.js` |
| **UI-TR-03** | Inline Chat Overlay | [x] Implemented | `templates/alert_detail.html` |
| **UI-CT-03** | **Smart Suggestions** | [x] Implemented | `templates/alert_detail.html` (JS) |
| **UI-GN-04** | **Builder Mode Hint** | [x] Implemented | `app/services/revive_orchestrator.py` |

## 3. Core Functional Requirements
*Reference: `docs/requirements/core_functional_requirements.md`*

| Req ID | Requirement | Status | Implemented In |
| :--- | :--- | :--- | :--- |
| **FR-AL-01** | Alert Ingestion | [x] Implemented | `app/routers/webhook.py` |
| **FR-AL-02** | Rules Engine | [x] Implemented | `app/services/rules_engine.py` |
| **FR-RV-01** | Provider Agnostic | [x] Implemented | `app/services/llm_service.py` |
| **FR-RV-04** | Grafana MCP | [x] Implemented | `app/routers/revive_grafana.py` |
| **FR-IN-01** | Natural Language Search| [x] Implemented | `app/services/agentic/inquiry_orchestrator.py` |
| **FR-AD-01** | Security (Encryption) | [x] Implemented | `app/utils/security.py` |
