# Alembic Database Migrations - Developer Guide

## Overview

The remediation engine now uses **Alembic** for automatic database schema management. Migrations run automatically on application startup.

## Current State (January 2026)

**All migrations have been consolidated into a single base migration:**
- `001_initial_base_schema.py` - Contains the complete current database schema

This was done to fix deployment issues on new VMs where accumulated migrations were causing conflicts.

## What Changed

### ✅ Auto-run on Startup
Every time the Docker container starts, Alembic automatically:
1. Checks current database schema version
2. Applies any pending migrations
3. Logs success/failure

**You don't need to run migrations manually!**

### ⚠️ Fresh Database Deployment
For new VM deployments, the single base migration will create all tables from scratch. No need for historical migration files.

### ✅ Auto-generation from Models
When you change SQLAlchemy models, Alembic can auto-generate migration files.

---

## For Developers

### Making Schema Changes

**Step 1: Modify the model**
```python
# In app/models_remediation.py
class Runbook(Base):
    # Add new field
    new_field = Column(String(100), nullable=True)
```

**Step 2: Generate migration (inside Docker container)**
```bash
# On development machine
docker exec -it remediation-engine alembic revision --autogenerate -m "Add new_field to runbooks"
```

This creates: `alembic/versions/XXX_add_new_field_to_runbooks.py`

**Step 3: Review the generated migration**
```bash
# Check what Alembic detected
cat alembic/versions/XXX_add_new_field_to_runbooks.py
```

**Step 4: Apply migration**
```bash
# Manual apply (or just restart container for auto-run)
docker exec -it remediation-engine alembic upgrade head
```

**Step 5: Commit migration file to git**
```bash
git add alembic/versions/XXX_add_new_field_to_runbooks.py
git commit -m "Add migration for new_field"
```

---

## On Production Server

### Deployment Process

1. **Pull latest code**
   ```bash
   git pull origin main
   ```

2. **Restart container**
   ```bash
   docker-compose restart remediation-engine
   ```

3. **Migrations run automatically!**
   ```bash
   # Check logs to confirm
   docker logs remediation-engine | grep -i alembic
   # Should see: "✅ Database migrations completed successfully"
   ```

---

## Useful Commands

### Check Current Schema Version
```bash
docker exec -it remediation-engine alembic current
```

### View Migration History
```bash
docker exec -it remediation-engine alembic history
```

### Manually Upgrade to Latest
```bash
docker exec -it remediation-engine alembic upgrade head
```

### Downgrade One Version (Rollback)
```bash
docker exec -it remediation-engine alembic downgrade -1
```

### Create Empty Migration (Manual SQL)
```bash
docker exec -it remediation-engine alembic revision -m "custom migration"
```

---

## Migration File Structure

```
alembic/
├── env.py                    # Alembic environment config
├── script.py.mako           # Migration template
└── versions/                # Migration files
    ├── 004_add_scheduler.py
    └── 005_add_runbook_version.py  # Auto-generated
```

---

## Troubleshooting

### "Alembic not found" Error
- Alembic runs inside Docker, not on host
- Use: `docker exec -it remediation-engine alembic ...`

### Migration Conflicts
If multiple developers create migrations:
```bash
# Merge migrations
docker exec -it remediation-engine alembic merge heads -m "merge migrations"
```

### Reset to Clean State
```bash
# WARNING: Deletes all data!
docker exec -it aiops-postgres psql -U aiops -d aiops -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker-compose restart remediation-engine
# Alembic will recreate from scratch
```

### Check What Alembic Will Do
```bash
# Dry run (show SQL without executing)
docker exec -it remediation-engine alembic upgrade head --sql
```

---

## Why Alembic?

**Before:**
- ❌ Manual SQL migration files
- ❌ No auto-generation
- ❌ Manual execution required
- ❌ Schema drift between environments

**After:**
- ✅ Auto-generated from model changes
- ✅ Automatic application on startup
- ✅ Version control in database
- ✅ Consistent schema everywhere

---

## Migration Best Practices

1. **Always review auto-generated migrations** - Alembic isn't perfect
2. **Test migrations in development first** - Before deploying to production
3. **Keep migrations small** - One logical change per migration
4. **Never edit applied migrations** - Create a new migration instead
5. **Commit migrations with code changes** - Keep schema and code in sync

---

## Configuration Files

### alembic.ini
- Database connection config
- Logging configuration

### alembic/env.py
- Imports all models
- Connects to database
- Runs migrations

### alembic/script.py.mako
- Template for new migration files

---

## See Also

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Models](app/models_remediation.py)
- [Database Configuration](app/database.py)
