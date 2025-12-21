# Prometheus Integration Configuration Guide

This document explains all configuration options for the Prometheus integration in the AIOps platform.

## Quick Start

Add these settings to your `.env` file:

```bash
PROMETHEUS_URL=http://prometheus:9090
ENABLE_PROMETHEUS_QUERIES=true
```

Restart the application, and you're ready to go!

## Configuration Categories

### 1. Basic Connection Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus server URL |
| `ENABLE_PROMETHEUS_QUERIES` | `true` | Master switch for all Prometheus features |
| `PROMETHEUS_TIMEOUT` | `30` | HTTP request timeout (seconds) |

**Example:**
```bash
PROMETHEUS_URL=http://10.0.0.50:9090
ENABLE_PROMETHEUS_QUERIES=true
PROMETHEUS_TIMEOUT=60
```

---

### 2. Dashboard Settings

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `PROMETHEUS_DASHBOARD_ENABLED` | `true` | Show Prometheus dashboard section | `true`, `false` |
| `PROMETHEUS_REFRESH_INTERVAL` | `30` | Auto-refresh interval (seconds) | `10-300` |
| `PROMETHEUS_DEFAULT_TIME_RANGE` | `24h` | Default time range for charts | `24h`, `7d`, `30d` |

**Example:**
```bash
PROMETHEUS_DASHBOARD_ENABLED=true
PROMETHEUS_REFRESH_INTERVAL=60
PROMETHEUS_DEFAULT_TIME_RANGE=24h
```

**Impact:**
- `PROMETHEUS_DASHBOARD_ENABLED=false` → Hides the Infrastructure Health section
- Higher `PROMETHEUS_REFRESH_INTERVAL` → Lower load on Prometheus, slower updates
- Lower values → More real-time, higher resource usage

---

### 3. Infrastructure Metrics

Control which metrics are displayed and their thresholds.

#### Visibility Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `INFRASTRUCTURE_METRICS_ENABLED` | `true` | Master switch for infrastructure section |
| `INFRASTRUCTURE_SHOW_CPU` | `true` | Show CPU metrics |
| `INFRASTRUCTURE_SHOW_MEMORY` | `true` | Show memory metrics |
| `INFRASTRUCTURE_SHOW_DISK` | `true` | Show disk metrics |

**Example:**
```bash
# Show only CPU and Memory, hide Disk
INFRASTRUCTURE_METRICS_ENABLED=true
INFRASTRUCTURE_SHOW_CPU=true
INFRASTRUCTURE_SHOW_MEMORY=true
INFRASTRUCTURE_SHOW_DISK=false
```

#### Threshold Settings

Control when metrics turn yellow (warning) or red (critical).

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| CPU | `INFRASTRUCTURE_CPU_WARNING_THRESHOLD=75` | `INFRASTRUCTURE_CPU_CRITICAL_THRESHOLD=90` |
| Memory | `INFRASTRUCTURE_MEMORY_WARNING_THRESHOLD=75` | `INFRASTRUCTURE_MEMORY_CRITICAL_THRESHOLD=90` |
| Disk | `INFRASTRUCTURE_DISK_WARNING_THRESHOLD=75` | `INFRASTRUCTURE_DISK_CRITICAL_THRESHOLD=90` |

**Color Coding:**
- 🟢 Green: Below warning threshold
- 🟡 Yellow: Between warning and critical
- 🔴 Red: Above critical threshold

**Example:**
```bash
# Conservative thresholds for production
INFRASTRUCTURE_CPU_WARNING_THRESHOLD=60
INFRASTRUCTURE_CPU_CRITICAL_THRESHOLD=80
INFRASTRUCTURE_MEMORY_WARNING_THRESHOLD=70
INFRASTRUCTURE_MEMORY_CRITICAL_THRESHOLD=85
```

---

### 4. Chart Configuration

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `CHART_LIBRARY` | `echarts` | Chart library to use | `echarts`, `chartjs` |
| `CHART_THEME` | `grafana-dark` | Chart theme | `grafana-dark`, `default`, `light` |
| `CHART_ENABLE_ZOOM` | `true` | Enable zoom/pan on charts | `true`, `false` |
| `CHART_ENABLE_ANIMATIONS` | `true` | Enable chart animations | `true`, `false` |
| `CHART_MAX_DATA_POINTS` | `1000` | Maximum data points per chart | `100-10000` |

