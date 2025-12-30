# ADVANCED TESTING TOOLS - SELF-HOSTED SOLUTIONS

**Version**: 1.0
**Date**: 2025-12-29
**Purpose**: Guide for self-hosted testing infrastructure on dedicated servers

---

## OVERVIEW

**Why Self-Host Testing Tools?**
- ✅ Complete control over test execution
- ✅ Unlimited test runs (no SaaS limits)
- ✅ Better performance (dedicated resources)
- ✅ Data privacy (no external services)
- ✅ Custom integrations
- ✅ One-time cost vs recurring SaaS fees

---

## TOOL CATEGORIES

| Category | Tools | Best For |
|----------|-------|----------|
| **E2E Browser Testing** | Playwright, Selenium Grid | UI/Web testing at scale |
| **Load Testing** | Locust, K6, JMeter | Performance testing |
| **API Testing** | Postman/Newman, Karate | REST/GraphQL testing |
| **Visual Testing** | Percy, BackstopJS | UI regression |
| **Security Testing** | OWASP ZAP, Nuclei | Vulnerability scanning |
| **Test Management** | TestRail, Zephyr | Test case management |

---

# 1. PLAYWRIGHT - E2E BROWSER TESTING

## 1.1 What is Playwright?

**Modern browser automation framework by Microsoft**

**Features**:
- Multi-browser support (Chromium, Firefox, WebKit)
- Fast and reliable (auto-waits)
- Built-in screenshots/videos
- Network interception
- Mobile emulation
- Parallel execution
- Headless or headed mode

**Use Cases**:
- Test Remediation Engine web UI
- Verify dashboard rendering
- Test chat interface
- Validate runbook execution UI
- Test login flows

---

## 1.2 Playwright Self-Hosted Setup

### Architecture

```
┌─────────────────────────────────────────┐
│   Dedicated Test Server (Ubuntu 22.04)  │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Playwright Test Execution         │ │
│  │  - Node.js runtime                 │ │
│  │  - Playwright browsers installed   │ │
│  │  - Test suites                     │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Browser Instances                 │ │
│  │  - Chromium (headless)            │ │
│  │  - Firefox (headless)             │ │
│  │  - WebKit (headless)              │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Test Artifacts Storage            │ │
│  │  - Screenshots                     │ │
│  │  - Videos                          │ │
│  │  - Trace files                     │ │
│  │  - HTML reports                    │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
          │
          │ HTTP/WebSocket
          ↓
┌─────────────────────────────────────────┐
│  Remediation Engine (App Under Test)    │
└─────────────────────────────────────────┘
```

---

### Installation on Dedicated Server

```bash
# 1. Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 2. Install Playwright
npm init -y
npm install -D @playwright/test

# 3. Install browsers
npx playwright install --with-deps

# 4. Verify installation
npx playwright --version
```

**System Requirements**:
- CPU: 4+ cores
- RAM: 8GB minimum (16GB for parallel execution)
- Disk: 10GB for browsers + artifacts
- OS: Ubuntu 22.04 LTS

---

### Example Test Suite

**Directory Structure**:
```
playwright-tests/
├── tests/
│   ├── login.spec.ts
│   ├── dashboard.spec.ts
│   ├── alerts.spec.ts
│   ├── runbooks.spec.ts
│   └── chat.spec.ts
├── playwright.config.ts
├── package.json
└── .github/
    └── workflows/
        └── e2e-tests.yml
```

