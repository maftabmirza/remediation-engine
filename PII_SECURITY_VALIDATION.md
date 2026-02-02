# PII Security Policy Validation

## Overview

This document describes how PII (Personally Identifiable Information) and secrets security is implemented and tested across all LLM agent modes in the Remediation Engine.

## Protected Agent Modes

### 1. /alert Endpoint (AI Alert Help Agent)
- **Agent Class**: `AiAlertHelpAgent`
- **Location**: `app/services/agentic/ai_alert_help_agent.py`
- **Purpose**: Analyzes alerts and provides troubleshooting assistance

### 2. RE-VIVE (Quick Help Agent)
- **Agent Class**: `ReviveQuickHelpAgent`
- **Location**: `app/services/revive/revive_agent.py`
- **Purpose**: Provides quick help and guidance through RE-VIVE interface

### 3. /troubleshoot Endpoint (Troubleshoot Agent)
- **Agent Class**: `TroubleshootNativeAgent`
- **Location**: `app/services/agentic/troubleshoot_native_agent.py`
- **Purpose**: Interactive terminal and command execution with AI assistance

## PII Security Implementation

### Detection Engines

The system uses two complementary detection engines:

1. **Presidio** (Microsoft)
   - Detects PII: Email, Phone, SSN, Credit Card, IP Address, Person Names
   - Pattern-based and ML-based detection
   - Highly configurable entity types

2. **detect-secrets** (Yelp)
   - Detects secrets: AWS keys, GitHub tokens, API keys
   - Plugin-based architecture
   - High-entropy string detection

### Security Flow

```
User Input → PII Detection → Redaction → LLM Processing → Response Scanning → User
```

#### 1. **User Input Scanning**
All three agents scan user messages before sending to LLM:

```python
async def _scan_and_redact_text(
    self,
    text: str,
    *,
    source_type: str,
    redaction_type: str = "tag",
    context_label: str = "text",
) -> str:
    """Detect + log + redact PII/secrets"""
    # Uses global PII service factory
    # Logs detections to database
    # Redacts with PIIMappingManager for consistency
```

#### 2. **Tool Output Scanning** (Troubleshoot Agent Only)
The troubleshoot agent also scans tool execution results:

```python
async def _execute_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
    """Execute tool calls and return results with PII scanning"""
    # Executes command/tool
    # Scans output for PII/secrets
    # Redacts before returning to LLM
```

#### 3. **Agent Response Scanning**
Final responses are scanned before being sent to users.

### Redaction Strategy

The system uses **PIIMappingManager** for session-consistent redaction:

- **Indexed Placeholders**: `[EMAIL_1]`, `[PHONE_1]`, `[AWS_KEY_1]`
- **Consistent Mapping**: Same value always gets same placeholder within a session
- **Reversible** (for authorized users): Can map placeholders back to original values
- **Audit Trail**: All detections logged to database

## Testing

### 1. Implementation Check

Validates that PII security is properly implemented:

```bash
python test_pii_security_integration.py
```

**Checks:**
- `_scan_and_redact_text` method exists in all agents
- PIIMappingManager integration is present
- Tool output scanning (for troubleshoot agent)

### 2. Integration Test

Tests actual PII detection and redaction with live API:

```bash
# Start the application first
docker-compose up -d

# Run integration tests
python test_pii_all_agents.py
```

**Tests:**
- Email addresses
- SSN numbers
- Phone numbers
- Credit card numbers
- AWS access keys
- GitHub tokens
- IP addresses
- Person names

## Expected Results

### ✅ Success Criteria

1. **No PII leakage**: Sensitive data should NOT appear in agent responses
2. **Proper redaction**: PII replaced with indexed placeholders like `[EMAIL_1]`
3. **Detection logging**: All detections logged to `pii_detection_logs` table
4. **Session consistency**: Same value → same placeholder within session

### Example Output

**User Input:**
```
My email is john.doe@company.com and SSN is 234-56-7890
```

**After Redaction (sent to LLM):**
```
My email is [EMAIL_1] and SSN is [US_SSN_1]
```

**User Sees (final response):**
```
I can help you with that issue. Your contact information has been redacted for security.
```

## Security Configuration

### Enabled Entity Types

Located in `app/services/pii_service.py`:

```python
DEFAULT_ENTITIES = [
    "EMAIL_ADDRESS", 
    "PHONE_NUMBER", 
    "PERSON", 
    "CREDIT_CARD", 
    "IP_ADDRESS", 
    "US_SSN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "IBAN_CODE",
    "US_BANK_NUMBER",
    "MEDICAL_LICENSE",
]
```

### Detection Logs

All detections are logged to the database:

```sql
SELECT * FROM pii_detection_logs 
ORDER BY detected_at DESC 
LIMIT 10;
```

Fields:
- `entity_type`: Type of PII detected (EMAIL_ADDRESS, etc.)
- `engine`: Detection engine used (presidio, detect_secrets)
- `confidence`: Confidence score (0.0 - 1.0)
- `source_type`: Where detected (user_input, tool_output, agent_response)
- `detected_at`: Timestamp

## Troubleshooting

### Issue: PII Not Being Redacted

**Check:**
1. PII service factory is initialized:
   ```python
   from app.services.llm_service import _pii_service_factory
   assert _pii_service_factory is not None
   ```

2. Agent has PIIMappingManager:
   ```python
   assert agent.pii_mapping_manager is not None
   ```

3. Review application logs for PII warnings:
   ```bash
   docker-compose logs app | grep "PII"
   ```

### Issue: False Positives

**Solution:**
- Adjust confidence thresholds in PII configuration
- Disable specific entity types if needed
- Use whitelist patterns for known safe values

### Issue: Missing Detections

**Solution:**
- Verify detection engines are loaded
- Check if entity type is in `DEFAULT_ENTITIES`
- Review pattern matching rules
- Add custom recognizers if needed

## API Endpoints for PII Management

### Detection API
```http
POST /api/v1/pii/detect
Content-Type: application/json

{
  "text": "Contact john@example.com",
  "source_type": "test",
  "engines": ["presidio", "detect_secrets"]
}
```

### Redaction API
```http
POST /api/v1/pii/redact
Content-Type: application/json

{
  "text": "SSN: 234-56-7890",
  "redaction_type": "tag"
}
```

### Configuration API
```http
GET /api/v1/pii/config
```

## Compliance

This implementation helps meet compliance requirements for:

- **GDPR**: Protects personal data of EU citizens
- **HIPAA**: Protects health information
- **PCI DSS**: Protects payment card data
- **SOC 2**: Demonstrates security controls

## References

- **Presidio Documentation**: https://microsoft.github.io/presidio/
- **detect-secrets**: https://github.com/Yelp/detect-secrets
- **OWASP Data Protection**: https://owasp.org/www-project-data-security/

## Maintenance

### Regular Tasks

1. **Review Detection Logs** (Weekly)
   - Check for new PII types
   - Identify false positives
   - Update entity configurations

2. **Update Detection Rules** (Monthly)
   - Add new secret patterns
   - Update regex patterns
   - Tune confidence thresholds

3. **Security Audit** (Quarterly)
   - Review redaction effectiveness
   - Test with new PII types
   - Update compliance documentation

## Contact

For security concerns or questions:
- File a security issue in the repository
- Contact the security team
- Review audit logs regularly
