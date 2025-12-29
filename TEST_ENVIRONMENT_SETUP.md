# TEST ENVIRONMENT SETUP GUIDE

**Version**: 1.0
**Date**: 2025-12-29

---

## OVERVIEW

This document outlines all components, servers, and integrations required to set up a complete test environment for the Remediation Engine.

---

## 1. CORE INFRASTRUCTURE

### 1.1 Application Server
**Component**: Remediation Engine Application

**Requirements**:
- Python 3.9+
- FastAPI application
- ASGI server (uvicorn)
- WebSocket support

**Setup**:
```bash
# Clone repository
git clone https://github.com/maftabmirza/remediation-engine.git
cd remediation-engine

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with test configurations

# Run application
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Server Specs**:
- CPU: 4+ cores
- RAM: 8GB minimum, 16GB recommended
- Disk: 50GB minimum
- OS: Linux (Ubuntu 22.04 LTS recommended)

---

### 1.2 Database Server
**Component**: PostgreSQL with pgvector extension

**Requirements**:
- PostgreSQL 14+
- pgvector extension (for vector embeddings)
- Database name: `remediation_engine_test`

**Setup**:
```bash
# Install PostgreSQL
sudo apt-get install postgresql-14 postgresql-contrib

# Install pgvector extension
sudo apt-get install postgresql-14-pgvector

# Create database
sudo -u postgres psql
CREATE DATABASE remediation_engine_test;
CREATE USER test_user WITH ENCRYPTED PASSWORD 'test_password';
GRANT ALL PRIVILEGES ON DATABASE remediation_engine_test TO test_user;

# Enable pgvector extension
\c remediation_engine_test
CREATE EXTENSION vector;
```

**Database Configuration**:
```
# .env file
DATABASE_URL=postgresql://test_user:test_password@localhost:5432/remediation_engine_test
```

**Server Specs**:
- CPU: 4+ cores
- RAM: 8GB minimum
- Disk: 100GB (SSD recommended)
- Backup: Daily snapshots

---

## 2. MONITORING & OBSERVABILITY STACK

### 2.1 Prometheus Server
**Component**: Prometheus for metrics collection

**Requirements**:
- Prometheus 2.40+
- Node exporter for server metrics
- Alert rules configured

**Setup**:
```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-2.40.0.linux-amd64.tar.gz
cd prometheus-2.40.0.linux-amd64

# Configure prometheus.yml
cat > prometheus.yml <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'remediation-engine'
    static_configs:
      - targets: ['localhost:8000']
EOF

# Run Prometheus
./prometheus --config.file=prometheus.yml
```

**Access**: http://localhost:9090

**Server Specs**:
- CPU: 2+ cores
- RAM: 4GB
- Disk: 50GB (time-series data)

**Test Data Requirements**:
- Create sample alert rules
- Generate test metrics
- Configure alerting rules

---

### 2.2 Alertmanager
**Component**: Prometheus Alertmanager for alert routing

**Requirements**:
- Alertmanager 0.25+
- Configured to send alerts to Remediation Engine

**Setup**:
```bash
# Download Alertmanager
wget https://github.com/prometheus/alertmanager/releases/download/v0.25.0/alertmanager-0.25.0.linux-amd64.tar.gz
tar xvfz alertmanager-0.25.0.linux-amd64.tar.gz
cd alertmanager-0.25.0.linux-amd64

# Configure alertmanager.yml
cat > alertmanager.yml <<EOF
global:
  resolve_timeout: 5m

route:
  receiver: 'remediation-engine'
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h

receivers:
  - name: 'remediation-engine'
    webhook_configs:
      - url: 'http://localhost:8000/webhook/alerts'
        send_resolved: true
EOF

# Run Alertmanager
./alertmanager --config.file=alertmanager.yml
```

**Access**: http://localhost:9093

**Test Alerts**:
```yaml
# Create test alert rule in Prometheus
groups:
  - name: test_alerts
    interval: 30s
    rules:
      - alert: HighCPUUsage
        expr: node_cpu_seconds_total > 0.8
        for: 1m
        labels:
          severity: critical
          instance: test-server-01
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is above 80%"
```

---

### 2.3 Grafana
**Component**: Grafana for visualization and datasource integration

**Requirements**:
- Grafana 9.0+
- Configured datasources (Prometheus, Loki, Tempo)

**Setup**:
```bash
# Install Grafana
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

