# AIOps Remediation Engine

An intelligent, AI-powered operations platform designed to streamline incident response and automated remediation. The platform integrates with your existing monitoring stack (Prometheus, Grafana, Loki, Tempo, Alertmanager) to provide automated root cause analysis, actionable remediation steps, runbook automation, and interactive tools for resolving issues.

## Key Features

### Intelligent Alert Analysis
- Automatically analyzes incoming alerts using state-of-the-art LLMs (Claude, GPT-4, Gemini, Llama, Ollama)
- Flexible rules engine to determine which alerts require immediate AI attention
- Alert clustering and correlation to identify related issues

### Runbook Automation
- Create and manage automated runbooks with step-by-step remediation procedures
- Support for branching logic, conditionals, and loops in runbooks
- Native agentic execution with ReAct agent framework
- SSH and WinRM execution capabilities for remote command execution
- Changeset management for tracking infrastructure changes

### Full LGTM Observability Stack
- **Prometheus** - Metrics collection with 15-day retention
- **Grafana Enterprise** - SSO-enabled, white-labeled dashboards with iframe embedding
- **Loki** - Log aggregation with programmatic query access
- **Tempo** - Distributed tracing with OTLP support
- **Mimir** - Long-term metrics storage
- **Alertmanager** - Alert routing and management

### Dashboard Builder
- Drag-and-drop dashboard creation with GridStack.js
- CodeMirror-based PromQL editor with syntax highlighting
- Multiple panel types: Graph, Stat, Gauge, Table, Heatmap, Bar, Pie
- Template variables with chaining support
- Dashboard snapshots and playlists with kiosk mode
- Fine-grained permissions and access control

### Interactive Remediation
- **Web Terminal**: Secure, browser-based SSH access to your infrastructure
- **AI Chat Assistant**: Context-aware chat interface for discussing alerts and potential fixes
- **Knowledge Base**: Store and search organizational knowledge for AI-enhanced responses

### Enterprise Security
- JWT-based authentication with role-based access control
- Encrypted storage for sensitive credentials (API keys, SSH keys) using Fernet encryption
- Production/test environment isolation with comprehensive security checks
- Audit logging for compliance tracking

## System Architecture

### Core Components

1. **API Layer (FastAPI)**: High-performance, async-ready REST API handling all client requests, webhooks, and WebSocket connections
2. **Service Layer**:
   - **Rules Engine**: Evaluates alerts against user-defined patterns (Regex/Wildcard)
   - **LLM Service**: Abstraction layer using LiteLLM to communicate with various AI providers
   - **Agentic Framework**: ReAct and Native agents for automated runbook execution
   - **SSH/WinRM Services**: Secure remote execution on target infrastructure
   - **Auth Service**: User management and JWT token generation/validation
3. **Data Layer (PostgreSQL)**: Persistent storage with pgvector extension for embeddings
4. **Frontend (Jinja2)**: Server-side rendered templates with modern JavaScript

### Technology Stack

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.12+ |
| **Web Framework** | FastAPI, Uvicorn |
| **Database** | PostgreSQL 16 with pgvector |
| **ORM/Migrations** | SQLAlchemy, Alembic |
| **AI/ML** | LiteLLM, LangChain, Anthropic SDK |
| **Security** | python-jose (JWT), Passlib (bcrypt), Cryptography (Fernet) |
| **Infrastructure** | Docker, Docker Compose |
| **Observability** | Prometheus, Grafana, Loki, Tempo, Mimir, Alertmanager |
| **Remote Execution** | AsyncSSH, pywinrm |

## Workflow

The platform follows a streamlined event-driven workflow:

1. **Ingestion**: Prometheus/Alertmanager detects an issue and sends a JSON payload to the `/webhook/alerts` endpoint
2. **Evaluation**: The Rules Engine matches alert metadata against configured auto-analyze rules
3. **Analysis**: The LLM Service constructs a context-rich prompt and queries the configured LLM provider
4. **Remediation**: SREs review analysis, execute runbooks, or use the web terminal for immediate troubleshooting

## Project Structure