**Example:**
```bash
# Optimize for performance
CHART_LIBRARY=echarts
CHART_THEME=grafana-dark
CHART_ENABLE_ZOOM=true
CHART_ENABLE_ANIMATIONS=false  # Disable for better performance
CHART_MAX_DATA_POINTS=500
```

---

### 5. Alert Trends

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `ALERT_TRENDS_ENABLED` | `true` | Show alert trends chart | `true`, `false` |
| `ALERT_TRENDS_DEFAULT_HOURS` | `24` | Default time range (hours) | `1-168` |
| `ALERT_TRENDS_STEP` | `1h` | Query resolution/step size | `15s`, `1m`, `5m`, `1h` |

**Example:**
```bash
# Show trends for last 7 days with hourly buckets
ALERT_TRENDS_ENABLED=true
ALERT_TRENDS_DEFAULT_HOURS=168
ALERT_TRENDS_STEP=1h
```

**Step Size Guide:**
- `15s` - High resolution, use for short time ranges (< 1 hour)
- `1m` - Medium resolution, good for 1-6 hours
- `5m` - Standard resolution, good for 1-2 days
- `1h` - Low resolution, best for > 7 days

---

### 6. Query Optimization

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `PROMETHEUS_USE_CACHE` | `true` | Enable query result caching | `true`, `false` |
| `PROMETHEUS_CACHE_TTL` | `60` | Cache time-to-live (seconds) | `10-3600` |
| `PROMETHEUS_MAX_RETRIES` | `3` | Max retry attempts on failure | `0-10` |
| `PROMETHEUS_RETRY_DELAY` | `2` | Delay between retries (seconds) | `1-60` |

**Example:**
```bash
# Aggressive caching for high-load scenarios
PROMETHEUS_USE_CACHE=true
PROMETHEUS_CACHE_TTL=300
PROMETHEUS_MAX_RETRIES=5
PROMETHEUS_RETRY_DELAY=3
```

---

## Configuration Scenarios

### Scenario 1: Development Environment

```bash
# Fast refresh, all features enabled
PROMETHEUS_URL=http://localhost:9090
ENABLE_PROMETHEUS_QUERIES=true
PROMETHEUS_REFRESH_INTERVAL=10
PROMETHEUS_TIMEOUT=10

INFRASTRUCTURE_METRICS_ENABLED=true
INFRASTRUCTURE_SHOW_CPU=true
INFRASTRUCTURE_SHOW_MEMORY=true
INFRASTRUCTURE_SHOW_DISK=true

CHART_ENABLE_ANIMATIONS=true
PROMETHEUS_USE_CACHE=false
```

### Scenario 2: Production Environment

```bash
# Conservative, performance-optimized
PROMETHEUS_URL=http://prometheus.production.internal:9090
ENABLE_PROMETHEUS_QUERIES=true
PROMETHEUS_REFRESH_INTERVAL=60
PROMETHEUS_TIMEOUT=30

# Stricter thresholds
INFRASTRUCTURE_CPU_WARNING_THRESHOLD=60
INFRASTRUCTURE_CPU_CRITICAL_THRESHOLD=80
INFRASTRUCTURE_MEMORY_WARNING_THRESHOLD=70
INFRASTRUCTURE_MEMORY_CRITICAL_THRESHOLD=85

# Performance optimizations
CHART_ENABLE_ANIMATIONS=false
CHART_MAX_DATA_POINTS=500
PROMETHEUS_USE_CACHE=true
PROMETHEUS_CACHE_TTL=300
```

### Scenario 3: Minimal Configuration

```bash
# Only show critical info, hide everything else
PROMETHEUS_URL=http://prometheus:9090
ENABLE_PROMETHEUS_QUERIES=true
PROMETHEUS_DASHBOARD_ENABLED=false
INFRASTRUCTURE_METRICS_ENABLED=false
ALERT_TRENDS_ENABLED=false
```

### Scenario 4: High-Load Environment

```bash
# Optimize for Prometheus server under heavy load
PROMETHEUS_REFRESH_INTERVAL=120
PROMETHEUS_TIMEOUT=60
PROMETHEUS_USE_CACHE=true
PROMETHEUS_CACHE_TTL=600
PROMETHEUS_MAX_RETRIES=5
PROMETHEUS_RETRY_DELAY=5

# Reduce data points
CHART_MAX_DATA_POINTS=200
ALERT_TRENDS_STEP=5m
```