**Sample Test** (`tests/dashboard.spec.ts`):
```typescript
import { test, expect } from '@playwright/test';

test.describe('Dashboard Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('http://remediation-engine.test');
    await page.fill('input[name="username"]', 'test_admin');
    await page.fill('input[name="password"]', 'Test@123456');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/.*dashboard/);
  });

  test('should display alert statistics', async ({ page }) => {
    await page.goto('http://remediation-engine.test/dashboard');

    // Wait for stats to load
    await page.waitForSelector('.stats-card');

    // Verify total alerts displayed
    const totalAlerts = await page.textContent('.total-alerts');
    expect(parseInt(totalAlerts)).toBeGreaterThan(0);

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/dashboard-stats.png',
      fullPage: true
    });
  });

  test('should create new runbook', async ({ page }) => {
    await page.goto('http://remediation-engine.test/runbooks');

    await page.click('button:has-text("New Runbook")');
    await page.fill('input[name="name"]', 'Test Runbook');
    await page.fill('textarea[name="description"]', 'E2E test runbook');

    // Add step
    await page.click('button:has-text("Add Step")');
    await page.fill('input[name="step_name"]', 'Echo test');
    await page.fill('textarea[name="command"]', 'echo "test"');

    // Save
    await page.click('button:has-text("Save")');

    // Verify created
    await expect(page.locator('text=Test Runbook')).toBeVisible();
  });

  test('should execute runbook and show results', async ({ page }) => {
    // Navigate to runbooks
    await page.goto('http://remediation-engine.test/runbooks');

    // Find test runbook
    await page.click('text=Test Runbook');

    // Execute
    await page.click('button:has-text("Execute")');

    // Wait for execution to complete
    await page.waitForSelector('.execution-status:has-text("Success")', {
      timeout: 30000
    });

    // Verify output
    const output = await page.textContent('.execution-output');
    expect(output).toContain('test');

    // Record video
    await page.video().path(); // Saved automatically
  });
});
```

---

### Configuration (`playwright.config.ts`)

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,

  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results.json' }],
    ['junit', { outputFile: 'junit.xml' }]
  ],

  use: {
    baseURL: 'http://remediation-engine.test',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    // Mobile viewports
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],

  webServer: {
    command: 'npm run start-test-server',
    port: 8000,
    reuseExistingServer: !process.env.CI,
  },
});
```

---

### CI/CD Integration

**GitHub Actions** (`.github/workflows/e2e-playwright.yml`):
```yaml
name: Playwright E2E Tests

on:
  push:
    branches: [ main, develop ]
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2 AM

jobs:
  e2e-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - uses: actions/setup-node@v3
        with:
          node-version: 20

      - name: Install dependencies
        run: |
          cd playwright-tests
          npm ci

      - name: Install Playwright browsers
        run: npx playwright install --with-deps

      - name: Run E2E tests
        run: npx playwright test
        env:
          BASE_URL: https://staging.remediation-engine.test

      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30

      - name: Upload failure screenshots
        uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: screenshots
          path: test-results/
```

---

### Self-Hosted Execution

**Run on dedicated server**:
```bash
# SSH into test server
ssh testuser@playwright-server.example.com

# Pull latest tests
cd /opt/playwright-tests
git pull

# Run tests
npx playwright test

# Generate HTML report
npx playwright show-report

# Serve report on port 9323
npx playwright show-report --port 9323 --host 0.0.0.0
```

**Scheduled Execution** (cron):
```bash
# /etc/cron.d/playwright-tests
0 2 * * * testuser cd /opt/playwright-tests && npx playwright test --reporter=html,json
```

---

### Cost & Resources

**Dedicated Server**:
- VPS/Cloud: $40-80/month (4 CPU, 8GB RAM)
- On-premise: One-time hardware cost

**Playwright License**: Free (Apache 2.0)

**Total Monthly**: $40-80 (vs $299/month for BrowserStack)

---

# 2. LOCUST - LOAD TESTING

## 2.1 What is Locust?

**Python-based load testing framework**

**Features**:
- Define user behavior in Python code
- Distributed load generation
- Real-time web UI
- HTTP/WebSocket/gRPC support
- Swarm mode (sudden traffic spikes)
- Scalable to millions of users

**Use Cases**:
- Load test alert ingestion (1000+ alerts/min)
- Test concurrent runbook executions
- Stress test API endpoints
- Test WebSocket chat at scale
- Validate database performance

---

## 2.2 Locust Self-Hosted Setup

### Architecture

```
┌───────────────────────────────────────────┐
│   Locust Master Server                    │
│   - Web UI (port 8089)                   │
│   - Orchestration                        │
│   - Result aggregation                   │
└───────────────────────────────────────────┘
          │
          │ TCP (port 5557)
          │
    ┌─────┴─────┬─────────┬─────────┐
    │           │         │         │
    ▼           ▼         ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Worker 1│ │Worker 2│ │Worker 3│ │Worker 4│
