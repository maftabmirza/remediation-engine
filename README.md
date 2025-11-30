# AIOps Remediation Engine

An intelligent, AI-powered operations platform designed to streamline incident response. This platform integrates with your existing monitoring stack (Prometheus/Alertmanager) to provide automated root cause analysis, actionable remediation steps, and interactive tools for resolving issues.

## 🚀 Key Features

- **Intelligent Alert Analysis**: Automatically analyzes incoming alerts using state-of-the-art LLMs (Claude, GPT-4, Gemini, Llama).
- **Flexible Rules Engine**: Define custom logic to determine which alerts require immediate AI attention, which can wait, and which should be ignored.
- **Multi-LLM Support**: Vendor-agnostic design via LiteLLM allows you to switch between AI providers or use local models (Ollama) seamlessly.
- **Interactive Remediation**:
    - **Web Terminal**: Secure, browser-based SSH access to your infrastructure for immediate troubleshooting.
    - **AI Chat Assistant**: Context-aware chat interface to discuss alerts and potential fixes with the AI.
- **Secure Design**: Enterprise-grade security with JWT authentication and encrypted storage for sensitive credentials (API keys, SSH keys).
- **Modern UI**: Clean, responsive dashboard for managing alerts, rules, and system settings.

## 🏗️ System Architecture & Design

The platform is built as a robust, modular application using modern Python standards.

### Core Components

1.  **API Layer (FastAPI)**: High-performance, async-ready REST API handling all client requests, webhooks, and WebSocket connections.
2.  **Service Layer**:
    -   **Rules Engine**: Evaluates alerts against user-defined patterns (Regex/Wildcard) to automate workflows.
    -   **LLM Service**: Abstraction layer using `LiteLLM` to communicate with various AI providers.
    -   **SSH Service**: Manages secure, asynchronous SSH connections for the web terminal using `AsyncSSH`.
    -   **Auth Service**: Handles user management and JWT token generation/validation.
3.  **Data Layer (PostgreSQL)**: Persistent storage for alerts, analysis results, user profiles, and encrypted credentials.
4.  **Frontend (Jinja2)**: Server-side rendered templates providing a lightweight, fast, and responsive user interface without the complexity of a heavy SPA framework.

### Technology Stack

-   **Language**: Python 3.12+
-   **Web Framework**: FastAPI, Uvicorn
-   **Database**: PostgreSQL, SQLAlchemy (ORM), Alembic (Migrations)
-   **AI/ML**: LiteLLM, LangChain, Anthropic SDK
-   **Security**: Python-Jose (JWT), Passlib (Bcrypt), Cryptography (Fernet encryption)
-   **Infrastructure**: Docker, Docker Compose
-   **Ops Integration**: AsyncSSH, Prometheus Webhooks

## 🔄 Workflow

The platform follows a streamlined event-driven workflow:

1.  **Ingestion**:
    -   Prometheus/Alertmanager detects an issue and sends a JSON payload to the `/webhook/alerts` endpoint.
2.  **Evaluation**:
    -   The **Rules Engine** intercepts the alert.
    -   It matches the alert's metadata (name, severity, instance, job) against configured **Auto-Analyze Rules**.
    -   **Action Decision**:
        -   `auto_analyze`: The alert is immediately sent to the LLM Service.
        -   `manual`: The alert is saved to the DB for human review.
        -   `ignore`: The alert is discarded (noise reduction).
3.  **Analysis (AI Loop)**:
    -   If triggered, the **LLM Service** constructs a context-rich prompt including the alert's summary, description, and labels.
    -   It queries the configured Default LLM Provider (e.g., Claude 3.5 Sonnet).
    -   The AI returns a structured analysis: **Root Cause**, **Impact**, **Immediate Actions**, and **Remediation Steps**.
4.  **Remediation**:
    -   **Review**: SREs view the alert and the AI's analysis on the dashboard.
    -   **Interact**: SREs can launch a **Web Terminal** session directly to the affected server to execute the recommended commands.
    -   **Refine**: SREs can use the **Chat** feature to ask follow-up questions to the AI about the specific alert context.

## 📦 Modules & Structure

```
app/
├── routers/            # API Endpoints & Controllers
│   ├── alerts.py       # Alert management
│   ├── rules.py        # Rule configuration
│   ├── webhook.py      # Alertmanager ingestion
│   ├── terminal_ws.py  # WebSocket for Web Terminal
│   └── ...
├── services/           # Business Logic
│   ├── llm_service.py  # AI Provider integration
│   ├── rules_engine.py # Pattern matching logic
│   ├── ssh_service.py  # SSH connection management
│   └── ...
├── models.py           # SQLAlchemy Database Models
├── schemas.py          # Pydantic Data Schemas
└── main.py             # Application Entry Point
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- An LLM API Key (Anthropic, OpenAI, or Google) OR a running Ollama instance.

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
   nano .env
   ```

3. **Launch Services**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. **Access the Platform**
   - **UI**: `http://localhost:8080`
   - **API Docs**: `http://localhost:8080/docs`
   - **Default Login**: `admin` / (password set in .env)

## 🔌 Integrations

### Alertmanager Configuration

Add this receiver to your `alertmanager.yml` to route alerts to the engine:

```yaml
receivers:
  - name: 'remediation-engine'
    webhook_configs:
      - url: 'http://<your-server-ip>:8080/webhook/alerts'
        send_resolved: true
```

## 🛡️ Security Note

This platform is designed with security in mind.
-   **API Keys**: Stored encrypted in the database.
-   **SSH Keys**: Stored encrypted; never exposed to the client.
-   **Access Control**: Role-based access (Admin/User) protects sensitive settings.

## License

**Proprietary / Non-Commercial Use Only**

This software is licensed for personal, non-commercial use only. Commercial use is strictly prohibited without prior written permission from the copyright holder. See the [LICENSE](LICENSE) file for details.

# remediation-engine