**Access**: http://localhost:3000 (admin/admin)

**Configuration**:
1. Add Prometheus datasource
2. Add Loki datasource
3. Add Tempo datasource
4. Configure API authentication for Remediation Engine integration

**Server Specs**:
- CPU: 2+ cores
- RAM: 2GB
- Disk: 20GB

---

### 2.4 Loki (Log Aggregation)
**Component**: Grafana Loki for log collection and querying

**Setup**:
```bash
# Download Loki
wget https://github.com/grafana/loki/releases/download/v2.8.0/loki-linux-amd64.zip
unzip loki-linux-amd64.zip
chmod +x loki-linux-amd64

# Download Loki config
wget https://raw.githubusercontent.com/grafana/loki/main/cmd/loki/loki-local-config.yaml

# Run Loki
./loki-linux-amd64 -config.file=loki-local-config.yaml
```

**Access**: http://localhost:3100

**Test Data**: Install Promtail to send logs to Loki

**Server Specs**:
- CPU: 2+ cores
- RAM: 4GB
- Disk: 100GB (log storage)

---

### 2.5 Tempo (Distributed Tracing)
**Component**: Grafana Tempo for trace collection

**Setup**:
```bash
# Download Tempo
wget https://github.com/grafana/tempo/releases/download/v2.1.0/tempo_2.1.0_linux_amd64.tar.gz
tar -xvzf tempo_2.1.0_linux_amd64.tar.gz

# Create config
cat > tempo-local.yaml <<EOF
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/traces
EOF

# Run Tempo
./tempo -config.file=tempo-local.yaml
```

**Access**: http://localhost:3200

**Server Specs**:
- CPU: 2+ cores
- RAM: 4GB
- Disk: 50GB

---

## 3. TEST SERVERS FOR RUNBOOK EXECUTION

### 3.1 Linux Test Server #1
**Purpose**: Test Linux command execution, SSH access

**Requirements**:
- Ubuntu 22.04 LTS or CentOS 8+
- SSH server enabled
- sudo access for test user
- Common tools: systemctl, docker, kubectl, etc.

**Setup**:
```bash
# Create test user
sudo useradd -m -s /bin/bash test_runner
sudo usermod -aG sudo test_runner

# Set up SSH key authentication
sudo mkdir -p /home/test_runner/.ssh
sudo cat > /home/test_runner/.ssh/authorized_keys <<EOF
# Paste public key from Remediation Engine
EOF
sudo chown -R test_runner:test_runner /home/test_runner/.ssh
sudo chmod 700 /home/test_runner/.ssh
sudo chmod 600 /home/test_runner/.ssh/authorized_keys

# Install test services
sudo apt-get update
sudo apt-get install -y apache2 nginx docker.io

# Allow passwordless sudo for specific commands (for testing)
echo "test_runner ALL=(ALL) NOPASSWD: /usr/bin/systemctl" | sudo tee /etc/sudoers.d/test_runner
```

**Server Specs**:
- CPU: 2+ cores
- RAM: 4GB
- Disk: 20GB
- Network: Accessible from Remediation Engine server

**Test Services to Install**:
- Apache2 (for restart tests)
- Nginx (for configuration tests)
- Docker (for container tests)
- PostgreSQL (for database tests)

**Hostname**: test-linux-01.example.com
**IP**: 192.168.1.101

---

### 3.2 Linux Test Server #2
**Purpose**: Test production-like scenarios, multi-server orchestration

**Similar setup to Server #1**

**Hostname**: test-linux-02.example.com
**IP**: 192.168.1.102

---

### 3.3 Windows Test Server
**Purpose**: Test Windows command execution via WinRM

**Requirements**:
- Windows Server 2019 or 2022
- WinRM enabled
- PowerShell 5.1+
- Test services (IIS, SQL Server Express)

**Setup**:
```powershell
# Enable WinRM
Enable-PSRemoting -Force
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "*" -Force

# Configure WinRM for HTTP (test only, use HTTPS in production)
winrm set winrm/config/service '@{AllowUnencrypted="true"}'
winrm set winrm/config/service/auth '@{Basic="true"}'

# Create test user
New-LocalUser -Name "test_runner" -Password (ConvertTo-SecureString "TestPass123!" -AsPlainText -Force)
Add-LocalGroupMember -Group "Administrators" -Member "test_runner"

# Install IIS for testing
Install-WindowsFeature -name Web-Server -IncludeManagementTools
```

