# PII & Secret Detection API Reference

## Base URL

```
http://localhost:8000/api/v1/pii
```

All endpoints require authentication with a valid JWT token in the `Authorization` header:

```
Authorization: Bearer <token>
```

## Endpoints

### Detection

#### POST `/detect`

Detect PII and secrets in text.

**Request Body:**

```json
{
  "text": "Contact john.doe@example.com or call 555-123-4567",
  "source_type": "runbook_output",
  "source_id": "uuid-of-execution",
  "engines": ["presidio", "detect_secrets"],
  "entity_types": ["EMAIL", "PHONE_NUMBER"]
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| text | string | Yes | Text to analyze |
| source_type | string | Yes | Type of source (runbook_output, llm_response, alert_data, etc.) |
| source_id | string | No | ID of source record |
| engines | array | No | Engines to use (default: both) |
| entity_types | array | No | Specific entity types to detect (default: all enabled) |

**Response (200 OK):**

```json
{
  "detections": [
    {
      "entity_type": "EMAIL_ADDRESS",
      "engine": "presidio",
      "confidence": 0.95,
      "start": 8,
      "end": 28,
      "context": "Contact john.doe@example.com or call"
    },
    {
      "entity_type": "PHONE_NUMBER",
      "engine": "presidio",
      "confidence": 0.85,
      "start": 37,
      "end": 49,
      "context": "or call 555-123-4567"
    }
  ],
  "detection_count": 2,
  "processing_time_ms": 45
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8000/api/v1/pii/detect \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "My API key is sk_live_abc123xyz",
    "source_type": "test"
  }'
```

**Python Example:**

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/pii/detect",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "text": "Email: admin@company.com",
        "source_type": "manual_check"
    }
)

detections = response.json()
print(f"Found {detections['detection_count']} PII/secrets")
```

---

#### POST `/redact`

Redact PII and secrets from text.

**Request Body:**

```json
{
  "text": "API key: sk_live_abc123xyz",
  "redaction_type": "mask",
  "mask_char": "*",
  "preserve_length": false
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| text | string | Yes | Text to redact |
| redaction_type | string | No | Type of redaction (mask, hash, remove, tag) |
| mask_char | string | No | Character for masking (default: *) |
| preserve_length | boolean | No | Preserve original length when masking |

**Response (200 OK):**

```json
{
  "original_length": 26,
  "redacted_text": "API key: [API_KEY]",
  "redactions_applied": 1,
  "detections": [
    {
      "entity_type": "API_KEY",
      "engine": "detect_secrets",
      "confidence": 0.90,
      "start": 9,
      "end": 26
    }
  ]
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8000/api/v1/pii/redact \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Password: SuperSecret123!",
    "redaction_type": "mask"
  }'
```

---

### Configuration

#### GET `/config`

Get current PII detection configuration.

**Response (200 OK):**

```json
{
  "presidio": {
    "enabled": true,
    "entities": [
      {
        "entity_type": "EMAIL",
        "enabled": true,
        "threshold": 0.7,
        "redaction_type": "mask"
      },
      {
        "entity_type": "PHONE_NUMBER",
        "enabled": true,
        "threshold": 0.6,
        "redaction_type": "mask"
      }
    ]
  },
  "detect_secrets": {
    "enabled": true,
    "plugins": [
      {
        "plugin_name": "HighEntropyString",
        "enabled": true,
        "settings": {
          "base64_limit": 4.5,
          "hex_limit": 3.0
        }
      }
    ]
  },
  "global_settings": {
    "log_detections": true,
    "auto_redact": true,
    "default_redaction_type": "mask"
  }
}
```

**cURL Example:**

```bash
curl -X GET http://localhost:8000/api/v1/pii/config \
  -H "Authorization: Bearer <token>"
```

---

#### PUT `/config`

Update PII detection configuration.

**Request Body (partial update):**

```json
{
  "presidio": {
    "entities": [
      {
        "entity_type": "EMAIL",
        "enabled": true,
        "threshold": 0.8
      }
    ]
  }
}
```

**Response (200 OK):**

```json
{
  "updated": true,
  "changes": [
    "presidio.entities.EMAIL.threshold: 0.7 -> 0.8"
  ]
}
```

**cURL Example:**

```bash
curl -X PUT http://localhost:8000/api/v1/pii/config \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "presidio": {
      "entities": [
        {
          "entity_type": "PHONE_NUMBER",
          "enabled": false
        }
      ]
    }
  }'
