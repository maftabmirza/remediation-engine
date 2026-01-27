# PII & Secret Detection User Guide

## Overview

The Remediation Engine includes a comprehensive PII (Personally Identifiable Information) and secret detection system that automatically scans and redacts sensitive data across all system outputs. This guide explains how to configure and use the PII detection features.

## What Is Detected

### PII Detection (Microsoft Presidio)

The system detects common PII types including:

- **EMAIL_ADDRESS** - Email addresses (e.g., user@example.com)
- **PHONE_NUMBER** - Phone numbers in various formats
- **US_SSN** - Social Security Numbers
- **CREDIT_CARD** - Credit card numbers
- **PERSON** - Person names (requires NLP model)
- **LOCATION** - Addresses and locations
- **DATE_TIME** - Dates and timestamps with context
- **US_DRIVER_LICENSE** - Driver's license numbers
- **US_PASSPORT** - Passport numbers

### Secret Detection (detect-secrets)

The system detects various credential types:

- **API Keys** - AWS, Google Cloud, Azure, Stripe, etc.
- **Passwords** - Passwords in code/config files
- **Private Keys** - SSH, RSA, PGP private keys
- **Tokens** - JWT tokens, GitHub tokens, Slack tokens
- **Connection Strings** - Database connection strings
- **High Entropy Strings** - Random strings likely to be secrets

### Custom Recognizers

Additional custom detectors:

- **HIGH_ENTROPY** - High entropy strings (random data likely to be sensitive)
- **INTERNAL_HOSTNAME** - Internal hostnames (*.internal, *.local, *.corp)
- **PRIVATE_IP** - Private IP addresses (RFC 1918 ranges)

## Where Detection Occurs

PII detection is automatically applied to:

1. **Runbook Execution Outputs** - All step outputs (stdout, stderr, API responses)
2. **LLM Responses** - AI-generated analysis and recommendations
3. **Alert Data** - Incoming alert annotations and descriptions

## Configuration

### Accessing Configuration UI

1. Navigate to **Settings > PII & Secret Detection**
2. You need `admin` role to access configuration

### Global Settings

Configure overall behavior:

```
☑ Enable PII Detection          ☑ Enable Secret Detection
☑ Auto-redact in outputs        ☑ Log all detections

Default Redaction: [Mask ▼]  Mask Character: [*]
```

- **Enable PII/Secret Detection** - Master switches for each engine
- **Auto-redact in outputs** - Automatically redact detected PII/secrets
- **Log all detections** - Create audit log entries for all detections
- **Default Redaction** - How to redact (Mask, Hash, Remove, Tag)
- **Mask Character** - Character to use for masking (default: *)

### Presidio Entity Configuration

Configure detection for each PII type:

| Entity Type | Enabled | Threshold | Redaction | Actions |
|-------------|---------|-----------|-----------|---------|
| EMAIL | ☑ | 0.7 | Mask | Edit, Test |
| PHONE_NUMBER | ☑ | 0.6 | Mask | Edit, Test |
| US_SSN | ☑ | 0.8 | Hash | Edit, Test |
| CREDIT_CARD | ☑ | 0.8 | Mask | Edit, Test |
| PERSON | ☐ | 0.5 | Tag | Edit, Test |

**Threshold** - Confidence level (0.0-1.0) required for detection
- Lower = More sensitive, may have false positives
- Higher = More specific, may miss some instances
- Recommended: 0.7 for most entity types

**Redaction Types:**
- **Mask** - Replace with [ENTITY_TYPE] or asterisks
- **Hash** - Replace with SHA-256 hash (same value = same hash)
- **Remove** - Delete the detected value
- **Tag** - Wrap in tags like `<EMAIL>user@example.com</EMAIL>`

### detect-secrets Plugin Configuration

Configure secret detection plugins:

| Plugin | Enabled | Settings | Actions |
|--------|---------|----------|---------|
| HighEntropyString | ☑ | Base64: 4.5, Hex: 3.0 | Config |
| KeywordDetector | ☑ | Keywords: password,secret | Config |
| AWSKeyDetector | ☑ | - | - |
| GitHubTokenDetector | ☑ | - | - |
| PrivateKeyDetector | ☑ | - | - |

**HighEntropyString Settings:**
- **Base64 Limit** - Entropy threshold for base64 strings (default: 4.5)
- **Hex Limit** - Entropy threshold for hex strings (default: 3.0)

Lower thresholds = more sensitive detection

**KeywordDetector Settings:**
- **Keywords** - Context words that indicate secrets (password, secret, api_key, etc.)

### Testing Your Configuration

Use the **Test** tab to verify detection before applying changes:

1. Enter sample text in the test box
2. Click **Run Detection**
3. Review detected entities and confidence scores
4. See redacted preview
5. Adjust thresholds if needed

Example test:
```
My email is test@example.com and API key is sk_live_abc123xyz
```

Expected results:
```
✓ EMAIL detected (Presidio) - confidence: 0.95
  Value: test@example.com
✓ API_KEY detected (detect-secrets) - confidence: 0.90
  Value: sk_live_abc123xyz

Redacted Preview:
My email is [EMAIL] and API key is [API_KEY]
```

## Viewing Detection Logs

### Accessing Logs

1. Navigate to **Logs > PII & Secret Detection**
2. You need `security_viewer` role to view logs

### Filtering Logs

Use filters to find specific detections:

