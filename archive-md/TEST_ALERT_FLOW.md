# End-to-End Alert Testing Guide

## Overview

This guide walks you through testing the complete alert-triggered remediation flow:
1. Create a runbook triggered by `NginxDown.*` alerts
2. Fire a test alert to Alertmanager
3. Watch the remediation engine receive and process the alert
4. Approve and execute the triggered runbook
5. Verify the results

## Prerequisites

✅ Prometheus running at http://172.234.217.11:9090  
✅ Alertmanager running at http://172.234.217.11:9093  
✅ Remediation Engine running at http://172.234.217.11:8080  
✅ Alertmanager configured to forward alerts to remediation engine  

## Configuration Check

### Alertmanager Webhook Configuration

Ensure your Alertmanager config (`alertmanager.yml`) has a webhook receiver:

```yaml
route:
  receiver: 'remediation-webhook'
  
receivers:
  - name: 'remediation-webhook'
    webhook_configs:
      - url: 'http://172.234.217.11:8080/api/alerts/webhook'
        send_resolved: true
```

## Step-by-Step Testing

### Step 1: Create Nginx Runbook

Run the script to create a runbook that will be triggered by NginxDown alerts:

```bash
python create_nginx_runbook.py
```

**Expected Output:**
```
Step 1: Logging in...
[OK] Logged in

Step 2: Looking up server 't-test-01'...
[OK] Found server: t-test-01 (ID: xxx)

Step 3: Creating Nginx restart runbook...
[OK] Created runbook: Restart Nginx Service (ID: xxx)

Runbook triggers:
  - NginxDown* alerts (any severity)
  - *nginx* alerts (critical)
```

**Verify:** Visit http://172.234.217.11:8080/runbooks and confirm the "Restart Nginx Service" runbook is there.

### Step 2: Fire Test Alert

Send a test alert to Alertmanager:

```bash
python fire_test_alert.py
```

**Expected Output:**
```
================================================================================
Firing Test Alert to Alertmanager
================================================================================

Alert Details:
  Name: NginxDown
  Severity: critical
  Instance: t-test-01
  Job: nginx-exporter

Sending alert to Alertmanager at http://172.234.217.11:9093...
[OK] Alert sent successfully!
     Status Code: 200

Next Steps:
1. Check Alertmanager UI: http://172.234.217.11:9093
2. Check remediation engine for triggered execution:
   http://172.234.217.11:8080/executions
3. Monitor runbook execution in real-time
```

### Step 3: Verify Alert in Alertmanager

1. Open: http://172.234.217.11:9093
2. You should see the "NginxDown" alert in the alerts list
3. Verify it's in "firing" state

### Step 4: Check Remediation Engine

1. Open: http://172.234.217.11:8080/alerts
2. You should see the NginxDown alert received
3. Open: http://172.234.217.11:8080/executions
4. You should see a NEW execution with status "pending" or "approved"

### Step 5: Approve Execution (if required)

If the runbook requires approval:

1. Go to: http://172.234.217.11:8080/executions
2. Find the execution for "Restart Nginx Service"
3. Click "Approve" button
4. Watch the execution progress in real-time

**Alternatively via API:**
```bash
# Get the execution ID from the UI or API
EXECUTION_ID="xxx"
TOKEN="your-auth-token"

curl -X POST "http://172.234.217.11:8080/api/remediation/executions/${EXECUTION_ID}/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "reason": "Testing alert-triggered remediation"}'
```

### Step 6: Monitor Execution

Watch the execution progress through these steps:

1. **Check Nginx Status** - Reads current status
2. **Test Nginx Configuration** - Validates nginx.conf
3. **Restart Nginx** - Restarts the service
4. **Verify Nginx Running** - Confirms it's active
5. **Test HTTP Response** - Checks web server

### Step 7: Resolve Alert (Optional)

After testing, resolve the alert:

```bash
# The script will prompt you to resolve
# Or run:
python fire_test_alert.py
# And press Enter when prompted
```

