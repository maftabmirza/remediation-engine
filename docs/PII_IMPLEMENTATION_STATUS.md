# PII & Secret Detection Implementation - FULLY OPERATIONAL

> **Last Updated**: January 31, 2026  
> **Status**: ✅ Production Ready (with Session-Persistent Indexed Placeholders)  
> **Test Results**: All functional tests passing

## Implementation Summary

The PII and Secret Detection system is **fully implemented and operational** across all phases. The system provides end-to-end protection for sensitive data in the troubleshooting chat workflow.

### Key Features (January 31, 2026 Update)

- ✅ **Indexed Placeholders**: Same PII → same placeholder across entire session (e.g., `[EMAIL_ADDRESS_1]`)
- ✅ **Session Persistence**: PII mappings stored in `ai_sessions.pii_mapping_json` column
- ✅ **Tool Output Scanning**: Terminal command outputs are now scanned and redacted
- ✅ **User Sees Original**: Original PII shown to user, redacted version sent to LLM

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER INPUT (Chat)                            │
│  "Contact john@example.com and jane@company.com"                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PII Service (Orchestrator)                          │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   Presidio Engine   │    │   detect-secrets Engine         │ │
│  │  - EMAIL_ADDRESS    │    │  - AWS Keys (AKIA...)           │ │
│  │  - PHONE_NUMBER     │    │  - GitHub Tokens (ghp_...)      │ │
│  │  - US_SSN           │    │  - Stripe Keys (sk_live_...)    │ │
│  │  - CREDIT_CARD      │    │  - JWT Tokens                   │ │
│  │  - PERSON           │    │  - Private Keys                 │ │
│  │  - IP_ADDRESS       │    │  - 20+ more patterns            │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PIIMappingManager (Session-Persistent)              │
│  - Assigns indexed placeholders: [EMAIL_ADDRESS_1], [EMAIL_2]   │
│  - Stores mapping in ai_sessions.pii_mapping_json               │
│  - Same PII value = same placeholder across entire session      │
│  - Supports de-anonymization for user display                   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────────┐
│   TO LLM (Redacted)      │     │   TO USER (Original)            │
│   "Contact               │     │   "Contact john@example.com     │
│    [EMAIL_ADDRESS_1] and │     │    and jane@company.com"        │
│    [EMAIL_ADDRESS_2]"    │     │   + [PII detected indicator]    │
└─────────────────────────┘     └─────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase Completion Status

### Phase 1: Database Schema & Models ✅
- **Migration**: `alembic/versions/20260126_add_pii_detection_tables.py`
- **Models**: `app/models/pii_models.py`
  - PIIDetectionConfig
  - PIIDetectionLog
  - SecretBaseline
- **Schemas**: `app/schemas/pii_schemas.py`
  - 20+ Pydantic models for API validation

### Phase 2: Presidio Service & Custom Recognizers ✅
- **Presidio Service**: `app/services/presidio_service.py`
  - Wrapper for Microsoft Presidio
  - Analyze and anonymize methods
  - Support for EMAIL, PHONE, SSN, CREDIT_CARD, PERSON, etc.

- **Custom Recognizers**:
  - `high_entropy_recognizer.py` - Detects high entropy strings (Shannon entropy calculation)
  - `hostname_recognizer.py` - Detects internal hostnames (.internal, .local, .corp, etc.)
  - `private_ip_recognizer.py` - Detects RFC 1918 private IP addresses
  - `__init__.py` - Recognizer registry

### Phase 3: detect-secrets Integration ✅
- **Secret Detection Service**: `app/services/secret_detection_service.py`
  - Wrapper for Yelp's detect-secrets library
  - 24 built-in plugins enabled
  - **Fixed**: Proper position calculation for accurate redaction
  
- **Supported Secret Types**:
  | Plugin | Pattern Example | Status |
  |--------|-----------------|--------|
  | AWSKeyDetector | `AKIA...` | ✅ |
  | GitHubTokenDetector | `ghp_...` (40 chars) | ✅ |
  | GitLabTokenDetector | `glpat-...` | ✅ |
  | OpenAIDetector | `sk-...` | ✅ |
  | StripeDetector | `sk_live_...`, `sk_test_...` | ✅ |
  | JwtTokenDetector | `eyJ...` | ✅ |
  | PrivateKeyDetector | `-----BEGIN...PRIVATE KEY-----` | ✅ |
  | SlackDetector | `xoxb-...`, `xoxp-...` | ✅ |
  | BasicAuthDetector | `user:pass@host` | ✅ |
  | + 15 more | Various patterns | ✅ |