- **Search** - Free text search across all fields
- **Date Range** - Filter by detection date
- **Entity Type** - Filter by PII/secret type
- **Engine** - Filter by detection engine (Presidio/detect-secrets)
- **Source** - Filter by source (runbook_output, llm_response, alert_data)
- **Confidence** - Filter by confidence score range

### Understanding Log Entries

Each log entry shows:

```
Timestamp: 2026-01-26 10:30:00 UTC
Entity Type: EMAIL
Detection Engine: Presidio
Confidence Score: 0.95
Source Type: runbook_output
Source ID: [Link to Execution]
Context: "...notification was sent to [EMAIL] for review by the..."
Position: 145-167
Was Redacted: Yes
Redaction Type: mask
```

**Important Notes:**
- Original values are NEVER stored in logs
- Only SHA-256 hash is stored for deduplication
- Context shows redacted preview

### Exporting Logs

Click **Export CSV** to download logs for compliance/audit:

```csv
detected_at,entity_type,engine,confidence,source_type,was_redacted
2026-01-26 10:30:00,EMAIL,presidio,0.95,runbook_output,true
2026-01-26 10:28:15,API_KEY,detect-secrets,0.90,llm_response,true
...
```

## Common Scenarios

### Scenario 1: Reduce False Positives

**Problem:** Too many person names are being flagged

**Solution:**
1. Go to Settings > PII & Secret Detection
2. Select Presidio Entities tab
3. Find "PERSON" entity
4. Increase threshold from 0.5 to 0.8
5. Or disable PERSON detection entirely
6. Click Save

### Scenario 2: Add Custom Internal Domains

**Problem:** Need to detect internal hostnames like `*.mycompany.local`

**Solution:**
1. Go to Settings > PII & Secret Detection
2. Select Custom Patterns tab
3. Add pattern: `\.mycompany\.local`
4. Set entity type: INTERNAL_HOSTNAME
5. Set threshold: 0.7
6. Click Save

### Scenario 3: Audit Recent Secret Exposures

**Problem:** Need to see all secrets detected in last 24 hours

**Solution:**
1. Go to Logs > PII & Secret Detection
2. Set date range: Last 24 hours
3. Set engine filter: detect-secrets
4. Click Apply Filters
5. Review results
6. Export CSV for records

### Scenario 4: Whitelist Known Values

**Problem:** A specific API key is flagged but is known/documented

**Solution:**
1. Go to Logs > PII & Secret Detection
2. Find the log entry
3. Click on the entry to expand details
4. Click "Acknowledge" button
5. Add note: "This is the public Stripe test key"
6. The value will no longer appear in active alerts

### Scenario 5: Testing New Runbooks

**Problem:** Want to verify runbook output doesn't leak PII before enabling

**Solution:**
1. Create runbook in UI
2. Run in dry-run mode first
3. Check execution logs for PII detections
4. Review detection log page for any sensitive data
5. Adjust runbook steps if needed
6. Enable for production

## Best Practices

### Configuration

1. **Start Conservative** - Begin with higher thresholds (0.8+) and lower over time
2. **Test Thoroughly** - Use the test sandbox before applying config changes
3. **Review Regularly** - Check detection logs weekly for patterns
4. **Document Exceptions** - Acknowledge known/safe detections with notes

### Security

1. **Limit Access** - Only grant `admin` role to security team for PII config
2. **Monitor Changes** - Review audit logs for configuration changes
3. **Export Regularly** - Export detection logs monthly for compliance
4. **Rotate Detected Secrets** - If real secrets are detected, rotate them immediately

### Performance

1. **Enable Only Needed Entities** - Disable unused entity types to improve speed
2. **Adjust Thresholds** - Higher thresholds = faster processing
3. **Review Log Retention** - Archive old logs to database performance

## Troubleshooting

### Detection Not Working

**Symptoms:** No PII detected in obvious cases

**Checks:**
1. Verify "Enable PII Detection" is checked in global settings
2. Check entity/plugin is enabled in configuration
3. Verify threshold is not too high (try 0.6-0.7)
4. Test in sandbox to isolate issue
5. Check application logs for errors

### Too Many False Positives

**Symptoms:** Normal text is flagged as PII

**Solutions:**
1. Increase threshold for that entity type
2. Disable entity type if not needed
3. For PERSON entity, consider disabling or setting threshold to 0.9+
4. For HIGH_ENTROPY, increase entropy limits

### Performance Issues

**Symptoms:** Slow runbook execution or LLM responses

**Solutions:**
1. Disable unused entity types
2. Increase confidence thresholds
3. Disable detect-secrets for non-critical sources
4. Check if Presidio NLP models are loaded (they download on first use)

### Logs Not Appearing

**Symptoms:** Detections happening but not in logs

**Checks:**
1. Verify "Log all detections" is enabled
2. Check database connectivity
3. Verify user has `security_viewer` role
4. Check date range filter in log viewer

## API Integration

For programmatic access, see the [PII Detection API Documentation](PII_DETECTION_API.md).

Quick example:

```bash
# Detect PII in text
curl -X POST http://localhost:8000/api/v1/pii/detect \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Contact admin@company.com",
    "source_type": "manual"
  }'

# Get detection logs
curl -X GET http://localhost:8000/api/v1/pii/logs?page=1&limit=20
```

## Support

For issues or questions:

1. Check logs at `/var/log/remediation-engine/app.log`
2. Review detection statistics dashboard
3. Contact security team for configuration help
4. See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for technical details