```

---

### Logs

#### GET `/logs`

Get detection logs with pagination and filtering.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| limit | integer | No | Items per page (default: 50, max: 100) |
| entity_type | string | No | Filter by entity type |
| engine | string | No | Filter by engine (presidio, detect_secrets) |
| source_type | string | No | Filter by source type |
| start_date | string | No | Start date (ISO 8601) |
| end_date | string | No | End date (ISO 8601) |

**Response (200 OK):**

```json
{
  "logs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "detected_at": "2026-01-26T10:30:00Z",
      "entity_type": "EMAIL",
      "detection_engine": "presidio",
      "confidence_score": 0.95,
      "source_type": "runbook_output",
      "source_id": "abc-123",
      "context_snippet": "notification sent to [EMAIL] for review",
      "was_redacted": true,
      "redaction_type": "mask"
    }
  ],
  "total": 1250,
  "page": 1,
  "limit": 50,
  "pages": 25
}
```

**cURL Example:**

```bash
curl -X GET "http://localhost:8000/api/v1/pii/logs?page=1&limit=20&entity_type=EMAIL&start_date=2026-01-01" \
  -H "Authorization: Bearer <token>"
```

---

#### GET `/logs/search`

Search logs with text query.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| q | string | Yes | Search query |
| engine | string | No | Filter by engine |
| confidence_min | float | No | Minimum confidence (0.0-1.0) |
| confidence_max | float | No | Maximum confidence (0.0-1.0) |

**Response (200 OK):**

```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "detected_at": "2026-01-26T10:30:00Z",
      "entity_type": "API_KEY",
      "confidence_score": 0.90,
      "source_type": "llm_response",
      "context_snippet": "use api key [API_KEY] to authenticate"
    }
  ],
  "total": 45,
  "query": "api key",
  "filters_applied": {
    "engine": "detect_secrets",
    "confidence_min": 0.8
  }
}
```

**cURL Example:**

```bash
curl -X GET "http://localhost:8000/api/v1/pii/logs/search?q=password&confidence_min=0.8" \
  -H "Authorization: Bearer <token>"
```

---

#### GET `/logs/stats`

Get detection statistics.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| period | string | No | Time period (24h, 7d, 30d) |

**Response (200 OK):**

```json
{
  "period": "7d",
  "total_detections": 3450,
  "by_entity_type": {
    "EMAIL": 1200,
    "PHONE_NUMBER": 450,
    "API_KEY": 950,
    "PASSWORD": 850
  },
  "by_engine": {
    "presidio": 2100,
    "detect_secrets": 1350
  },
  "by_source": {
    "runbook_output": 2000,
    "llm_response": 1000,
    "alert_data": 450
  },
  "trend": [
    {"date": "2026-01-20", "count": 420},
    {"date": "2026-01-21", "count": 485},
    {"date": "2026-01-22", "count": 510}
  ]
}
```

**cURL Example:**

```bash
curl -X GET "http://localhost:8000/api/v1/pii/logs/stats?period=30d" \
  -H "Authorization: Bearer <token>"
```

---

#### GET `/logs/export`

Export logs to CSV.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| format | string | No | Export format (csv, json) |
| start_date | string | No | Start date (ISO 8601) |
| end_date | string | No | End date (ISO 8601) |

**Response (200 OK):**

Returns CSV file as streaming download.

**cURL Example:**

```bash
curl -X GET "http://localhost:8000/api/v1/pii/logs/export?format=csv&start_date=2026-01-01" \
  -H "Authorization: Bearer <token>" \
  -o detections.csv
```

---

### Testing

#### POST `/test`

Test detection without logging.

**Request Body:**

```json
{
  "text": "My password is SuperSecret123! and my API key is sk_test_abc",
  "engines": ["presidio", "detect_secrets"]
}
```

**Response (200 OK):**

```json
{
  "detections": [
    {
      "entity_type": "PASSWORD",
      "engine": "detect_secrets",
      "confidence": 0.88,
      "start": 15,
      "end": 29
    },
    {
      "entity_type": "API_KEY",
      "engine": "detect_secrets",
      "confidence": 0.90,
      "start": 47,
      "end": 59
    }
  ],
  "redacted_preview": "My password is [PASSWORD] and my API key is [API_KEY]",
  "engine_results": {
    "presidio": {
      "detections": 0,
      "processing_time_ms": 12
    },
    "detect_secrets": {
      "detections": 2,
      "processing_time_ms": 18
    }
  }
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8000/api/v1/pii/test \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Test email: admin@example.com",
    "engines": ["presidio"]
  }'