- **Note**: High-entropy detectors (Base64/Hex) are **disabled by default** to prevent false positives on normal text.

### Phase 4: Unified PII Service ✅
- **Main Service**: `app/services/pii_service.py`
  - Orchestrates both detection engines
  - Detection, redaction, logging
  - Configuration management
  - Log retrieval and stats

- **Detection Merger**: `app/services/detection_merger.py`
  - Merges results from both engines
  - Deduplicates overlapping detections
  - Entity type normalization

### Phase 5: API Layer ✅
- **PII Router**: `app/routers/pii.py`
  - `POST /api/v1/pii/detect` - Detect PII/secrets in text
  - `POST /api/v1/pii/redact` - Redact detected entities
  - `GET /api/v1/pii/config` - Get current configuration
  - `PUT /api/v1/pii/config` - Update configuration
  - `POST /api/v1/pii/test` - Test detection with sample text
  - `GET /api/v1/pii/entities` - List available entity types
  - `GET /api/v1/pii/plugins` - List detect-secrets plugins

### Phase 6: Frontend UI ✅
- **Configuration Page**: `static/js/pii_config.js`
- **Detection Test Sandbox**: Inline testing in UI
- **Log Viewer**: Detection audit logs

### Phase 7: Integration Points ✅

#### /troubleshoot Pillar
- **Troubleshoot Chat API**: `app/routers/troubleshoot_api.py`
  - User input scanned before LLM
  - Redacted messages stored in DB
  - PII mapping for de-anonymization
  - Session-persistent indexed placeholders (e.g., `[EMAIL_ADDRESS_1]`)
  
- **Troubleshoot Agent**: `app/services/agentic/troubleshoot_native_agent.py`
  - `_scan_and_redact_text()` method
  - Scans user input, agent responses, tool outputs
  - PIIMappingManager for consistent session placeholders
  
- **Native Agent**: `app/services/agentic/native_agent.py`
  - Full PII scanning in `run()` and `stream()` methods
  - Tool output scanning
  
- **LLM Service**: `app/services/llm_service.py`
  - PII service factory injection
  - Output scanning enabled

#### /alert Pillar
- **AI Alert Help Agent**: `app/services/agentic/ai_alert_help_agent.py`
  - `_scan_and_redact_text()` method
  - Scans user input in `run()` and `stream()` methods
  - PIIMappingManager support for consistent placeholders

#### RE-VIVE Agent (AIops Platform)
- **RE-VIVE Quick Help Agent**: `app/services/revive/revive_agent.py`
  - `_scan_and_redact_text()` method
  - Scans user input in `run()` and `stream()` methods
  - PIIMappingManager support for session-persistent redaction

- **RE-VIVE Chat Stream Router**: `app/routers/revive.py`
  - User input scanned before LLM
  - Session-persistent PII mappings via `ai_session.pii_mapping_json`
  - Frontend notified of redacted input

- **RE-VIVE WebSocket Handler**: `app/services/revive/websocket_handler.py`
  - Real-time PII scanning for WebSocket messages
  - Session-persistent PII mappings
  - Frontend notified of redacted input

#### RE-VIVE on Grafana Stack
- **RE-VIVE Grafana Router**: `app/routers/revive_grafana.py`
  - User query scanned before LLM
  - PIIMappingManager for redaction

- **RE-VIVE App Router**: `app/routers/revive_app.py`
  - User query scanned before LLM
  - PIIMappingManager for redaction

### Phase 8: Testing ✅
- **Test Suite**: `test_pii_suite.py`, `test_pii_e2e.py`
- **All functional tests passing** (6/6)
- **Performance**: ~30ms for 1KB, ~200ms for 10KB, ~1.5s for 100KB

---

## Test Results (January 31, 2026)

### Functional Tests: 6/6 PASSED ✅