**Server Specs**:
- CPU: 2+ cores
- RAM: 8GB
- Disk: 40GB
- Network: Accessible from Remediation Engine

**Test Services**:
- IIS (for restart tests)
- Windows Services (for management tests)
- SQL Server Express (for database tests)

**Hostname**: test-win-01.example.com
**IP**: 192.168.1.103

---

## 4. ITSM & INTEGRATION SYSTEMS

### 4.1 ServiceNow Developer Instance
**Purpose**: Test ITSM integration and change correlation

**Setup**:
1. Sign up for ServiceNow Developer instance: https://developer.servicenow.com
2. Request developer instance (free)
3. Configure API access
4. Create test change requests

**Configuration**:
```
Instance URL: https://devXXXXX.service-now.com
Username: admin
Password: (from ServiceNow)
API Endpoint: /api/now/table/change_request
```

**Test Data Requirements**:
- Create 50+ sample change requests
- Assign to different services
- Vary change types (standard, normal, emergency)
- Set timestamps for correlation testing

**Alternative**: If ServiceNow not available, use CSV file imports

---

### 4.2 Jira Test Instance
**Purpose**: Test Jira integration for issue tracking

**Setup**:
1. Create free Jira Cloud account: https://www.atlassian.com/try/cloud/signup
2. Create test project
3. Generate API token

**Configuration**:
```
Base URL: https://your-domain.atlassian.net
Email: your-email@example.com
API Token: (generate from account settings)
Project Key: TEST
```

**Test Data**:
- Create test project "Operations"
- Create 20+ sample issues
- Use labels for filtering
- Set various issue types and priorities

---

### 4.3 GitHub Test Repository
**Purpose**: Test GitHub integration for change events

**Setup**:
1. Create test repository
2. Generate personal access token
3. Configure webhooks (optional)

**Configuration**:
```
Repository: https://github.com/yourorg/test-repo
Token: ghp_xxxxxxxxxxxx
```

**Test Data**:
- Create commits with timestamps
- Create pull requests
- Add release tags

---

## 5. LLM PROVIDERS (API KEYS)

### 5.1 Anthropic Claude
**Purpose**: Primary LLM for AI analysis

**Setup**:
1. Sign up: https://console.anthropic.com
2. Create API key
3. Set up billing (for testing)

**Configuration**:
```
API Key: sk-ant-api03-xxxxx
Model: claude-3-5-sonnet-20241022
Rate Limits: Check account tier
```

**Test Budget**: $50-100 recommended for comprehensive testing

---

### 5.2 OpenAI GPT
**Purpose**: Alternative LLM provider

**Setup**:
1. Sign up: https://platform.openai.com
2. Create API key
3. Set up billing

**Configuration**:
```
API Key: sk-xxxxx
Model: gpt-4-turbo-preview
```

**Test Budget**: $50-100 recommended

---

### 5.3 Google Gemini
**Purpose**: Test Google AI provider

**Setup**:
1. Google Cloud Console: https://console.cloud.google.com
2. Enable Vertex AI API
3. Create service account and key

**Configuration**:
```
Project ID: your-project-id
Location: us-central1
Model: gemini-pro
```

---

### 5.4 Ollama (Local)
**Purpose**: Test local LLM deployment

**Setup**:
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama2
ollama pull mistral

# Run Ollama server
ollama serve
```

**Configuration**:
```
Base URL: http://localhost:11434
Model: llama2
```

**Server Specs** (for Ollama):
- CPU: 8+ cores
- RAM: 16GB minimum (32GB for larger models)
- GPU: Optional but recommended (NVIDIA with CUDA)
- Disk: 50GB for model storage

---

### 5.5 Azure OpenAI
**Purpose**: Test Azure OpenAI integration

**Setup**:
1. Azure Portal: https://portal.azure.com
2. Create Azure OpenAI resource
3. Deploy model
4. Get endpoint and key

**Configuration**:
```
Endpoint: https://your-resource.openai.azure.com
API Key: xxxxx
Deployment: gpt-4-deployment
API Version: 2023-05-15
```

---

## 6. ADDITIONAL INFRASTRUCTURE

### 6.1 Redis (Optional - for caching)
**Purpose**: Cache query results, session data

**Setup**:
```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
```

**Configuration**:
```
REDIS_URL=redis://localhost:6379/0
```

---

### 6.2 Message Queue (Optional - for async tasks)
**Purpose**: Background job processing

**Options**:
- RabbitMQ
- Celery with Redis

**Setup**:
```bash
sudo apt-get install rabbitmq-server
sudo systemctl start rabbitmq-server
```

---

### 6.3 Object Storage (for Knowledge Base files)
**Purpose**: Store PDF files, images, documents

**Options**:
1. **MinIO** (local S3-compatible storage)
```bash
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
./minio server /data --console-address ":9001"
```

2. **AWS S3** (cloud storage)
3. **Local filesystem** (for simple testing)

---

## 7. NETWORK CONFIGURATION

### 7.1 Network Topology
```
Internet
    |
    v
