# Troubleshooting GPT/OpenAI Provider Issues

## Issue: GPT Provider Fails with Anthropic Authentication Error

### Symptoms
- You've configured an OpenAI/GPT provider in Settings > LLM Providers
- Test connection works successfully  
- When using /troubleshoot and selecting the GPT provider, you get:
  ```
  Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}}
  ```
- The error references Anthropic API even though GPT is selected
- Anthropic provider works correctly

### Root Causes

This issue can occur due to several reasons:

#### 1. **Wrong Provider Type in Database**
The provider entry in the database might have `provider_type` set incorrectly (e.g., "anthropic" instead of "openai").

#### 2. **Case Sensitivity or Whitespace Issues**
The provider_type field might have extra whitespace or incorrect capitalization.

#### 3. **Session Provider Not Switched Properly**
The session might still be using a cached/old provider ID even after switching.

#### 4. **API Key Not Properly Configured**
The OpenAI API key might not be correctly stored or accessible.

---

## Diagnostic Steps

### Step 1: Check Provider Configuration

Run the diagnostic script:
```powershell
cd d:\remediation-engine-vscode
python check_llm_providers.py
```

This will show:
- All providers in the database
- Their types, models, and enabled status
- Whether they have encrypted keys or use environment variables
- Any configuration issues

### Step 2: Check Docker Logs

If running in Docker, check the engine logs:
```powershell
docker-compose logs -f engine --tail=100
```

Look for lines like:
```
_call_llm: provider_type='openai', model=gpt-4, has_api_key=True
Using session's stored provider: GPT-4 (type=openai, model=gpt-4)
```

If you see `provider_type='anthropic'` when GPT is selected, the database has wrong data.

### Step 3: Verify Session Provider Switch

After switching providers in the UI:
1. Check browser DevTools > Network tab
2. Look for `PATCH /api/troubleshoot/sessions/{session_id}/provider`
3. Verify the response shows the correct provider

---

## Solutions

### Solution 1: Update Provider Type in Database

If the provider has the wrong `provider_type` value:

```python
# fix_provider_type.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import SessionLocal
from app.models import LLMProvider

db = SessionLocal()
try:
    # Find the problematic provider
    provider = db.query(LLMProvider).filter(
        LLMProvider.name.ilike('%gpt%')  # Adjust filter as needed
    ).first()
    
    if provider:
        print(f"Current provider_type: {provider.provider_type}")
        provider.provider_type = "openai"  # Fix it
        db.commit()
        print("Fixed!")
    else:
        print("Provider not found")
finally:
    db.close()
```

### Solution 2: Clear Session and Re-select Provider

1. In the /troubleshoot UI, clear the chat history
2. Refresh the page (F5)
3. Select the GPT provider again from the dropdown
4. Start a new conversation

### Solution 3: Update Environment Variables

Ensure both API keys are set in `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...
```

Then restart the application:
```powershell
docker-compose down
docker-compose up -d
```

### Solution 4: Recreate the Provider

If the provider is corrupted:

1. Go to Settings > LLM Providers
2. **Delete** the problematic GPT provider
3. Click "Add Provider"
4. Fill in:
   - **Name**: GPT-4
   - **Provider Type**: openai
   - **Model ID**: gpt-4 (or gpt-4-turbo-preview, gpt-3.5-turbo, etc.)
   - **API Key**: Your OpenAI API key
5. Click "Test Connection" - should succeed
6. Click "Save"
7. Make it default if desired

### Solution 5: Check Model ID Format

OpenAI model IDs should NOT have a prefix:
- ✅ Correct: `gpt-4`
- ✅ Correct: `gpt-4-turbo-preview`
- ✅ Correct: `gpt-3.5-turbo`
- ❌ Wrong: `openai/gpt-4`

If your model ID has a prefix, update it:
1. Settings > LLM Providers
2. Edit the GPT provider
3. Change Model ID to remove the prefix
4. Save

---

## Verification

After applying fixes:

1. Go to /troubleshoot
2. Select the GPT provider from dropdown
3. Send a test message: "Say hello"
4. Check logs for:
   ```
   _call_llm: provider_type='openai', model=gpt-4, has_api_key=True
   ```
5. Verify you get a response (not an error)

---

## Additional Notes

### Why Anthropic Works But OpenAI Doesn't

The code has special handling for Anthropic to work around LiteLLM bugs:
```python
# For Anthropic, use direct SDK
if provider_type == "anthropic" and api_key:
    return await self._call_anthropic_directly(api_key)
```

For OpenAI, it uses LiteLLM's `acompletion()` function, which is more sensitive to:
- Model ID format
- API key format/validity
- Provider type configuration

### Logging Improvements

The latest code includes enhanced logging to help diagnose these issues:
- Provider type, model, and API key presence are logged
- Session provider selection is logged  
- Direct Anthropic SDK usage is logged

Check logs after each troubleshoot request to see which provider is actually being used.

---

## Still Having Issues?

1. **Check API Key Validity**: Test your OpenAI API key at https://platform.openai.com/api-keys
2. **Check API Quota**: Ensure you have credits/quota available
3. **Check Model Access**: Some models require special access (e.g., GPT-4)
4. **Review Full Logs**: The full stacktrace might reveal additional issues

For more help, review:
- [DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md)
- [LLM Provider Documentation](LLM_PROVIDER_GUIDE.md)
