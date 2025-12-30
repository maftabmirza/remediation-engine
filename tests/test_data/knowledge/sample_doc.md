# Remediation Engine Architecture

## Overview

The AIOps Remediation Engine is an intelligent incident response and automation platform that integrates with monitoring systems like Prometheus and Grafana to automatically analyze and remediate infrastructure issues.

## System Components

### 1. Core Application (FastAPI)

The main application is built with FastAPI and provides:
- RESTful API endpoints
- WebSocket support for real-time updates
- Authentication and authorization (JWT-based)
- Database integration (PostgreSQL with SQLAlchemy)

**Technology Stack**:
- Python 3.9+
- FastAPI
- SQLAlchemy ORM
- Pydantic for data validation

### 2. Alert Ingestion System

Receives alerts from monitoring systems via webhooks.

**Supported Sources**:
- Alertmanager (Prometheus)
- Grafana Alerts
- Custom webhooks

**Processing Flow**:
1. Webhook receives alert
2. Alert validated and normalized
3. Rule matching executed
4. Action determined (analyze, remediate, ignore)
5. Alert stored in database

### 3. AI Analysis Engine

Leverages Large Language Models (LLMs) to analyze alerts and suggest remediation actions.

**Supported Providers**:
- Anthropic Claude
- OpenAI GPT-4
- Google Gemini

**Features**:
- Root cause analysis
- Impact assessment
- Remediation suggestions
- Knowledge base integration

### 4. Remediation Execution Engine

Executes runbooks to automatically or semi-automatically resolve incidents.

**Executor Types**:
- SSH Command Execution
- PowerShell Remote Execution
- REST API Calls
- Python Scripts

**Safety Features**:
- Approval workflows
- Rate limiting
- Circuit breaker pattern
- Blackout windows
- Rollback capability

### 5. Knowledge Base

Stores operational documentation for context-aware AI analysis.

**Features**:
- Document upload (Markdown, PDF, images)
- Semantic search (vector embeddings)
- Full-text search
- Image analysis (architecture diagrams)

**Technology**:
- PostgreSQL pgvector extension
- Sentence transformers for embeddings
- OCR for image text extraction

### 6. Rules Engine

Matches incoming alerts to rules and determines appropriate actions.

**Pattern Matching**:
- Wildcard patterns (*, ?)
- JSON Logic for complex conditions
- Priority-based rule selection

**Actions**:
- Auto-analyze
- Trigger runbook
- Notify only
- Ignore

## Data Flow

```
┌─────────────┐
│ Prometheus  │
│AlertManager │
└─────┬───────┘
      │ Webhook
      ▼
┌─────────────────────┐
│  Alert Ingestion    │
│  (/webhook/alerts)  │
└─────────┬───────────┘
          │
          ▼
    ┌─────────────┐
    │ Rules Engine│
    └─────┬───────┘
          │
    ┌─────┴──────────┬─────────────┐
    │                │             │
    ▼                ▼             ▼
┌────────┐    ┌──────────┐   ┌────────┐
│Analyze │    │ Runbook  │   │ Ignore │
│ w/ AI  │    │Execution │   │        │
└────────┘    └──────────┘   └────────┘
```

## Database Schema

### Core Tables

1. **users** - User accounts and authentication
2. **alerts** - Ingested alerts
3. **rules** - Alert matching rules
4. **runbooks** - Remediation procedures
5. **runbook_steps** - Individual runbook steps
6. **executions** - Runbook execution records
7. **design_documents** - Knowledge base documents
8. **document_chunks** - Chunked document content with embeddings

### Relationships

- Alerts → Rules (many-to-one)
- Runbooks → Steps (one-to-many)
- Executions → Runbooks (many-to-one)
- Executions → Step Results (one-to-many)
- Documents → Chunks (one-to-many)

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/refresh` - Refresh JWT token

### Alerts
- `GET /api/alerts` - List alerts
- `GET /api/alerts/{id}` - Get alert details
- `POST /api/alerts/{id}/analyze` - Analyze alert
- `POST /webhook/alerts` - Alertmanager webhook

### Remediation
- `GET /api/remediation/runbooks` - List runbooks
- `POST /api/remediation/runbooks` - Create runbook
- `POST /api/remediation/runbooks/{id}/execute` - Execute runbook
- `GET /api/remediation/executions` - List executions

### Knowledge Base
- `POST /api/knowledge/documents` - Upload document
- `POST /api/knowledge/search` - Search documents
- `GET /api/knowledge/documents` - List documents

## Deployment Architecture

### Production Setup

```
                    ┌──────────────┐
                    │ Load Balancer│
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     ┌────▼───┐       ┌────▼───┐      ┌────▼───┐
     │  App   │       │  App   │      │  App   │
     │Instance│       │Instance│      │Instance│
     └────┬───┘       └────┬───┘      └────┬───┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼───────┐
                    │  PostgreSQL  │
                    │   (Primary)  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  PostgreSQL  │
                    │  (Replica)   │
                    └──────────────┘
```

### Container Deployment

- **Docker**: Dockerfile included
- **Docker Compose**: Multi-service orchestration
- **Environment Variables**: Configuration via .env

## Security Considerations

### Authentication
- JWT tokens with expiration
- Password hashing (bcrypt)
- Role-based access control (RBAC)

### Data Protection
- Encrypted credentials storage
- SSH key encryption
- API token encryption

### Network Security
- HTTPS enforcement
- CORS configuration
- Rate limiting

## Monitoring and Observability

### Metrics
- API request metrics (Prometheus format)
- Execution success/failure rates
- LLM API usage tracking

### Logging
- Structured JSON logging
- Log levels (DEBUG, INFO, WARNING, ERROR)
- Request/response logging

### Health Checks
- Database connectivity
- LLM provider availability
- Disk space monitoring

## Scaling Considerations

### Horizontal Scaling
- Stateless application design
- Load balancer distribution
- Database connection pooling

### Performance Optimization
- Database indexes
- Query optimization
- Caching layer (Redis - optional)
- Async processing

## Future Enhancements

1. **Multi-tenancy support**
2. **Advanced analytics dashboard**
3. **Machine learning for pattern detection**
4. **Integration with more ITSM platforms**
5. **Mobile app for approvals**

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://www.sqlalchemy.org/)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [Anthropic Claude API](https://www.anthropic.com/api)