[Load Balancer] (optional)
    |
    v
[Remediation Engine] :8000
    |
    +-- [PostgreSQL] :5432
    +-- [Redis] :6379
    +-- [Prometheus] :9090
    +-- [Alertmanager] :9093
    +-- [Grafana] :3000
    +-- [Loki] :3100
    +-- [Tempo] :3200
    |
    +-- SSH --> [Linux Test Servers] :22
    +-- WinRM --> [Windows Test Server] :5985
    |
    +-- HTTPS --> [External APIs]
                  - ServiceNow
                  - Jira
                  - GitHub
                  - LLM Providers
```

### 7.2 Firewall Rules
```bash
# Remediation Engine
Allow inbound: 8000 (HTTP/HTTPS)
Allow outbound: 443 (HTTPS), 22 (SSH), 5985 (WinRM)

# Database
Allow inbound: 5432 (from app server only)

# Monitoring
Allow inbound: 9090 (Prometheus), 9093 (Alertmanager), 3000 (Grafana)

# Test Servers
Allow inbound: 22 (SSH), 5985 (WinRM) from app server only
```

### 7.3 DNS Configuration
```
remediation-engine.test.local   -> 192.168.1.100
prometheus.test.local           -> 192.168.1.100
grafana.test.local              -> 192.168.1.100
test-linux-01.test.local        -> 192.168.1.101
test-linux-02.test.local        -> 192.168.1.102
test-win-01.test.local          -> 192.168.1.103
```

---

## 8. TEST DATA PREPARATION

### 8.1 Sample Alerts (1000+ alerts)
```python
# Script to generate test alerts
import requests
import random
from datetime import datetime, timedelta

alertnames = ["HighCPUUsage", "HighMemoryUsage", "DiskSpaceLow", "ServiceDown", "HighLatency"]
severities = ["critical", "warning", "info"]
instances = [f"server-{i:02d}" for i in range(1, 21)]
jobs = ["node-exporter", "application", "database", "web-server"]

for i in range(1000):
    alert = {
        "receiver": "remediation-engine",
        "status": random.choice(["firing", "resolved"]),
        "alerts": [{
            "status": random.choice(["firing", "resolved"]),
            "labels": {
                "alertname": random.choice(alertnames),
                "severity": random.choice(severities),
                "instance": random.choice(instances),
                "job": random.choice(jobs)
            },
            "annotations": {
                "summary": f"Test alert {i}",
                "description": f"This is test alert number {i}"
            },
            "startsAt": (datetime.utcnow() - timedelta(minutes=random.randint(1, 60))).isoformat() + "Z",
            "fingerprint": f"fp{i:06d}"
        }]
    }
    requests.post("http://localhost:8000/webhook/alerts", json=alert)
```

### 8.2 Sample Runbooks (50+ runbooks)
- Linux: Restart services, clear logs, check disk space
- Windows: Restart IIS, clear temp files, check services
- API calls: Kubernetes scale, AWS EC2 actions
- Multi-step: Complex troubleshooting workflows

### 8.3 Sample Knowledge Base Documents (100+ docs)
- Architecture diagrams (PDF, PNG)
- Runbook documentation (Markdown)
- API documentation (HTML)
- Configuration examples (YAML)

### 8.4 Sample Users
```sql
-- Admin user
INSERT INTO users (username, email, password_hash, role) VALUES
('test_admin', 'admin@test.com', '$2b$12$...', 'admin');

