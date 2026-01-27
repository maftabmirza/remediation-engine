# Alembic Migration Best Practices

## Current Status
✅ **Single Head**: `5dafb466e337` (merge_multiple_heads)  
✅ **All migrations applied successfully**

## Common Commands

### Check Migration Status
```bash
# Check current version
docker exec remediation-engine python -m alembic current

# Check all heads (should be 1)
docker exec remediation-engine python -m alembic heads

# View migration history
docker exec remediation-engine python -m alembic history

# Check for branches
docker exec remediation-engine python -m alembic branches
```

### Create Migrations
```bash
# Auto-generate migration from model changes
python -m alembic revision --autogenerate -m "description"

# Create empty migration
python -m alembic revision -m "description"

# Merge multiple heads (if they exist)
python -m alembic merge -m "merge_multiple_heads" <head1> <head2>
```

### Apply Migrations
```bash
# Upgrade to latest
docker exec remediation-engine python -m alembic upgrade head

# Downgrade one version
docker exec remediation-engine python -m alembic downgrade -1

# Upgrade to specific version
docker exec remediation-engine python -m alembic upgrade <revision>
```

## Best Practices

### 1. **Always Check for Multiple Heads Before Creating New Migrations**
```bash
python -m alembic heads
```
If you see multiple heads, merge them first!

### 2. **Make Migrations Idempotent**
Always check if changes already exist:
```python
def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if column exists
    columns = [col['name'] for col in inspector.get_columns('table_name')]
    if 'new_column' not in columns:
        op.add_column('table_name', sa.Column('new_column', ...))
    
    # Check if table exists
    tables = inspector.get_table_names()
    if 'new_table' not in tables:
        op.create_table('new_table', ...)
```

### 3. **Test Migrations Locally First**
```bash
# Rebuild container with new migration
docker-compose up -d --build remediation-engine

# Check logs for migration errors
docker logs remediation-engine --tail 100 | grep -i "migration\|alembic\|error"
```

### 4. **Never Edit Applied Migrations**
Once a migration is applied (especially in production):
- ❌ Don't edit the migration file
- ✅ Create a new migration to fix issues

### 5. **Handle Schema Drift**
If the database schema doesn't match models:
```python
# In upgrade():
# 1. Check current state
from sqlalchemy import inspect
conn = op.get_bind()
inspector = inspect(conn)

# 2. Make conditional changes
columns = [col['name'] for col in inspector.get_columns('table')]
if 'column' not in columns:
    op.add_column(...)
elif columns_match_old_type:
    op.alter_column(...)
```

### 6. **Naming Convention**
Use descriptive migration names:
- ✅ `add_user_email_verification`
- ✅ `fix_agent_steps_column_types`
- ❌ `update_tables`
- ❌ `fix_stuff`

## Troubleshooting

### Multiple Heads Detected
```bash
# 1. Check which heads exist
python -m alembic heads

# 2. Create merge migration
python -m alembic merge -m "merge_heads" <head1> <head2>

# 3. Rebuild and deploy
docker-compose up -d --build remediation-engine
```

### Migration Fails: Column Already Exists
```
ProgrammingError: column "summary" already exists
```
**Solution**: Make the migration idempotent (see example above)

### Migration Stuck on Multiple Versions
```bash
# Check database state
docker exec aiops-postgres psql -U aiops -d aiops -c "SELECT * FROM alembic_version;"

# If multiple rows, manually clean up (carefully!)
docker exec aiops-postgres psql -U aiops -d aiops -c "DELETE FROM alembic_version WHERE version_num != '<keep_this_version>';"
```

### Rollback Failed Migration
```bash
# Downgrade one step
docker exec remediation-engine python -m alembic downgrade -1

# Or to specific version
docker exec remediation-engine python -m alembic downgrade <revision>
```

## Migration Workflow

### Standard Flow
1. **Pull latest code**
   ```bash
   git pull origin Demo-1.0
   ```

2. **Check migration status**
   ```bash
   python -m alembic heads  # Should show 1 head
   python -m alembic current  # Check current version
   ```

3. **Make model changes** in `app/models*.py`

4. **Generate migration**
   ```bash
   python -m alembic revision --autogenerate -m "descriptive_name"
   ```

5. **Review generated migration**
   - Check `alembic/versions/` for new file
   - Verify upgrade/downgrade logic
   - Add idempotency checks if needed

6. **Test locally**
   ```bash
   docker-compose up -d --build remediation-engine
   docker logs remediation-engine --tail 50
   ```

7. **Commit and push**
   ```bash
   git add alembic/versions/<new_migration>.py
   git commit -m "Add migration: <description>"
   git push
   ```

## Production Deployment

### Pre-Deployment Checklist
- [ ] All migrations tested locally
- [ ] Single head confirmed
- [ ] Migrations are idempotent
- [ ] Backup database before deployment
- [ ] Downgrade path tested (if needed)

### Deployment
```bash
# 1. Pull latest code on server
git pull origin Demo-1.0

# 2. Rebuild container
docker-compose up -d --build remediation-engine

# 3. Monitor logs
docker logs remediation-engine -f

# 4. Verify migration applied
docker exec remediation-engine python -m alembic current

# 5. Test application
curl http://localhost:8080/health
```

## Current Migration Tree
```
└── 5dafb466e337 (head) [merge_multiple_heads]
    ├── g6b7c8d9e0f1 [fix_agent_steps_column_types]
    │   └── f5a6b7c8d9e0 + e352288a28d6
    └── d36fe2f0aa7c [add_summary_to_alert_correlations]
        └── e352288a28d6
```

## Quick Reference: Fixed Issues

### Issue 1: Multiple Heads (RESOLVED)
- **Problem**: Two migration branches (`g6b7c8d9e0f1` and `d36fe2f0aa7c`)
- **Solution**: Created merge migration `5dafb466e337`
- **Status**: ✅ Single head now

### Issue 2: Duplicate Column Migration (RESOLVED)
- **Problem**: Migration tried to add existing `summary` column
- **Solution**: Added idempotency check in `d36fe2f0aa7c`
- **Status**: ✅ Migration now checks before adding

### Issue 3: Schema Drift (RESOLVED)
- **Problem**: Model types didn't match database
- **Solution**: Created migrations `f5a6b7c8d9e0` and `g6b7c8d9e0f1`
- **Status**: ✅ All tables aligned with models
