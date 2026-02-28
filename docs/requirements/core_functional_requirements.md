# Core Functional Requirements

This document outlines the core backend and service-level requirements for the AIOps Remediation Engine (excluding specific specialized AI Agent rules).

## 1. Alert Management System

| Req ID | Requirement | Implementation Details |
| :--- | :--- | :--- |
| **FR-AL-01** | **Alert Ingestion** | The system must accept HTTP POST requests from Prometheus/Alertmanager at `/webhook/alerts` containing JSON payloads. |
| **FR-AL-02** | **Rules Engine** | **Auto-Analyze Rules**: Users must be able to define regex-based rules that trigger automatic AI analysis.<br>**Ignore Rules**: Capability to silence/discard alerts based on patterns. |
| **FR-AL-03** | **Alert Persistence** | All ingested alerts (except ignored ones) must be persisted to the PostgreSQL database with full metadata. |

## 2. AI & Orchestration (RE-VIVE)

| Req ID | Requirement | Implementation Details |
| :--- | :--- | :--- |
| **FR-RV-01** | **Provider Agnostic** | `App/services/llm_service.py` supports OpenAI, Anthropic, Google (Gemini). Uses `litellm` (or direct Anthropic SDK for tool fix). |
| **FR-RV-02** | **Context Gathering** | **Observability**: Fetches log samples (max 3), metric samples (max 5) via `observability_orchestrator`.<br>**Remediation**: Searches `runbook_search_service`. |
| **FR-RV-03** | **Intent Routing** | `ReviveOrchestrator` uses LLM to route query to: `remediation` (Runbooks), `observability` (Metrics/Logs), or `general` (Chat). |
| **FR-RV-04** | **Grafana MCP** | The system must expose an MCP (Model Context Protocol) compatible endpoint for Grafana integration. |

## 3. Inquiry & Knowledge

| Req ID | Requirement | Implementation Details |
| :--- | :--- | :--- |
| **FR-IN-01** | **Natural Language Search** | Users must be able to query the system state ("Show me all critical alerts for db-01") using natural language. |
| **FR-IN-02** | **Read-Only Tools** | The Inquiry Agent must be restricted to **read-only** tools (db select, log read) and never allowed to modify state. |

## 4. Administration

| Req ID | Requirement | Implementation Details |
| :--- | :--- | :--- |
| **FR-AD-01** | **Security** | Secrets encrypted using `cryptography.fernet.Fernet` (Symmetric). Requires `ENCRYPTION_KEY` env var. Implemented in `app/utils/crypto.py`. |
| **FR-AD-02** | **RBAC** | Role-Based Access Control must distinguish between 'Admin' (can change settings) and 'User' (can view/act). |
