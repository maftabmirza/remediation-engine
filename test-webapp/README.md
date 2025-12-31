# AIOps Test Management WebApp

Comprehensive test management system for the AIOps Remediation Engine platform. This application provides a centralized platform for managing, executing, and monitoring end-to-end tests for automated remediation workflows.

## Features

### Core Capabilities

- **Test Case Management**: Create, organize, and manage test cases across multiple categories
- **Test Execution**: Execute tests manually, on schedule, or via API/webhook triggers
- **Real-time Monitoring**: Track test execution in real-time with live status updates
- **Results Dashboard**: Visualize test metrics, trends, and success rates
- **Webhook Integration**: Receive test results from pytest custom reporter
- **Alert-Triggered Testing**: Automatically execute tests when specific alerts fire

### Test Categories

- **Linux Remediation**: Tests for Linux system remediation scenarios (CPU, memory, disk)
- **Safety Mechanisms**: Tests for rate limiting, concurrent execution, and dangerous operation prevention
- **Approval Workflows**: Tests for approval and authorization processes
- **Windows Remediation**: Tests for Windows system remediation (optional)

## Architecture

### Technology Stack

- **Backend**: FastAPI (async Python web framework)
- **Database**: PostgreSQL with asyncpg driver
- **ORM**: SQLAlchemy 2.0 (async support)
- **Frontend**: HTMX + Alpine.js + Tailwind CSS
- **Charts**: Chart.js for data visualization
- **Testing**: Pytest with custom reporter plugin
- **Migrations**: Alembic for database schema management

### Project Structure

```
test-webapp/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database connection
│   ├── api/                 # API routes
│   │   ├── dashboard.py     # Dashboard endpoints
│   │   ├── test_cases.py    # Test case CRUD
│   │   ├── test_runs.py     # Test run management
│   │   └── webhook.py       # Webhook receivers
│   ├── models/              # SQLAlchemy models
│   │   ├── test_suite.py
│   │   ├── test_case.py
│   │   ├── test_run.py
│   │   ├── test_result.py
│   │   ├── test_schedule.py
│   │   └── test_alert_link.py
│   ├── services/            # Business logic
│   │   └── executor.py      # Test execution service
│   └── templates/           # HTML templates
│       ├── base.html
│       ├── dashboard.html
│       ├── test_cases.html
│       ├── test_runs.html
│       └── test_run_details.html
├── tests/
│   ├── conftest.py          # Pytest configuration
│   └── e2e/                 # End-to-end tests
│       ├── linux/           # Linux remediation tests
│       ├── safety/          # Safety mechanism tests
│       ├── approval/        # Approval workflow tests
│       └── windows/         # Windows remediation tests
├── scripts/
│   ├── init_db.py           # Database initialization
│   └── run_tests.sh         # Test execution script
├── alembic/                 # Database migrations
├── docker-compose.yml       # Docker services
├── Dockerfile               # Application container
└── requirements.txt         # Python dependencies
```

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optional)

### Quick Start with Docker

1. **Clone the repository**:
   ```bash
   git clone https://github.com/maftabmirza/aiops-testing-webapp.git
   cd test-webapp
   ```

2. **Start services**:
   ```bash
   docker-compose up -d
   ```

3. **Initialize database**:
   ```bash
   docker-compose exec webapp python scripts/init_db.py
   ```

4. **Access the application**:
   - Web UI: http://localhost:8001
   - API Docs: http://localhost:8001/docs

### Manual Installation

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Set up database**:
   ```bash
   # Create PostgreSQL database
   createdb aiops_test_manager

   # Run migrations
   alembic upgrade head

   # Seed initial data
   python scripts/init_db.py
   ```

5. **Start application**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

## Usage

### Managing Test Cases

1. Navigate to **Test Cases** page
2. Filter by category, priority, or status
3. Click **New Test Case** to create a test
4. Fill in test details:
   - Test ID (e.g., L01, S01)
   - Name and description
   - Test file path and function
   - Priority and timeout
   - Tags for organization

### Executing Tests

#### Manual Execution

1. Go to **Test Runs** page
2. Click **New Test Run**
3. Select test suite or individual tests
4. Click **Run**

