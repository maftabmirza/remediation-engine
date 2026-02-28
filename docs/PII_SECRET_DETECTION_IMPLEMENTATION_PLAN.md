# PII & Secret Detection Implementation Plan

## Overview

This plan implements a comprehensive PII (Personally Identifiable Information) and secret detection system for the Remediation Engine. The system combines **Microsoft Presidio** for PII detection (emails, phone numbers, SSNs, names) with **detect-secrets** library for credential/secret detection (API keys, passwords, tokens). A unified service layer merges results from both engines, providing a single API for detection, configuration, and audit logging. A full-featured UI enables administrators to configure detection rules, view detection logs, search audit history, and tune sensitivity thresholds.

### High-Level Success Criteria
- All runbook outputs, LLM responses, and execution logs are scanned for PII/secrets before display or storage
- Detected sensitive data is masked/redacted based on configurable rules
- Complete audit trail of all detections with searchable log viewer
- UI for configuring detection rules, thresholds, and entity types
- Zero false negatives for high-confidence patterns (API keys, SSNs)
- False positive rate < 5% for entropy-based detection

---

## Scope

### What Is Included
1. **Presidio Integration** - Custom recognizers for PII detection
2. **detect-secrets Integration** - Secret/credential detection with 20+ plugins
3. **Unified PIIService** - Single service merging both detection engines
4. **Custom Recognizers** - High-entropy strings, internal hostnames, private IPs
5. **Configuration API** - CRUD endpoints for detection rules and thresholds
6. **Detection Logging** - Audit trail with timestamps, detection type, context
7. **Configuration UI** - React components for rule management
8. **Log Viewer UI** - Searchable, filterable detection audit log
9. **Database Schema** - Tables for configuration, detection logs, baselines
10. **Integration Points** - Hooks into runbook execution, LLM responses, alerts

### What Is Explicitly Out of Scope
- Real-time streaming detection (batch processing only)
- Custom ML model training for PII detection
- File system scanning (only in-memory text scanning)
- DLP (Data Loss Prevention) policy enforcement
- Integration with external SIEM systems
- Multi-tenant configuration isolation
- Encryption key management

---

## Design

