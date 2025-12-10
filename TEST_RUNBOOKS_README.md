# Test Runbooks Creation Guide

This document describes the test runbooks that can be created for the `t-test-01` server to test the remediation engine functionality.

## Overview

The `create_test_runbooks.py` script creates multiple different types of runbooks targeting server `t-test-01` using the Remediation Engine REST API. These runbooks cover various operational scenarios to thoroughly test the platform's capabilities.

## Prerequisites

1. **Python 3.6+** with `requests` library installed:
   ```bash
   pip install requests
   ```

2. **Server Setup**: Ensure server `t-test-01` exists in the system
   - Hostname: `t-test-01`
   - OS Type: Linux
   - Protocol: SSH

3. **API Access**:
   - API URL: `http://172.234.217.11:8080`
   - Username: `admin`
   - Password: `Passw0rd`

## Usage

### Running the Script

```bash
# From the remediation-engine directory
python create_test_runbooks.py
```

### Configuration

Edit the script to customize:
- `API_BASE_URL`: API endpoint URL
- `USERNAME`: API username
- `PASSWORD`: API password
- `TARGET_SERVER_HOSTNAME`: Target server hostname

## Created Runbooks

The script creates **6 different runbook types**:

### 1. Apache Restart Runbook
**Category**: web-services  
**Auto-Execute**: No (requires approval)
**Steps**:
1. Check Apache status
2. Restart Apache service
3. Verify Apache is running
4. Test HTTP response

**Triggers**:
- Alert pattern: `*Apache*` or `*httpd*`
- Severity: critical
- Instance: `t-test-01*`

**Use Case**: Automatically restart Apache when it becomes unresponsive or crashes.

---

### 2. Disk Space Cleanup Runbook
**Category**: infrastructure  
**Auto-Execute**: No (requires approval)  
**Steps**:
1. Check disk usage before cleanup
2. Clean package manager cache (apt/yum)
3. Remove old log files (>30 days)
4. Clean temporary files (>7 days)
5. Check disk usage after cleanup

**Triggers**:
- Alert pattern: `*DiskSpace*` or `*HighDiskUsage*`
- Severity: warning or any
- Instance: `t-test-01*`

**Use Case**: Free up disk space when filesystems are running low.

---

### 3. System Health Check Runbook
**Category**: diagnostics  
**Auto-Execute**: Yes (safe read-only commands)  
**Steps**:
1. Check CPU usage
2. Check memory usage
3. Check disk I/O statistics
4. Check network connectivity
5. List running services
6. Check system uptime

**Triggers**:
- Alert pattern: `*SystemCheck*`
- Severity: any
- Instance: `t-test-01*`

**Use Case**: Automated system health diagnostics triggered by alerts.

---

### 4. Kill Hung Process Runbook
**Category**: process-management  
**Auto-Execute**: No (requires approval)  
**Steps**:
1. Identify high CPU processes
2. List zombie processes
3. Send SIGTERM (graceful termination)
4. Send SIGKILL (force kill if needed)
5. Verify process terminated

**Triggers**:
- Alert pattern: `*ProcessHung*` or `*HighCPU*`
- Severity: critical or any
- Instance: `t-test-01*`

**Use Case**: Terminate hung or zombie processes consuming excessive resources.

---

### 5. Network Diagnostics Runbook
**Category**: network  
**Auto-Execute**: Yes (safe diagnostic commands)  
**Steps**:
1. Check network interfaces
2. Test DNS resolution
3. Check default gateway
4. Ping gateway
5. Traceroute to 8.8.8.8
6. Check active connections

**Triggers**:
- Alert pattern: `*NetworkDown*` or `*DNSFailure*`
- Severity: any
- Instance: `t-test-01*`

**Use Case**: Comprehensive network diagnostics when connectivity issues arise.

---

### 6. PostgreSQL Restart Runbook
**Category**: database  
**Auto-Execute**: No (requires approval)  
**Steps**:
1. Check PostgreSQL status
2. Check active database connections
3. Restart PostgreSQL service
4. Verify PostgreSQL is running
5. Test database connection

**Triggers**:
- Alert pattern: `*PostgreSQL*` or `*DatabaseDown*`
- Severity: critical
- Instance: `t-test-01*`

**Use Case**: Safely restart PostgreSQL database with pre and post validation checks.

---

## Testing the Runbooks

After creating the runbooks, you can test them:

### 1. Manual Execution via UI
1. Navigate to `http://172.234.217.11:8080/runbooks`
2. Find the runbook you want to test
3. Click "Execute"
4. Select server `t-test-01`
5. Approve execution (if required)
6. Monitor execution progress

### 2. Manual Execution via API
```bash
# Execute a runbook
curl -X POST "http://172.234.217.11:8080/api/remediation/runbooks/{runbook_id}/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "SERVER_UUID",
    "dry_run": false
  }'
```

### 3. Trigger-Based Execution
Create matching alerts in Prometheus/Alertmanager to automatically trigger the runbooks.

## Runbook Features Demonstrated

These test runbooks demonstrate various platform capabilities:

1. **Multi-step workflows**: Each runbook has 4-6 steps
2. **Error handling**: Retry logic, continue-on-fail options
3. **Rollback commands**: For critical operations like service restarts
4. **Approval workflows**: Some require manual approval, others auto-execute
5. **Safety mechanisms**: 
   - Rate limiting (max executions per hour)
   - Cooldown periods between executions
   - Execution timeouts
6. **Trigger patterns**: Alert name, severity, and instance matching
7. **Notifications**: Slack and email notifications on different events
8. **Platform support**: Linux-specific commands with OS filtering

## Cleanup

To remove all created runbooks:

```bash
# List all runbooks
curl -X GET "http://172.234.217.11:8080/api/remediation/runbooks" \
  -H "Authorization: Bearer $TOKEN"

# Delete a runbook
curl -X DELETE "http://172.234.217.11:8080/api/remediation/runbooks/{runbook_id}" \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

### Server Not Found
If you get "Server t-test-01 not found":
1. Create the server via UI or API
2. Or update `TARGET_SERVER_HOSTNAME` in the script to match an existing server

### Authentication Failed
- Verify credentials in the script
- Check if the API is accessible at the configured URL

### Runbook Creation Failed
- Check API response for detailed error messages
- Verify all required fields are present
- Ensure server_id is valid UUID

## API Endpoints Reference

- **Login**: `POST /api/auth/login`
- **List Servers**: `GET /api/servers`
- **List Runbooks**: `GET /api/remediation/runbooks`
- **Create Runbook**: `POST /api/remediation/runbooks`
- **Get Runbook**: `GET /api/remediation/runbooks/{id}`
- **Execute Runbook**: `POST /api/remediation/runbooks/{id}/execute`
- **Delete Runbook**: `DELETE /api/remediation/runbooks/{id}`

## Notes

- All runbooks target Linux servers only (`target_os_filter: ["linux"]`)
- Commands use common Linux utilities (systemctl, apt-get, yum, etc.)
- Some commands may require sudo privileges (`requires_elevation: true`)
- Diagnostic runbooks are safe to auto-execute
- Destructive operations (restarts, kills) require approval

## Next Steps

After creating these runbooks:

1. **Test execution**: Run each runbook manually to verify functionality
2. **Create alerts**: Set up matching Prometheus alerts to trigger runbooks
3. **Monitor executions**: Review execution history and logs
4. **Tune parameters**: Adjust timeouts, retry counts, cooldown periods
5. **Add notifications**: Configure Slack/email notification channels
6. **Create variations**: Clone and modify runbooks for different servers/scenarios
