# Manual Deployment Steps

## What We Fixed
Fixed the bug in `app/services/trigger_matcher.py` where it was trying to access `trigger.conditions` which doesn't exist. Now it properly uses the RunbookTrigger pattern fields:
- `alert_name_pattern`
- `severity_pattern`  
- `instance_pattern`
- `job_pattern`

## Already Done
✅ Fixed the code locally
✅ Committed the fix to git
✅ Pushed to remote repository

## Now You Need To Manually Do on Server

### 1. SSH to the server
```bash
ssh aftab@172.234.217.11
```

### 2. Navigate to the app directory
```bash
cd /home/aftab/aiops-platform
```

### 3. Pull the latest code
```bash
git pull origin codex/suggest-improvements-for-dashboard-ux
```

### 4. Stop the current container
```bash
docker-compose stop remediation-engine
```

### 5. Rebuild and restart the container
```bash
docker-compose up --build -d remediation-engine
```

### 6. Check the container is running
```bash
docker ps | grep remediation-engine
```

### 7. Watch the logs for the fix
```bash
docker logs remediation-engine --tail 100 --follow
```

Look for:
- No more "'RunbookTrigger' object has no attribute 'conditions'" errors
- Successful trigger matching when alerts come in

### 8. Exit the log viewer
Press `Ctrl+C` to stop following logs

### 9. Exit SSH
```bash
exit
```

## Then Test the Alert Again

Back on your local machine:

```bash
cd D:\remediate-engine-antigravity\remediation-engine
python fire_test_alert.py
```

Then monitor:
```bash
python monitor_alert_processing.py
```

## What to Look For

### In the logs, you should see:
```
2025-12-10 XX:XX:XX - app.routers.webhook - INFO - Stored alert: NginxDown (action: manual)
2025-12-10 XX:XX:XX - app.routers.webhook - INFO - Checking auto-remediation triggers for alert: NginxDown
2025-12-10 XX:XX:XX - app.services.trigger_matcher - INFO - Alert <id> processing complete: X auto-executed, Y pending approval, Z blocked
```

### No more ERROR like:
```
ERROR - 'RunbookTrigger' object has no attribute 'conditions'
```

### In the monitoring script:
```
[OK] Found 1 Nginx-related alert(s)
[OK] Execution triggered: 1 execution(s)
  Runbook: Restart Nginx Service (t-test-01)
  Status: pending
  [NEXT] Next Step: Approve the execution
```

## Alternative: Single SSH Command

If you prefer to do it all in one command:

```bash
ssh aftab@172.234.217.11 "cd /home/aftab/aiops-platform && git pull origin codex/suggest-improvements-for-dashboard-ux && docker-compose stop remediation-engine && docker-compose up --build -d remediation-engine && sleep 10 && docker logs remediation-engine --tail 50"
```

## Verification

After deployment and firing the alert:

1. ✅ Alert received in remediation engine
2. ✅ Trigger matching succeeds (no errors)
3. ✅ Runbook execution created
4. ✅ Execution awaiting approval or auto-executing
5. ✅ Full alert -> runbook flow working!
