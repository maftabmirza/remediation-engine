# API Credentials Refactoring - Implementation Guide

## Overview

This guide provides detailed steps to complete the refactoring that separates API credentials from server inventory. This architectural change was requested to keep external API services (Ansible AWX, Jenkins, K8s) separate from managed server inventory.

## Current Status

### ✅ Completed (Pushed to branch)

1. **Database Migration** (`migrations/004_credential_profiles.sql`)
   - Creates `api_credential_profiles` table
   - Adds `api_credential_profile_id` to `runbook_steps`

2. **Data Model** (`app/models.py`)
   - `APICredentialProfile` model with OAuth support
   - Fixed SQLAlchemy reserved keyword issue (`metadata` → `profile_metadata`)

3. **Pydantic Schemas** (`app/schemas.py`)
   - `APICredentialProfileCreate/Update/Response` schemas
   - Security-focused (tokens never exposed in responses)

4. **API Endpoints** (`app/api_credential_profiles.py`)
   - Full CRUD for credential profiles
   - Connection testing endpoint
   - Proper encryption/decryption

5. **RunbookStep Model** (`app/models_remediation.py`)
   - Added `api_credential_profile_id` foreign key
   - Added relationship to `APICredentialProfile`

6. **Executor Factory** (`app/services/executor_factory.py`)
   - `get_api_executor_from_profile()` method to create API executors from profiles

## Remaining Work

### 1. Update Runbook Executor (CRITICAL)

**File**: `app/services/runbook_executor.py`

**What to do**: Modify the step execution logic to use API credential profiles for API steps.

**Implementation**:

```python
# Around line 156, before creating the executor, add this helper method:

async def _get_executor_for_step(self, step: RunbookStep, server: ServerCredential):
    """Get the appropriate executor for the step type."""
    from ..models import APICredentialProfile

    # For API steps with credential profile
    if step.step_type == "api" and step.api_credential_profile_id:
        # Load the API credential profile
        profile = self.db.query(APICredentialProfile).filter(
            APICredentialProfile.id == step.api_credential_profile_id
        ).first()

        if not profile:
            raise ValueError(f"API credential profile {step.api_credential_profile_id} not found")

        if not profile.enabled:
            raise ValueError(f"API credential profile '{profile.name}' is disabled")

        # Create executor from profile
        return ExecutorFactory.get_api_executor_from_profile(profile, self.fernet_key)

    # For command steps or legacy API steps (using server credentials)
    else:
        return ExecutorFactory.get_executor(server, self.fernet_key)

# Then modify the execution loop (around line 158):
# BEFORE:
executor = ExecutorFactory.get_executor(server, self.fernet_key)

async with executor:
    for step in steps:
        # ... step execution logic

# AFTER:
for step in steps:
    # Get executor specific to this step
    executor = await self._get_executor_for_step(step, server)

    async with executor:
        # ... rest of step execution logic (indented one more level)
```

**Why**: This allows each API step to use its own credential profile while command steps continue using server credentials.

### 2. Register API Router in Main App

**File**: `app/main.py`

**What to do**: Import and register the API credential profiles router.

**Implementation**:

```python
# Add import at top
from app.api_credential_profiles import router as credential_profiles_router

# In the create_app() function, add:
app.include_router(credential_profiles_router)
```

**Why**: This makes the `/api/credential-profiles/*` endpoints available.

### 3. Create UI Page for API Credential Profiles

**File**: `templates/credential_profiles.html` (NEW FILE)

**What to do**: Create a dedicated page for managing API credential profiles, separate from the server inventory.

**Template Structure**:
```html
{% extends "layout.html" %}
{% set active_page = 'credential-profiles' %}

<!-- Page with:
  1. List of credential profiles (table/cards)
  2. Create/Edit modal
  3. Test connection button
  4. Delete confirmation
-->
```

**Key Features**:
- Display profile name, base URL, auth type, status
- Create/Edit form with all fields from `APICredentialProfileCreate` schema
- Test connection button (calls `/api/credential-profiles/{id}/test`)
- Enable/disable toggle
- Delete with confirmation
- Search/filter

**Styling**: Follow the same design patterns as `settings.html`

### 4. Update Runbook Form UI

**File**: `templates/runbook_form.html`

**What to do**: For API steps, add a dropdown to select the credential profile.

**Implementation**:

