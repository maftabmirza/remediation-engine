# MCP Grafana Setup Guide

## Overview

The MCP (Model Context Protocol) Grafana server provides a standardized interface for AI agents to interact with Grafana, including dashboards, alerts, queries, and datasources. This guide covers deployment, configuration, and troubleshooting.

## Prerequisites

### 1. Grafana Instance
- Grafana version 9.0 or higher
- Accessible via HTTP/HTTPS
- Admin access for service account creation

### 2. Docker Environment
- Docker Engine 20.10+
- Docker Compose 2.0+
- Network: `aiops-network` (created by main application)

### 3. Service Account Token
You need a Grafana service account with appropriate permissions.

## Quick Start

### Step 1: Create Grafana Service Account

1. Log in to Grafana as admin
2. Navigate to **Administration → Service Accounts**
3. Click **Add service account**
4. Configure:
   - **Display name**: `MCP Server`
   - **Role**: `Editor` or `Admin` (depending on required permissions)
5. Click **Create**
6. Click **Add service account token**
7. Configure token:
   - **Display name**: `MCP Access Token`
   - **Expiration**: Set based on your security policy (or no expiration for lab)
8. Click **Generate token**
9. **IMPORTANT**: Copy the token immediately (starts with `glsa_`)

### Step 2: Configure Environment

```bash
cd docker/mcp-grafana
cp .env.example .env
```

Edit `.env` and set:

```bash
GRAFANA_URL=http://grafana:3000  # Or your Grafana URL
GRAFANA_SERVICE_ACCOUNT_TOKEN=glsa_xxxxxxxxxxxxxxxxxxxxx  # Token from Step 1
```

### Step 3: Deploy

```bash
# Ensure aiops-network exists
docker network create aiops-network

# Start MCP Grafana server
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Step 4: Verify Deployment

```bash
# Check health endpoint
curl http://localhost:8081/health

# Expected response:
# {"status": "healthy", "grafana_connection": "ok"}
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GRAFANA_URL` | Grafana instance URL | `http://grafana:3000` | ✅ |
| `GRAFANA_SERVICE_ACCOUNT_TOKEN` | Service account token | - | ✅ |
| `MCP_SERVER_PORT` | Internal server port | `8080` | ❌ |
| `MCP_EXTERNAL_PORT` | External mapped port | `8081` | ❌ |
| `LOG_LEVEL` | Logging verbosity | `info` | ❌ |
| `NETWORK_NAME` | Docker network name | `aiops-network` | ❌ |

### Logging Levels

- `debug`: Verbose logging (use for troubleshooting)
- `info`: Standard operational logging (recommended)
- `warn`: Warnings and errors only
- `error`: Errors only

## Integration with Remediation Engine

### Update Application Configuration

Edit `app/config.py` (or environment variables):

```python
# MCP Grafana Configuration
MCP_GRAFANA_URL = "http://mcp-grafana:8080"  # Internal Docker network
# or
MCP_GRAFANA_URL = "http://localhost:8081"    # If running separately
```

### Verify Connection

```python
# From Python shell or test script
from app.services.mcp.client import MCPClient

client = MCPClient()
result = await client.list_tools()
print(f"Available tools: {len(result.tools)}")
# Expected: 20+ Grafana tools
```

## Available MCP Tools

Once deployed, the following tool categories are available:

### Dashboard Management
- `search_dashboards` - Find dashboards by query
- `get_dashboard` - Get dashboard by UID
- `create_dashboard` - Create new dashboard
- `update_dashboard` - Modify existing dashboard
- `delete_dashboard` - Remove dashboard

### Alert Management
- `list_alert_rules` - Query alert rules
- `get_alert_rule` - Get specific rule
- `create_alert_rule` - Define new alert
- `update_alert_rule` - Modify alert
- `delete_alert_rule` - Remove alert

### Queries & Datasources
- `query_prometheus` - Execute PromQL queries
- `query_loki` - Execute LogQL queries
- `query_tempo` - Query traces
- `list_datasources` - Get configured datasources
- `test_datasource` - Verify datasource connection

### Annotations
- `create_annotation` - Add annotation to dashboard
- `list_annotations` - Query annotations

