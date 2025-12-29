# TEST HISTORY & PERFORMANCE TRACKING

**Version**: 1.0
**Date**: 2025-12-29
**Purpose**: Track test results, coverage, and performance metrics across repository versions

---

## OVERVIEW

**Goal**: Maintain historical records of:
- Test pass/fail rates per version
- Code coverage trends over time
- Test execution performance
- Flaky test identification
- Regression detection

---

## APPROACH 1: BUILT-IN CI/CD (FREE, SIMPLE)

### 1.1 GitHub Actions Test Reporting

**Built-in features** (no additional tools needed):

#### **Test Summary in Workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Run tests
        run: |
          pytest tests/ \
            --junit-xml=test-results/junit.xml \
            --cov=app \
            --cov-report=xml \
            --cov-report=html

      # Generate test summary (visible in GitHub UI)
      - name: Publish test results
        uses: dorny/test-reporter@v1
        if: always()
        with:
          name: Test Results
          path: test-results/junit.xml
          reporter: java-junit

      # Store test results as artifacts
      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: test-results-${{ github.sha }}
          path: |
            test-results/
            htmlcov/
          retention-days: 90  # Keep for 90 days
```

**What you get**:
- ✅ Test summary in GitHub Actions UI
- ✅ Failed test details
- ✅ Test artifacts stored for 90 days
- ✅ Coverage HTML reports downloadable

**Limitations**:
- No trend analysis
- No historical comparisons
- Manual artifact download

---

### 1.2 GitHub Actions Matrix for Version Tracking

**Track metrics per branch/version**:

```yaml
jobs:
  test:
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
      - name: Run tests
        run: pytest --cov=app

      - name: Generate metrics file
        run: |
          echo "version=${{ github.ref_name }}" >> metrics.txt
          echo "commit=${{ github.sha }}" >> metrics.txt
          echo "date=$(date -u +%Y-%m-%d)" >> metrics.txt
          coverage report >> metrics.txt

      - name: Store metrics
        uses: actions/upload-artifact@v3
        with:
          name: metrics-${{ github.ref_name }}-${{ github.sha }}
          path: metrics.txt
```

---

## APPROACH 2: COVERAGE TRACKING (FREE, AUTOMATED)

### 2.1 Codecov (Recommended for Coverage History)

**Setup** (Free for open source, paid for private repos):

1. **Sign up**: https://codecov.io
2. **Add token to GitHub Secrets**: `CODECOV_TOKEN`
3. **Update workflow**:

```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: ./coverage.xml
    flags: unittests
    name: codecov-umbrella
    fail_ci_if_error: true
```

**What you get**:
- ✅ Coverage trends over time (graphs)
- ✅ Per-file coverage changes
- ✅ Pull request coverage diff
- ✅ Coverage badges
- ✅ Historical data (unlimited)
- ✅ Regression detection

**Dashboard shows**:
- Coverage percentage per commit
- Coverage change per PR
- Files with decreasing coverage
- Uncovered lines highlighted

**Free tier**: Unlimited for public repos
**Paid**: $10/month for 1 private repo

---

### 2.2 Coveralls (Alternative)

Similar to Codecov:
```yaml
- name: Coveralls
  uses: coverallsapp/github-action@v2
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## APPROACH 3: TEST REPORTING PLATFORMS

### 3.1 Allure Report (FREE, Self-Hosted)

**Best for**: Rich test reports with history

**Setup**:

1. **Install Allure pytest plugin**:
```bash
pip install allure-pytest
```

2. **Run tests with Allure**:
```bash
pytest --alluredir=allure-results
```

3. **Generate report**:
```bash
allure generate allure-results -o allure-report --clean
```

4. **GitHub Actions workflow**:
```yaml
- name: Run tests with Allure
  run: pytest --alluredir=allure-results

- name: Generate Allure report
  run: |
    wget https://github.com/allure-framework/allure2/releases/download/2.24.0/allure-2.24.0.tgz
    tar -zxvf allure-2.24.0.tgz
    ./allure-2.24.0/bin/allure generate allure-results -o allure-report

- name: Deploy to GitHub Pages
  uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./allure-report
```

**What you get**:
- ✅ Beautiful HTML reports
- ✅ Test execution trends
- ✅ Test duration graphs
- ✅ Flaky test detection
- ✅ Test history (stored in git)
- ✅ Categorization by feature/severity
- ✅ Screenshots and logs attachment

**View**: `https://your-username.github.io/remediation-engine/`

**Storage**: GitHub Pages (free, unlimited history)

---

### 3.2 ReportPortal (FREE, Self-Hosted)

**Best for**: Enterprise-grade test analytics