│50 users│ │50 users│ │50 users│ │50 users│
└────────┘ └────────┘ └────────┘ └────────┘
    │           │         │         │
    └─────┬─────┴─────────┴─────────┘
          │
          │ HTTP Requests
          ▼
┌───────────────────────────────────────────┐
│   Remediation Engine (Target System)      │
└───────────────────────────────────────────┘
```

---

### Installation

```bash
# Install Locust
pip install locust

# Verify
locust --version
```

---

### Example Load Test

**Directory Structure**:
```
locust-tests/
├── locustfiles/
│   ├── alert_ingestion.py
│   ├── api_load.py
│   ├── runbook_execution.py
│   └── concurrent_users.py
├── config/
│   ├── dev.conf
│   └── prod.conf
└── results/
    └── reports/
```

**Alert Ingestion Load Test** (`locustfiles/alert_ingestion.py`):
```python
from locust import HttpUser, task, between, events
import json
import random
from datetime import datetime

class AlertIngestionUser(HttpUser):
    wait_time = between(0.1, 0.5)  # 100-500ms between requests
    host = "http://remediation-engine.test:8000"

    def on_start(self):
        """Login before starting tasks"""
        response = self.client.post("/api/auth/login", json={
            "username": "load_test_user",
            "password": "Test@123456"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(10)  # Weight: 10 (most common)
    def ingest_firing_alert(self):
        """Simulate Alertmanager sending firing alert"""
        alert_payload = {
            "receiver": "remediation-engine",
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": random.choice([
                        "HighCPUUsage", "HighMemory", "DiskFull",
                        "ServiceDown", "HighLatency"
                    ]),
                    "severity": random.choice(["critical", "warning", "info"]),
                    "instance": f"server-{random.randint(1, 20):02d}",
                    "job": random.choice(["node-exporter", "application", "database"])
                },
                "annotations": {
                    "summary": f"Load test alert {random.randint(1, 1000000)}",
                    "description": "Generated by Locust load test"
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "fingerprint": f"fp{random.randint(1, 1000000):08d}"
            }],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093"
        }

        with self.client.post(
            "/webhook/alerts",
            json=alert_payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)  # Weight: 3
    def ingest_resolved_alert(self):
        """Simulate resolved alert"""
        # Similar to firing but with status=resolved and endsAt
        pass

    @task(5)  # Weight: 5
    def query_alerts(self):
        """Query alerts API"""
        self.client.get(
            "/api/alerts?page=1&page_size=50",
            headers=self.headers,
            name="/api/alerts [query]"
        )

    @task(2)
    def get_alert_stats(self):
        """Get alert statistics"""
        self.client.get(
            "/api/alerts/stats",
            headers=self.headers,
            name="/api/alerts/stats"
        )


class ConcurrentRunbookUser(HttpUser):
    """Test concurrent runbook executions"""
    wait_time = between(5, 10)

    @task
    def execute_runbook(self):
        # Authenticate
        # Execute runbook
        # Poll for completion
        pass


# Custom event handlers for detailed reporting
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests"""
    if response_time > 5000:  # 5 seconds
        print(f"Slow request: {name} took {response_time}ms")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate summary report"""
    print("Load test completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")
```

---

### Running Locust

**Single Machine** (Master + Workers):
```bash
# Start master
locust -f locustfiles/alert_ingestion.py --master