| Test Case | Input | Expected | Detected | Status |
|-----------|-------|----------|----------|--------|
| Email | `john.doe@example.com` | EMAIL | EMAIL_ADDRESS | ✅ |
| SSN | `234-56-7890` | SSN | US_SSN | ✅ |
| Phone | `555-123-4567` | PHONE | PHONE_NUMBER | ✅ |
| Credit Card | `4111-1111-1111-1111` | CREDIT | CREDIT_CARD | ✅ |
| AWS Key | `AKIAIOSFODNN7EXAMPLE` | AWS | AWS Access Key | ✅ |
| GitHub Token | `ghp_xxxx...` (40 chars) | GitHub | GitHub Token | ✅ |

### Performance Tests

| Size | Avg Response | Throughput | Detections |
|------|-------------|------------|------------|
| 1 KB | 30ms | 27.9 KB/s | 2 |
| 10 KB | 199ms | 47.9 KB/s | 6 |
| 100 KB | 1,585ms | 61.4 KB/s | 23 |

### Redaction Test: PASSED ✅

**Input:**
```
Hello, my name is John Smith.
My email is john.smith@company.com and my SSN is 234-56-7890.
The AWS access key is AKIAIOSFODNN7EXAMPLE.
Credit card: 4111111111111111
```

**Output (Redacted):**
```
Hello, my name is [PERSON].
My email is [EMAIL_ADDRESS] and my SSN is [US_SSN].
The AWS access key is [AWS Access Key].
Credit card: [CREDIT_CARD]
```

---

## Security Workflow

### Chat Message Flow

```
1. User sends message with potential PII/secrets
   ↓
2. troubleshoot_api.py intercepts message
   ↓
3. PII Service detects sensitive data
   ↓
4. Detections logged to pii_detection_logs table
   ↓
5. Message redacted (e.g., email → [EMAIL_ADDRESS])
   ↓
6. REDACTED message sent to LLM
   ↓
7. LLM response scanned for any leaked PII
   ↓
8. Clean response returned to user
```

### What Gets Protected

| Data Type | Example | Redacted As |
|-----------|---------|-------------|
| Email | `john@example.com` | `[EMAIL_ADDRESS]` |
| Phone | `555-123-4567` | `[PHONE_NUMBER]` |
| SSN | `234-56-7890` | `[US_SSN]` |
| Credit Card | `4111111111111111` | `[CREDIT_CARD]` |
| Person Name | `John Smith` | `[PERSON]` |
| AWS Key | `AKIAIOSFODNN7EXAMPLE` | `[AWS Access Key]` |
| GitHub Token | `ghp_xxx...` | `[GitHub Token]` |
| Stripe Key | `sk_live_xxx...` | `[Secret Keyword]` |
| Private Key | `-----BEGIN RSA...` | `[Private Key]` |

---

## Known Limitations

### 1. Generic High-Entropy Strings
**Issue**: Random strings without known patterns (e.g., `fEgAN2S592XRmOammaRsdW3dlHXUDWZHTZ8JlHq1q3`) are NOT detected.

**Reason**: High-entropy detectors are disabled because they cause excessive false positives on normal text like "The quick brown fox jumps over the lazy dog".

**Workaround**: Users should avoid sharing generic tokens. Known API key formats (AWS, GitHub, Stripe, etc.) ARE detected.

### 2. SSN Pattern Validation
**Issue**: Some SSN-like patterns may not be detected if they don't follow valid SSN rules.

**Example**: `123-45-6789` (invalid first digit pattern) vs `234-56-7890` (valid pattern) ✅

### 3. Context-Dependent Detection
Some detections require context keywords:
- `password=secret123` → Detected ✅
- `secret123` alone → Not detected (no context)

---

## Next Steps (Optional Enhancements)

## Dependencies (Installed)

In `requirements.txt`:
```
presidio-analyzer>=2.2.354
presidio-anonymizer>=2.2.354
detect-secrets>=1.4.0
```

## Environment Variables

Add to `.env`:
```
PII_PRESIDIO_ENABLED=true
PII_PRESIDIO_DEFAULT_THRESHOLD=0.7
PII_PRESIDIO_LANGUAGE=en

SECRET_DETECTION_ENABLED=true
SECRET_HIGH_ENTROPY_BASE64_LIMIT=4.5
SECRET_HIGH_ENTROPY_HEX_LIMIT=3.0

PII_AUTO_REDACT=true
PII_LOG_DETECTIONS=true
PII_SCAN_RUNBOOK_OUTPUTS=true
PII_SCAN_LLM_RESPONSES=true
PII_SCAN_ALERTS=true

PII_LOG_RETENTION_DAYS=90
```