### Architecture Diagram (Textual)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React)                                   │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │ PII Config Page     │  │ Secret Config Page  │  │ Detection Log View  │  │
│  │ - Entity toggles    │  │ - Plugin toggles    │  │ - Search/filter     │  │
│  │ - Threshold sliders │  │ - Entropy thresholds│  │ - Date range        │  │
│  │ - Test sandbox      │  │ - Custom patterns   │  │ - Export CSV        │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND API (FastAPI)                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ /api/v1/pii/*                                                           ││
│  │   POST /detect          - Detect PII/secrets in text                    ││
│  │   POST /redact          - Redact detected entities                      ││
│  │   GET  /config          - Get current configuration                     ││
│  │   PUT  /config          - Update configuration                          ││
│  │   GET  /logs            - Get detection audit logs                      ││
│  │   GET  /logs/search     - Search logs with filters                      ││
│  │   GET  /logs/stats      - Detection statistics                          ││
│  │   POST /test            - Test detection on sample text                 ││
│  │   GET  /entities        - List available entity types                   ││
│  │   GET  /plugins         - List detect-secrets plugins                   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ PIIService (app/services/pii_service.py)                                ││
│  │   - Orchestrates detection from both engines                            ││
│  │   - Merges and deduplicates results                                     ││
│  │   - Applies configuration rules                                         ││
│  │   - Logs all detections                                                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│           │                                           │                      │
│           ▼                                           ▼                      │
│  ┌─────────────────────────┐             ┌─────────────────────────────────┐│
│  │ PresidioService         │             │ SecretDetectionService          ││
│  │ (presidio_service.py)   │             │ (secret_detection_service.py)   ││
│  │  ├─ AnalyzerEngine      │             │  ├─ HighEntropyString           ││
│  │  │   ├─ EmailRecognizer │             │  ├─ KeywordDetector             ││
│  │  │   ├─ PhoneRecognizer │             │  ├─ AWSKeyDetector              ││
│  │  │   ├─ SSNRecognizer   │             │  ├─ GitHubTokenDetector         ││
│  │  │   ├─ NameRecognizer  │             │  ├─ PrivateKeyDetector          ││
│  │  │   └─ Custom:         │             │  ├─ JwtTokenDetector            ││
│  │  │      ├─ HighEntropy  │             │  └─ ... (20+ plugins)           ││
│  │  │      ├─ Hostname     │             │                                 ││
│  │  │      └─ PrivateIP    │             │                                 ││
│  │  └─ AnonymizerEngine    │             │                                 ││
│  └─────────────────────────┘             └─────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATABASE (PostgreSQL)                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ pii_config      │  │ detection_logs  │  │ secret_baselines            │  │
│  │ - entity_types  │  │ - timestamp     │  │ - secret_hash               │  │
│  │ - thresholds    │  │ - entity_type   │  │ - first_seen                │  │
│  │ - enabled       │  │ - source        │  │ - acknowledged              │  │
│  └─────────────────┘  │ - context       │  └─────────────────────────────┘  │
│                       └─────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Model Changes

#### New Tables

**Table: `pii_detection_config`**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| config_type | VARCHAR(50) | 'presidio' or 'detect_secrets' |
| entity_type | VARCHAR(100) | Entity/plugin name |
| enabled | BOOLEAN | Whether detection is enabled |
| threshold | FLOAT | Confidence threshold (0.0-1.0) |
| redaction_type | VARCHAR(50) | 'mask', 'hash', 'remove', 'tag' |
| custom_pattern | TEXT | Optional custom regex |
| settings_json | JSONB | Additional settings |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

**Table: `pii_detection_logs`**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| detected_at | TIMESTAMP | Detection timestamp |
| entity_type | VARCHAR(100) | Type of entity detected |
| detection_engine | VARCHAR(50) | 'presidio' or 'detect_secrets' |
| confidence_score | FLOAT | Detection confidence |
| source_type | VARCHAR(50) | 'runbook_output', 'llm_response', 'alert', etc. |
| source_id | UUID | FK to source record |
| context_snippet | TEXT | Surrounding text (redacted) |
| position_start | INTEGER | Start position in text |
| position_end | INTEGER | End position in text |
| was_redacted | BOOLEAN | Whether it was redacted |
| redaction_type | VARCHAR(50) | How it was redacted |
| original_hash | VARCHAR(64) | SHA-256 hash of original value |
| created_at | TIMESTAMP | Log creation timestamp |

**Table: `secret_baselines`**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| secret_hash | VARCHAR(64) | SHA-256 hash of secret |
| secret_type | VARCHAR(100) | Type of secret |
| first_detected | TIMESTAMP | First detection time |
| last_detected | TIMESTAMP | Last detection time |
| detection_count | INTEGER | Number of times detected |
| is_acknowledged | BOOLEAN | Acknowledged as known/allowed |
| acknowledged_by | VARCHAR(100) | Who acknowledged |
| acknowledged_at | TIMESTAMP | When acknowledged |
| notes | TEXT | Admin notes |

### API Contract Changes

#### New Endpoints

**POST `/api/v1/pii/detect`**
```json
// Request
{
  "text": "Contact john.doe@example.com or call 555-123-4567",
  "source_type": "runbook_output",
  "source_id": "uuid-of-execution",
  "engines": ["presidio", "detect_secrets"],  // optional, defaults to both
  "entity_types": ["EMAIL", "PHONE_NUMBER"]   // optional, defaults to all enabled
}

// Response 200 OK
{
  "detections": [
    {
      "entity_type": "EMAIL",
      "engine": "presidio",
      "value": "john.doe@example.com",
      "start": 8,
      "end": 28,
      "confidence": 0.95,
      "context": "Contact [REDACTED] or call..."
    },
    {
      "entity_type": "PHONE_NUMBER",
      "engine": "presidio",
      "value": "555-123-4567",
      "start": 37,
      "end": 49,
      "confidence": 0.85,
      "context": "...or call [REDACTED]"
    }
  ],
  "detection_count": 2,
  "processing_time_ms": 45
}
```

**POST `/api/v1/pii/redact`**
```json
// Request
{
  "text": "API key: sk_live_abc123xyz",
  "redaction_type": "mask",  // 'mask', 'hash', 'remove', 'tag'
  "mask_char": "*",
  "preserve_length": false
}

// Response 200 OK
{
  "original_length": 26,
  "redacted_text": "API key: [SECRET_KEY]",
  "redactions_applied": 1,
  "detections": [...]
}
```

**GET `/api/v1/pii/config`**
```json
// Response 200 OK
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
      // ... more entities
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
      },
      {
        "plugin_name": "AWSKeyDetector",
        "enabled": true,
        "settings": {}
      }
      // ... more plugins
    ]
  },
  "global_settings": {
    "log_detections": true,
    "auto_redact": true,
    "default_redaction_type": "mask"
  }
}
```

**PUT `/api/v1/pii/config`**
```json
// Request (partial update)
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

// Response 200 OK
{
  "updated": true,
  "changes": ["presidio.entities.EMAIL.threshold: 0.7 -> 0.8"]
}
```

**GET `/api/v1/pii/logs`**
```json
// Query params: ?page=1&limit=50&entity_type=EMAIL&source_type=runbook_output&start_date=2026-01-01&end_date=2026-01-26

// Response 200 OK
{
  "logs": [
    {
      "id": "uuid",
      "detected_at": "2026-01-26T10:30:00Z",
      "entity_type": "EMAIL",
      "detection_engine": "presidio",
      "confidence_score": 0.95,
      "source_type": "runbook_output",
      "source_id": "execution-uuid",
      "context_snippet": "...sent to [EMAIL] for review...",
      "was_redacted": true
    }
  ],
  "total": 1250,
  "page": 1,
  "limit": 50,
  "pages": 25
}
```

**GET `/api/v1/pii/logs/search`**
```json
// Query params: ?q=api+key&engine=detect_secrets&confidence_min=0.8

// Response 200 OK
{
  "results": [...],
  "total": 45,
  "query": "api key",
  "filters_applied": {
    "engine": "detect_secrets",
    "confidence_min": 0.8
  }
}
```

**GET `/api/v1/pii/logs/stats`**
```json
// Query params: ?period=7d

// Response 200 OK
{
  "period": "7d",
  "total_detections": 3450,
  "by_entity_type": {
    "EMAIL": 1200,
    "PHONE_NUMBER": 450,
    "API_KEY": 800,
    "AWS_KEY": 150,
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
    {"date": "2026-01-21", "count": 510},
    // ...
  ]
}
```

**POST `/api/v1/pii/test`**
```json
// Request
{
  "text": "My password is SuperSecret123! and my API key is sk_test_abc",
  "engines": ["presidio", "detect_secrets"]
}

// Response 200 OK
{
  "detections": [...],
  "redacted_preview": "My password is [PASSWORD] and my API key is [API_KEY]",
  "engine_results": {
    "presidio": {
      "detections": 1,
      "processing_time_ms": 12
    },
    "detect_secrets": {
      "detections": 2,
      "processing_time_ms": 8
    }
  }
}
```

**GET `/api/v1/pii/entities`**
```json
// Response 200 OK
{
  "presidio_entities": [
    {"name": "EMAIL", "description": "Email addresses", "built_in": true},
    {"name": "PHONE_NUMBER", "description": "Phone numbers", "built_in": true},
    {"name": "US_SSN", "description": "US Social Security Numbers", "built_in": true},
    {"name": "CREDIT_CARD", "description": "Credit card numbers", "built_in": true},
    {"name": "PERSON", "description": "Person names", "built_in": true},
    {"name": "HIGH_ENTROPY_SECRET", "description": "High entropy strings", "built_in": false},
    {"name": "INTERNAL_HOSTNAME", "description": "Internal hostnames", "built_in": false},
    {"name": "PRIVATE_IP", "description": "Private IP addresses", "built_in": false}
  ]
}
```

**GET `/api/v1/pii/plugins`**
```json
// Response 200 OK
{
  "detect_secrets_plugins": [
    {"name": "HighEntropyString", "description": "Detects high entropy strings", "configurable": true},
    {"name": "KeywordDetector", "description": "Detects secrets by context keywords", "configurable": true},
    {"name": "AWSKeyDetector", "description": "AWS access keys", "configurable": false},
    {"name": "AzureStorageKeyDetector", "description": "Azure storage keys", "configurable": false},
    {"name": "BasicAuthDetector", "description": "Basic auth in URLs", "configurable": false},
    {"name": "GitHubTokenDetector", "description": "GitHub tokens", "configurable": false},
    {"name": "JwtTokenDetector", "description": "JWT tokens", "configurable": false},
    {"name": "PrivateKeyDetector", "description": "RSA/SSH private keys", "configurable": false},
    {"name": "SlackDetector", "description": "Slack tokens", "configurable": false},
    {"name": "StripeDetector", "description": "Stripe API keys", "configurable": false},
    {"name": "TwilioKeyDetector", "description": "Twilio API keys", "configurable": false}
    // ... more plugins
  ]
}
```

### UI/UX Changes

#### New Pages

**1. PII Detection Configuration Page (`/settings/pii-detection`)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Settings > PII & Secret Detection                                    [Save] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌─ Global Settings ───────────────────────────────────────────────────────┐ │
│ │ [✓] Enable PII Detection          [✓] Enable Secret Detection           │ │
│ │ [✓] Auto-redact in outputs        [✓] Log all detections                │ │
│ │                                                                         │ │
│ │ Default Redaction: [Mask ▼]  Mask Character: [*]                        │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─ Tabs ──────────────────────────────────────────────────────────────────┐ │
│ │ [Presidio Entities] [detect-secrets Plugins] [Custom Patterns] [Test]   │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ PRESIDIO ENTITIES TAB:                                                      │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Entity Type       │ Enabled │ Threshold │ Redaction │ Actions           │ │
│ ├───────────────────┼─────────┼───────────┼───────────┼───────────────────┤ │
│ │ EMAIL             │ [✓]     │ [===●==] 0.7 │ [Mask ▼] │ [Edit] [Test]  │ │
│ │ PHONE_NUMBER      │ [✓]     │ [==●===] 0.6 │ [Mask ▼] │ [Edit] [Test]  │ │
│ │ US_SSN            │ [✓]     │ [====●=] 0.8 │ [Hash ▼] │ [Edit] [Test]  │ │
│ │ CREDIT_CARD       │ [✓]     │ [====●=] 0.8 │ [Mask ▼] │ [Edit] [Test]  │ │
│ │ PERSON            │ [ ]     │ [=●====] 0.5 │ [Tag ▼]  │ [Edit] [Test]  │ │
│ │ HIGH_ENTROPY*     │ [✓]     │ [===●==] 0.7 │ [Mask ▼] │ [Edit] [Test]  │ │
│ │ INTERNAL_HOSTNAME*│ [✓]     │ [===●==] 0.7 │ [Mask ▼] │ [Edit] [Test]  │ │
│ │ PRIVATE_IP*       │ [✓]     │ [===●==] 0.7 │ [Mask ▼] │ [Edit] [Test]  │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ * Custom recognizer                                                         │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ DETECT-SECRETS PLUGINS TAB:                                                 │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Plugin              │ Enabled │ Settings                    │ Actions   │ │
│ ├─────────────────────┼─────────┼─────────────────────────────┼───────────┤ │
│ │ HighEntropyString   │ [✓]     │ Base64: 4.5, Hex: 3.0       │ [Config]  │ │
│ │ KeywordDetector     │ [✓]     │ Keywords: password,secret   │ [Config]  │ │
│ │ AWSKeyDetector      │ [✓]     │ -                           │ -         │ │
│ │ GitHubTokenDetector │ [✓]     │ -                           │ -         │ │
│ │ PrivateKeyDetector  │ [✓]     │ -                           │ -         │ │
│ │ JwtTokenDetector    │ [✓]     │ -                           │ -         │ │
│ │ SlackDetector       │ [✓]     │ -                           │ -         │ │
│ │ StripeDetector      │ [✓]     │ -                           │ -         │ │
│ │ ... more plugins                                                        │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ TEST TAB:                                                                   │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Test Text:                                                              │ │
│ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ Enter text to test detection...                                     │ │ │
│ │ │ Example: My email is test@example.com and API key is sk_live_xxx    │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘ │ │
│ │                                                                         │ │
│ │ [Run Detection]                                                         │ │
│ │                                                                         │ │
│ │ Results:                                                                │ │
│ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ ✓ EMAIL detected (Presidio) - confidence: 0.95                      │ │ │
│ │ │   Value: test@example.com                                           │ │ │
│ │ │ ✓ API_KEY detected (detect-secrets) - confidence: 0.90              │ │ │
│ │ │   Value: sk_live_xxx                                                │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘ │ │
│ │                                                                         │ │
│ │ Redacted Preview:                                                       │ │
│ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ My email is [EMAIL] and API key is [API_KEY]                        │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**2. Detection Log Viewer Page (`/logs/pii-detection`)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Logs > PII & Secret Detection                              [Export CSV]     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌─ Filters ───────────────────────────────────────────────────────────────┐ │
│ │ Search: [________________________] [🔍]                                  │ │
│ │                                                                         │ │
│ │ Date Range: [2026-01-01] to [2026-01-26]                                │ │
│ │                                                                         │ │
│ │ Entity Type: [All ▼]   Engine: [All ▼]   Source: [All ▼]               │ │
│ │                                                                         │ │
│ │ Confidence: [Min: 0.0 ●========] [Max: =========● 1.0]                  │ │
│ │                                                                         │ │
│ │ [Apply Filters] [Clear]                                                 │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─ Statistics ────────────────────────────────────────────────────────────┐ │
│ │ Total: 3,450  │  Today: 245  │  Top: EMAIL (1,200)  │  Redacted: 98%   │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─ Detection Log ─────────────────────────────────────────────────────────┐ │
│ │ Timestamp           │ Type        │ Engine    │ Score │ Source   │ Act  │ │
│ ├─────────────────────┼─────────────┼───────────┼───────┼──────────┼──────┤ │
│ │ 2026-01-26 10:30:00 │ EMAIL       │ Presidio  │ 0.95  │ Runbook  │ [👁] │ │
│ │ 2026-01-26 10:28:15 │ API_KEY     │ detect-s  │ 0.90  │ LLM      │ [👁] │ │
│ │ 2026-01-26 10:25:00 │ AWS_KEY     │ detect-s  │ 0.99  │ Alert    │ [👁] │ │
│ │ 2026-01-26 10:22:30 │ PHONE       │ Presidio  │ 0.85  │ Runbook  │ [👁] │ │
│ │ 2026-01-26 10:20:00 │ PASSWORD    │ detect-s  │ 0.88  │ LLM      │ [👁] │ │
│ │ ... more rows                                                           │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ [< Prev] Page 1 of 69 [Next >]                                              │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ ┌─ Detail View (click row to expand) ─────────────────────────────────────┐ │
│ │ Detection ID: 550e8400-e29b-41d4-a716-446655440000                      │ │
│ │ Detected At: 2026-01-26 10:30:00 UTC                                    │ │
│ │ Entity Type: EMAIL                                                      │ │
│ │ Detection Engine: Presidio                                              │ │
│ │ Confidence Score: 0.95                                                  │ │
│ │ Source Type: runbook_output                                             │ │
│ │ Source ID: [Link to Execution]                                          │ │
│ │ Context: "...notification was sent to [EMAIL] for review by the..."    │ │
│ │ Position: 145-167                                                       │ │
│ │ Was Redacted: Yes                                                       │ │
│ │ Redaction Type: mask                                                    │ │
│ │ Original Hash: a1b2c3d4e5f6...                                          │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**3. Detection Statistics Dashboard Widget**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PII & Secret Detection (Last 7 Days)                           [View All →] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │    3,450    │ │     245     │ │    98.2%    │ │     12      │           │
│  │   Total     │ │   Today     │ │  Redacted   │ │  Unacked    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                                             │
│  Detections by Type:          Trend (7 days):                              │
│  ┌──────────────────────┐     ┌────────────────────────────────────┐       │
│  │ EMAIL      ████████ 35%│   │     *                              │       │
│  │ API_KEY    ██████   23%│   │    * *    *                        │       │
│  │ PASSWORD   █████    20%│   │   *   *  * *                       │       │
│  │ PHONE      ███      12%│   │  *     **   *                      │       │
│  │ OTHER      ██       10%│   │ M  T  W  T  F  S  S                │       │
│  └──────────────────────┘     └────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Security and Privacy Considerations

1. **Sensitive Data Handling**
   - Original detected values are NEVER stored in plain text
   - Only SHA-256 hashes stored for deduplication/baseline tracking
   - Context snippets always show redacted versions
   - Database encryption at rest for detection logs table

2. **Access Control**
   - PII configuration requires `admin` role
   - Detection log viewing requires `security_viewer` role
   - Audit log export requires `security_admin` role

3. **Audit Trail**
   - All configuration changes logged with user ID and timestamp
   - Detection log records are immutable (append-only)
   - No deletion of detection logs (retention policy based archival)

4. **Rate Limiting**
   - Detection API rate limited to prevent abuse
   - Test endpoint limited to 10 requests/minute per user

5. **Data Retention**
   - Detection logs retained for 90 days by default (configurable)
   - Archived logs compressed and moved to cold storage

---

## Implementation Plan

### Phase 1: Core Infrastructure (Days 1-2)

#### Task 1.1: Database Schema Migration
| Attribute | Value |
|-----------|-------|
| **Description** | Create Alembic migration for PII detection tables |
| **Files to Create** | `alembic/versions/xxx_add_pii_detection_tables.py` |
| **Files to Modify** | None |
| **Interfaces** | Database schema |
| **Complexity** | Low |
| **Dependencies** | None |

**Function Signatures:**
```python
# Migration file
def upgrade():
    # Create pii_detection_config table
    # Create pii_detection_logs table
    # Create secret_baselines table
    # Create indexes for search performance

def downgrade():
    # Drop tables in reverse order
```

**Configuration Keys:** None

---

#### Task 1.2: SQLAlchemy Models
| Attribute | Value |
|-----------|-------|
| **Description** | Create ORM models for PII detection tables |
| **Files to Create** | `app/models/pii_models.py` |
| **Files to Modify** | `app/models/__init__.py` |
| **Interfaces** | ORM layer |
| **Complexity** | Low |
| **Dependencies** | Task 1.1 |

**Class Names:**
```python
class PIIDetectionConfig(Base):
    __tablename__ = "pii_detection_config"
    # ... columns as defined in schema

class PIIDetectionLog(Base):
    __tablename__ = "pii_detection_logs"
    # ... columns as defined in schema

class SecretBaseline(Base):
    __tablename__ = "secret_baselines"
    # ... columns as defined in schema
```

---

#### Task 1.3: Pydantic Schemas
| Attribute | Value |
|-----------|-------|
| **Description** | Create request/response schemas for PII API |
| **Files to Create** | `app/schemas/pii_schemas.py` |
| **Files to Modify** | `app/schemas/__init__.py` |
| **Interfaces** | API validation |
| **Complexity** | Low |
| **Dependencies** | None |

**Class Names:**
```python
class DetectionRequest(BaseModel): ...
class DetectionResponse(BaseModel): ...
class DetectionResult(BaseModel): ...
class PIIConfigResponse(BaseModel): ...
class PIIConfigUpdate(BaseModel): ...
class DetectionLogResponse(BaseModel): ...
class DetectionLogQuery(BaseModel): ...
class DetectionStatsResponse(BaseModel): ...
class TestDetectionRequest(BaseModel): ...
class TestDetectionResponse(BaseModel): ...
class EntityListResponse(BaseModel): ...
class PluginListResponse(BaseModel): ...
```

---

### Phase 2: Presidio Integration (Days 2-3)

#### Task 2.1: Base Presidio Service
| Attribute | Value |
|-----------|-------|
| **Description** | Create Presidio analyzer and anonymizer service wrapper |
| **Files to Create** | `app/services/presidio_service.py` |
| **Files to Modify** | `requirements.txt` (add presidio-analyzer, presidio-anonymizer) |
| **Interfaces** | Internal service |
| **Complexity** | Medium |
| **Dependencies** | None |

**Function Signatures:**
```python
class PresidioService:
    def __init__(self, config: PIIConfig): ...
    def analyze(self, text: str, entities: List[str] = None) -> List[PresidioResult]: ...
    def anonymize(self, text: str, results: List[PresidioResult], redaction_type: str) -> str: ...
    def get_supported_entities(self) -> List[EntityInfo]: ...
    def update_config(self, config: PIIConfig) -> None: ...
```

**Configuration Keys:**
- `PII_PRESIDIO_ENABLED` (bool, default: true)
- `PII_PRESIDIO_DEFAULT_THRESHOLD` (float, default: 0.7)
- `PII_PRESIDIO_LANGUAGE` (str, default: "en")

---

#### Task 2.2: Custom High Entropy Recognizer
| Attribute | Value |
|-----------|-------|
| **Description** | Create custom Presidio recognizer for high entropy strings |
| **Files to Create** | `app/services/recognizers/high_entropy_recognizer.py` |
| **Files to Modify** | None |
| **Interfaces** | Presidio EntityRecognizer |
| **Complexity** | Medium |
| **Dependencies** | Task 2.1 |

**Class Names:**
```python
class HighEntropySecretRecognizer(EntityRecognizer):
    def __init__(self, base64_threshold: float = 4.5, hex_threshold: float = 3.0): ...
    def load(self) -> None: ...
    def analyze(self, text: str, entities: List[str], nlp_artifacts) -> List[RecognizerResult]: ...
    
    @staticmethod
    def calculate_entropy(data: str) -> float: ...
    
    @staticmethod
    def is_base64(s: str) -> bool: ...
    
    @staticmethod
    def is_hex(s: str) -> bool: ...
```

**Context Keywords:**
```python
CONTEXT_KEYWORDS = [
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "auth", "credential", "private_key", "access_key", "bearer"
]
```

---

#### Task 2.3: Custom Hostname Recognizer
| Attribute | Value |
|-----------|-------|
| **Description** | Create recognizer for internal hostnames |
| **Files to Create** | `app/services/recognizers/hostname_recognizer.py` |
| **Files to Modify** | None |
| **Interfaces** | Presidio EntityRecognizer |
| **Complexity** | Low |
| **Dependencies** | Task 2.1 |

**Class Names:**
```python
class InternalHostnameRecognizer(EntityRecognizer):
    def __init__(self, internal_domains: List[str] = None): ...
    def load(self) -> None: ...
    def analyze(self, text: str, entities: List[str], nlp_artifacts) -> List[RecognizerResult]: ...
```

**Default Internal Domains:**
```python
DEFAULT_INTERNAL_DOMAINS = [".internal", ".local", ".corp", ".lan", ".private"]
```

---

#### Task 2.4: Custom Private IP Recognizer
| Attribute | Value |
|-----------|-------|
| **Description** | Create recognizer for private IP addresses (RFC 1918) |
| **Files to Create** | `app/services/recognizers/private_ip_recognizer.py` |
| **Files to Modify** | None |
| **Interfaces** | Presidio EntityRecognizer |
| **Complexity** | Low |
| **Dependencies** | Task 2.1 |

**Class Names:**
```python
class PrivateIPRecognizer(EntityRecognizer):
    def __init__(self): ...
    def load(self) -> None: ...
    def analyze(self, text: str, entities: List[str], nlp_artifacts) -> List[RecognizerResult]: ...
    
    @staticmethod
    def is_private_ip(ip: str) -> bool: ...
```

**IP Ranges:**
```python
PRIVATE_RANGES = [
    "10.0.0.0/8",      # Class A
    "172.16.0.0/12",   # Class B
    "192.168.0.0/16",  # Class C
    "127.0.0.0/8",     # Loopback
]
```

---

#### Task 2.5: Recognizer Registry
| Attribute | Value |
|-----------|-------|
| **Description** | Create registry to manage and initialize all recognizers |
| **Files to Create** | `app/services/recognizers/__init__.py` |
| **Files to Modify** | `app/services/presidio_service.py` |
| **Interfaces** | Internal |
| **Complexity** | Low |
| **Dependencies** | Tasks 2.2, 2.3, 2.4 |

**Function Signatures:**
```python
def get_custom_recognizers(config: PIIConfig) -> List[EntityRecognizer]:
    """Return list of configured custom recognizers"""
    ...

def register_recognizers(analyzer: AnalyzerEngine, recognizers: List[EntityRecognizer]) -> None:
    """Register custom recognizers with Presidio analyzer"""
    ...
```

---

### Phase 3: detect-secrets Integration (Days 3-4)

#### Task 3.1: Secret Detection Service
| Attribute | Value |
|-----------|-------|
| **Description** | Create wrapper service for detect-secrets library |
| **Files to Create** | `app/services/secret_detection_service.py` |
| **Files to Modify** | `requirements.txt` (add detect-secrets>=1.4.0) |
| **Interfaces** | Internal service |
| **Complexity** | Medium |
| **Dependencies** | None |

**Function Signatures:**
```python
class SecretDetectionService:
    def __init__(self, config: SecretDetectionConfig): ...
    def scan_text(self, text: str, plugins: List[str] = None) -> List[SecretResult]: ...
    def get_available_plugins(self) -> List[PluginInfo]: ...
    def update_config(self, config: SecretDetectionConfig) -> None: ...
    
    def _initialize_plugins(self) -> Dict[str, BasePlugin]: ...
    def _convert_result(self, secret: PotentialSecret) -> SecretResult: ...
```

**Configuration Keys:**
- `SECRET_DETECTION_ENABLED` (bool, default: true)
- `SECRET_HIGH_ENTROPY_BASE64_LIMIT` (float, default: 4.5)
- `SECRET_HIGH_ENTROPY_HEX_LIMIT` (float, default: 3.0)
- `SECRET_KEYWORD_EXCLUDE` (list, default: [])

---

#### Task 3.2: Plugin Configuration Manager
| Attribute | Value |
|-----------|-------|
| **Description** | Manage detect-secrets plugin configuration |
| **Files to Create** | `app/services/secret_plugin_config.py` |
| **Files to Modify** | None |
| **Interfaces** | Internal |
| **Complexity** | Low |
| **Dependencies** | Task 3.1 |

**Function Signatures:**
```python
class SecretPluginConfig:
    @staticmethod
    def get_default_plugins() -> Dict[str, Dict]: ...
    
    @staticmethod
    def configure_high_entropy(base64_limit: float, hex_limit: float) -> Dict: ...
    
    @staticmethod
    def configure_keyword_detector(keywords: List[str]) -> Dict: ...
    
    @staticmethod
    def get_plugin_info() -> List[PluginInfo]: ...
```

**Default Plugins:**
```python
DEFAULT_PLUGINS = {
    "HighEntropyString": {"base64_limit": 4.5, "hex_limit": 3.0},
    "KeywordDetector": {"keyword_exclude": []},
    "AWSKeyDetector": {},
    "AzureStorageKeyDetector": {},
    "BasicAuthDetector": {},
    "GitHubTokenDetector": {},
    "JwtTokenDetector": {},
    "PrivateKeyDetector": {},
    "SlackDetector": {},
    "StripeDetector": {},
    "TwilioKeyDetector": {},
}
```

---

### Phase 4: Unified PII Service (Day 4)

#### Task 4.1: Main PII Service
| Attribute | Value |
|-----------|-------|
| **Description** | Create unified service that orchestrates both detection engines |
| **Files to Create** | `app/services/pii_service.py` |
| **Files to Modify** | `app/services/__init__.py` |
| **Interfaces** | Main service interface |
| **Complexity** | High |
| **Dependencies** | Tasks 2.1, 3.1 |

**Function Signatures:**
```python
class PIIService:
    def __init__(
        self,
        db: AsyncSession,
        presidio_service: PresidioService,
        secret_service: SecretDetectionService
    ): ...
    
    async def detect(
        self,
        text: str,
        source_type: str,
        source_id: str = None,
        engines: List[str] = None,
        entity_types: List[str] = None
    ) -> DetectionResponse: ...
    
    async def redact(
        self,
        text: str,
        redaction_type: str = "mask",
        mask_char: str = "*"
    ) -> RedactionResponse: ...
    
    async def get_config(self) -> PIIConfigResponse: ...
    
    async def update_config(self, update: PIIConfigUpdate) -> PIIConfigResponse: ...
    
    async def log_detection(self, detection: DetectionResult, source_type: str, source_id: str) -> None: ...
    
    def _merge_results(
        self,
        presidio_results: List[PresidioResult],
        secret_results: List[SecretResult]
    ) -> List[DetectionResult]: ...
    
    def _deduplicate_results(self, results: List[DetectionResult]) -> List[DetectionResult]: ...
```

---

#### Task 4.2: Detection Result Merger
| Attribute | Value |
|-----------|-------|
| **Description** | Logic to merge and deduplicate results from both engines |
| **Files to Create** | `app/services/detection_merger.py` |
| **Files to Modify** | None |
| **Interfaces** | Internal utility |
| **Complexity** | Medium |
| **Dependencies** | None |

**Function Signatures:**
```python
class DetectionMerger:
    @staticmethod
    def merge(
        presidio_results: List[PresidioResult],
        secret_results: List[SecretResult]
    ) -> List[DetectionResult]: ...
    
    @staticmethod
    def deduplicate(results: List[DetectionResult], overlap_threshold: float = 0.8) -> List[DetectionResult]: ...
    
    @staticmethod
    def calculate_overlap(r1: DetectionResult, r2: DetectionResult) -> float: ...
    
    @staticmethod
    def normalize_entity_type(engine: str, entity_type: str) -> str: ...
```

---

### Phase 5: API Layer (Days 4-5)

#### Task 5.1: PII Detection Router
| Attribute | Value |
|-----------|-------|
| **Description** | Create FastAPI router for PII detection endpoints |
| **Files to Create** | `app/routers/pii.py` |
| **Files to Modify** | `app/main.py` (register router) |
| **Interfaces** | REST API |
| **Complexity** | Medium |
| **Dependencies** | Task 4.1 |

**Endpoint Functions:**
```python
router = APIRouter(prefix="/api/v1/pii", tags=["PII Detection"])

@router.post("/detect")
async def detect_pii(request: DetectionRequest, service: PIIService = Depends()) -> DetectionResponse: ...

@router.post("/redact")
async def redact_pii(request: RedactionRequest, service: PIIService = Depends()) -> RedactionResponse: ...

@router.get("/config")
async def get_config(service: PIIService = Depends()) -> PIIConfigResponse: ...

@router.put("/config")
async def update_config(update: PIIConfigUpdate, service: PIIService = Depends()) -> PIIConfigResponse: ...

@router.post("/test")
async def test_detection(request: TestDetectionRequest, service: PIIService = Depends()) -> TestDetectionResponse: ...

@router.get("/entities")
async def list_entities(service: PIIService = Depends()) -> EntityListResponse: ...

@router.get("/plugins")
async def list_plugins(service: PIIService = Depends()) -> PluginListResponse: ...
```

---

#### Task 5.2: Detection Logs Router
| Attribute | Value |
|-----------|-------|
| **Description** | Create FastAPI router for detection log endpoints |
| **Files to Create** | `app/routers/pii_logs.py` |
| **Files to Modify** | `app/main.py` (register router) |
| **Interfaces** | REST API |
| **Complexity** | Medium |
| **Dependencies** | Task 4.1 |

**Endpoint Functions:**
```python
router = APIRouter(prefix="/api/v1/pii/logs", tags=["PII Detection Logs"])

@router.get("")
async def get_logs(
    page: int = 1,
    limit: int = 50,
    entity_type: str = None,
    engine: str = None,
    source_type: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    service: PIIService = Depends()
) -> DetectionLogListResponse: ...

@router.get("/search")
async def search_logs(
    q: str,
    engine: str = None,
    confidence_min: float = None,
    confidence_max: float = None,
    service: PIIService = Depends()
) -> DetectionLogSearchResponse: ...

@router.get("/stats")
async def get_stats(period: str = "7d", service: PIIService = Depends()) -> DetectionStatsResponse: ...

@router.get("/{log_id}")
async def get_log_detail(log_id: UUID, service: PIIService = Depends()) -> DetectionLogDetailResponse: ...

@router.get("/export")
async def export_logs(
    format: str = "csv",
    start_date: datetime = None,
    end_date: datetime = None,
    service: PIIService = Depends()
) -> StreamingResponse: ...
```

---

### Phase 6: Frontend UI (Days 5-7)

#### Task 6.1: PII Configuration Page Component
| Attribute | Value |
|-----------|-------|
| **Description** | Create main PII configuration page with tabs |
| **Files to Create** | `frontend/src/pages/settings/PIIDetectionSettings.tsx` |
| **Files to Modify** | `frontend/src/App.tsx` (add route) |
| **Interfaces** | React component |
| **Complexity** | High |
| **Dependencies** | Task 5.1 |

**Component Structure:**
```typescript
// Main page component
const PIIDetectionSettings: React.FC = () => { ... }

// Tabs
type TabType = 'presidio' | 'detect-secrets' | 'custom' | 'test';

// Props interfaces
interface PIIDetectionSettingsProps { }

interface TabPanelProps {
  value: TabType;
  index: TabType;
  children: React.ReactNode;
}
```

---

#### Task 6.2: Presidio Entities Configuration Component
| Attribute | Value |
|-----------|-------|
| **Description** | Table component for configuring Presidio entities |
| **Files to Create** | `frontend/src/components/pii/PresidioEntitiesConfig.tsx` |
| **Files to Modify** | None |
| **Interfaces** | React component |
| **Complexity** | Medium |
| **Dependencies** | Task 6.1 |

**Component Structure:**
```typescript
interface PresidioEntity {
  entity_type: string;
  enabled: boolean;
  threshold: number;
  redaction_type: 'mask' | 'hash' | 'remove' | 'tag';
  is_custom: boolean;
}

interface PresidioEntitiesConfigProps {
  entities: PresidioEntity[];
  onUpdate: (entities: PresidioEntity[]) => void;
  onTest: (entityType: string) => void;
}

const PresidioEntitiesConfig: React.FC<PresidioEntitiesConfigProps> = ({ ... }) => { ... }
```

---

#### Task 6.3: detect-secrets Plugins Configuration Component
| Attribute | Value |
|-----------|-------|
| **Description** | Table component for configuring detect-secrets plugins |
| **Files to Create** | `frontend/src/components/pii/DetectSecretsConfig.tsx` |
| **Files to Modify** | None |
| **Interfaces** | React component |
| **Complexity** | Medium |
| **Dependencies** | Task 6.1 |

**Component Structure:**
```typescript
interface SecretPlugin {
  plugin_name: string;
  enabled: boolean;
  configurable: boolean;
  settings: Record<string, any>;
}

interface DetectSecretsConfigProps {
  plugins: SecretPlugin[];
  onUpdate: (plugins: SecretPlugin[]) => void;
  onConfigurePlugin: (pluginName: string) => void;
}

const DetectSecretsConfig: React.FC<DetectSecretsConfigProps> = ({ ... }) => { ... }
```

---

#### Task 6.4: Detection Test Sandbox Component
| Attribute | Value |
|-----------|-------|
| **Description** | Interactive component for testing PII detection |
| **Files to Create** | `frontend/src/components/pii/DetectionTestSandbox.tsx` |
| **Files to Modify** | None |
| **Interfaces** | React component |
| **Complexity** | Medium |
| **Dependencies** | Task 5.1 |

**Component Structure:**
```typescript
interface TestResult {
  detections: Detection[];
  redacted_preview: string;
  engine_results: {
    presidio: { detections: number; processing_time_ms: number };
    detect_secrets: { detections: number; processing_time_ms: number };
  };
}

interface DetectionTestSandboxProps {
  onTest: (text: string, engines: string[]) => Promise<TestResult>;
}

const DetectionTestSandbox: React.FC<DetectionTestSandboxProps> = ({ ... }) => { ... }
```

---

#### Task 6.5: Detection Log Viewer Page
| Attribute | Value |
|-----------|-------|
| **Description** | Create detection log viewer page with search and filters |
| **Files to Create** | `frontend/src/pages/logs/PIIDetectionLogs.tsx` |
| **Files to Modify** | `frontend/src/App.tsx` (add route) |
| **Interfaces** | React component |
| **Complexity** | High |
| **Dependencies** | Task 5.2 |

**Component Structure:**
```typescript
interface LogFilters {
  search: string;
  entityType: string | null;
  engine: string | null;
  sourceType: string | null;
  startDate: Date | null;
  endDate: Date | null;
  confidenceMin: number;
  confidenceMax: number;
}

interface PIIDetectionLogsProps { }

const PIIDetectionLogs: React.FC<PIIDetectionLogsProps> = () => { ... }
```

---

#### Task 6.6: Detection Log Table Component
| Attribute | Value |
|-----------|-------|
| **Description** | Paginated table component for detection logs |
| **Files to Create** | `frontend/src/components/pii/DetectionLogTable.tsx` |
| **Files to Modify** | None |
| **Interfaces** | React component |
| **Complexity** | Medium |
| **Dependencies** | Task 6.5 |

**Component Structure:**
```typescript
interface DetectionLog {
  id: string;
  detected_at: string;
  entity_type: string;
  detection_engine: string;
  confidence_score: number;
  source_type: string;
  source_id: string;
  context_snippet: string;
  was_redacted: boolean;
}

interface DetectionLogTableProps {
  logs: DetectionLog[];
  totalCount: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onRowClick: (log: DetectionLog) => void;
  loading: boolean;
}

const DetectionLogTable: React.FC<DetectionLogTableProps> = ({ ... }) => { ... }
```

---

#### Task 6.7: Detection Statistics Component
| Attribute | Value |
|-----------|-------|
| **Description** | Statistics cards and charts for detection dashboard |
| **Files to Create** | `frontend/src/components/pii/DetectionStats.tsx` |
| **Files to Modify** | None |
| **Interfaces** | React component |
| **Complexity** | Medium |
| **Dependencies** | Task 5.2 |

**Component Structure:**
```typescript
interface DetectionStats {
  total_detections: number;
  by_entity_type: Record<string, number>;
  by_engine: Record<string, number>;
  by_source: Record<string, number>;
  trend: { date: string; count: number }[];
}

interface DetectionStatsProps {
  stats: DetectionStats;
  period: '24h' | '7d' | '30d';
  onPeriodChange: (period: string) => void;
}

const DetectionStats: React.FC<DetectionStatsProps> = ({ ... }) => { ... }
```

---

#### Task 6.8: Log Filter Panel Component
| Attribute | Value |
|-----------|-------|
| **Description** | Filter panel component for log viewer |
| **Files to Create** | `frontend/src/components/pii/LogFilterPanel.tsx` |
| **Files to Modify** | None |
| **Interfaces** | React component |
| **Complexity** | Low |
| **Dependencies** | Task 6.5 |

**Component Structure:**
```typescript
interface LogFilterPanelProps {
  filters: LogFilters;
  onFilterChange: (filters: LogFilters) => void;
  onApply: () => void;
  onClear: () => void;
  entityTypes: string[];
  engines: string[];
  sourceTypes: string[];
}

const LogFilterPanel: React.FC<LogFilterPanelProps> = ({ ... }) => { ... }
```

---

#### Task 6.9: API Hooks for PII
| Attribute | Value |
|-----------|-------|
| **Description** | Create React Query hooks for PII API |
| **Files to Create** | `frontend/src/hooks/usePII.ts` |
| **Files to Modify** | None |
| **Interfaces** | React hooks |
| **Complexity** | Medium |
| **Dependencies** | Tasks 5.1, 5.2 |

**Hook Functions:**
```typescript
// Configuration hooks
export const usePIIConfig = () => useQuery(...);
export const useUpdatePIIConfig = () => useMutation(...);

// Detection hooks  
export const useDetectPII = () => useMutation(...);
export const useTestDetection = () => useMutation(...);

// Entity/plugin list hooks
export const useEntities = () => useQuery(...);
export const usePlugins = () => useQuery(...);

// Log hooks
export const useDetectionLogs = (filters: LogFilters) => useQuery(...);
export const useSearchLogs = (query: string) => useQuery(...);
export const useDetectionStats = (period: string) => useQuery(...);
export const useExportLogs = () => useMutation(...);
```

---

#### Task 6.10: Navigation Updates
| Attribute | Value |
|-----------|-------|
| **Description** | Add PII Detection to navigation menu |
| **Files to Create** | None |
| **Files to Modify** | `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/routes.ts` |
| **Interfaces** | Navigation |
| **Complexity** | Low |
| **Dependencies** | Tasks 6.1, 6.5 |

**Route Definitions:**
```typescript
// Add to routes.ts
{
  path: '/settings/pii-detection',
  component: PIIDetectionSettings,
  name: 'PII Detection',
  icon: ShieldIcon,
  requiredRole: 'admin'
},
{
  path: '/logs/pii-detection',
  component: PIIDetectionLogs,
  name: 'Detection Logs',
  icon: SearchIcon,
  requiredRole: 'security_viewer'
}
```

---

### Phase 7: Integration Points (Days 7-8)

#### Task 7.1: Runbook Execution Integration
| Attribute | Value |
|-----------|-------|
| **Description** | Integrate PII detection into runbook execution output |
| **Files to Create** | None |
| **Files to Modify** | `app/services/execution_service.py` |
| **Interfaces** | Internal integration |
| **Complexity** | Medium |
| **Dependencies** | Task 4.1 |

**Integration Points:**
```python
class ExecutionService:
    async def execute_step(self, ...):
        # Existing execution logic
        result = await self._run_command(...)
        
        # NEW: Scan output for PII/secrets
        if self.pii_service.config.auto_scan_outputs:
            detection_result = await self.pii_service.detect(
                text=result.output,
                source_type="runbook_output",
                source_id=str(execution_id)
            )
            
            if self.pii_service.config.auto_redact:
                result.output = await self.pii_service.redact(result.output)
        
        return result
```

---

#### Task 7.2: LLM Response Integration
| Attribute | Value |
|-----------|-------|
| **Description** | Integrate PII detection into LLM service responses |
| **Files to Create** | None |
| **Files to Modify** | `app/services/llm_service.py` |
| **Interfaces** | Internal integration |
| **Complexity** | Medium |
| **Dependencies** | Task 4.1 |

**Integration Points:**
```python
class LLMService:
    async def generate_response(self, ...):
        # Existing LLM call
        response = await self._call_llm(...)
        
        # NEW: Scan LLM response for leaked secrets
        if self.pii_service.config.scan_llm_responses:
            await self.pii_service.detect(
                text=response.content,
                source_type="llm_response",
                source_id=str(request_id)
            )
            
            if self.pii_service.config.auto_redact:
                response.content = await self.pii_service.redact(response.content)
        
        return response
```

---

#### Task 7.3: Alert Data Integration
| Attribute | Value |
|-----------|-------|
| **Description** | Integrate PII detection into incoming alert data |
| **Files to Create** | None |
| **Files to Modify** | `app/services/alert_service.py` |
| **Interfaces** | Internal integration |
| **Complexity** | Low |
| **Dependencies** | Task 4.1 |

**Integration Points:**
```python
class AlertService:
    async def process_alert(self, alert_data: dict):
        # Convert alert to text for scanning
        alert_text = json.dumps(alert_data, default=str)
        
        # NEW: Scan alert data
        if self.pii_service.config.scan_alerts:
            await self.pii_service.detect(
                text=alert_text,
                source_type="alert_data",
                source_id=alert_data.get("fingerprint")
            )
        
        # Continue with alert processing...
```

---

### Phase 8: Testing & Documentation (Days 8-9)

#### Task 8.1: Unit Tests for Services
| Attribute | Value |
|-----------|-------|
| **Description** | Create unit tests for PII services |
| **Files to Create** | `tests/unit/test_pii_service.py`, `tests/unit/test_presidio_service.py`, `tests/unit/test_secret_detection_service.py` |
| **Files to Modify** | None |
| **Interfaces** | pytest |
| **Complexity** | Medium |
| **Dependencies** | Phase 4 |

See Testing section below.

---

#### Task 8.2: Integration Tests
| Attribute | Value |
|-----------|-------|
| **Description** | Create integration tests for PII API |
| **Files to Create** | `tests/integration/test_pii_api.py` |
| **Files to Modify** | None |
| **Interfaces** | pytest, httpx |
| **Complexity** | Medium |
| **Dependencies** | Phase 5 |

See Testing section below.

---

#### Task 8.3: Frontend Tests
| Attribute | Value |
|-----------|-------|
| **Description** | Create Jest/React Testing Library tests for UI components |
| **Files to Create** | `frontend/src/components/pii/__tests__/*.test.tsx`, `frontend/src/pages/settings/__tests__/PIIDetectionSettings.test.tsx` |
| **Files to Modify** | None |
| **Interfaces** | Jest, React Testing Library |
| **Complexity** | Medium |
| **Dependencies** | Phase 6 |

See Testing section below.

---

#### Task 8.4: Documentation
| Attribute | Value |
|-----------|-------|
| **Description** | Create user and developer documentation |
| **Files to Create** | `docs/PII_DETECTION_USER_GUIDE.md`, `docs/PII_DETECTION_API.md` |
| **Files to Modify** | `docs/README.md` |
| **Interfaces** | Markdown documentation |
| **Complexity** | Low |
| **Dependencies** | All phases |

---

## Testing

### Unit Tests

#### `tests/unit/test_pii_service.py`
```python
# Test names and assertions:
class TestPIIService:
    def test_detect_email_returns_email_entity(self):
        """Assert EMAIL entity detected with confidence > 0.7"""
    
    def test_detect_multiple_entities(self):
        """Assert all entity types detected in mixed text"""
    
    def test_redact_mask_replaces_with_asterisks(self):
        """Assert redacted text contains [ENTITY_TYPE] markers"""
    
    def test_redact_hash_produces_consistent_hash(self):
        """Assert same input produces same hash output"""
    
    def test_config_update_persists_to_database(self):
        """Assert config changes saved and retrieved correctly"""
    
    def test_detection_logged_to_database(self):
        """Assert detection creates log entry with all fields"""
    
    def test_merge_results_deduplicates_overlapping(self):
        """Assert overlapping detections merged, higher confidence kept"""
    
    def test_disabled_entity_not_detected(self):
        """Assert disabled entity types not returned"""
    
    def test_threshold_filters_low_confidence(self):
        """Assert results below threshold filtered out"""
```

#### `tests/unit/test_presidio_service.py`
```python
class TestPresidioService:
    def test_analyze_email(self): ...
    def test_analyze_phone_number(self): ...
    def test_analyze_ssn(self): ...
    def test_analyze_credit_card(self): ...
    def test_analyze_person_name(self): ...
    def test_custom_high_entropy_recognizer(self): ...
    def test_custom_hostname_recognizer(self): ...
    def test_custom_private_ip_recognizer(self): ...
    def test_anonymize_mask(self): ...
    def test_anonymize_hash(self): ...
    def test_anonymize_remove(self): ...
```

#### `tests/unit/test_secret_detection_service.py`
```python
class TestSecretDetectionService:
    def test_detect_aws_key(self): ...
    def test_detect_github_token(self): ...
    def test_detect_jwt_token(self): ...
    def test_detect_private_key(self): ...
    def test_detect_high_entropy_base64(self): ...
    def test_detect_high_entropy_hex(self): ...
    def test_detect_keyword_password(self): ...
    def test_plugin_enable_disable(self): ...
    def test_entropy_threshold_adjustment(self): ...
```

#### `tests/unit/test_recognizers.py`
```python
class TestHighEntropyRecognizer:
    def test_entropy_calculation_random_string(self): ...
    def test_entropy_calculation_repeated_chars(self): ...
    def test_base64_detection(self): ...
    def test_hex_detection(self): ...
    def test_context_keyword_boost(self): ...
    def test_false_positive_uuid(self): ...  # UUIDs should not trigger

class TestHostnameRecognizer:
    def test_internal_domain_detected(self): ...
    def test_public_domain_ignored(self): ...
    def test_custom_domain_pattern(self): ...

class TestPrivateIPRecognizer:
    def test_10_x_range_detected(self): ...
    def test_172_16_range_detected(self): ...
    def test_192_168_range_detected(self): ...
    def test_public_ip_ignored(self): ...
    def test_loopback_detected(self): ...
```

### Integration Tests

#### `tests/integration/test_pii_api.py`
```python
class TestPIIDetectionAPI:
    async def test_detect_endpoint_returns_200(self): ...
    async def test_detect_endpoint_returns_detections(self): ...
    async def test_redact_endpoint_returns_redacted_text(self): ...
    async def test_config_get_returns_all_settings(self): ...
    async def test_config_put_updates_settings(self): ...
    async def test_test_endpoint_returns_preview(self): ...
    async def test_entities_endpoint_returns_list(self): ...
    async def test_plugins_endpoint_returns_list(self): ...

class TestPIILogsAPI:
    async def test_logs_endpoint_returns_paginated(self): ...
    async def test_logs_filter_by_entity_type(self): ...
    async def test_logs_filter_by_date_range(self): ...
    async def test_logs_search_returns_results(self): ...
    async def test_logs_stats_returns_aggregates(self): ...
    async def test_logs_export_returns_csv(self): ...
```

### End-to-End Tests

#### Scenarios
1. **Full Detection Flow**
   - Input text with email, phone, API key
   - Verify all detected
   - Verify redaction applied
   - Verify log entries created

2. **Configuration Update Flow**
   - Update threshold for EMAIL
   - Run detection
   - Verify new threshold applied

3. **Log Search Flow**
   - Create multiple detection logs
   - Search with various filters
   - Verify correct results returned

### Test Data and Fixtures

#### `tests/fixtures/pii_test_data.py`
```python
TEST_TEXTS = {
    "email_only": "Contact support@example.com for help",
    "phone_only": "Call us at 555-123-4567",
    "api_key_only": "API key: sk_live_abc123xyz789def456",
    "mixed": """
        Contact john.doe@company.com or call 555-123-4567.
        Use API key: AKIAIOSFODNN7EXAMPLE
        Password: SuperSecret123!
    """,
    "no_pii": "This is a clean text with no sensitive data.",
    "high_entropy": "Token: aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Q=",
}

TEST_SECRETS = {
    "aws_key": "AKIAIOSFODNN7EXAMPLE",
    "github_token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...",
}
```

### Performance and Load Test Suggestions

1. **Throughput Test**
   - Measure detections/second with 1KB text blocks
   - Target: >100 detections/second

2. **Latency Test**
   - Measure P99 latency for detection endpoint
   - Target: <200ms for 1KB text

3. **Memory Test**
   - Monitor memory usage during batch processing
   - Ensure no memory leaks over 10,000 requests

4. **Concurrent Users Test**
   - Simulate 50 concurrent users
   - Verify no degradation in response times

---

## Acceptance Criteria

### Functional Criteria
- [ ] Presidio detects EMAIL, PHONE_NUMBER, US_SSN, CREDIT_CARD, PERSON with >90% accuracy
- [ ] detect-secrets detects AWS keys, GitHub tokens, JWT, private keys with >95% accuracy
- [ ] High entropy detection catches random strings >20 chars with <5% false positive rate
- [ ] Redaction correctly masks/hashes/removes detected entities
- [ ] Configuration changes persist across service restarts
- [ ] Detection logs capture all required fields
- [ ] Log search returns results within 2 seconds for 100K+ records
- [ ] Statistics aggregate correctly for all time periods
- [ ] UI displays all configuration options
- [ ] UI test sandbox provides real-time feedback
- [ ] CSV export includes all log fields

### Non-Functional Criteria
- [ ] Detection latency <200ms for 1KB text (P99)
- [ ] API supports 100 concurrent requests
- [ ] UI loads configuration page in <2 seconds
- [ ] Log viewer pagination loads in <500ms

### Manual Test Checklist
- [ ] Enable/disable individual entity types in UI
- [ ] Adjust threshold sliders and verify detection changes
- [ ] Test sandbox with various PII types
- [ ] View detection logs with different filters
- [ ] Export logs to CSV
- [ ] Verify redaction in runbook execution output
- [ ] Verify redaction in LLM response display
- [ ] Check statistics accuracy after multiple detections

---

## Branch and Commit Guidance

### Branch Name
```
feature/pii-secret-detection
```

### Atomic Commit Messages
```
feat(db): add PII detection database schema

feat(models): add SQLAlchemy models for PII detection

feat(schemas): add Pydantic schemas for PII API

feat(presidio): implement base Presidio service wrapper

feat(recognizers): add high entropy secret recognizer

feat(recognizers): add internal hostname recognizer

feat(recognizers): add private IP recognizer

feat(recognizers): create recognizer registry

feat(detect-secrets): implement secret detection service wrapper

feat(detect-secrets): add plugin configuration manager

feat(pii): implement unified PII service

feat(pii): add detection result merger utility

feat(api): add PII detection router endpoints

feat(api): add detection logs router endpoints

feat(ui): add PII configuration page

feat(ui): add Presidio entities configuration component

feat(ui): add detect-secrets plugins configuration component

feat(ui): add detection test sandbox component

feat(ui): add detection log viewer page

feat(ui): add detection log table component

feat(ui): add detection statistics component

feat(ui): add log filter panel component

feat(hooks): add React Query hooks for PII API

feat(nav): add PII Detection to navigation menu

feat(integration): integrate PII detection with runbook execution

feat(integration): integrate PII detection with LLM responses

feat(integration): integrate PII detection with alert processing

test(unit): add PII service unit tests

test(unit): add Presidio service unit tests

test(unit): add secret detection service unit tests

test(unit): add custom recognizer unit tests

test(integration): add PII API integration tests

test(ui): add PII component tests

docs: add PII detection user guide

docs: add PII detection API documentation
```

### PR Description Template
```markdown
## Summary
Implements comprehensive PII and secret detection system using Microsoft Presidio 
and detect-secrets library with full UI for configuration and log viewing.

## Changes
- Database schema for configuration, logs, and baselines
- Presidio integration with custom recognizers (high entropy, hostname, private IP)
- detect-secrets integration with 20+ plugins
- Unified PIIService merging both engines
- REST API for detection, configuration, and logs
- React UI for configuration and log viewer
- Integration with runbook execution, LLM responses, and alerts

## Testing
- [ ] Unit tests pass (XX tests)
- [ ] Integration tests pass (XX tests)
- [ ] UI tests pass (XX tests)
- [ ] Manual testing completed per checklist

## Screenshots
[Include screenshots of configuration UI and log viewer]

## Migration Notes
- Run `alembic upgrade head` to create new tables
- Default configuration will be seeded on first startup
```

---

## Developer Notes

### Known Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positives on high entropy | Medium | Medium | Tune thresholds per environment, provide easy adjustment UI |
| Performance degradation with large texts | Low | High | Implement text chunking, add caching for config |
| detect-secrets version incompatibility | Low | Medium | Pin version in requirements, add version check |
| Presidio model download on first run | Medium | Low | Pre-download models in Docker build |
| Memory usage with concurrent requests | Low | Medium | Implement request queuing, add memory limits |

### Helpful References
- [Presidio Documentation](https://microsoft.github.io/presidio/)
- [Presidio Custom Recognizers](https://microsoft.github.io/presidio/analyzer/adding_recognizers/)
- [detect-secrets Documentation](https://github.com/Yelp/detect-secrets)
- [detect-secrets Plugin Architecture](https://github.com/Yelp/detect-secrets/blob/master/docs/plugins.md)
- [Shannon Entropy Explained](https://en.wikipedia.org/wiki/Entropy_(information_theory))
- [RFC 1918 Private IP Ranges](https://datatracker.ietf.org/doc/html/rfc1918)

### Environment Variables Required
```bash
# Presidio settings
PII_PRESIDIO_ENABLED=true
PII_PRESIDIO_DEFAULT_THRESHOLD=0.7
PII_PRESIDIO_LANGUAGE=en

# detect-secrets settings
SECRET_DETECTION_ENABLED=true
SECRET_HIGH_ENTROPY_BASE64_LIMIT=4.5
SECRET_HIGH_ENTROPY_HEX_LIMIT=3.0

# Feature flags
PII_AUTO_REDACT=true
PII_LOG_DETECTIONS=true
PII_SCAN_RUNBOOK_OUTPUTS=true
PII_SCAN_LLM_RESPONSES=true
PII_SCAN_ALERTS=true

# Retention
PII_LOG_RETENTION_DAYS=90
```

### Docker Build Notes
```dockerfile
# Add to Dockerfile to pre-download Presidio models
RUN python -c "from presidio_analyzer import AnalyzerEngine; AnalyzerEngine()"
```

---

## DONE Checklist

- [ ] Database migration created and tested
- [ ] SQLAlchemy models implemented
- [ ] Pydantic schemas defined
- [ ] Presidio service with custom recognizers working
- [ ] detect-secrets service with plugin configuration working
- [ ] Unified PIIService orchestrating both engines
- [ ] Detection API endpoints functional
- [ ] Log API endpoints functional
- [ ] UI configuration page complete
- [ ] UI log viewer page complete
- [ ] Integration with runbook execution
- [ ] Integration with LLM responses
- [ ] Integration with alerts
- [ ] Unit tests passing (>90% coverage)
- [ ] Integration tests passing
- [ ] UI tests passing
- [ ] Documentation complete
- [ ] Performance benchmarks met
- [ ] Security review completed
- [ ] Code review approved
- [ ] Deployed to staging
- [ ] QA sign-off
- [ ] Production deployment ready
