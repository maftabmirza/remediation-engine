# PII Detection - LLM Integration Fix

## Current Issue

**The PII detection service is NOT integrated with LLM requests** - email addresses and other PII pass through to the LLM without any scanning or redaction.

## Root Cause

The PII detection infrastructure exists but is **never initialized**:

1. ✅ PII Service exists at [app/services/pii_service.py](../app/services/pii_service.py)
2. ✅ LLM Service has PII scanning code at [app/services/llm_service.py](../app/services/llm_service.py#L234-L269)
3. ❌ **PII Service is never injected** - `set_pii_service()` is never called during app startup
4. ❌ `_pii_service` remains `None`, so the check `if _pii_service and analysis:` always fails

### Code Evidence

**LLM Service (lines 234-269):**
```python
# Scan and redact PII/secrets from LLM response if service is available
if _pii_service and analysis:  # ❌ _pii_service is None
    try:
        detection_response = await _pii_service.detect(
            text=analysis,
            source_type="llm_response",
            source_id=f"{provider.id}_{int(time.time())}"
        )
        # ... redaction logic
```

**Module-level variable (line 21):**
```python
_pii_service = None  # ❌ Never initialized!
```

**Initialization function exists but is never called:**
```python
def set_pii_service(pii_service):
    """Set the PII service instance for LLM output scanning."""
    global _pii_service
    _pii_service = pii_service
```

## Solution

Initialize PII service during app startup and inject it into the LLM service.

### Implementation Steps

**1. Add PII service initialization to app startup** ([app/main.py](../app/main.py) lifespan function):

```python
# After starting background workers, before scheduler
if not settings.testing:
    # ... existing code ...
    
    # Initialize PII service for LLM scanning
    logger.info("Initializing PII detection for LLM scanning...")
    try:
        from app.database import get_async_db
        from app.services.pii_service import PIIService
        from app.services.presidio_service import PresidioService
        from app.services.secret_detection_service import SecretDetectionService
        from app.services import llm_service
        
        # Get a database session
        async for db in get_async_db():
            presidio = PresidioService()
            secrets = SecretDetectionService()
            pii_service = PIIService(db, presidio, secrets)
            
            # Inject into LLM service
            llm_service.set_pii_service(pii_service)
            logger.info("✅ PII detection enabled for LLM requests")
            break
    except Exception as e:
        logger.error(f"Failed to initialize PII service: {e}")
        # Don't fail startup, but log the issue
```

**2. Handle async database properly:**

The current implementation uses `AsyncSession` for PII service, but the lifespan context may need a persistent connection. Consider:

- Creating a module-level async session for PII scanning
- OR: Creating PII service per-request (less efficient but cleaner)
- OR: Using sync database session for PII service

**Recommended approach:** Use a sync database session for PII service during initialization:

```python
# In app/main.py lifespan()
from app.database import SessionLocal  # Sync session
from app.services.pii_service import PIIService

# Create sync version or modify PIIService to accept sync session
db_sync = SessionLocal()
pii_service = PIIService(db_sync, presidio, secrets)
llm_service.set_pii_service(pii_service)
```

## Testing

After implementation, verify:

1. **PII service initialization:**
   ```bash
   # Check logs on startup for:
   "Initializing PII detection for LLM scanning..."
   "✅ PII detection enabled for LLM requests"
   ```

2. **LLM request scanning:**
   ```bash
   # Send a prompt with an email to the AI chat
   # Check logs for:
   "Detected X PII/secret(s) in LLM response from [provider]"
   ```

3. **Database logging:**
   ```sql
   SELECT * FROM pii_detection_logs 
   WHERE source_type = 'llm_response' 
   ORDER BY detected_at DESC LIMIT 10;
   ```

4. **API endpoint test:**
   ```bash
   # Test the PII detection endpoint directly
   curl -X POST http://localhost:8080/api/v1/pii/detect \
     -H "Content-Type: application/json" \
     -d '{"text": "Contact me at magn@ghlk.com", "source_type": "test"}'
   ```

## Expected Behavior After Fix

### Before Fix (Current)
- ❌ Email addresses pass through to LLM
- ❌ No PII detection logs
- ❌ No redaction of sensitive data
- ❌ `_pii_service` is `None`

### After Fix
- ✅ All LLM responses scanned for PII
- ✅ Detections logged to `pii_detection_logs` table
- ✅ Sensitive data redacted with tags (e.g., `<EMAIL_ADDRESS>`)
- ✅ Available in PII logs UI at `/pii-detection`

## Alternative: Per-Request PII Service

If persistent PII service is problematic, use per-request injection:

```python
# In app/services/llm_service.py
async def generate_completion(
    db: Session,
    prompt: str,
    provider: Optional[LLMProvider] = None,
    json_mode: bool = False,
    pii_service: Optional[PIIService] = None  # Add parameter
) -> Tuple[str, LLMProvider]:
    # ... existing code ...
    
    # Use provided PII service instead of global
    if pii_service and analysis:
        detection_response = await pii_service.detect(...)
```

Then pass PII service from routers that use LLM service.

## Files to Modify

1. [app/main.py](../app/main.py) - Add PII service initialization in `lifespan()`
2. Potentially [app/services/pii_service.py](../app/services/pii_service.py) - Make compatible with sync sessions
3. Test files to verify integration

## Related Documentation

- [PII Detection Implementation Plan](./PII_SECRET_DETECTION_IMPLEMENTATION_PLAN.md)
- [PII Detection API](./PII_DETECTION_API.md)
- [PII Detection User Guide](./PII_DETECTION_USER_GUIDE.md)