```html
<!-- In the API Configuration section (around line 674), ADD THIS after step type selector: -->

<div class="mb-4" id="${stepId}-api-profile" style="${stepData?.step_type === 'api' ? '' : 'display:none'}">
    <label class="block text-secondary text-xs mb-1">
        API Credential Profile <span class="text-red-400">*</span>
    </label>
    <select class="step-api-profile input-field w-full px-3 py-2 rounded text-sm">
        <option value="">-- Select API Credential Profile --</option>
        <!-- Populated via JavaScript from /api/credential-profiles -->
    </select>
    <p class="text-xs text-secondary mt-1">
        Base URL and auth configured in the selected profile
    </p>
</div>

<!-- JavaScript to load profiles -->
<script>
let apiProfiles = [];

async function loadApiProfiles() {
    try {
        const response = await fetch('/api/credential-profiles?enabled_only=true');
        if (response.ok) {
            apiProfiles = await response.json();
            // Update all API profile dropdowns
            updateApiProfileDropdowns();
        }
    } catch (error) {
        console.error('Error loading API profiles:', error);
    }
}

function updateApiProfileDropdowns() {
    document.querySelectorAll('.step-api-profile').forEach(select => {
        const currentValue = select.value;
        select.innerHTML = '<option value="">-- Select API Credential Profile --</option>';
        apiProfiles.forEach(profile => {
            const option = document.createElement('option');
            option.value = profile.id;
            option.textContent = `${profile.name} (${profile.base_url})`;
            if (profile.id === currentValue) option.selected = true;
            select.appendChild(option);
        });
    });
}

// Call on page load
document.addEventListener('DOMContentLoaded', async function() {
    await loadApiProfiles();
    // ... existing initialization
});

// Update collectFormData() to include api_credential_profile_id:
// In the "Add API-specific fields" section (around line 900):
stepData.api_credential_profile_id = stepEl.querySelector('.step-api-profile')?.value || null;
</script>
```

**Why**: Users need to select which credential profile an API step should use.

### 5. Remove API Protocol from Server Credentials UI

**File**: `templates/settings.html`

**What to do**: Remove the "API / REST" option from the protocol dropdown.

**Implementation**:

```html
<!-- REMOVE this line (around line 648): -->
<option value="api">API / REST</option>

<!-- Keep only: -->
<option value="ssh">SSH (Linux/Windows)</option>
<option value="winrm">WinRM (Windows)</option>

<!-- Also REMOVE the entire apiConfigSection div (lines ~673-746) -->
```

**JavaScript Changes**:
```javascript
// Remove API-related code from toggleProtocolFields()
// Remove API field handling from form submission
// Remove API fields from showEditServerModal()
```

**Why**: API credentials are now managed separately in the Credential Profiles section.

### 6. Update Navigation Menu

**File**: `templates/layout.html` (or wherever the nav menu is)

**What to do**: Add a new menu item for "Credential Profiles" under Settings.

**Implementation**:

```html
<!-- In the settings section of nav menu: -->
<a href="/credential-profiles" class="nav-link {% if active_page == 'credential-profiles' %}active{% endif %}">
    <i class="fas fa-key"></i>
    <span>Credential Profiles</span>
</a>
```

**Route**: Add route in `app/routes.py`:
```python
@app.get("/credential-profiles", response_class=HTMLResponse)
async def credential_profiles_page(request: Request):
    return templates.TemplateResponse("credential_profiles.html", {"request": request})
```

### 7. Run Database Migration

**Command**:
```bash
# Connect to your PostgreSQL database
psql -U your_user -d your_database -f migrations/004_credential_profiles.sql
```

**Verify**:
```sql
-- Check table exists
\d api_credential_profiles

-- Check foreign key added
\d runbook_steps
-- Should see: api_credential_profile_id | uuid |
```

**Rollback** (if needed):
```sql
DROP TABLE IF EXISTS api_credential_profiles CASCADE;
ALTER TABLE runbook_steps DROP COLUMN IF EXISTS api_credential_profile_id;
```

### 8. Testing Checklist

1. **Migration**:
   - [ ] Run migration successfully
   - [ ] Verify tables created
   - [ ] Check indexes exist

2. **API Endpoints**:
   - [ ] Create credential profile via POST /api/credential-profiles
   - [ ] List profiles via GET /api/credential-profiles
   - [ ] Update profile via PUT /api/credential-profiles/{id}
   - [ ] Test connection via POST /api/credential-profiles/{id}/test
   - [ ] Delete profile via DELETE /api/credential-profiles/{id}

3. **Runbook Creation**:
   - [ ] Create runbook with API step
   - [ ] Select credential profile from dropdown
   - [ ] Save runbook successfully
   - [ ] Verify api_credential_profile_id is saved

4. **Execution**:
   - [ ] Execute runbook with API step using credential profile
   - [ ] Verify correct API endpoint is called
   - [ ] Verify authentication works
   - [ ] Check step execution logs