**Setup**: Docker Compose
```yaml
version: '3'
services:
  postgres:
    image: postgres:12
    environment:
      POSTGRES_PASSWORD: reportportal

  reportportal:
    image: reportportal/reportportal:latest
    ports:
      - "8080:8080"
    depends_on:
      - postgres
```

**Integration**:
```python
# pytest.ini
[pytest]
addopts = --reportportal
```

**What you get**:
- ✅ Test execution history (unlimited)
- ✅ Trend analysis and dashboards
- ✅ Flaky test detection with ML
- ✅ Test execution time analytics
- ✅ Defect tracking integration
- ✅ Email notifications
- ✅ Custom dashboards

**Cost**: Free (self-hosted)
**Maintenance**: Requires server + database

---

## APPROACH 4: CUSTOM DATABASE SOLUTION

### 4.1 Store Test Results in Database

**For complete control and custom analytics**

**Schema**:
```sql
CREATE TABLE test_runs (
    id SERIAL PRIMARY KEY,
    git_commit VARCHAR(40),
    git_branch VARCHAR(100),
    git_tag VARCHAR(50),
    run_date TIMESTAMP,
    total_tests INT,
    passed INT,
    failed INT,
    skipped INT,
    duration_seconds INT,
    coverage_percent DECIMAL(5,2)
);

CREATE TABLE test_results (
    id SERIAL PRIMARY KEY,
    test_run_id INT REFERENCES test_runs(id),
    test_name VARCHAR(500),
    test_file VARCHAR(500),
    status VARCHAR(20),  -- passed, failed, skipped
    duration_ms INT,
    error_message TEXT,
    stack_trace TEXT
);

CREATE TABLE coverage_history (
    id SERIAL PRIMARY KEY,
    test_run_id INT REFERENCES test_runs(id),
    file_path VARCHAR(500),
    coverage_percent DECIMAL(5,2),
    lines_covered INT,
    lines_total INT
);
```

**Python script to store results**:
```python
# scripts/store_test_results.py
import json
import psycopg2
from datetime import datetime

def store_test_results(junit_file, coverage_file, git_commit, git_branch):
    conn = psycopg2.connect("postgresql://user:pass@localhost/test_metrics")
    cur = conn.cursor()

    # Parse JUnit XML
    # Parse coverage.xml
    # Insert into database

    cur.execute("""
        INSERT INTO test_runs (git_commit, git_branch, run_date, total_tests, passed, failed, coverage_percent)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (git_commit, git_branch, datetime.now(), total, passed, failed, coverage))

    test_run_id = cur.fetchone()[0]

    # Insert individual test results
    # ...

    conn.commit()
```

**GitHub Actions**:
```yaml
- name: Store test results
  env:
    DB_HOST: ${{ secrets.METRICS_DB_HOST }}
    DB_PASSWORD: ${{ secrets.METRICS_DB_PASSWORD }}
  run: |
    python scripts/store_test_results.py \
      --junit test-results/junit.xml \
      --coverage coverage.xml \
      --commit ${{ github.sha }} \
      --branch ${{ github.ref_name }}
```

**Analytics Dashboard** (Grafana + PostgreSQL):
```sql
-- Coverage trend over time
SELECT run_date, coverage_percent
FROM test_runs
WHERE git_branch = 'main'
ORDER BY run_date DESC
LIMIT 100;

-- Test execution time trend
SELECT run_date, duration_seconds
FROM test_runs
WHERE git_branch = 'main'
ORDER BY run_date;

-- Flaky tests (sometimes pass, sometimes fail)
SELECT test_name,
       COUNT(*) as total_runs,
       SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passes,
       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failures
FROM test_results
WHERE test_run_id IN (SELECT id FROM test_runs WHERE run_date > NOW() - INTERVAL '30 days')
GROUP BY test_name
HAVING SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) > 0
   AND SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) > 0
ORDER BY failures DESC;
```

**What you get**:
- ✅ Unlimited history (as long as you keep DB)
- ✅ Custom queries and analytics
- ✅ Integration with your monitoring stack
- ✅ Full control over data

**Cost**: Database hosting (~$20-50/month for managed DB)

---

## APPROACH 5: SONARQUBE (CODE QUALITY + TESTS)

### 5.1 SonarQube Setup

**Best for**: Comprehensive code quality tracking

**Setup** (Docker):
```bash
docker run -d --name sonarqube -p 9000:9000 sonarqube:lts
```

**Integrate with pytest**:
```yaml
- name: Run tests with coverage
  run: pytest --cov=app --cov-report=xml

- name: SonarQube Scan
  uses: sonarsource/sonarqube-scan-action@master
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
  with:
    args: >
      -Dsonar.projectKey=remediation-engine
      -Dsonar.python.coverage.reportPaths=coverage.xml
      -Dsonar.sources=app
      -Dsonar.tests=tests
```