## Expected Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Fire Test Alert                                          │
│    python fire_test_alert.py                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Alertmanager Receives Alert                              │
│    http://172.234.217.11:9093 /#/alerts                     │
│    Alert State: FIRING                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Alertmanager Forwards to Webhook                         │
│    POST http://172.234.217.11:8080/api/alerts/webhook       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Remediation Engine Receives Alert                        │
│    - Stores alert in database                                │
│    - Matches against runbook triggers                        │
│    - Pattern: "NginxDown*" matches "NginxDown"              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Runbook Triggered                                        │
│    - Creates RunbookExecution record                         │
│    - Status: "pending" (waiting for approval)                │
│    - Target: t-test-01 server                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. User Approves Execution                                  │
│    http://172.234.217.11:8080/executions                    │
│    Click "Approve" button                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Runbook Executes                                         │
│    Status: "running"                                         │
│    Steps execute one by one:                                 │
│    [1/5] Check Nginx Status                                  │
│    [2/5] Test Nginx Configuration                            │
│    [3/5] Restart Nginx                                       │
│    [4/5] Verify Nginx Running                                │
│    [5/5] Test HTTP Response                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Execution Complete                                       │
│    Status: "success" or "failed"                             │
│    Result Summary: "All 5 steps completed successfully"      │
│    Notifications sent (Slack/Email)                          │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Alert Not Received

**Check:**
1. Alertmanager logs: `docker logs alertmanager`
2. Verify webhook URL in alertmanager config
3. Check remediation engine logs: `docker logs remediation-engine`
4. Test webhook manually:
   ```bash
   curl -X POST http://172.234.217.11:8080/api/alerts/webhook \
     -H "Content-Type: application/json" \
     -d '{"alerts":[{"labels":{"alertname":"NginxDown","instance":"t-test-01"}}]}'
   ```

### Runbook Not Triggered

**Check:**
1. Verify trigger pattern matches:
   - Alert name: "NginxDown"
   - Pattern: "NginxDown*"
   - Should match: ✅
2. Check runbook is enabled
3. Check trigger is enabled
4. Verify instance pattern matches: "t-test-01*"

### Execution Stuck in Pending

**Check:**
1. approval_required is set to True
2. User must manually approve
3. Check approval timeout (default 30 minutes)

### Execution Failed

**Check:**
1. View execution details in UI
2. Check step-by-step output
3. Verify server connectivity
4. Check command permissions (sudo required?)

## Verification Checklist

After running the test:

- [ ] Alert visible in Alertmanager UI
- [ ] Alert visible in Remediation Engine (/alerts)
- [ ] Execution created (/executions)
- [ ] Execution shows correct runbook name
- [ ] Execution shows correct target server
- [ ] Trigger pattern matched correctly
- [ ] Approval workflow works (if enabled)
- [ ] Steps execute in order
- [ ] Step output is captured
- [ ] Execution completes successfully
- [ ] Notifications sent (check Slack/Email)

## Advanced Testing

### Test Different Alert Patterns

```python
# Modify fire_test_alert.py to test different patterns:

# Test 1: Exact match
ALERT_NAME = "NginxDown"  # ✅ Matches "NginxDown*"

# Test 2: With suffix
ALERT_NAME = "NginxDownCritical"  # ✅ Matches "NginxDown*"

# Test 3: Lowercase nginx
ALERT_NAME = "nginxservicedown"  # ✅ Matches "*nginx*" (critical)

# Test 4: Should NOT match
ALERT_NAME = "ApacheDown"  # ❌ Won't trigger Nginx runbook
```

### Test Auto-Execute vs Manual Approval

Edit the runbook:
```python
"auto_execute": True,   # Will run immediately without approval
"approval_required": False,
```

### Test Dry Run

Execute runbook in dry run mode:
```bash
curl -X POST "http://172.234.217.11:8080/api/remediation/runbooks/{runbook_id}/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"server_id":"xxx","dry_run":true}'
```

## Cleanup

After testing, you may want to:

1. **Resolve the alert:**
   ```bash
   python fire_test_alert.py
   # Press Enter when prompted
   ```

2. **Delete test executions:**
   - Via UI: Go to /executions and delete
   - Or keep them for audit trail

3. **Disable test runbook:**
   - Via UI: Edit runbook and set "enabled" to false
   - Or keep it for future testing

## Next Steps

1. ✅ Create production runbooks for real services
2. ✅ Configure Prometheus rules for actual service monitoring
3. ✅ Set up proper notification channels
4. ✅ Enable circuit breakers for safety
5. ✅ Configure blackout windows for maintenance
6. ✅ Set up RBAC for approval workflows

## Files Created

- `create_nginx_runbook.py` - Creates NginxDown runbook
- `fire_test_alert.py` - Fires test alert to Alertmanager
- `test_alert_flow.md` - This guide

## Support

If you encounter issues:
1. Check logs: `docker logs remediation-engine`
2. Check database for alert/execution records
3. Verify webhook configuration in Alertmanager
4. Test connectivity between services
