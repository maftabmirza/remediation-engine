# GitHub Copilot Instructions

## Project Overview

This is the Remediation Engine - an automated incident response and remediation system.

## Development Environment

### Local Development Setup

- **Operating System**: Windows laptop
- **Container Runtime**: Local Docker running on Windows
- **Docker Compose**: Used for orchestrating multi-container setup

### Running the Application Locally

```bash
# Start all services with Docker Compose
- Follow PEP 8 style guidelines

- PostgreSQL database with migrations
# GitHub Copilot Instructions

## Project Overview

This is the Remediation Engine — an automated incident response and remediation system.

## Development Environment

### Local Development Setup (Windows)

- **Operating System**: Windows laptop
- **Container Runtime**: Docker Desktop for Windows (recommended)
- **WSL2**: Enable WSL2 and use Linux containers for best compatibility
- **Docker Compose**: Project uses both `docker compose` (v2) and `docker-compose` in scripts — both are supported on Windows when Docker Desktop is installed.

### Prerequisites

- `Python 3.11+`
- `Docker Desktop` (with WSL2 backend recommended)
- `Docker Compose` (v2 included with Docker Desktop)
- `Git`

### Quick Start — Windows (PowerShell)

1. Clone the repo and enter it:

```powershell
git clone https://github.com/maftabmirza/remediation-engine.git
cd remediation-engine
```

2. (Optional) Create & activate a venv for local Python development:

```powershell
python -m venv venv
venv\Scripts\activate
```

3. Copy environment example and edit `.env` as needed:

```powershell
copy .env.example .env
```

4. Build & run with Docker Compose (preferred):

```powershell
# Using Docker Compose v2 command
docker compose up --build -d

# Fallback to legacy command if scripts use it
docker-compose up -d
```

5. View logs and run DB migrations (example):

```powershell
docker compose logs -f remediation-engine
docker compose exec remediation-engine alembic upgrade head
```

Notes:
- Some helper scripts (e.g. `setup_local.ps1`) call `docker-compose up -d --build` and then run DB migrations; use PowerShell to execute those scripts.
- If you use WSL2, run Docker commands in WSL or enable integration for your distro in Docker Desktop.

### Running Tests (Docker)

The project includes a `docker-compose.test.yml` used for test orchestration. Example:

```powershell
docker compose -f docker-compose.test.yml up --build -d
# or
docker-compose -f docker-compose.test.yml up --build -d
```

Unit/functional tests may also be executed inside the test container or locally with `pytest` if dependencies are installed.

## Key Configuration Files

- `docker-compose.yml` — Main Docker Compose configuration
- `docker-compose.test.yml` — Test environment configuration
- `Dockerfile` — Production application image
- `Dockerfile.test` — Test-only image
- `setup_local.ps1` — Windows helper script that bootstraps local dev environment and runs migrations

## Python / Local Run (non-Docker)

You can run the app directly for iteration/debugging:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

API docs available when running locally:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## Conventions & Notes

- Language: Python 3.11+; follow PEP 8 and use type hints.
- Tests: follow `test_*.py` naming; project uses `docker-compose.test.yml` for CI-like test runs.
- Secrets: never commit `.env`; use `.env.example` as a template.

## Troubleshooting Tips (Windows)

- Ensure Docker Desktop is running and WSL2 is enabled when using Linux containers.
- If compose commands fail, try the alternative form (`docker compose` vs `docker-compose`).
- Use PowerShell to run repository helper scripts (e.g., `setup_local.ps1`).

## Where to find more details

- Developer guide: `DEVELOPER_GUIDE.md`
- Deployment checklist: `DEPLOYMENT_CHECKLIST.md`
- Docs folder: `docs/`

This file helps Copilot and other tooling provide accurate suggestions for local development on a Windows laptop with Docker.