```
.
├── app/
│   ├── routers/           # API Endpoints (50+ routers)
│   │   ├── alerts.py      # Alert management
│   │   ├── remediation.py # Runbook execution
│   │   ├── webhook.py     # Alertmanager ingestion
│   │   ├── terminal_ws.py # WebSocket for Web Terminal
│   │   ├── dashboards_api.py # Dashboard CRUD
│   │   ├── grafana_proxy.py # Grafana SSO proxy
│   │   └── ...
│   ├── services/          # Business Logic (60+ services)
│   │   ├── llm_service.py     # AI Provider integration
│   │   ├── rules_engine.py    # Pattern matching
│   │   ├── runbook_executor.py # Runbook automation
│   │   ├── agentic/           # Agentic framework
│   │   │   ├── native_agent.py
│   │   │   ├── react_agent.py
│   │   │   └── tool_registry.py
│   │   └── ...
│   ├── models*.py         # SQLAlchemy Database Models
│   ├── schemas*.py        # Pydantic Data Schemas
│   └── main.py            # Application Entry Point
├── templates/             # Jinja2 HTML Templates
├── static/                # CSS, JavaScript, Assets
├── tests/                 # Comprehensive Test Suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── e2e/              # End-to-end tests
│   └── security/         # Security tests
├── alembic/              # Database Migrations
├── docs/                 # Documentation
├── prometheus/           # Prometheus Configuration
├── grafana/              # Grafana Provisioning
├── loki/                 # Loki Configuration
├── tempo/                # Tempo Configuration
└── docker-compose.yml    # Service Orchestration
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An LLM API Key (Anthropic, OpenAI, or Google) OR a running Ollama instance

### Deployment

1. **Clone the repository**
   ```bash
   git clone https://github.com/maftabmirza/remediation-engine.git
   cd remediation-engine
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and API keys
   ```

3. **Launch Services**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. **Access the Platform**
   - **UI**: `http://localhost:8080`
   - **API Docs**: `http://localhost:8080/docs`
   - **Grafana**: `http://localhost:8080/grafana`
   - **Default Login**: `admin` / (password set in .env)

## Docker Services

The platform runs the following services via Docker Compose:

| Service | Port | Description |
|---------|------|-------------|
| `remediation-engine` | 8080 | Main application |
| `postgres` | 5432 | PostgreSQL database with pgvector |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Visualization (SSO via proxy) |
| `loki` | 3100 | Log aggregation |
| `tempo` | 3200 | Distributed tracing |
| `mimir` | 9009 | Long-term metrics storage |
| `alertmanager` | 9093 | Alert management |

## Alertmanager Integration

Add this receiver to your `alertmanager.yml` to route alerts to the engine:

```yaml
receivers:
  - name: 'remediation-engine'
    webhook_configs:
      - url: 'http://<your-server-ip>:8080/webhook/alerts'
        send_resolved: true
```

## Documentation

- **[User Guide](USER_GUIDE.md)**: How to use the dashboard, manage alerts, and use the AI assistant
- **[Developer Guide](DEVELOPER_GUIDE.md)**: Setup instructions, architecture overview, and contribution guidelines
- **[Testing Guide](TESTING_QUICKSTART.md)**: How to run and write tests
- **[Database Schema](DATABASE_SCHEMA.md)**: Complete database documentation
- **[docs/](docs/)**: Additional planning and architecture documentation

## Testing

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest tests/unit -v
pytest tests/integration -v
```

## Security

This platform is designed with enterprise security in mind:

- **API Keys**: Stored encrypted in the database using Fernet encryption
- **SSH Keys**: Stored encrypted; never exposed to the client
- **Access Control**: Role-based access (Admin/User) protects sensitive settings
- **Production Isolation**: Comprehensive security checks prevent test data in production
- **Audit Logging**: Track all user actions for compliance

## License

**Proprietary / Non-Commercial Use Only**

This software is licensed for personal, non-commercial use only. Commercial use is strictly prohibited without prior written permission from the copyright holder. See the [LICENSE](LICENSE) file for details.