# Start workers (in separate terminals)
locust -f locustfiles/alert_ingestion.py --worker --master-host=localhost
locust -f locustfiles/alert_ingestion.py --worker --master-host=localhost
locust -f locustfiles/alert_ingestion.py --worker --master-host=localhost
locust -f locustfiles/alert_ingestion.py --worker --master-host=localhost
```

**Distributed** (Multiple Servers):
```bash
# On master server (192.168.1.100)
locust -f alert_ingestion.py --master --master-bind-host=0.0.0.0

# On worker servers
locust -f alert_ingestion.py --worker --master-host=192.168.1.100
```

**Headless Mode** (CI/CD):
```bash
locust -f alert_ingestion.py \
  --headless \
  --users 1000 \
  --spawn-rate 50 \
  --run-time 10m \
  --html report.html \
  --csv results
```

---

### Web UI

**Access**: http://localhost:8089

**Features**:
- Real-time charts (RPS, response times)
- Request statistics table
- Failure tracking
- Start/stop controls
- Export results (CSV, JSON)

**Dashboard**:
```
┌─────────────────────────────────────────────────┐
│  Locust Dashboard                               │
│                                                 │
│  Users: 1000 | Spawn Rate: 50/s               │
│  RPS: 850    | Failures: 0.2%                 │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │  Response Time (ms)                       │ │
│  │  500 ┤              ╭─╮                   │ │
│  │  400 ┤          ╭───╯ ╰─╮                 │ │
│  │  300 ┤      ╭───╯       ╰───╮             │ │
│  │  200 ┤  ╭───╯               ╰─╮           │ │
│  │  100 ┼──╯                     ╰───        │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
│  Top Endpoints:                                │
│  POST /webhook/alerts       850 RPS  150ms    │
│  GET  /api/alerts          120 RPS   80ms     │
│  GET  /api/alerts/stats     50 RPS   200ms    │
└─────────────────────────────────────────────────┘
```

---

### Scheduled Load Tests

**Systemd Service** (`/etc/systemd/system/locust-nightly.service`):
```ini
[Unit]
Description=Nightly Locust Load Test
After=network.target

[Service]
Type=oneshot
User=testuser
WorkingDirectory=/opt/locust-tests
ExecStart=/usr/local/bin/locust \
  -f locustfiles/alert_ingestion.py \
  --headless \
  --users 1000 \
  --spawn-rate 50 \
  --run-time 30m \
  --html /var/www/html/locust-reports/$(date +\%Y\%m\%d).html

[Install]
WantedBy=multi-user.target
```

**Systemd Timer** (`/etc/systemd/system/locust-nightly.timer`):
```ini
[Unit]
Description=Run Locust load test nightly

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

**Enable**:
```bash
sudo systemctl enable locust-nightly.timer
sudo systemctl start locust-nightly.timer
```

---

### Cost & Resources

**Master Server**:
- CPU: 2 cores
- RAM: 4GB
- Disk: 20GB
- Cost: $20/month

**Worker Servers** (4x):
- CPU: 2 cores each
- RAM: 2GB each
- Cost: $10/month each = $40/month

**Total**: $60/month for 1000+ concurrent users

**vs SaaS**: BlazeMeter $999/month for similar capacity

---

# 3. K6 - MODERN LOAD TESTING

## 3.1 What is K6?

**Modern load testing tool with JavaScript/Go**

**Features**:
- JavaScript ES6 test scripts
- Built-in metrics and checks
- Thresholds and SLOs
- Cloud execution option
- Docker support
- WebSocket/gRPC support

**Advantages over Locust**:
- Better for API testing
- Easier syntax (JavaScript)
- Better CI/CD integration
- Built-in cloud option

---

## 3.2 K6 Setup