```

---

### Metadata

#### GET `/entities`

List all available entity types.

**Response (200 OK):**

```json
{
  "presidio_entities": [
    {
      "name": "EMAIL",
      "description": "Email addresses",
      "built_in": true
    },
    {
      "name": "PHONE_NUMBER",
      "description": "Phone numbers",
      "built_in": true
    },
    {
      "name": "HIGH_ENTROPY",
      "description": "High entropy strings",
      "built_in": false
    }
  ]
}
```

---

#### GET `/plugins`

List all detect-secrets plugins.

**Response (200 OK):**

```json
{
  "detect_secrets_plugins": [
    {
      "name": "HighEntropyString",
      "description": "Detects high entropy strings",
      "configurable": true
    },
    {
      "name": "AWSKeyDetector",
      "description": "Detects AWS access keys",
      "configurable": false
    }
  ]
}
```

---

## Error Responses

All endpoints may return these error responses:

### 400 Bad Request

Invalid request parameters.

```json
{
  "detail": "Invalid redaction_type: must be one of mask, hash, remove, tag"
}
```

### 401 Unauthorized

Missing or invalid authentication token.

```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden

Insufficient permissions.

```json
{
  "detail": "User does not have required role: admin"
}
```

### 404 Not Found

Resource not found.

```json
{
  "detail": "Detection log not found"
}
```

### 500 Internal Server Error

Server error during processing.

```json
{
  "detail": "PII detection service unavailable"
}
```

---

## Rate Limiting

API endpoints are rate limited:

- **Detection endpoints** (`/detect`, `/redact`): 100 requests/minute per user
- **Test endpoint** (`/test`): 10 requests/minute per user
- **Configuration endpoints**: 20 requests/minute per user
- **Log query endpoints**: 50 requests/minute per user

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1643200000
```

---

## Webhooks

You can configure webhooks to receive notifications when PII/secrets are detected.

### Webhook Payload

```json
{
  "event": "pii_detected",
  "timestamp": "2026-01-26T10:30:00Z",
  "detection": {
    "entity_type": "API_KEY",
    "confidence": 0.90,
    "source_type": "runbook_output",
    "source_id": "abc-123"
  }
}
```

### Configuring Webhooks

```bash
curl -X POST http://localhost:8000/api/v1/pii/webhooks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-service.com/pii-alert",
    "events": ["pii_detected"],
    "filters": {
      "min_confidence": 0.8,
      "entity_types": ["API_KEY", "PASSWORD"]
    }
  }'
```

---

## Best Practices

### Security

1. **Always use HTTPS** in production
2. **Rotate tokens** regularly
3. **Log access** to configuration endpoints
4. **Limit permissions** - only security team should have config access

### Performance

1. **Batch requests** when possible
2. **Cache config** - fetch once, use multiple times
3. **Filter logs** - use specific queries instead of fetching all
4. **Use test endpoint** for development - it doesn't create log entries

### Integration

1. **Handle errors gracefully** - detection should not break workflows
2. **Async processing** - use background tasks for large texts
3. **Monitor rate limits** - implement exponential backoff
4. **Version your API calls** - use `/api/v1/` prefix

---

## SDK Examples

### Python SDK

```python
from pii_detection_client import PIIClient

client = PIIClient(base_url="http://localhost:8000", token="your-token")

# Detect PII
result = client.detect("Email: test@example.com")
print(f"Found {result.detection_count} entities")

# Redact text
redacted = client.redact("Password: secret123", redaction_type="mask")
print(f"Redacted: {redacted.redacted_text}")

# Get logs
logs = client.get_logs(entity_type="EMAIL", start_date="2026-01-01")
for log in logs:
    print(f"{log.detected_at}: {log.entity_type}")
```

### JavaScript SDK

```javascript
const { PIIClient } = require('@remediation/pii-detection');

const client = new PIIClient({
  baseUrl: 'http://localhost:8000',
  token: 'your-token'
});

// Detect PII
const result = await client.detect('Email: test@example.com');
console.log(`Found ${result.detection_count} entities`);

// Get statistics
const stats = await client.getStats('7d');
console.log(`Total detections: ${stats.total_detections}`);
```

---

## Support

For API issues or questions:

- **Documentation**: [User Guide](PII_DETECTION_USER_GUIDE.md)
- **Issues**: GitHub Issues
- **Security**: security@yourcompany.com