-- Engineer users (5)
-- Operator users (5)
```

---

## 9. MONITORING & HEALTH CHECKS

### 9.1 Component Health Dashboard
Create Grafana dashboard to monitor:
- Remediation Engine API response times
- Database connection pool
- Alert ingestion rate
- Runbook execution queue
- LLM API latency
- Test server availability

### 9.2 Automated Health Checks
```bash
#!/bin/bash
# health-check.sh

echo "Checking Remediation Engine..."
curl -f http://localhost:8000/health || echo "FAIL"

echo "Checking PostgreSQL..."
pg_isready -h localhost -p 5432 || echo "FAIL"

echo "Checking Prometheus..."
curl -f http://localhost:9090/-/healthy || echo "FAIL"

echo "Checking Grafana..."
curl -f http://localhost:3000/api/health || echo "FAIL"

echo "Checking test servers..."
ssh test_runner@test-linux-01 "echo OK" || echo "FAIL"
```

---

## 10. BACKUP & DISASTER RECOVERY

### 10.1 Database Backups
```bash
# Daily backup script
#!/bin/bash
pg_dump remediation_engine_test > backup_$(date +%Y%m%d).sql
```

### 10.2 Test Data Snapshots
- VM snapshots of test servers
- Database dump before each test run
- Configuration backups

---

## 11. COST ESTIMATION

### Cloud Infrastructure (if using AWS/GCP/Azure)
- **App Server**: t3.large - $60/month
- **Database**: db.t3.medium - $50/month
- **Test Servers** (3x): t3.medium - $90/month
- **Storage**: 200GB - $20/month
- **LLM API calls**: $100-200/month (testing)

**Total**: ~$400-500/month

### On-Premise/Local
- Physical servers or VMs
- Network infrastructure
- No monthly cloud costs (one-time hardware investment)

---

## 12. DEPLOYMENT OPTIONS

### Option 1: Single Server (Development)
- All components on one beefy server
- Docker Compose for orchestration
- Suitable for initial testing

### Option 2: Multi-Server (Staging)
- Separate servers for app, database, monitoring
- Closer to production
- Recommended for comprehensive testing

### Option 3: Kubernetes (Production-like)
- Full Kubernetes deployment
- Auto-scaling, high availability
- Most realistic testing environment

---

## 13. QUICK START SCRIPT

```bash
#!/bin/bash
# quick-setup.sh - Bootstrap test environment

# 1. Install dependencies
sudo apt-get update
sudo apt-get install -y postgresql-14 postgresql-14-pgvector redis-server docker.io

# 2. Set up database
sudo -u postgres psql -c "CREATE DATABASE remediation_engine_test;"
sudo -u postgres psql -c "CREATE USER test_user WITH PASSWORD 'test_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE remediation_engine_test TO test_user;"

# 3. Clone and configure app
git clone https://github.com/maftabmirza/remediation-engine.git
cd remediation-engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Create .env file
cat > .env <<EOF
DATABASE_URL=postgresql://test_user:test_password@localhost:5432/remediation_engine_test
SECRET_KEY=$(openssl rand -hex 32)
EOF

# 5. Run migrations
alembic upgrade head

# 6. Start application
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

echo "Test environment ready!"
echo "Access: http://localhost:8000"
```

---

## 14. TROUBLESHOOTING

### Common Issues

**Database connection failed**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connection
psql -h localhost -U test_user -d remediation_engine_test
```

**LLM API rate limits**
- Use multiple provider keys
- Implement retry logic
- Monitor API usage

**Test server SSH issues**
```bash
# Check SSH connectivity
ssh -v test_runner@test-linux-01

# Check SSH keys
cat ~/.ssh/id_rsa.pub
```

---

## 15. CHECKLIST

### Pre-Testing Checklist
- [ ] All servers provisioned
- [ ] Database created and migrated
- [ ] Test users created
- [ ] LLM API keys configured
- [ ] Test servers accessible via SSH/WinRM
- [ ] Prometheus collecting metrics
- [ ] Grafana datasources configured
- [ ] ITSM integrations tested
- [ ] Sample data loaded
- [ ] Health checks passing

### Post-Testing Cleanup
- [ ] Reset database to clean state
- [ ] Clear test data
- [ ] Stop expensive cloud resources
- [ ] Archive test results
- [ ] Document issues found

---

**END OF TEST ENVIRONMENT SETUP GUIDE**