## Database Migration

Run the migration:
```bash
alembic upgrade head
```

## Quick Test Commands

### Test via API:
```bash
# Detect PII
curl -X POST http://localhost:8080/api/v1/pii/detect \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact john@example.com", "source_type": "test"}'

# Redact PII
curl -X POST http://localhost:8080/api/v1/pii/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "Email: john@example.com", "redaction_type": "tag"}'
```

### Test via Docker:
```bash
docker exec -w /app remediation-engine python test_pii_suite.py --base-url http://localhost:8080
docker exec -w /app remediation-engine python test_pii_e2e.py
```

### Test in Python:
```python
from app.services.presidio_service import PresidioService
from app.services.secret_detection_service import SecretDetectionService
from app.services.pii_service import PIIService

# Initialize services
presidio = PresidioService()
secrets = SecretDetectionService()
pii_service = PIIService(db, presidio, secrets)

# Test detection
result = await pii_service.detect(
    text="Contact john@example.com or call 555-123-4567. API key: AKIAIOSFODNN7EXAMPLE",
    source_type="test",
    engines=["presidio", "detect_secrets"]
)

print(f"Found {result.detection_count} detections")
for detection in result.detections:
    print(f"- {detection.entity_type}: {detection.value} (confidence: {detection.confidence})")
```

## File Structure

```
app/
├── models/
│   └── pii_models.py ✅
├── schemas/
│   └── pii_schemas.py ✅
├── services/
│   ├── presidio_service.py ✅
│   ├── secret_detection_service.py ✅ (fixed position calculation)
│   ├── secret_plugin_config.py ✅
│   ├── pii_service.py ✅
│   ├── detection_merger.py ✅
│   ├── llm_service.py ✅ (PII factory injection)
│   └── recognizers/
│       ├── __init__.py ✅
│       ├── high_entropy_recognizer.py ✅
│       ├── hostname_recognizer.py ✅
│       └── private_ip_recognizer.py ✅
├── routers/
│   ├── pii.py ✅
│   ├── troubleshoot_api.py ✅ (PII integration)
│   ├── revive.py ✅ (PII integration - RE-VIVE chat stream)
│   ├── revive_grafana.py ✅ (PII integration - Grafana context)
│   └── revive_app.py ✅ (PII integration - App context)
├── services/agentic/
│   ├── native_agent.py ✅ (PII scanning)
│   ├── troubleshoot_native_agent.py ✅ (PII scanning)
│   └── ai_alert_help_agent.py ✅ (PII scanning)
├── services/revive/
│   ├── revive_agent.py ✅ (PII scanning - RE-VIVE Quick Help Agent)
│   └── websocket_handler.py ✅ (PII scanning - WebSocket)
static/
└── js/
    └── troubleshoot_chat.js ✅ (redaction UI notification)
alembic/
└── versions/
    └── 20260126_add_pii_detection_tables.py ✅
tests/
├── test_pii_suite.py ✅
└── test_pii_e2e.py ✅
```

2. **Custom Recognizers**: High entropy, hostnames, private IPs
3. **Intelligent Merging**: Deduplicates overlapping detections
4. **Accurate Positioning**: Proper start/end positions for redaction
5. **Audit Logging**: Complete audit trail with SHA-256 hashing
6. **Flexible Redaction**: Mask, hash, remove, or tag
7. **Context Extraction**: Provides surrounding text (redacted)
8. **24 Secret Patterns**: AWS, GitHub, JWT, Stripe, private keys, etc.
9. **Configurable Thresholds**: Per-entity confidence thresholds
10. **End-to-End Chat Protection**: User input and AI responses scanned
11. **Session-Persistent Indexed Placeholders**: Same PII → same placeholder across session
12. **Tool Output Scanning**: Terminal command outputs scanned before LLM

## Indexed Placeholder System (NEW)
### Real-World Example

**User Input:**
```
Hello, I am Aftab and email is aftab@gmail.com
```

**System Behavior:**
- **Notification:** "🔒 PII redacted before sending to AI"
- **Detection:** `aftab@gmail.com` detected as EMAIL_ADDRESS (confidence: 0.95)
- **Redacted:** "Hello, I am Aftab and email is [EMAIL_ADDRESS_1]"
- **AI Response:** "Hello Aftab! I'm your AI Troubleshooting Assistant..."

