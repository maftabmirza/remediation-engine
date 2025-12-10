# Database Schema Management - Current vs Ideal

## Your Question
> Why do we need to update keys on database manually? Doesn't the Docker build check the target database schema?

**Short Answer:** The application has migrations but doesn't run them automatically on startup. When code models change, the database schema doesn't update automatically.

---

## Current System

### What Exists ✅
1. **Migration Files** (`migrations/*.sql`)
   ```
   002_auto_remediation.sql
   003_api_execution.sql
   007_add_scheduler_tables.sql
   ```

2. **Migration Runner** (`run_migrations.py`)
   - Reads SQL files
   - Executes them with idempotency
   - Handles "already exists" errors

### What's Missing ❌
1. **Auto-run on startup** - Migrations must be run manually
2. **Auto-generation** - Schema changes require manual SQL files
3. **Version tracking** - No database table tracking applied migrations

---

## What Happens Now

### Code Change Flow (Current)
```
Developer changes model:
  app/models_remediation.py
    + runbook_version = Column(Integer, nullable=False)
    ↓
Docker rebuild
    ↓
Container starts
    ↓
❌ Database schema NOT updated!
    ↓
Runtime error: Column 'runbook_version' doesn't exist
    ↓
Manual fix required:
  ALTER TABLE runbook_executions ADD COLUMN runbook_version...
```

### Why Manual Updates Were Needed

When we added `runbook_version` to the model:
1. Code changed ✅
2. Docker image rebuilt ✅  
3. Container restarted ✅
4. **Database schema unchanged** ❌

Result: Runtime errors because database doesn't match code.

---

## Ideal System (Production Best Practice)

### Option 1: Auto-Run Existing Migrations

**Add to `app/main.py` startup:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting AIOps Platform...")
    
    # RUN MIGRATIONS FIRST
    logger.info("Running database migrations...")
    from run_migrations import run_migrations
    run_migrations()
    
    init_db()  # Then init default data
    # ... rest of startup
```

**Benefits:**
- ✅ Automatic on every startup
- ✅ Idempotent (safe to run multiple times)
- ✅ No manual intervention needed

**Drawbacks:**
- ❌ Still requires manual SQL file creation
- ❌ No auto-generation from models

---

### Option 2: Use Alembic (Better)

**Full migration framework:**

1. **Auto-generate migrations:**
   ```bash
   alembic revision --autogenerate -m "Add runbook_version"
   ```
   This creates: `alembic/versions/abc123_add_runbook_version.py`

2. **Auto-run on startup:**
   ```python
   from alembic import command
   from alembic.config import Config
   
   alembic_cfg = Config("alembic.ini")
   command.upgrade(alembic_cfg, "head")
   ```

3. **Version tracking:**
   Database table `alembic_version` tracks applied migrations

**Benefits:**
- ✅ Auto-generation from model changes
- ✅ Version control
- ✅ Up/down migrations (rollback support)
- ✅ Team collaboration (no schema conflicts)

---

## Why Docker Build Doesn't Handle This

**Docker builds the application, not the database schema.**

```
Docker Build Process:
  1. Copy code
  2. Install dependencies
  3. Create image
  ❌ Does NOT touch database
```

**Database is external to the container:**
```
[Docker Container: remediation-engine]
        ↓ connects to
[Separate Container: aiops-postgres]
        ↓ persists to
[Volume: database files]
```

The database schema must be updated **at runtime**, not build time.

---

## Recommended Fix

### Immediate (Quick Fix)
Add migration auto-run to startup in `app/main.py`:

```python
async def lifespan(app: FastAPI):
    logger.info("Starting AIOps Platform...")
    
    # Auto-run migrations
    try:
        from run_migrations import run_migrations
        run_migrations()
        logger.info("Migrations completed")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    
    init_db()
    # ... rest
```

### Long-term (Best Practice)
1. **Set up Alembic** properly
2. **Auto-generate** migrations when models change
3. **Auto-apply** on container startup
4. **Track versions** in database

---

## For This Project

### What We Did
✅ Fixed bugs in code
✅ Manually updated schema with SQL
✅ System works perfectly now

### What Should Be Added
🔄 Auto-run migrations on startup
🔄 Document: "Run migrations before code changes"
🔄 Consider switching to Alembic for auto-generation

### Migration File for runbook_version

**Should have been:**
```sql
-- migrations/008_add_runbook_version.sql

ALTER TABLE runbook_executions 
ADD COLUMN IF NOT EXISTS runbook_version INTEGER NOT NULL DEFAULT 1;
```

Then on next startup: automatic!

---

## Summary

**Your observation is 100% correct!** 

The system **should** automatically ensure database schema matches code. Currently it doesn't because:

1. Migrations exist but aren't auto-run
2. New migrations aren't auto-generated from model changes
3. Docker builds code, not database schema

**Fix:** Add migration auto-run to startup lifecycle.

**Best practice:** Use Alembic for full migration management.