---

## API Endpoints

### Get Current Configuration

```bash
GET /api/prometheus/config
```

**Response:**
```json
{
  "prometheus_url": "http://prometheus:9090",
  "enable_prometheus_queries": true,
  "prometheus_timeout": 30,
  "infrastructure_cpu_warning_threshold": 75,
  "infrastructure_cpu_critical_threshold": 90,
  ...
}
```

### Update Configuration

```bash
PUT /api/prometheus/config
Content-Type: application/json

{
  "prometheus_url": "http://prometheus:9090",
  "infrastructure_cpu_warning_threshold": 80,
  ...
}
```

**Note:** Configuration updates are written to `.env` and require application restart.

---

## Troubleshooting

### Prometheus Not Connecting

**Symptom:** Infrastructure Health shows "Offline" or "Error"

**Solutions:**
1. Check `PROMETHEUS_URL` is correct
2. Verify Prometheus is running: `curl http://prometheus:9090/-/healthy`
3. Check network connectivity from AIOps container
4. Increase `PROMETHEUS_TIMEOUT` if network is slow

### High Memory Usage

**Symptom:** Application consumes excessive memory

**Solutions:**
1. Reduce `CHART_MAX_DATA_POINTS` to `200-500`
2. Increase `PROMETHEUS_REFRESH_INTERVAL` to `120`
3. Disable caching: `PROMETHEUS_USE_CACHE=false`
4. Use larger `ALERT_TRENDS_STEP` (e.g., `5m` instead of `1m`)

### Slow Dashboard Loading

**Symptom:** Dashboard takes > 5 seconds to load

**Solutions:**
1. Enable caching: `PROMETHEUS_USE_CACHE=true`
2. Increase cache TTL: `PROMETHEUS_CACHE_TTL=300`
3. Reduce time range: `ALERT_TRENDS_DEFAULT_HOURS=12`
4. Disable animations: `CHART_ENABLE_ANIMATIONS=false`

### Metrics Not Showing

**Symptom:** Infrastructure Health section is empty

**Solutions:**
1. Verify `INFRASTRUCTURE_METRICS_ENABLED=true`
2. Check `INFRASTRUCTURE_SHOW_CPU/MEMORY/DISK` are `true`
3. Ensure Prometheus has `node_exporter` targets configured
4. Check Prometheus targets: `GET /api/prometheus/targets`

---

## Best Practices

### 1. Start with Defaults

Don't over-configure initially. The defaults work well for most scenarios:

```bash
PROMETHEUS_URL=http://prometheus:9090
ENABLE_PROMETHEUS_QUERIES=true
```

### 2. Tune for Your Workload

- **High-frequency monitoring** → Lower refresh interval (10-30s)
- **Large infrastructure** → Higher cache TTL, larger step sizes
- **Development** → All features enabled, fast refresh
- **Production** → Conservative thresholds, caching enabled

### 3. Monitor Prometheus Load

If Prometheus shows high load:
- Increase `PROMETHEUS_REFRESH_INTERVAL`
- Increase `ALERT_TRENDS_STEP`
- Reduce `CHART_MAX_DATA_POINTS`
- Enable caching with high TTL

### 4. Adjust Thresholds Based on Workload

```bash
# For batch processing servers (high CPU normal)
INFRASTRUCTURE_CPU_WARNING_THRESHOLD=85
INFRASTRUCTURE_CPU_CRITICAL_THRESHOLD=95

# For database servers (high memory normal)
INFRASTRUCTURE_MEMORY_WARNING_THRESHOLD=85
INFRASTRUCTURE_MEMORY_CRITICAL_THRESHOLD=95
```

---

## Summary

| Priority | Settings to Configure First |
|----------|---------------------------|
| **Must Configure** | `PROMETHEUS_URL`, `ENABLE_PROMETHEUS_QUERIES` |
| **Should Configure** | Warning/Critical thresholds for your workload |
| **Nice to Have** | Refresh interval, cache settings |
| **Optional** | Chart theme, animations, step sizes |

---

## See Also

- [Prometheus Query API Documentation](https://prometheus.io/docs/prometheus/latest/querying/api/)
- [Apache ECharts Documentation](https://echarts.apache.org/)
- [ECHARTS_MIGRATION.md](./ECHARTS_MIGRATION.md) - Chart library migration guide