**Note:** Person names like "Aftab" may not be redacted by default. This is configurable via the PERSON entity type threshold in PII configuration.
### How It Works

When PII is detected, the system assigns **indexed placeholders** that are consistent across the entire chat session:

| Message | Original | LLM Sees | Mapping |
|---------|----------|----------|---------|
| Msg 1 | `john@example.com` | `[EMAIL_ADDRESS_1]` | Stored |
| Msg 2 | `jane@company.com` | `[EMAIL_ADDRESS_2]` | Stored |
| Msg 3 | `john@example.com` | `[EMAIL_ADDRESS_1]` | Reused! |

### Storage

PII mappings are stored in the `ai_sessions.pii_mapping_json` column:

```json
{
  "[EMAIL_ADDRESS_1]": "john@example.com",
  "[EMAIL_ADDRESS_2]": "jane@company.com",
  "[AWS_KEY_1]": "AKIAIOSFODNN7EXAMPLE",
  "_counters": {"EMAIL_ADDRESS": 2, "AWS_KEY": 1},
  "_reverse": {
    "john@example.com": "[EMAIL_ADDRESS_1]",
    "jane@company.com": "[EMAIL_ADDRESS_2]"
  }
}
```

### Benefits

1. **Consistency**: Same email always gets same placeholder
2. **Context Preservation**: LLM knows `[EMAIL_ADDRESS_1]` and `[EMAIL_ADDRESS_2]` are different
3. **Session Persistence**: Resuming old session restores correct mappings
4. **De-anonymization**: Frontend can show original values to user

### Coverage

| Data Flow | Scanned? | Details |
|-----------|----------|---------|
| User input (/troubleshoot chat) | ✅ Yes | Before sending to LLM |
| User input (/alert) | ✅ Yes | Before sending to LLM |
| User input (RE-VIVE AIops) | ✅ Yes | Before sending to LLM |
| User input (RE-VIVE Grafana) | ✅ Yes | Before sending to LLM |
| User input (RE-VIVE WebSocket) | ✅ Yes | Before sending to LLM |
| Tool output (terminal) | ✅ Yes | Before adding to conversation |
| Agent response | ✅ Yes | Before returning to user |
| Runbook step output | ✅ Yes | In runbook_executor.py |

## LLM Interaction Points Summary

| Pillar/Feature | Router/Agent | PII Enabled |
|----------------|--------------|-------------|
| /troubleshoot | `troubleshoot_api.py` | ✅ Yes |
| /troubleshoot agent | `troubleshoot_native_agent.py` | ✅ Yes |
| /alert | `ai_alert_help_agent.py` | ✅ Yes |
| RE-VIVE (AIops) | `revive.py`, `revive_agent.py` | ✅ Yes |
| RE-VIVE WebSocket | `websocket_handler.py` | ✅ Yes |
| RE-VIVE (Grafana) | `revive_grafana.py` | ✅ Yes |
| RE-VIVE (App) | `revive_app.py` | ✅ Yes |
| Native Agent | `native_agent.py` | ✅ Yes |
| LLM Service | `llm_service.py` | ✅ Yes |

## Performance Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| 1KB Detection | <100ms | ~30ms ✅ |
| 10KB Detection | <500ms | ~200ms ✅ |
| 100KB Detection | <3000ms | ~1585ms ✅ |
| Throughput | >20 KB/s | 61.4 KB/s ✅ |

## Changelog

### January 31, 2026 (Session-Persistent Indexed Placeholders)
- **NEW**: Added `PIIMappingManager` class for consistent indexed placeholders
- **NEW**: Added `pii_mapping_json` column to `ai_sessions` table
- **NEW**: Tool output (terminal commands) now scanned for PII
- **NEW**: Same PII value → same placeholder across entire session
- **NEW**: Mappings persist when resuming old sessions
- Fixed secret detection position calculation (was returning `start=0, end=0`)
- Verified all 6 functional tests passing
- Documented known limitations (generic high-entropy strings)
- Updated all phase statuses to completed

### January 26, 2026
- Initial implementation of all phases
- Database schema and models
- Presidio and detect-secrets integration
- API endpoints and frontend UI
