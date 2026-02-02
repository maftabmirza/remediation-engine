# PII False Positive Feedback System - Implementation Guide

## Overview

This feature allows users to report false positive PII/secret detections and automatically whitelist them to prevent future false detections. The system includes UI highlighting, user feedback collection, whitelist management, and admin review capabilities.

## Components Implemented

### 1. Database Layer ✅
- **Migration**: `atlas/migrations/20260201000000_add_pii_false_positive_feedback.sql`
- **Schema**: Updated `schema/schema.sql` with new table definition
- **Model**: `app/models/pii_models.py::PIIFalsePositiveFeedback`
- **Indexes**: Optimized for whitelist lookups and feedback queries

### 2. Schemas ✅
- **File**: `app/schemas/pii_schemas.py`
- **Added Schemas**:
  - `FalsePositiveFeedbackRequest` - Submit feedback
  - `FalsePositiveFeedbackResponse` - Feedback confirmation
  - `FalsePositiveFeedbackDetail` - Full feedback details
  - `WhitelistEntry` - Whitelist item
  - `WhitelistResponse` - List of whitelisted items
  - `PIIHighlightInfo` - UI highlighting metadata

### 3. Services ✅
- **Whitelist Service**: `app/services/pii_whitelist_service.py`
  - Submit false positive feedback
  - Check if text is whitelisted
  - Get whitelist entries
  - Admin review workflow
  - In-memory cache (5min TTL)

- **Updated PII Service**: `app/services/pii_service.py`
  - Integrated whitelist filtering
  - Filters detections against whitelist before logging

### 4. API Endpoints ✅
- **Router**: `app/routers/pii_feedback.py`
- **Endpoints**:
  - `POST /api/v1/pii/feedback/false-positive` - Submit feedback
  - `GET /api/v1/pii/feedback/whitelist` - Get whitelist
  - `GET /api/v1/pii/feedback/reports` - List feedback
  - `PUT /api/v1/pii/feedback/{id}/whitelist` - Update status (admin)
  - `DELETE /api/v1/pii/feedback/{id}` - Delete entry (admin)

## Deployment Steps

### Step 1: Run Database Migration (Atlas)

This project uses **Atlas** for database migrations, not Alembic.

```bash
# Option 1: Using Atlas CLI directly
atlas migrate apply \
  --env prod \
  --url "postgres://user:pass@localhost:5432/remediation_db?sslmode=disable"

# Option 2: Apply specific migration
psql -h localhost -U remediation_user -d remediation_db \
  -f atlas/migrations/20260201000000_add_pii_false_positive_feedback.sql

# Verify table creation
psql -h localhost -U remediation_user -d remediation_db -c "\d pii_false_positive_feedback"
```

### Step 2: Update Application

```bash
# Restart the application to load new code
docker-compose restart app

# Or if running locally
python -m uvicorn app.main:app --reload
```

### Step 3: Verify API Endpoints

```bash
# Check API docs
open http://localhost:8080/docs

# Look for "PII Feedback" section with new endpoints
```

## How It Works

### User Flow

1. **User interacts with agent** (Alert/RE-VIVE/Troubleshoot)
2. **System detects PII** in message
3. **Response includes PII metadata** with highlighting info
4. **Frontend highlights PII** with visual indicator
5. **User clicks "Not PII"** button/tooltip
6. **Feedback submitted** to API
7. **System whitelists** the text
8. **Future detections skipped** for that text

### Technical Flow

```
User Message → PII Detection → Check Whitelist → Filter Results → Agent Processing
                                      ↓
                                (Skip if whitelisted)
```

### Whitelist Check

```python
# Before detection
detected_items = await pii_service.detect(text)

# Whitelist filtering happens inside detect()
# Returns only non-whitelisted items
```

### Cache Strategy

- **TTL**: 5 minutes
- **Invalidation**: On new feedback submission
- **Structure**: `{scope}:{entity_type}` → Set[text]
- **Max Size**: 10,000 entries

## Frontend Integration (TODO)

### Step 1: Response Format

Agents should return PII metadata:

