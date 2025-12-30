# Dry Run Implementation - Code Review

## Overview

The dry run functionality in the remediation engine allows you to **validate runbook execution WITHOUT actually running commands** on target servers. This is critical for testing and validation.

## How Dry Run Works

### 1. **Request Level** (Line 308 in schemas_remediation.py)

```python
class ExecuteRunbookRequest(BaseModel):
    dry_run: bool = False  # Test execution without running commands
```

When you execute a runbook via API, you can pass `dry_run: true` to enable dry run mode.

### 2. **Execution Record** (Line 247 in models_remediation.py)

```python
class RunbookExecution(Base):
    dry_run = Column(Boolean, default=False)
```

The dry_run flag is stored in the execution record, so you can see which executions were dry runs.

### 3. **Critical Implementation** (Lines 698-708 in runbook_executor.py)

This is **THE KEY PART** - where actual command execution is skipped:

```python
if execution.dry_run:
    # Dry run - don't actually execute
    return ExecutionResult(
        success=True,
        exit_code=0,
        stdout="[DRY RUN] Command would be executed",
        stderr="",
        duration_ms=0,
        command=command,
        server_hostname=executor.hostname
    )
```

**What happens:**
- ✅ Command is rendered with template variables
- ✅ Server connection is validated
- ✅ Steps are validated
- ✅ Execution records are created
- ❌ **Commands are NOT executed on the server**
- ✅ A fake successful result is returned

### 4. **Rollback Protection** (Line 291)

```python
if completed_steps and not execution.dry_run:
    await self._execute_rollback(...)
```

Rollback commands are **also skipped** in dry run mode to prevent any changes.

## Dry Run Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User triggers runbook with dry_run=True                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. RunbookExecution record created with dry_run=True            │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. For each step:                                                │
│    - Template variables are rendered                             │
│    - OS compatibility is checked                                 │
│    - Command is prepared                                         │
│    - StepExecution record is created                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Check: if execution.dry_run == True:                         │
│    ✅ Return fake success result                                 │
│    ✅ stdout = "[DRY RUN] Command would be executed"             │
│    ✅ exit_code = 0 (success)                                    │
│    ✅ duration_ms = 0                                            │
│    ❌ SKIP actual command execution                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Step marked as successful without execution                  │
│    - step_exec.status = "success"                                │
│    - step_exec.stdout = "[DRY RUN] Command would be executed"   │
│    - NO actual changes on the server                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. All steps complete successfully                               │
│    - execution.status = "success"                                │
│    - Rollback is SKIPPED (dry run check on line 291)            │
└─────────────────────────────────────────────────────────────────┘
```

## Alternative: `execute_dry_run()` Method

There's also a separate method for dry run validation (Lines 323-407):

```python
async def execute_dry_run(
    self,
    runbook: Runbook,
    server: ServerCredential,
    alert_context: Optional[Dict[str, Any]] = None,
    variables: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
```

**This method provides more detailed validation:**
- ✅ Validates each step without creating execution records
- ✅ Renders all templates
- ✅ Checks for unresolved variables
- ✅ Tests server connectivity
- ✅ Returns detailed validation report:
  ```python
  {
      "valid": bool,
      "steps": [...],      # List of steps with rendered commands
      "errors": [...],     # Validation errors
      "warnings": [...]    # Warnings (unresolved vars, etc.)
  }
  ```

## Key Differences

| Feature | `execution.dry_run=True` | `execute_dry_run()` |
|---------|-------------------------|---------------------|
| **Creates execution record** | ✅ Yes | ❌ No |
| **Creates step executions** | ✅ Yes | ❌ No |
| **Visible in UI** | ✅ Yes (as dry run) | ❌ No |
| **Tests connectivity** | ✅ Yes | ✅ Yes |
| **Template rendering** | ✅ Yes | ✅ Yes |
| **Validates variables** | ⚠️ Basic | ✅ Advanced |
| **Returns detailed report** | ❌ No | ✅ Yes |
| **Use case** | Execute with tracking | Pre-flight validation |

## Status Indicators

### In Execution Records
```python
# Line 247 in models_remediation.py
dry_run = Column(Boolean, default=False)
```

### In Step Executions
```python
# Dry run steps show in stdout:
step_exec.stdout = "[DRY RUN] Command would be executed"
```

### In API Responses
```python
# schemas_remediation.py
class RunbookExecutionResponse(BaseModel):
    dry_run: bool  # Line 363
    
class ExecutionListResponse(BaseModel):
    dry_run: bool  # Line 403
```

## Safety Mechanisms

### 1. **No Command Execution**
```python
if execution.dry_run:
    return ExecutionResult(success=True, ...)  # No execution!
```

### 2. **No Rollback**
```python
if completed_steps and not execution.dry_run:  # Skip rollback
    await self._execute_rollback(...)
```

### 3. **No Actual Changes**
- Commands are prepared but never sent to executor
- Server receives no commands
- No files are modified
- No services are restarted
- No processes are killed

## Testing Dry Run

### Via API
```bash
curl -X POST "http://172.234.217.11:8080/api/remediation/runbooks/{id}/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "uuid-here",
    "dry_run": true    # THIS ENABLES DRY RUN
  }'
