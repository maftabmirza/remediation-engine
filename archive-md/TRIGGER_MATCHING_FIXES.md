# Alert Trigger Matching - Bugs Fixed

## Summary

Fixed **3 critical bugs** in `app/services/trigger_matcher.py` that prevented alert-triggered runbook execution from working.

## Bugs Fixed

### Bug 1: Non-existent `trigger.conditions` attribute
**Error**: `'RunbookTrigger' object has no attribute 'conditions'`

**Cause**: Code was written for an old model that used a JSON `conditions` field

**Fix**: Updated to use actual RunbookTrigger pattern fields:
- `alert_name_pattern` (e.g., "NginxDown*")
- `severity_pattern` (e.g., "*", "critical")
- `instance_pattern` (e.g., "t-test-01*")
- `job_pattern` (e.g., "*")

### Bug 2: Non-existent `CircuitBreaker.runbook_id`
**Error**: `type object 'CircuitBreaker' has no attribute 'runbook_id'`

**Cause**: CircuitBreaker model uses generic `scope` and `scope_id` fields

**Fix**: Changed query from:
```python
CircuitBreaker.runbook_id == runbook.id
```
To:
```python
CircuitBreaker.scope == "runbook" AND CircuitBreaker.scope_id == runbook.id
```

### Bug 3: Non-existent `ExecutionRateLimit.runbook_id`
**Error**: `type object 'ExecutionRateLimit' has no attribute 'runbook_id'`

**Cause**: Code tried to query ExecutionRateLimit table which doesn't match the actual model

**Fix**: Use runbook's own built-in rate limiting settings instead:
- `runbook.max_executions_per_hour` - Max executions in 1 hour window
- `runbook.cooldown_minutes` - Minimum time between executions

## Deployment Required

### On Server (172.234.217.11):

```bash
ssh aftab@172.234.217.11
cd /home/aftab/aiops-platform
git pull origin codex/suggest-improvements-for-dashboard-ux
docker-compose restart remediation-engine
sleep 10
docker logs remediation-engine --tail 100 --follow
# Press Ctrl+C to stop watching logs
exit
```

### Then Test Again:

```bash
cd D:\remediate-engine-antigravity\remediation-engine
python fire_test_alert.py
python monitor_alert_processing.py
```

## Expected Result After Fix

✅ No more `'RunbookTrigger' object has no attribute 'conditions'` error  
✅ No more `'CircuitBreaker' object has no attribute 'runbook_id'` error  
✅ No more `'ExecutionRateLimit' object has no attribute 'runbook_id'` error  
✅ Trigger matching completes successfully  
✅ Runbook execution is automatically created  
✅ Full alert → runbook triggering works!

## Git Commits

```
e7f0235 - Fix: Rate limiting to use runbook's own settings instead of ExecutionRateLimit table
a5a0140 - Fix: CircuitBreaker query to use scope and scope_id instead of runbook_id
bc7ff97 - Fix: Alert trigger matching - use actual RunbookTrigger fields
```

## Files Changed

- `app/services/trigger_matcher.py` (3 fixes applied)

All fixes have been committed and pushed to the repository.
