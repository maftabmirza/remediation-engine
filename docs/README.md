# Documentation Index

This directory contains planning, architecture, and reference documentation for the AIOps Remediation Engine.

## Quick Navigation

| If you want to... | Read this |
|-------------------|-----------|
| Understand current project status | [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) |
| Learn the full implementation plan | [CONSOLIDATED_IMPLEMENTATION_PLAN.md](./CONSOLIDATED_IMPLEMENTATION_PLAN.md) |
| Use the dashboard builder | [DASHBOARD_BUILDER_USER_GUIDE.md](./DASHBOARD_BUILDER_USER_GUIDE.md) |
| Test dashboard features | [DASHBOARD_TESTING_GUIDE.md](./DASHBOARD_TESTING_GUIDE.md) |
| Set up Prometheus | [PROMETHEUS_CONFIGURATION.md](./PROMETHEUS_CONFIGURATION.md) |
| Present to stakeholders | [EXECUTIVE_PRESENTATION.md](./EXECUTIVE_PRESENTATION.md) |

## Project Status Summary

**Last Updated:** January 2026

### Completed Features

| Component | Status | Description |
|-----------|--------|-------------|
| **Dashboard Builder** | Complete | GridStack drag-drop, PromQL editor, panels, variables, snapshots, playlists |
| **LGTM Observability Stack** | Complete | Prometheus, Loki, Tempo, Mimir, Alertmanager integration |
| **Grafana SSO Integration** | Complete | Iframe embedding, auto user provisioning, white-labeling |
| **Runbook Automation** | Complete | Native and ReAct agent execution, SSH/WinRM support |
| **Alert Management** | Complete | Webhook ingestion, rules engine, clustering, correlation |
| **AI Chat Interface** | Complete | LLM integration, knowledge base, context-aware responses |
| **Security Features** | Complete | JWT auth, encrypted credentials, production isolation |

### In Progress

- Phase 3: Enhanced datasource expansion (Loki/Tempo programmatic access)
- Phase 4: AI query translation (natural language to PromQL/LogQL)
- Phase 5: Enhanced chat UI with split-screen data visualization

## Document Categories

### Implementation & Planning

| Document | Description |
|----------|-------------|
| [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) | Quick status reference with progress bars and checklists |
| [CONSOLIDATED_IMPLEMENTATION_PLAN.md](./CONSOLIDATED_IMPLEMENTATION_PLAN.md) | Master implementation plan with all phases |
| [PLAN_UPDATES_2025-12-26.md](./PLAN_UPDATES_2025-12-26.md) | Plan adjustments and updates |
| [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) | Original dashboard builder roadmap |

### Architecture & Design

| Document | Description |
|----------|-------------|
| [ARCHITECTURE_DIAGRAMS.md](./ARCHITECTURE_DIAGRAMS.md) | System architecture visuals and flow diagrams |
| [AGENTIC_RAG_SUMMARY.md](./AGENTIC_RAG_SUMMARY.md) | Agentic RAG architecture overview |
| [AI_CHAT_PLANNING_README.md](./AI_CHAT_PLANNING_README.md) | AI chat architecture design |
| [AI_TERMINAL_IMPROVEMENT_PLAN.md](./AI_TERMINAL_IMPROVEMENT_PLAN.md) | Terminal enhancement plans |

### Dashboard & Visualization

| Document | Description |
|----------|-------------|
| [DASHBOARD_BUILDER_USER_GUIDE.md](./DASHBOARD_BUILDER_USER_GUIDE.md) | How to use the dashboard builder |
| [DASHBOARD_BUILDER_STATUS.md](./DASHBOARD_BUILDER_STATUS.md) | Dashboard builder feature status |
| [DASHBOARD_TESTING_GUIDE.md](./DASHBOARD_TESTING_GUIDE.md) | Dashboard testing procedures |
| [PROMETHEUS_DASHBOARD_BUILDER.md](./PROMETHEUS_DASHBOARD_BUILDER.md) | Dashboard builder technical docs |
| [ECHARTS_MIGRATION.md](./ECHARTS_MIGRATION.md) | ECharts implementation guide |
| [QUICK_START_DRAG_DROP.md](./QUICK_START_DRAG_DROP.md) | GridStack drag-drop quick start |

### Grafana Integration

