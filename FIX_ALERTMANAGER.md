# 🔧 Fix Alertmanager Webhook Configuration

## Problem

Alertmanager is sending alerts to **WRONG URL**:
- ❌ Current: `http://remediation-engine:8080/webhook/alerts`
- ✅ Should be: `http://remediation-engine:8080/api/alerts/webhook`

This is why no alerts are reaching the remediation engine!

## Solution

### On Server (172.234.217.11)

```bash
ssh aftab@172.234.217.11
cd /home/aftab/aiops-platform
```

### Option 1: Quick Fix with sed

```bash
# Backup current config
cp alertmanager/alertmanager.yml alertmanager/alertmanager.yml.backup

# Fix all webhook URLs
sed -i 's|/webhook/alerts|/api/alerts/webhook|g' alertmanager/alertmanager.yml

# Verify the fix
grep "webhook" alertmanager/alertmanager.yml

# Reload Alertmanager
docker exec alertmanager kill -HUP 1
```

### Option 2: Manual Edit

```bash
# Edit the config file
nano alertmanager/alertmanager.yml

# Change all instances of:
#   url: 'http://remediation-engine:8080/webhook/alerts'
# To:
#   url: 'http://remediation-engine:8080/api/alerts/webhook'

# Save and exit (Ctrl+X, Y, Enter)

# Reload Alertmanager
docker exec alertmanager kill -HUP 1
```

### Option 3: Copy Pre-Fixed File

From your local machine:

```bash
# Copy the fixed config to server
scp alertmanager-fix.yml aftab@172.234.217.11:/home/aftab/aiops-platform/alertmanager/alertmanager.yml

# Then on server, reload:
ssh aftab@172.234.217.11 "docker exec alertmanager kill -HUP 1"
```

## Verify Fix

After applying the fix, check that Alertmanager reloaded successfully:

```bash
docker logs --tail 20 alertmanager
```

Look for:
```
level=info msg="Completed loading of configuration file"
```

## Test Alert Flow

After fixing the configuration:

```bash
python fire_test_alert.py
```

Wait 5 seconds, then:

```bash
python monitor_alert_processing.py
```

## Expected Result

✅ Alert sent to Alertmanager  
✅ Alertmanager forwards to **correct** webhook URL  
✅ Remediation engine receives alert  
✅ Trigger matching runs  
✅ Execution created with status "pending_approval"  
✅ **SUCCESS!** 🎉

## Why This Happened

The remediation engine API uses the standard FastAPI route structure:
- `/api/alerts/webhook` - Correct webhook endpoint
- `/webhook/alerts` - This route doesn't exist!

The Alertmanager config was using an old/incorrect path.
