# AIOps Remediation Engine - Developer Guide

Welcome to the developer documentation for the AIOps Remediation Engine. This guide is designed to help you understand the codebase, set up your development environment, and contribute to the project.

## 🛠️ Development Setup

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **PostgreSQL** (if running locally without Docker)
- **Git**

### Local Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/maftabmirza/remediation-engine.git
   cd remediation-engine
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   Copy `.env.example` to `.env` and configure your local settings.
   ```bash
   cp .env.example .env
   ```
   For local development, you might want to set `POSTGRES_HOST=localhost` if you are running a local DB, or use the Docker container's mapped port.

5. **Run the Application**
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

### Docker Development

The easiest way to develop is using Docker Compose, which spins up the database and the app.

```bash
# Build and start services
docker compose up --build

# View logs
docker compose logs -f remediation-engine
```

## 🏗️ Project Structure

```
aiops-platform/
├── app/
│   ├── __init__.py
│   ├── main.py             # Application entry point & FastAPI app definition
│   ├── config.py           # Pydantic settings & env var loading
│   ├── database.py         # SQLAlchemy session & engine setup
│   ├── models.py           # Database models (Users, Alerts, Rules)
│   ├── models_chat.py      # Chat-specific database models
│   ├── schemas.py          # Pydantic schemas for API request/response
│   ├── routers/            # API Route Controllers
│   │   ├── alerts.py       # Alert management endpoints
│   │   ├── auth.py         # Authentication & Login
│   │   ├── chat_ws.py      # WebSocket for AI Chat
│   │   ├── terminal_ws.py  # WebSocket for SSH Terminal
│   │   ├── webhook.py      # Alertmanager ingestion endpoint
│   │   └── ...
│   └── services/           # Business Logic Layer
│       ├── llm_service.py  # Interface with LiteLLM (Claude, GPT, etc.)
│       ├── rules_engine.py # Pattern matching logic for alerts
│       ├── ssh_service.py  # AsyncSSH wrapper for terminal sessions
│       └── auth_service.py # JWT handling and user CRUD
├── static/                 # CSS, JS, Images
├── templates/              # Jinja2 HTML Templates
├── storage/                # Local storage for recordings/logs
├── deploy.sh               # Deployment script
├── docker-compose.yml      # Container orchestration
└── requirements.txt        # Python dependencies
```

## 🧩 Key Components & Extensibility

### 1. Adding a New LLM Provider

The platform uses `LiteLLM` to abstract provider differences. To add a new provider type (if not already supported by LiteLLM's auto-detection):

1.  Update `app/models.py`: Add the provider type to any validation logic if necessary.
2.  Update `app/services/llm_service.py`:
    -   Modify `get_api_key_for_provider` to retrieve the new provider's key.
    -   Update `analyze_alert` to handle any specific parameter mapping for the new provider.

### 2. Modifying the Rules Engine

The rules engine (`app/services/rules_engine.py`) currently supports Regex and Wildcard matching.

-   **Adding a new match type**:
    -   Update `AutoAnalyzeRule` model in `app/models.py` to store the new pattern field.
    -   Update `match_rule` in `app/services/rules_engine.py` to implement the logic.

### 3. WebSockets & Real-time Features

-   **Chat**: Handled in `app/routers/chat_ws.py`. It uses LangChain to manage conversation history and context.
-   **Terminal**: Handled in `app/routers/terminal_ws.py`. It bridges a WebSocket connection to an SSH process using `asyncssh`.

## 🧪 Testing

Currently, the project relies on manual testing. We encourage adding automated tests.

### Recommended Test Stack
-   **Pytest**: Test runner.
-   **TestClient** (from FastAPI): For API integration tests.
-   **Pytest-Asyncio**: For async function testing.

### Running Tests (Future)
```bash
pytest
```

## 📝 Contribution Guidelines

1.  **Fork the repository**.
2.  **Create a feature branch**: `git checkout -b feature/my-new-feature`.
3.  **Commit your changes**: `git commit -m 'Add some feature'`.
4.  **Push to the branch**: `git push origin feature/my-new-feature`.
5.  **Open a Pull Request**.

### Code Style
-   Follow **PEP 8**.
-   Use **Type Hints** for function arguments and return values.
-   Ensure **Docstrings** are present for all modules, classes, and complex functions.

## 🔒 Security Considerations

-   **Secrets**: Never commit `.env` files. Ensure `gitignore` is respected.
-   **Input Validation**: Always use Pydantic schemas to validate incoming data.
-   **SSH**: The `SSHClient` in `ssh_service.py` handles sensitive connections. Ensure keys are decrypted only in memory and never logged.

## 📚 API Documentation

When the application is running, interactive API documentation is available at:
-   **Swagger UI**: `http://localhost:8080/docs`
-   **ReDoc**: `http://localhost:8080/redoc`