```

### Via Python Script
```python
# In create_test_runbooks.py
runbook_data = {
    "server_id": server_id,
    "dry_run": True,  # Enable dry run
    "variables": {}
}
```

### Result
```json
{
  "id": "execution-uuid",
  "dry_run": true,
  "status": "success",
  "steps_total": 5,
  "steps_completed": 5,
  "step_executions": [
    {
      "step_name": "Check Apache Status",
      "stdout": "[DRY RUN] Command would be executed",
      "exit_code": 0,
      "duration_ms": 0
    }
  ]
}
```

## Template Rendering in Dry Run

**Important:** Templates ARE rendered in dry run mode!

```python
# Line 208 - Template rendering happens BEFORE dry run check
rendered_command = self._render_template(command, context)
step_exec.command_executed = rendered_command  # Stored in DB

# Line 698 - THEN dry run check happens
if execution.dry_run:
    return fake_success_result()  # No execution
```

This means:
- ✅ You can see what commands WOULD be executed
- ✅ Template variables are substituted
- ✅ Jinja2 errors are caught
- ✅ Command validation happens
- ❌ Commands are never sent to the server

## Benefits of Dry Run

1. **Safety Testing**
   - Test new runbooks without risk
   - Validate commands before production use

2. **Template Validation**
   - Ensure variables are correctly substituted
   - Catch template errors early

3. **Debugging**
   - See exact commands that would run
   - Understand execution flow

4. **Approval Preview**
   - Show what will be executed before approval
   - Give approvers confidence

5. **Integration Testing**
   - Test runbook flow without affecting systems
   - Validate step ordering and logic

## Code Location Summary

| Feature | File | Line | Description |
|---------|------|------|-------------|
| Dry run flag (request) | `schemas_remediation.py` | 308 | Request schema |
| Dry run flag (model) | `models_remediation.py` | 247 | Database model |
| **Main dry run logic** | `runbook_executor.py` | **698-708** | **Where execution is skipped** |
| Dry run validation method | `runbook_executor.py` | 323-407 | Detailed validation |
| Rollback skip | `runbook_executor.py` | 291 | Prevents rollback |
| Context building | `runbook_executor.py` | 558-561 | Adds dry_run to context |

## Conclusion

The dry run implementation is **simple but effective**:

1. ✅ Flag is set at request time
2. ✅ Stored in execution record
3. ✅ All preparation happens normally (templates, validation, etc.)
4. ✅ **At execution time (line 698), if dry_run=True, return fake success**
5. ✅ No commands actually run
6. ✅ All records show "[DRY RUN]" in output

This allows complete testing of runbook logic without any risk to target systems!