```json
{
  "response": "Contact john@example.com for help",
  "session_id": "...",
  "pii_detections": [
    {
      "text": "john@example.com",
      "entity_type": "EMAIL_ADDRESS",
      "start_pos": 8,
      "end_pos": 24,
      "confidence": 0.95,
      "can_report": true,
      "detection_id": "uuid"
    }
  ]
}
```

### Step 2: Highlighting

```jsx
// Example React component
function HighlightedText({ text, detections }) {
  return (
    <span>
      {renderWithHighlights(text, detections)}
    </span>
  );
}

function PII Tooltip({ detection, onMarkAsFalsePositive }) {
  return (
    <Tooltip>
      <div>Type: {detection.entity_type}</div>
      <button onClick={() => onMarkAsFalsePositive(detection)}>
        Not PII
      </button>
    </Tooltip>
  );
}
```

### Step 3: Submit Feedback

```javascript
async function markAsFalsePositive(detection) {
  const response = await fetch('/api/v1/pii/feedback/false-positive', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      detected_text: detection.text,
      detected_entity_type: detection.entity_type,
      detection_engine: detection.engine || 'presidio',
      session_id: currentSessionId,
      agent_mode: 'alert', // or 'revive', 'troubleshoot'
      detection_log_id: detection.detection_id
    })
  });
  
  if (response.ok) {
    // Remove highlighting immediately
    removeHighlight(detection);
    showToast('Feedback submitted. This text will no longer be flagged.');
  }
}
```

## Agent Integration

### Update Response Format

Each agent needs to return PII highlight information:

```python
# In agent's run() or run_streaming() method
async def run_streaming(self, user_message: str):
    # ... existing logic ...
    
    # Add PII detection metadata
    pii_detections = await self._extract_pii_metadata(response_text)
    
    # Yield final response with metadata
    yield json.dumps({
        "response": response_text,
        "pii_detections": pii_detections
    })

async def _extract_pii_metadata(self, text: str) -> List[dict]:
    """Extract PII positions for highlighting"""
    if not self.pii_mapping_manager:
        return []
    
    detections = []
    for mapping in self.pii_mapping_manager.get_all_mappings():
        # Find position of placeholder in response
        placeholder = mapping['placeholder']
        original = mapping['original_value']
        
        # Note: You may need to track original positions
        # This is simplified - actual implementation depends on your redaction strategy
        if placeholder in text:
            start = text.index(placeholder)
            detections.append({
                "text": original,
                "entity_type": mapping['entity_type'],
                "start_pos": start,
                "end_pos": start + len(placeholder),
                "confidence": mapping.get('confidence', 1.0),
                "can_report": True
            })
    
    return detections
```

## Testing

### Test False Positive Submission

```bash
# 1. Login and get token
TOKEN=$(curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

# 2. Submit false positive feedback
curl -X POST http://localhost:8080/api/v1/pii/feedback/false-positive \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "detected_text": "test-server-01",
    "detected_entity_type": "IP_ADDRESS",
    "detection_engine": "presidio",
    "session_id": "test-session",
    "agent_mode": "troubleshoot",
    "user_comment": "This is a server hostname, not an IP"
  }'

# 3. Verify in whitelist
curl -X GET http://localhost:8080/api/v1/pii/feedback/whitelist \
  -H "Authorization: Bearer $TOKEN"

# 4. Test detection with whitelisted item
curl -X POST http://localhost:8080/api/v1/pii/detect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Server test-server-01 is down",
    "source_type": "test"
  }'
# Should return 0 detections (filtered by whitelist)
```

### Test Admin Functions

```bash
# Get all feedback reports
curl -X GET "http://localhost:8080/api/v1/pii/feedback/reports?page=1&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Update whitelist status (disable)
curl -X PUT http://localhost:8080/api/v1/pii/feedback/{feedback_id}/whitelist \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "whitelisted": false,
    "review_notes": "Actually is PII, reverting"
  }'
```

## Configuration

### Environment Variables

Add to `.env` if needed:

```bash
# PII Feedback Settings
PII_FEEDBACK_ENABLED=true
PII_FEEDBACK_AUTO_APPROVE=true
PII_WHITELIST_SCOPE=organization
PII_WHITELIST_CACHE_TTL=300
PII_FEEDBACK_RATE_LIMIT=50
```