5. **UI**:
   - [ ] Credential profiles page displays correctly
   - [ ] Create/Edit modal works
   - [ ] Server settings no longer shows API option
   - [ ] Runbook form shows credential profile dropdown for API steps

## Migration Strategy

### For Existing API Steps

If you have existing runbooks using the old server-based API configuration:

1. **Create migration script** to move existing API server credentials to credential profiles:

```python
# migration_script.py
from app.database import SessionLocal
from app.models import ServerCredential, APICredentialProfile
from app.models_remediation import RunbookStep

db = SessionLocal()

# Find all servers with protocol='api'
api_servers = db.query(ServerCredential).filter(
    ServerCredential.protocol == 'api'
).all()

for server in api_servers:
    # Create corresponding credential profile
    profile = APICredentialProfile(
        name=server.name,
        description=f"Migrated from server: {server.hostname}",
        base_url=server.api_base_url,
        auth_type=server.api_auth_type,
        auth_header=server.api_auth_header,
        token_encrypted=server.api_token_encrypted,
        username=server.username,
        verify_ssl=server.api_verify_ssl,
        timeout_seconds=server.api_timeout_seconds,
        default_headers=server.api_headers_json or {},
        profile_metadata=server.api_metadata_json or {},
        enabled=True
    )
    db.add(profile)
    db.flush()

    # Update runbook steps that reference this server
    # (This requires knowing which steps use which servers - may need manual mapping)

db.commit()
db.close()
```

2. **Gradual rollout**:
   - Keep backward compatibility (allow steps without credential_profile_id to use server credentials)
   - Migrate runbooks one at a time
   - Remove old API servers once all runbooks are migrated

## Architecture Diagram

```
BEFORE:
┌─────────────────┐
│ server_credentials │ (Mixed: SSH servers + API endpoints)
└─────────────────┘
        ↓
   ┌────────┐
   │ runbooks │
   └────────┘

AFTER:
┌─────────────────┐     ┌──────────────────────────┐
│ server_credentials │     │ api_credential_profiles │
│ (SSH/WinRM only)  │     │ (API endpoints only)     │
└─────────────────┘     └──────────────────────────┘
        ↓                          ↓
        └────────┬─────────────────┘
               ┌────────┐
               │ runbooks │
               └────────┘
```

## Benefits of This Architecture

1. **Clear Separation**: Server inventory vs external API services
2. **Reusability**: One credential profile used by multiple runbooks
3. **Security**: Centralized credential management
4. **Flexibility**: Easy to add new auth types (OAuth, mTLS, etc.)
5. **Better UX**: Clear distinction in UI between servers and API credentials

## Support

If you encounter issues:
1. Check application logs for detailed error messages
2. Verify migration ran successfully
3. Test API endpoints individually using curl/Postman
4. Check database for data integrity

## Example Usage

### Creating an AWX Credential Profile

```bash
curl -X POST http://localhost:8000/api/credential-profiles \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production AWX",
    "description": "Ansible AWX production instance",
    "base_url": "https://awx.example.com/api/v2",
    "auth_type": "bearer",
    "token": "your-awx-token-here",
    "verify_ssl": true,
    "timeout_seconds": 30,
    "default_headers": {
      "Content-Type": "application/json"
    }
  }'
```

### Using in Runbook

When creating a runbook step:
1. Set `step_type` = "api"
2. Set `api_credential_profile_id` = UUID of the profile
3. Set `api_endpoint` = "/job_templates/123/launch/"
4. Set `api_method` = "POST"
5. Set `api_body` = '{"extra_vars": {"target": "{{ server.hostname }}"}}'

The executor will automatically use the base URL and auth from the profile!

## Files Modified Summary

- ✅ `migrations/004_credential_profiles.sql` - Database schema
- ✅ `app/models.py` - APICredentialProfile model
- ✅ `app/schemas.py` - Pydantic schemas
- ✅ `app/api_credential_profiles.py` - API endpoints
- ✅ `app/models_remediation.py` - RunbookStep updates
- ✅ `app/services/executor_factory.py` - Profile-based executor creation
- ⏳ `app/services/runbook_executor.py` - Use profiles in execution
- ⏳ `app/main.py` - Register router
- ⏳ `templates/credential_profiles.html` - New UI page
- ⏳ `templates/runbook_form.html` - Profile selector
- ⏳ `templates/settings.html` - Remove API fields

**Legend**: ✅ Done | ⏳ Pending

---

**Last Updated**: Current date
**Status**: Phase 2 - Backend Complete, UI Pending