| Document | Description |
|----------|-------------|
| [GRAFANA_INTEGRATION_PLAN.md](./GRAFANA_INTEGRATION_PLAN.md) | Grafana integration approach |
| [GRAFANA_AI_CHAT_INTEGRATION_PLAN.md](./GRAFANA_AI_CHAT_INTEGRATION_PLAN.md) | AI chat with Grafana data |
| [GRAFANA_TESTING_GUIDE.md](./GRAFANA_TESTING_GUIDE.md) | Grafana integration testing |
| [GRAFANA_COMPARISON.md](./GRAFANA_COMPARISON.md) | Feature comparison vs Grafana |
| [AI_CHAT_GRAFANA_BRIEF_APPROACH.md](./AI_CHAT_GRAFANA_BRIEF_APPROACH.md) | Brief integration approach |

### Configuration & Operations

| Document | Description |
|----------|-------------|
| [PROMETHEUS_CONFIGURATION.md](./PROMETHEUS_CONFIGURATION.md) | Prometheus setup and configuration |
| [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) | Quick command reference |
| [API_EXECUTION.md](./API_EXECUTION.md) | API execution documentation |
| [API_CREDENTIALS_REFACTOR_GUIDE.md](./API_CREDENTIALS_REFACTOR_GUIDE.md) | Credential management guide |

### Knowledge Base

| Document | Description |
|----------|-------------|
| [kb-ai-analysis.md](./kb-ai-analysis.md) | Knowledge base AI analysis documentation |

### Executive Summary

| Document | Description |
|----------|-------------|
| [EXECUTIVE_PRESENTATION.md](./EXECUTIVE_PRESENTATION.md) | High-level presentation slides |

## Getting Started by Role

### New Developer

1. Read [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) to understand current state
2. Review [CONSOLIDATED_IMPLEMENTATION_PLAN.md](./CONSOLIDATED_IMPLEMENTATION_PLAN.md) for architecture
3. Follow [DASHBOARD_BUILDER_USER_GUIDE.md](./DASHBOARD_BUILDER_USER_GUIDE.md) to see what's built
4. Check [../tests/README.md](../tests/README.md) for testing guidelines

### DevOps/SRE

1. Start with [PROMETHEUS_CONFIGURATION.md](./PROMETHEUS_CONFIGURATION.md) for setup
2. Use [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) for common operations
3. Review [GRAFANA_TESTING_GUIDE.md](./GRAFANA_TESTING_GUIDE.md) for integration testing

### Product Manager

1. Read [EXECUTIVE_PRESENTATION.md](./EXECUTIVE_PRESENTATION.md) for overview
2. Check [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) for progress tracking
3. Review [GRAFANA_COMPARISON.md](./GRAFANA_COMPARISON.md) for competitive analysis

## Related Root-Level Documentation

These documents are in the project root directory:

| Document | Description |
|----------|-------------|
| [../README.md](../README.md) | Main project README |
| [../USER_GUIDE.md](../USER_GUIDE.md) | End-user guide |
| [../DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md) | Developer setup and contribution |
| [../DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) | Complete database documentation |
| [../TESTING_QUICKSTART.md](../TESTING_QUICKSTART.md) | Testing quick start |
| [../TESTING_PLAN.md](../TESTING_PLAN.md) | Comprehensive testing strategy |
| [../TEST_COVERAGE_ANALYSIS.md](../TEST_COVERAGE_ANALYSIS.md) | Test coverage analysis |
| [../DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md) | Deployment checklist |

## Contributing to Documentation

### When to Update

- After completing a phase or major milestone
- When adding new features not in the plan
- After making architecture decisions
- When finding outdated or incorrect information

### Style Guide

**Formatting:**
- Use GitHub-flavored Markdown
- Include code examples where applicable
- Use tables for comparisons and status tracking
- Add diagrams for complex flows (ASCII or Mermaid)

**Status Icons:**
- Complete: Use clear language indicating completion
- In Progress: Note what's being worked on
- Pending: Describe what's planned

## External References

- **Grafana Documentation:** https://grafana.com/docs/
- **Prometheus Documentation:** https://prometheus.io/docs/
- **Loki Documentation:** https://grafana.com/docs/loki/
- **Tempo Documentation:** https://grafana.com/docs/tempo/
- **PromQL Guide:** https://prometheus.io/docs/prometheus/latest/querying/basics/
- **LogQL Guide:** https://grafana.com/docs/loki/latest/logql/
- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **SQLAlchemy Documentation:** https://docs.sqlalchemy.org/