### OnCall (if configured)
- `get_oncall_schedule` - Get on-call schedules
- `get_oncall_users` - List on-call users

## Troubleshooting

### Connection Issues

**Problem**: MCP server won't start

```bash
# Check logs
docker-compose logs

# Common issues:
# 1. Invalid Grafana URL
# 2. Network not created
# 3. Port conflict
```

**Solution**:
```bash
# Verify network
docker network ls | grep aiops

# Create if missing
docker network create aiops-network

# Check port availability
netstat -an | grep 8081
```

**Problem**: Health check failing

```bash
# Check Grafana connectivity from container
docker exec mcp-grafana curl -v http://grafana:3000/api/health
```

**Solution**:
- Verify `GRAFANA_URL` is correct
- Ensure Grafana is running and accessible
- Check service account token is valid

### Permission Issues

**Problem**: Tools return 403 Forbidden

**Cause**: Service account has insufficient permissions

**Solution**:
1. Check service account role in Grafana
2. Ensure role has required permissions:
   - **Viewer**: Read-only access
   - **Editor**: Read + create/update
   - **Admin**: Full access including delete

### Performance Issues

**Problem**: Slow response times

**Diagnosis**:
```bash
# Check resource usage
docker stats mcp-grafana

# Check logs for slow queries
docker-compose logs | grep "duration"
```

**Solution**:
- Increase resource limits in `docker-compose.yml`
- Enable caching in Grafana
- Optimize database queries

## Security Considerations

### Service Account Token
- **Never commit tokens to version control**
- Use environment variables or secrets management
- Rotate tokens periodically
- Set expiration dates where possible

### Network Security
- Keep MCP server on internal Docker network
- Use TLS for Grafana connection in production
- Restrict MCP port exposure (only to application)

### RBAC Integration
The Remediation Engine's AI Permission Service controls which users can execute which MCP tools. The MCP server itself uses a service account with broad permissions, but user actions are filtered by the application layer.

## Monitoring

### Health Checks

The MCP server exposes a health endpoint:

```bash
curl http://localhost:8081/health
```

Response:
```json
{
  "status": "healthy",
  "grafana_connection": "ok",
  "uptime_seconds": 3600,
  "version": "1.0.0"
}
```

### Metrics (if available)

Some MCP implementations expose Prometheus metrics at `/metrics`:

```bash
curl http://localhost:8081/metrics
```

### Log Aggregation

Configure Docker logging to send to your log aggregation system:

```yaml
logging:
  driver: "syslog"
  options:
    syslog-address: "tcp://logstash:5000"
    tag: "mcp-grafana"
```

## Upgrading

```bash
# Pull latest image
docker-compose pull

# Restart with new image
docker-compose up -d

# Verify
docker-compose logs -f
```

## Backup & Recovery

The MCP server is stateless - all configuration is in Grafana. To backup:

1. Backup Grafana database/dashboards
2. Save `.env` file securely
3. Document service account tokens

## Development Mode

For local development with hot-reload:

```yaml
# docker-compose.override.yml
services:
  mcp-grafana:
    environment:
      - LOG_LEVEL=debug
      - DEV_MODE=true
    volumes:
      - ./mcp-grafana-config:/config  # If custom config needed
```

## FAQ

**Q: Can I run MCP Grafana on a different host?**  
A: Yes, set `MCP_GRAFANA_URL` in the application config to the remote URL.

**Q: Does this work with Grafana Cloud?**  
A: Yes, set `GRAFANA_URL` to your Grafana Cloud instance URL.

**Q: How many concurrent requests can it handle?**  
A: Depends on resources. Default limits support ~10-20 concurrent AI sessions.

**Q: Can I use multiple MCP servers for load balancing?**  
A: Yes, deploy multiple instances behind a load balancer and update `MCP_GRAFANA_URL`.

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Verify Grafana connectivity
3. Test with `curl` to isolate issue
4. Review [MCP Grafana GitHub](https://github.com/grafana/mcp-grafana)

## References

- [MCP Protocol Specification](https://modelcontextprotocol.io/docs)
- [Grafana API Documentation](https://grafana.com/docs/grafana/latest/developers/http_api/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