### Feature Flags

Configure in application:

```python
PII_FEEDBACK_CONFIG = {
    "enabled": True,
    "require_admin_approval": False,
    "whitelist_scope": "organization",
    "cache_ttl": 300,
    "max_feedback_per_user_per_day": 50,
}
```

## Admin Dashboard (TODO)

### Metrics to Display

1. **False Positive Rate**
   - Total detections vs false positive reports
   - By entity type
   - By detection engine

2. **Whitelist Size**
   - Total whitelisted items
   - Growth over time
   - Most reported types

3. **User Activity**
   - Top reporters
   - Feedback submission trends
   - Average reports per user

4. **Review Queue**
   - Pending reviews (if approval enabled)
   - Average review time
   - Approve/reject ratio

### SQL Queries for Metrics

```sql
-- False positive rate by entity type
SELECT 
    detected_entity_type,
    COUNT(*) as false_positives,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM pii_detection_logs), 2) as percentage
FROM pii_false_positive_feedback
WHERE whitelisted = true
GROUP BY detected_entity_type
ORDER BY false_positives DESC;

-- Recent feedback activity
SELECT 
    DATE_TRUNC('day', reported_at) as date,
    COUNT(*) as submissions,
    COUNT(DISTINCT user_id) as unique_users
FROM pii_false_positive_feedback
WHERE reported_at > NOW() - INTERVAL '30 days'
GROUP BY date
ORDER BY date DESC;

-- Top reporters
SELECT 
    u.username,
    COUNT(f.id) as feedback_count,
    COUNT(CASE WHEN f.review_status = 'approved' THEN 1 END) as approved,
    COUNT(CASE WHEN f.review_status = 'rejected' THEN 1 END) as rejected
FROM pii_false_positive_feedback f
JOIN users u ON u.id = f.user_id
GROUP BY u.username
ORDER BY feedback_count DESC
LIMIT 10;
```

## Security Considerations

### Rate Limiting

Add rate limiting to prevent abuse:

```python
from fastapi_limiter.depends import RateLimiter

@router.post("/false-positive", dependencies=[Depends(RateLimiter(times=50, hours=24))])
async def submit_false_positive_feedback(...):
    # ... implementation ...
```

### Validation

- Limit text length (500 chars)
- Validate entity types against known list
- Sanitize user comments
- Prevent duplicate submissions

### Audit Trail

All actions are logged:
- Who reported false positive
- When it was reported
- Original detection details
- Admin reviews and changes

## Monitoring

### Metrics to Track

1. **Feedback submission rate**
2. **Whitelist cache hit rate**
3. **Detection reduction after whitelisting**
4. **API response times**
5. **Cache memory usage**

### Alerts

Set up alerts for:
- High false positive rate (>20%)
- Whitelist size exceeding threshold
- Cache performance degradation
- Unusual feedback patterns

## Future Enhancements

1. **Pattern-Based Whitelisting**
   - Whitelist all emails from `@company.com`
   - Whitelist IP ranges
   - Regex patterns

2. **Machine Learning**
   - Learn from feedback to improve detection
   - Suggest auto-whitelist candidates
   - Confidence score adjustment

3. **User-Specific Whitelist**
   - Personal whitelist per user
   - Team-level whitelists
   - Hierarchical scopes

4. **Bulk Operations**
   - Import whitelist from CSV
   - Export for backup
   - Bulk approve/reject

5. **Integration**
   - Slack notifications for admin review
   - Webhook on new feedback
   - Analytics dashboard

## Rollback Plan

If issues arise:

1. **Disable feature flag**
   ```python
   PII_FEEDBACK_CONFIG["enabled"] = False
   ```

2. **Revert migration**
   ```sql
   DROP TABLE pii_false_positive_feedback CASCADE;
   ```

3. **Remove router**
   ```python
   # Comment out in main.py
   # app.include_router(pii_feedback.router)
   ```

## Support

- Review implementation plan: `session-state/plan.md`
- Check API documentation: `/docs#/PII%20Feedback`
- Database schema: `migrations/008_add_pii_false_positive_feedback.sql`
- Service code: `app/services/pii_whitelist_service.py`