```bash
# Install K6
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

---

### Example K6 Test

**Alert Ingestion Test** (`k6-tests/alert-load.js`):
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // Ramp up to 100 users
    { duration: '5m', target: 100 },   // Stay at 100 users
    { duration: '2m', target: 200 },   // Ramp to 200 users
    { duration: '5m', target: 200 },   // Stay at 200 users
    { duration: '2m', target: 0 },     // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests < 500ms
    errors: ['rate<0.1'],              // Error rate < 10%
  },
};

export default function () {
  const payload = JSON.stringify({
    receiver: 'remediation-engine',
    status: 'firing',
    alerts: [{
      status: 'firing',
      labels: {
        alertname: 'LoadTestAlert',
        severity: 'warning',
        instance: `server-${__VU}`, // Use virtual user ID
        job: 'load-test'
      },
      annotations: {
        summary: `K6 load test alert from VU ${__VU}`,
        description: 'Performance test'
      },
      startsAt: new Date().toISOString(),
      fingerprint: `fp-${__VU}-${__ITER}` // VU + iteration
    }]
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const res = http.post('http://remediation-engine.test:8000/webhook/alerts', payload, params);

  // Checks
  const checkResult = check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  errorRate.add(!checkResult);

  sleep(1); // Wait 1 second between requests
}
```

---

### Run K6 Tests

```bash
# Local execution
k6 run k6-tests/alert-load.js

# With output to InfluxDB
k6 run --out influxdb=http://localhost:8086/k6 k6-tests/alert-load.js

# Cloud execution (K6 Cloud account required)
k6 cloud k6-tests/alert-load.js

# Docker
docker run -i --rm loadimpact/k6 run - <k6-tests/alert-load.js
```

---

### K6 with InfluxDB + Grafana

**Architecture**:
```
K6 → InfluxDB → Grafana Dashboard
```

**Docker Compose** (`docker-compose-k6.yml`):
```yaml
version: '3.8'

services:
  influxdb:
    image: influxdb:1.8
    ports:
      - "8086:8086"
    environment:
      INFLUXDB_DB: k6
    volumes:
      - influxdb-data:/var/lib/influxdb

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana-dashboards:/etc/grafana/provisioning/dashboards

volumes:
  influxdb-data:
  grafana-data:
```

**Run**:
```bash
docker-compose -f docker-compose-k6.yml up -d

# Run K6 with InfluxDB output
k6 run --out influxdb=http://localhost:8086/k6 alert-load.js

# Access Grafana: http://localhost:3000
# Import K6 dashboard: ID 2587
```

---

# 4. COMPARISON TABLE

| Feature | Playwright | Locust | K6 | Selenium Grid |
|---------|-----------|--------|-----|---------------|
| **Purpose** | E2E Browser Testing | Load Testing | Load Testing | Browser Testing |
| **Language** | TypeScript/JS | Python | JavaScript | Any |
| **Learning Curve** | Easy | Easy | Easy | Medium |
| **Parallel Execution** | ✅ Built-in | ✅ Distributed | ✅ Cloud | ✅ Grid |
| **CI/CD Integration** | ✅ Excellent | ✅ Good | ✅ Excellent | ⚠️ Complex |
| **Resource Usage** | Medium | Low | Low | High |
| **Scalability** | 1-100 browsers | 1M+ users | 1M+ users | 100s browsers |
| **Real-time UI** | ❌ No | ✅ Yes | ⚠️ Basic | ❌ No |
| **Cloud Option** | ❌ No | ❌ No | ✅ Yes (paid) | ✅ Yes (BrowserStack) |
| **Cost (Self-hosted)** | $40/month | $60/month | $20/month | $100/month |
| **Best For** | UI Testing | HTTP Load | API Load | Cross-browser |

---

# 5. RECOMMENDED SELF-HOSTED STACK

## For Remediation Engine Testing:

### Tier 1: Essential (Cost: $60/month)
```
1. Playwright (1 server)      - $40/month - E2E testing
2. K6 (shared server)          - $20/month - API load testing
```