**What you get**:
- ✅ Code quality trends
- ✅ Test coverage history
- ✅ Code smells tracking
- ✅ Security vulnerabilities
- ✅ Duplication tracking
- ✅ Quality gates (fail builds if metrics degrade)

**Cost**:
- Free (self-hosted, Community Edition)
- $150/year per 100k lines (Enterprise)

---

## APPROACH 6: PERFORMANCE METRICS TRACKING

### 6.1 pytest-benchmark for Test Performance

**Track test execution time over commits**:

```bash
pip install pytest-benchmark
```

**Usage**:
```python
def test_alert_ingestion_performance(benchmark):
    result = benchmark(ingest_alert, sample_alert)
    assert result is not None
```

**Run with JSON output**:
```bash
pytest --benchmark-json=benchmark.json
```

**Store benchmark results**:
```yaml
- name: Run performance tests
  run: pytest tests/performance/ --benchmark-json=benchmark-${{ github.sha }}.json

- name: Store benchmark results
  uses: benchmark-action/github-action-benchmark@v1
  with:
    tool: 'pytest'
    output-file-path: benchmark-${{ github.sha }}.json
    github-token: ${{ secrets.GITHUB_TOKEN }}
    auto-push: true
```

**View**: Automatically creates GitHub Pages with performance graphs

---

### 6.2 Custom Performance Tracking

**Track performance metrics per version**:

```python
# tests/performance/track_metrics.py
import time
import json
from datetime import datetime

def track_performance(test_name, duration, git_commit):
    metric = {
        "test": test_name,
        "duration_ms": duration * 1000,
        "commit": git_commit,
        "date": datetime.utcnow().isoformat()
    }

    # Append to metrics file
    with open("performance_metrics.jsonl", "a") as f:
        f.write(json.dumps(metric) + "\n")
```

**Store in git**:
```yaml
- name: Commit performance metrics
  run: |
    git config user.name "GitHub Actions"
    git config user.email "actions@github.com"
    git add performance_metrics.jsonl
    git commit -m "Update performance metrics for ${{ github.sha }}"
    git push
```

---

## RECOMMENDED SOLUTION (BASED ON TEAM SIZE)

### Small Team (1-5 developers)

**Tier 1 (Free)**:
1. **Codecov** for coverage tracking
2. **GitHub Actions built-in** for test summaries
3. **Allure Report** on GitHub Pages for rich reports

**Setup time**: 2-4 hours
**Cost**: Free
**Maintenance**: Minimal

---

### Medium Team (5-20 developers)

**Tier 2 (Low Cost)**:
1. **Codecov** for coverage
2. **Allure Report** for test history
3. **Custom PostgreSQL database** for detailed analytics
4. **Grafana** for dashboards

**Setup time**: 1-2 days
**Cost**: ~$50/month (hosted DB + Codecov)
**Maintenance**: Low

---

### Enterprise Team (20+ developers)

**Tier 3 (Full Featured)**:
1. **ReportPortal** for test management
2. **SonarQube** for code quality
3. **Custom analytics database** for deep insights
4. **Dedicated test analytics team**

**Setup time**: 1-2 weeks
**Cost**: $200-500/month
**Maintenance**: Moderate (requires admin)

---

## IMPLEMENTATION ROADMAP

### Week 1: Basic Tracking
```yaml
✅ Set up GitHub Actions test summary
✅ Configure JUnit XML output
✅ Store test artifacts (90-day retention)
✅ Enable coverage reporting
```

### Week 2: Coverage History
```yaml
✅ Sign up for Codecov
✅ Integrate Codecov action
✅ Configure coverage thresholds
✅ Add coverage badge to README
```

### Week 3: Rich Reporting
```yaml
✅ Install Allure pytest plugin
✅ Generate Allure reports
✅ Deploy to GitHub Pages
✅ Set up historical trend tracking
```

### Week 4: Custom Analytics (Optional)
```yaml
⚠️ Set up PostgreSQL for metrics
⚠️ Create storage scripts
⚠️ Build Grafana dashboards
⚠️ Schedule periodic reports
```

---

## METRICS TO TRACK

### Essential Metrics

1. **Test Count**
   - Total tests
   - Tests added/removed per version

2. **Pass Rate**
   - % of tests passing
   - Failed test count
   - Flaky test detection

3. **Code Coverage**
   - Overall coverage %
   - Coverage per file/module
   - Coverage trend (increasing/decreasing)

4. **Test Execution Time**
   - Total suite duration
   - Slowest tests
   - Duration trend

5. **Version Info**
   - Git commit hash
   - Git branch/tag
   - Execution date/time

---