#### Via Script

```bash
# Run all tests
./scripts/run_tests.sh

# Run specific suite
./scripts/run_tests.sh --suite linux

# Run specific test
./scripts/run_tests.sh --test-id L01

# With webhook reporting
./scripts/run_tests.sh --run-id 123 --webhook-url http://localhost:8001/webhook/pytest-results
```

#### Via API

```bash
curl -X POST http://localhost:8001/test-runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "suite_id": 1,
    "trigger": "manual",
    "triggered_by": "user@example.com"
  }'
```

### Viewing Results

1. **Dashboard**: Overview with charts and statistics
2. **Test Runs**: List of all test executions with filters
3. **Test Run Details**: Detailed results for individual runs

### Custom Pytest Reporter

The custom pytest plugin automatically reports results to the webapp:

```bash
# pytest automatically uses the custom reporter
pytest tests/e2e/linux/ --run-id=123 --webhook-url=http://localhost:8001/webhook/pytest-results
```

## API Documentation

### Endpoints

#### Dashboard
- `GET /dashboard/stats` - Get dashboard statistics
- `GET /dashboard/trends` - Get test execution trends
- `GET /dashboard/category-breakdown` - Get tests by category

#### Test Cases
- `GET /test-cases/list` - List test cases
- `GET /test-cases/{id}` - Get test case details
- `POST /test-cases/` - Create test case
- `PUT /test-cases/{id}` - Update test case
- `DELETE /test-cases/{id}` - Delete test case

#### Test Runs
- `GET /test-runs/list` - List test runs
- `GET /test-runs/{id}` - Get test run details
- `POST /test-runs/` - Create and execute test run
- `POST /test-runs/{id}/cancel` - Cancel running test
- `DELETE /test-runs/{id}` - Delete test run

#### Webhooks
- `POST /webhook/pytest-results` - Receive pytest results
- `POST /webhook/alert-triggered` - Handle alert webhooks

Full API documentation available at: http://localhost:8001/docs

## Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=aiops_test_manager
POSTGRES_USER=aiops
POSTGRES_PASSWORD=aiops_secure_password

# Application
DEBUG=false
HOST=0.0.0.0
PORT=8001

# Remediation Engine
REMEDIATION_ENGINE_URL=http://localhost:8080

# Test Execution
TEST_TIMEOUT=300
MAX_CONCURRENT_TESTS=5

# Redis (for background jobs)
REDIS_HOST=redis
REDIS_PORT=6379
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific category
pytest tests/e2e/linux/

# Verbose output
pytest -v
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Show current version
alembic current
```

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
pylint app/

# Type checking
mypy app/
```

## Deployment

### Docker Production Build

```bash
docker build -t aiops-test-webapp:latest .
docker run -p 8001:8001 aiops-test-webapp:latest
```

### Production Considerations

1. **Database**: Use managed PostgreSQL service
2. **Secrets**: Use environment-specific secrets management
3. **Scaling**: Run multiple webapp instances behind load balancer
4. **Monitoring**: Add APM and logging solutions
5. **Backups**: Regular database backups
6. **SSL**: Use HTTPS in production

## Troubleshooting

### Common Issues

**Database connection fails**:
```bash
# Check PostgreSQL is running
docker-compose ps

# Check connection settings
echo $POSTGRES_HOST
```

**Tests not reporting results**:
```bash
# Verify webhook URL is correct
echo $WEBHOOK_URL

# Check webapp logs
docker-compose logs webapp
```

**Migration errors**:
```bash
# Reset database (CAUTION: destroys data)
alembic downgrade base
alembic upgrade head
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see LICENSE file for details

## Support

- Documentation: See `/docs` in repository
- Issues: GitHub Issues
- Email: support@example.com

## Roadmap

- [ ] Scheduled test execution with cron
- [ ] Test result history and trends
- [ ] Integration with CI/CD pipelines
- [ ] Custom test reporters (JUnit, HTML)
- [ ] Test case versioning
- [ ] Advanced filtering and search
- [ ] Email/Slack notifications
- [ ] Performance benchmarking
- [ ] Test data management
- [ ] Multi-tenancy support

---

Built with ❤️ for AIOps platform testing
