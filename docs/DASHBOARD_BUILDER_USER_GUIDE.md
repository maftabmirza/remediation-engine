# Prometheus Dashboard Builder - User Guide

Welcome to the AIOps Platform's integrated Prometheus Dashboard Builder! This guide will help you create custom dashboards to visualize your Prometheus metrics without needing external Grafana.

## 📚 Table of Contents

1. [Getting Started](#getting-started)
2. [Managing Datasources](#managing-datasources)
3. [Creating Panels](#creating-panels)
4. [Building Dashboards](#building-dashboards)
5. [Using Templates](#using-templates)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## 🚀 Getting Started

### Prerequisites

- Access to the AIOps Platform
- At least one Prometheus server running
- User account with appropriate permissions

### Quick Start (5 Minutes)

1. **Configure Datasource**: Navigate to `/datasources` and verify your default Prometheus datasource is configured
2. **Browse Templates**: Go to `/panels` and explore the 15 pre-built panel templates
3. **Create Dashboard**: Visit `/dashboards-builder` and create your first dashboard
4. **Add Panels**: Select panels from templates and add them to your dashboard
5. **View Results**: Click the eye icon to view your dashboard with live charts

## 🔌 Managing Datasources

Datasources are connections to your Prometheus servers. You can configure multiple Prometheus instances.

### Adding a Datasource

1. Navigate to **Datasources** page (`/datasources`)
2. Click **"Add Datasource"**
3. Fill in the form:
   - **Name**: Friendly name (e.g., "Production Prometheus")
   - **URL**: Full URL including protocol (e.g., `http://prometheus:9090`)
   - **Description**: Optional description
   - **Authentication**: Choose auth type (None, Basic Auth, or Bearer Token)
   - **Timeout**: Request timeout in seconds (default: 30)
   - **Set as Default**: Check to make this the default datasource
   - **Enabled**: Check to enable this datasource
4. Click **"Save"**

### Testing Connection

After creating a datasource:
1. Click the ⚡ (lightning bolt) icon next to your datasource
2. Wait for the test to complete
3. Success message will show Prometheus version
4. Error message will help diagnose connection issues

### Managing Multiple Datasources

You can have multiple Prometheus servers configured:
- **Production**: Your production metrics
- **Staging**: Staging environment metrics
- **Development**: Development metrics

Each panel can query a different datasource!

## 📊 Creating Panels

Panels are reusable query configurations that fetch data from Prometheus and display it as charts.

### Using Pre-Built Templates

The platform includes 15 pre-built templates:

1. **CPU Usage by Instance** - Shows CPU percentage per instance
2. **Memory Usage** - Memory usage in GB
3. **Disk Usage Percentage** - Disk space usage with thresholds
4. **Network Traffic (RX/TX)** - Network receive and transmit rates
5. **HTTP Request Rate** - Requests per second by method and status
6. **HTTP Error Rate** - Percentage of 5xx errors
7. **HTTP Latency (p95)** - 95th percentile request duration
8. **Container CPU/Memory** - Kubernetes container metrics
9. **Pod Restarts** - Kubernetes pod restart counts
10. **Database Connections** - PostgreSQL connection pool
11. **API Response Time** - Average response time by endpoint
12. **Active Alerts** - Current firing alerts
13. **Up/Down Status** - Target availability

To use a template:
1. Navigate to `/panels`
2. Filter by "Templates Only"
3. Click edit icon to view the template
4. Modify as needed and save with a new name

### Creating Custom Panels

1. Go to **Panels** page (`/panels`)
2. Click **"Create Panel"**
3. Fill in the form:

#### Basic Information
- **Panel Name**: Descriptive name (e.g., "API Server CPU")
- **Description**: Optional detailed description
- **Datasource**: Select which Prometheus to query
- **Panel Type**: Choose visualization type
  - **Graph**: Time-series line chart
  - **Gauge**: Single value with colored ranges
  - **Stat**: Large number display
  - **Table**: Tabular data view

#### Query Configuration
- **Query Examples**: Select from dropdown to auto-populate common queries
- **PromQL Query**: Your Prometheus query (required)
- **Legend Format**: Template for series names (e.g., `{{instance}}`)
- **Tags**: Comma-separated tags for organization

#### Display Settings
- **Time Range**: Default time window (5m to 30d)
- **Refresh Interval**: How often to update (5-3600 seconds)
- **Save as Template**: Check to make this reusable
- **Public**: Check to share with other users

4. Click **"Test Query"** to validate before saving
5. Click **"Save Panel"**

### PromQL Query Examples

Here are some useful PromQL queries:

```promql
# CPU Usage Percentage
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory Usage in GB
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1024 / 1024 / 1024

# Disk Usage Percentage
100 - ((node_filesystem_avail_bytes * 100) / node_filesystem_size_bytes)

# HTTP Request Rate
sum(rate(http_requests_total[5m])) by (method, status)

# Active Alerts
ALERTS{alertstate="firing"}

# Container CPU
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (container)
```

## 🎨 Building Dashboards

Dashboards combine multiple panels into a unified view.

### Creating a Dashboard

1. Navigate to **Dashboard Builder** (`/dashboards-builder`)
2. Click **"New Dashboard"**
3. Configure dashboard:
   - **Name**: Dashboard name (e.g., "Infrastructure Overview")
   - **Description**: Optional description
   - **Time Range**: Default time range for all panels
   - **Refresh Interval**: Auto-refresh interval in seconds
   - **Auto Refresh**: Enable automatic data refresh
   - **Folder**: Optional folder for organization
   - **Public**: Make dashboard visible to all users
   - **Favorite**: Mark as favorite for quick access
   - **Set as Home**: Make this the default dashboard
4. Click **"Save Dashboard"**

### Adding Panels to Dashboard

1. Find your dashboard in the list
2. Click **"Add Panels"** button
3. Select panels from the list (checkboxes)
4. Click **"Add Selected"**
5. Panels are automatically arranged in a grid layout

### Viewing Dashboard

1. Click the 👁️ (eye) icon on your dashboard
2. The dashboard view shows:
   - All panels with live data
   - Time range selector
   - Refresh button
   - Auto-refresh indicator
3. Charts update based on the dashboard's refresh interval

### Dashboard Management

**Edit Dashboard**:
- Click edit icon
- Modify settings
- Save changes

**Clone Dashboard**:
- Useful for creating variations
- Creates a copy with all panels

**Delete Dashboard**:
- Removes dashboard but keeps panels
- Panels can be reused in other dashboards

## 🎯 Using Templates

### Panel Templates

Panel templates are pre-configured queries that you can use as-is or customize:

1. Browse templates at `/panels` (filter: Templates Only)
2. Click edit to view the template
3. Modify for your environment
4. Save with a new name
5. Add to your dashboards

### Creating Your Own Templates

1. Create a panel with a commonly-used query
2. Check **"Save as Template"**
3. Add descriptive tags
4. Save
5. It will appear in templates list

### Template Best Practices

- Use clear, descriptive names
- Add comprehensive descriptions
- Include all relevant tags
- Test queries thoroughly
- Use legend format for clarity

## 💡 Best Practices

### Query Optimization

1. **Use appropriate time ranges**: Longer ranges = more data
2. **Rate vs irate**: Use `rate()` for alerts, `irate()` for graphs
3. **Aggregation**: Use `by` clause to group metrics
4. **Regex carefully**: Regex in labels can be slow

### Dashboard Organization

1. **Group related panels**: CPU, memory, disk together
2. **Use consistent time ranges**: Easier to correlate issues
3. **Name dashboards clearly**: "Prod - Infrastructure" not "Dashboard 1"
4. **Use folders**: Organize by environment or service
5. **Set home dashboard**: Your most important view

### Performance Tips

1. **Limit panels per dashboard**: 10-20 panels max
2. **Use appropriate refresh intervals**: Don't refresh every 5s unless needed
3. **Optimize queries**: Avoid expensive queries
4. **Use caching**: Prometheus caches query results

### Security

1. **Credential management**: Use environment variables for sensitive data
2. **Access control**: Mark dashboards as public only when appropriate
3. **Authentication**: Always use authentication for production Prometheus
4. **Encryption**: Platform encrypts all passwords/tokens

## 🔧 Troubleshooting

### Datasource Connection Failed

**Symptoms**: Test connection shows error

**Solutions**:
1. Verify Prometheus URL is correct (include `http://` or `https://`)
2. Check Prometheus is running: `curl http://prometheus:9090/api/v1/status/buildinfo`
3. Verify network connectivity
4. Check authentication credentials
5. Review timeout setting (increase if needed)

### Query Returns No Data

**Symptoms**: Panel shows "No data" or empty chart

**Solutions**:
1. Test query in Prometheus UI first
2. Verify time range has data
3. Check metric names are correct
4. Ensure labels match your environment
5. Use `up` query to verify Prometheus is scraping targets

### Templates Not Showing

**Symptoms**: No panel templates visible

**Solutions**:
1. Check application logs for template seeding errors
2. Verify default datasource exists
3. Manually trigger template seed (restart application)
4. Check database: `SELECT COUNT(*) FROM prometheus_panels WHERE is_template = true;`

### Charts Not Rendering

**Symptoms**: Dashboard view shows loading or errors

**Solutions**:
1. Check browser console for JavaScript errors
2. Verify Prometheus has data for the time range
3. Test panel queries individually
4. Check if auto-refresh is causing issues
5. Try different time ranges

### Authentication Errors

**Symptoms**: "Unauthorized" or "401" errors

**Solutions**:
1. Verify you're logged in
2. Check token hasn't expired
3. Ensure user has appropriate permissions
4. Try logging out and back in

### Migration Issues

**Symptoms**: Application won't start, database errors

**Solutions**:
1. Check migration logs
2. Verify all migrations ran: `SELECT * FROM alembic_version;`
3. Manually run migration if needed
4. Check for conflicting table names

## 📖 Additional Resources

- **Prometheus Query Documentation**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **PromQL Examples**: https://prometheus.io/docs/prometheus/latest/querying/examples/
- **Best Practices**: https://prometheus.io/docs/practices/naming/
- **Metric Types**: https://prometheus.io/docs/concepts/metric_types/

## 🆘 Getting Help

If you encounter issues:

1. Check this guide's troubleshooting section
2. Review application logs
3. Test queries in Prometheus UI
4. Check GitHub issues: https://github.com/anthropics/aiops-platform/issues
5. Contact your platform administrator

## 📝 Quick Reference

### Keyboard Shortcuts

- `Ctrl/Cmd + S`: Save (in modal forms)
- `Esc`: Close modal
- `F5`: Refresh page

### API Endpoints

- `GET /api/datasources/` - List datasources
- `POST /api/datasources/` - Create datasource
- `GET /api/panels/` - List panels
- `POST /api/panels/` - Create panel
- `POST /api/panels/test-query` - Test query
- `GET /api/dashboards/` - List dashboards
- `POST /api/dashboards/` - Create dashboard

### Common PromQL Functions

- `rate()` - Per-second rate over time
- `sum()` - Sum values across dimensions
- `avg()` - Average values
- `max()` / `min()` - Maximum/minimum values
- `by` - Group by labels
- `histogram_quantile()` - Calculate percentiles

---

**Version**: 2.0.0
**Last Updated**: December 2025
**Platform**: AIOps Remediation Engine