### Advanced Metrics

6. **Reliability**
   - Flaky test rate
   - Test stability score

7. **Performance**
   - Tests per second
   - Parallelization efficiency

8. **Quality**
   - Code complexity trends
   - Security vulnerabilities
   - Code duplication

---

## EXAMPLE QUERIES & REPORTS

### Coverage Regression Detection
```sql
-- Find files where coverage decreased
SELECT
    ch1.file_path,
    ch1.coverage_percent as current_coverage,
    ch2.coverage_percent as previous_coverage,
    (ch1.coverage_percent - ch2.coverage_percent) as change
FROM coverage_history ch1
JOIN coverage_history ch2 ON ch1.file_path = ch2.file_path
WHERE ch1.test_run_id = (SELECT MAX(id) FROM test_runs)
  AND ch2.test_run_id = (SELECT MAX(id) FROM test_runs WHERE id < ch1.test_run_id)
  AND ch1.coverage_percent < ch2.coverage_percent
ORDER BY change ASC;
```

### Test Execution Time Regression
```sql
-- Find tests that got slower
SELECT
    tr1.test_name,
    tr1.duration_ms as current_duration,
    AVG(tr2.duration_ms) as avg_previous_duration,
    (tr1.duration_ms - AVG(tr2.duration_ms)) as slowdown_ms
FROM test_results tr1
JOIN test_results tr2 ON tr1.test_name = tr2.test_name
WHERE tr1.test_run_id = (SELECT MAX(id) FROM test_runs)
  AND tr2.test_run_id IN (SELECT id FROM test_runs ORDER BY run_date DESC LIMIT 10 OFFSET 1)
GROUP BY tr1.test_name, tr1.duration_ms
HAVING tr1.duration_ms > AVG(tr2.duration_ms) * 1.5  -- 50% slower
ORDER BY slowdown_ms DESC;
```

---

## ALERTING & NOTIFICATIONS

### Set up alerts for:

1. **Coverage Drop**: Alert if coverage < 80% or drops >5%
2. **Flaky Tests**: Alert if same test fails intermittently
3. **Slow Tests**: Alert if test duration increases >50%
4. **Failed Builds**: Immediate notification

**Example** (GitHub Actions + Slack):
```yaml
- name: Notify on coverage drop
  if: steps.coverage.outputs.coverage < 80
  uses: 8398a7/action-slack@v3
  with:
    status: custom
    text: '⚠️ Coverage dropped to ${{ steps.coverage.outputs.coverage }}%'
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

---

## VISUALIZATION EXAMPLES

### Grafana Dashboard Panels

1. **Coverage Trend** (Line chart)
   - X-axis: Date
   - Y-axis: Coverage %
   - Goal line at 80%

2. **Test Execution Time** (Line chart)
   - X-axis: Date
   - Y-axis: Duration (seconds)
   - Threshold at 600s (10 min)

3. **Test Pass Rate** (Gauge)
   - Current: 98.5%
   - Thresholds: Red <95%, Yellow 95-98%, Green >98%

4. **Top 10 Slowest Tests** (Bar chart)

5. **Flaky Test Detection** (Table)
   - Test name, pass rate, last 10 runs

---

## RECOMMENDED SETUP (SIMPLE & EFFECTIVE)

### For Your Use Case:

**Phase 1: Immediate (1 day)**
```yaml
1. Add Codecov integration → Coverage history (free)
2. Use GitHub Actions artifacts → Test results for 90 days
3. Add coverage badge to README → Visible trend
```

**Phase 2: Enhanced (1 week)**
```yaml
4. Set up Allure Reports → Rich HTML reports
5. Deploy Allure to GitHub Pages → Historical test reports
6. Configure flaky test detection → Quality improvement
```

**Phase 3: Advanced (Optional)**
```yaml
7. Custom PostgreSQL DB → Unlimited history
8. Grafana dashboards → Custom analytics
9. Automated alerting → Proactive monitoring
```

---

## SUMMARY

### Question: How to keep test history?
**Answer**: Use Codecov (free) + Allure Reports (free, self-hosted)

### Question: Track performance per version?
**Answer**: pytest-benchmark + GitHub Actions benchmark action

### Question: Do I need a tool?
**Answer**: Yes, but free tools are sufficient:
- **Codecov** → Coverage history
- **Allure** → Test execution history
- **GitHub Actions** → Test summaries
- **pytest-benchmark** → Performance tracking

### Total Cost: $0 (free tier)
### Setup Time: 4-8 hours
### Maintenance: Minimal

---

**END OF TEST HISTORY & PERFORMANCE TRACKING**

**Recommendation**: Start with Codecov + Allure. Upgrade to custom DB only if you need >1 year history or custom analytics.