### Tier 2: Comprehensive (Cost: $120/month)
```
1. Playwright (1 server)       - $40/month - E2E testing
2. Locust (master + 4 workers) - $60/month - Load testing
3. InfluxDB + Grafana          - $20/month - Metrics
```

### Tier 3: Enterprise (Cost: $200/month)
```
1. Playwright (2 servers)      - $80/month - Parallel E2E
2. Locust cluster (8 workers)  - $100/month - High load
3. Selenium Grid (4 nodes)     - $80/month - Multi-browser
4. Monitoring stack            - $40/month - Full observability
```

---

# 6. INFRASTRUCTURE SETUP

## 6.1 Dedicated Test Server Specs

**Option 1: Single Server (Budget)**
```
CPU: 8 cores
RAM: 16GB
Disk: 100GB SSD
Network: 1Gbps
OS: Ubuntu 22.04 LTS

Install:
- Docker + Docker Compose
- Playwright
- K6
- Python (for Locust)

Cost: $80-120/month (cloud) or $1500 one-time (hardware)
```

**Option 2: Distributed Setup (Recommended)**
```
Master Server:
  - CPU: 4 cores, RAM: 8GB
  - Orchestration, reporting
  - Cost: $40/month

Worker Servers (4x):
  - CPU: 2 cores, RAM: 4GB each
  - Test execution
  - Cost: $20/month each = $80/month

Storage Server:
  - NFS for shared artifacts
  - Cost: $20/month

Total: $140/month
```

---

## 6.2 Network Configuration

```
┌──────────────────────────────────────────┐
│  Test Infrastructure Network             │
│  (Isolated VLAN or VPC)                 │
│                                          │
│  ┌─────────────────────────────────┐   │
│  │  Load Balancer (HAProxy)         │   │
│  │  - Distribute test traffic       │   │
│  └─────────────────────────────────┘   │
│              │                          │
│      ┌───────┴────────┬────────┐       │
│      │                │        │       │
│  ┌───▼───┐     ┌─────▼──┐  ┌──▼────┐  │
│  │ Worker│     │ Worker │  │Worker │  │
│  │   1   │     │   2    │  │  3    │  │
│  └───────┘     └────────┘  └───────┘  │
│                                          │
└──────────────────────────────────────────┘
        │
        │ Firewall (only outbound to app)
        ▼
┌──────────────────────────────────────────┐
│  Application Under Test                  │
│  (Remediation Engine - Staging)          │
└──────────────────────────────────────────┘
```

---

# 7. SCHEDULING & AUTOMATION

## 7.1 Nightly Test Suite

**Crontab** (`/etc/cron.d/nightly-tests`):
```bash
# E2E tests at 2 AM
0 2 * * * testuser cd /opt/playwright-tests && npx playwright test --project=chromium > /var/log/playwright-nightly.log 2>&1

# Load tests at 3 AM
0 3 * * * testuser cd /opt/locust-tests && locust -f alert_ingestion.py --headless --users 1000 --spawn-rate 50 --run-time 30m --html /var/www/reports/locust-$(date +\%Y\%m\%d).html > /var/log/locust-nightly.log 2>&1

# API tests at 4 AM
0 4 * * * testuser k6 run /opt/k6-tests/api-suite.js --out influxdb=http://localhost:8086/k6 > /var/log/k6-nightly.log 2>&1
```

---

## 7.2 CI/CD Triggered Tests

**Jenkins Pipeline**:
```groovy
pipeline {
    agent { label 'test-server' }

    stages {
        stage('Deploy to Staging') {
            steps {
                sh 'deploy-staging.sh'
            }
        }

        stage('Smoke Tests') {
            steps {
                sh 'npx playwright test tests/smoke/'
            }
        }

        stage('Load Test') {
            steps {
                sh 'k6 run k6-tests/quick-load.js'
            }
        }

        stage('Full E2E Suite') {
            when { branch 'main' }
            steps {
                sh 'npx playwright test'
            }
        }
    }

    post {
        always {
            publishHTML([
                reportDir: 'playwright-report',
                reportFiles: 'index.html',
                reportName: 'Playwright Report'
            ])
        }
    }
}
```

