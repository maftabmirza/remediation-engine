# AIOps Platform v2.0

AI-powered Operations Platform with intelligent alert analysis using multiple LLM providers.

## Features

- **On-demand AI Analysis**: Analyze alerts when you need them, not automatically
- **Rules Engine**: Configure which alerts auto-analyze based on patterns
- **Multi-LLM Support**: Use Claude, GPT-4, Gemini, or local Ollama models
- **Modern Web UI**: Dark theme, responsive design
- **REST API**: Full API with OpenAPI documentation
- **PostgreSQL**: Production-ready database
- **Authentication**: JWT-based auth with user management

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Anthropic API key (or other LLM provider key)

### Deployment

1. **Clone/Copy files to your server**

```bash
scp -r aiops-platform/ user@server:~/
```

2. **Configure environment**

```bash
cd ~/aiops-platform
cp .env.example .env
nano .env  # Edit with your values
```

Required settings:
- `POSTGRES_PASSWORD`: Strong database password
- `JWT_SECRET`: Random 32+ character string
- `ADMIN_PASSWORD`: Initial admin password
- `ANTHROPIC_API_KEY`: Your Claude API key

3. **Deploy**

```bash
chmod +x deploy.sh
./deploy.sh
```

4. **Access the platform**

- Web UI: `http://your-server:8080`
- API Docs: `http://your-server:8080/docs`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AIOps Platform v2                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │ Prometheus  │───►│ Alertmanager│───►│  Remediation Engine │  │
│  └─────────────┘    └─────────────┘    │                     │  │
│                                         │  ┌───────────────┐ │  │
│                                         │  │ Rules Engine  │ │  │
│                                         │  └───────────────┘ │  │
│                                         │                     │  │
│                                         │  ┌───────────────┐ │  │
│                                         │  │ LLM Router    │ │  │
│                                         │  │ (LiteLLM)     │ │  │
│                                         │  └───────┬───────┘ │  │
│                                         └──────────┼─────────┘  │
│                                                    │             │
│                           ┌────────────────────────┼───────┐    │
│                           ▼            ▼           ▼       ▼    │
│                       Claude        GPT-4      Gemini    Llama  │
│                                                                   │
│  ┌─────────────┐                                                 │
│  │ PostgreSQL  │ ◄──── Alert Storage + Rules + Users            │
│  └─────────────┘                                                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Alert Flow

1. **Prometheus** detects metric breach
2. **Alertmanager** receives alert and routes to webhook
3. **Rules Engine** evaluates alert against configured rules
4. Based on rule action:
   - `auto_analyze`: Queue for immediate AI analysis
   - `manual`: Store and wait for user to click "Analyze"
   - `ignore`: Don't store the alert
5. User views alerts in Web UI and analyzes on-demand
6. AI analysis is cached - no duplicate API calls

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user

### Alerts
- `GET /api/alerts` - List alerts (with filters)
- `GET /api/alerts/{id}` - Get single alert
- `POST /api/alerts/{id}/analyze` - Analyze alert with AI
- `DELETE /api/alerts/{id}` - Delete alert
- `GET /api/alerts/stats` - Get statistics

### Rules
- `GET /api/rules` - List rules
- `POST /api/rules` - Create rule
- `PUT /api/rules/{id}` - Update rule
- `DELETE /api/rules/{id}` - Delete rule
- `POST /api/rules/test` - Test rule matching
- `POST /api/rules/{id}/toggle` - Enable/disable rule

### Settings (LLM Providers)
- `GET /api/settings/llm` - List providers
- `POST /api/settings/llm` - Add provider
- `PUT /api/settings/llm/{id}` - Update provider
- `DELETE /api/settings/llm/{id}` - Delete provider
- `POST /api/settings/llm/{id}/set-default` - Set as default
- `POST /api/settings/llm/{id}/toggle` - Enable/disable

### Webhook
- `POST /webhook/alerts` - Alertmanager webhook (no auth)

## Alertmanager Configuration

Update your Alertmanager config to send alerts to the platform:

```yaml
receivers:
  - name: 'aiops-platform'
    webhook_configs:
      - url: 'http://remediation-engine:8080/webhook/alerts'
        send_resolved: true
```

## Rules Configuration

Rules are evaluated in priority order (lower number = higher priority).

### Example Rules

1. **Auto-analyze all critical alerts**
   - Priority: 10
   - Severity Pattern: `critical`
   - Action: `auto_analyze`

2. **Auto-analyze production database alerts**
   - Priority: 20
   - Instance Pattern: `prod-db-*`
   - Action: `auto_analyze`

3. **Ignore test environment**
   - Priority: 30
   - Instance Pattern: `test-*`
   - Action: `ignore`

4. **Default: Manual analysis**
   - Priority: 1000
   - All patterns: `*`
   - Action: `manual`

## Adding LLM Providers

### Claude (Default)
- Provider Type: `anthropic`
- Model ID: `claude-sonnet-4-20250514`

### OpenAI GPT-4
- Provider Type: `openai`
- Model ID: `gpt-4-turbo-preview`

### Google Gemini
- Provider Type: `google`
- Model ID: `gemini-pro`

### Local Ollama
- Provider Type: `ollama`
- Model ID: `llama2`
- API Base URL: `http://ollama:11434`

## Management Commands

```bash
# View logs
docker logs -f remediation-engine

# Restart services
docker compose restart

# Stop services
docker compose down

# Database access
docker exec -it aiops-postgres psql -U aiops -d aiops

# Rebuild after code changes
docker compose build --no-cache
docker compose up -d
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| POSTGRES_HOST | Database host | postgres |
| POSTGRES_PORT | Database port | 5432 |
| POSTGRES_DB | Database name | aiops |
| POSTGRES_USER | Database user | aiops |
| POSTGRES_PASSWORD | Database password | (required) |
| JWT_SECRET | JWT signing key | (required) |
| JWT_EXPIRY_HOURS | Token expiry | 24 |
| ADMIN_USERNAME | Initial admin user | admin |
| ADMIN_PASSWORD | Initial admin password | (required) |
| ANTHROPIC_API_KEY | Claude API key | (optional) |
| OPENAI_API_KEY | OpenAI API key | (optional) |
| GOOGLE_API_KEY | Gemini API key | (optional) |
| DEBUG | Enable debug mode | false |

## Troubleshooting

### Application won't start
```bash
docker logs remediation-engine
```

### Database connection issues
```bash
docker logs aiops-postgres
docker exec aiops-postgres pg_isready -U aiops
```

### Webhook not receiving alerts
1. Check Alertmanager config uses correct URL
2. Verify network connectivity: `docker network ls`
3. Check webhook logs: `docker logs remediation-engine | grep webhook`

## License

MIT License
# remediation-engine
