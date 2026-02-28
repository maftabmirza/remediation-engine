# PII Security Testing - Quick Start Guide

## Quick Test Commands

### 1. Implementation Check (No running app needed)
```bash
python test_pii_security_integration.py
```
**What it does:** Verifies PII security code is properly implemented in all agents

### 2. Full Integration Test (Requires running app)
```bash
# Start app if not running
docker-compose up -d

# Run comprehensive tests
python test_pii_all_agents.py
```
**What it does:** Tests actual PII detection/redaction with live API calls

### 3. Direct PII API Test
```bash
python test_pii_e2e.py
```
**What it does:** Tests PII detection and redaction APIs directly

## Test Coverage

| Agent Mode | Endpoint | PII Detection | Tool Scanning | Status |
|------------|----------|---------------|---------------|--------|
| Alert Help | `/api/alerts/{id}/chat` | ✅ | N/A | ✅ IMPLEMENTED |
| RE-VIVE | `/api/revive/chat` | ✅ | N/A | ✅ IMPLEMENTED |
| Troubleshoot | `/api/troubleshoot/chat` | ✅ | ✅ | ✅ IMPLEMENTED |

## What Gets Tested

### PII Types
- ✅ Email addresses
- ✅ Phone numbers
- ✅ SSN (Social Security Numbers)
- ✅ Credit card numbers
- ✅ IP addresses
- ✅ Person names

### Secrets
- ✅ AWS access keys
- ✅ GitHub tokens
- ✅ API keys
- ✅ High-entropy strings

## Expected Test Results

### ✅ PASS
```
✅ Alert Agent:        PASS
✅ RE-VIVE Agent:      PASS
✅ Troubleshoot Agent: PASS

8/8 tests passed
```

### ❌ FAIL (Security Issue)
```
❌ FAIL: Sensitive data leaked in response
```

## Key Implementation Details

### All Three Agents Have:

1. **User Input Scanning**
   ```python
   processed_message = await self._scan_and_redact_text(
       user_message,
       source_type="user_input",
       context_label="user input",
   )
   ```

2. **PIIMappingManager Integration**
   - Consistent redaction across session
   - Indexed placeholders: `[EMAIL_1]`, `[PHONE_1]`
   - Reversible for authorized users

3. **Detection Logging**
   - All detections logged to database
   - Audit trail for compliance
   - Source type tracking

### Troubleshoot Agent Also Has:

4. **Tool Output Scanning**
   ```python
   # After tool execution
   result_for_llm, _ = self.pii_mapping_manager.redact_text_with_mappings(
       text=str(result),
       detections=detection_dicts
   )
   ```

## Verification Checklist

- [ ] Run `test_pii_security_integration.py` - All agents pass
- [ ] Run `test_pii_all_agents.py` - No data leaks detected
- [ ] Check logs for PII warnings: `docker-compose logs | grep PII`
- [ ] Verify database logs: `SELECT * FROM pii_detection_logs LIMIT 10`
- [ ] Test with custom PII data specific to your use case
- [ ] Document any exceptions or whitelisted values

## Files Created

1. **test_pii_all_agents.py** - Comprehensive integration test
2. **test_pii_security_integration.py** - Implementation validation
3. **PII_SECURITY_VALIDATION.md** - Detailed documentation
4. **PII_TESTING_QUICKSTART.md** - This file

## Monitoring in Production

### Check Detection Logs
```sql
-- Recent detections
SELECT 
    entity_type,
    engine,
    source_type,
    COUNT(*) as count,
    MAX(detected_at) as last_seen
FROM pii_detection_logs
WHERE detected_at > NOW() - INTERVAL '24 hours'
GROUP BY entity_type, engine, source_type
ORDER BY count DESC;
```

### Alert on Failures
```python
# Monitor for PII detection failures
if "PII detection failed" in logs:
    send_alert("PII detection service down")
```

## Common Issues

### Issue: "PII service factory not found"
**Solution:** Ensure PII service is initialized in `app/services/llm_service.py`

### Issue: "No detections found for known PII"
**Solution:** Check if entity types are enabled in `DEFAULT_ENTITIES`

### Issue: "High false positive rate"
**Solution:** Adjust confidence thresholds in PII configuration

## Next Steps After Testing

1. **Review Results**: Check all tests pass
2. **Inspect Logs**: Review PII detection patterns
3. **Configure Alerts**: Set up monitoring for production
4. **Document Exceptions**: Whitelist known safe values
5. **Schedule Audits**: Regular security reviews

## Support

- Review `PII_SECURITY_VALIDATION.md` for detailed documentation
- Check application logs for PII-related warnings
- Consult Presidio and detect-secrets documentation
- File security issues through proper channels