---

# 8. MONITORING & ALERTING

## 8.1 Test Execution Monitoring

**Prometheus + Grafana Stack**:

**Metrics to Track**:
- Test execution duration
- Pass/fail rates
- Response times (P50, P95, P99)
- Error rates
- Resource usage (CPU, RAM)

**Grafana Dashboard**:
```
Test Infrastructure Health
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌────────────────┬────────────────┬────────────────┐
│ E2E Pass Rate  │ Load Test RPS  │ API Errors    │
│     98.5%      │     850        │     0.2%      │
└────────────────┴────────────────┴────────────────┘

┌─────────────────────────────────────────────────┐
│  Test Execution Duration (Last 7 Days)          │
│  600s ┤                                    ╭─   │
│  500s ┤                              ╭─────╯    │
│  400s ┤                      ╭───────╯          │
│  300s ┤          ╭───────────╯                  │
│  200s ┼──────────╯                              │
└─────────────────────────────────────────────────┘

Worker Server Status:
✅ Worker 1: Healthy (CPU 45%, RAM 60%)
✅ Worker 2: Healthy (CPU 50%, RAM 55%)
⚠️ Worker 3: Warning (CPU 85%, RAM 90%)
✅ Worker 4: Healthy (CPU 40%, RAM 50%)
```

---

## 8.2 Alerting Rules

**Alert on**:
- Test suite duration >20 minutes
- Pass rate <95%
- Worker server down
- Disk space <10GB

**Notification Channels**:
- Slack
- Email
- PagerDuty (for critical)

---

# 9. COST COMPARISON

## SaaS vs Self-Hosted (1 Year)

| Service | SaaS Cost/Year | Self-Hosted Cost/Year | Savings |
|---------|----------------|----------------------|---------|
| **Browser Testing** | $3,588 (BrowserStack) | $480 (Playwright server) | $3,108 |
| **Load Testing** | $11,988 (BlazeMeter) | $720 (Locust cluster) | $11,268 |
| **Test Management** | $1,800 (TestRail) | $240 (ReportPortal) | $1,560 |
| **Monitoring** | $1,200 (Datadog) | $240 (Grafana stack) | $960 |
| **TOTAL** | **$18,576** | **$1,680** | **$16,896** |

**ROI**: 91% savings with self-hosted approach

---

# 10. QUICK START GUIDE

## Week 1: Setup Playwright
```bash
1. Provision Ubuntu 22.04 server (4 CPU, 8GB RAM)
2. Install Node.js and Playwright
3. Write first E2E test
4. Run locally, verify works
5. Set up cron for nightly runs
```

## Week 2: Add Load Testing
```bash
6. Install K6 on same server
7. Write API load test
8. Run manual load test
9. Set up InfluxDB + Grafana
10. Schedule weekly load tests
```

## Week 3: Advanced Setup
```bash
11. Add Locust for complex scenarios
12. Set up distributed workers
13. Configure monitoring
14. Integrate with CI/CD
```

---

# SUMMARY

**Question**: Can I use Playwright, Locust, etc. on dedicated servers?

**Answer**: Yes! Recommended approach:

1. **Playwright** - E2E browser testing ($40/month)
2. **Locust or K6** - Load testing ($60/month for distributed)
3. **Self-hosted** - Complete control, better value

**Total Cost**: $100-140/month
**vs SaaS**: $1,500+/month for equivalent

**Benefits**:
- ✅ No usage limits
- ✅ Data stays private
- ✅ Custom integrations
- ✅ Better ROI (91% savings)
- ✅ Full control

**Setup Time**: 1-2 weeks
**Maintenance**: 2-4 hours/month

---

**END OF ADVANCED TESTING TOOLS GUIDE**
