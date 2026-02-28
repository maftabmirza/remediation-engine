# Atlas Database Migrations - Developer Guide

## Overview

The remediation engine uses **Atlas** for declarative database schema management. Atlas is simpler and more reliable than Alembic - you define the desired schema state, and Atlas figures out the migrations.

## Migration Approach: Versioned Migrations

We use Atlas's **versioned migrations** approach:
1. Schema changes are tracked in migration files under `atlas/migrations/`
2. Each migration is applied once and tracked in `atlas_schema_revisions` table
3. Migrations run automatically on container startup

---

## Directory Structure

```
project/
├── atlas.hcl              # Atlas configuration
├── schema/
│   └── schema.sql         # Current complete schema (source of truth)
├── atlas/
│   └── migrations/        # Versioned migration files
│       ├── atlas.sum      # Migration checksums
│       └── YYYYMMDDHHMMSS_name.sql
└── entrypoint.sh          # Runs migrations on startup
```

---

## For Developers

### Making Schema Changes

**Step 1: Edit the schema file**
```sql
-- In schema/schema.sql
-- Add new column to existing table
ALTER TABLE runbooks ADD COLUMN new_field VARCHAR(100);
```

**Step 2: Generate migration (requires Atlas CLI)**
```bash
# Generate migration from schema diff
atlas migrate diff add_new_field \
  --to file://schema/schema.sql \
  --dev-url "docker://postgres/16/dev?search_path=public"
```

This creates: `atlas/migrations/YYYYMMDDHHMMSS_add_new_field.sql`

**Step 3: Review the generated migration**
```bash
cat atlas/migrations/YYYYMMDDHHMMSS_add_new_field.sql
```

**Step 4: Commit both files**
```bash
git add schema/schema.sql atlas/migrations/
git commit -m "Add new_field to runbooks"
```

---

## On Production/VM Deployment

### Fresh Database (New VM)

Container startup automatically:
1. Detects empty database
2. Applies baseline migration (20260126000000_initial_schema.sql)
3. Creates all tables

```bash
# Just start the container
docker-compose up -d

# Verify tables created
docker exec aiops-postgres psql -U aiops -d aiops -c "\dt"
```

### Existing Database

Container startup automatically:
1. Detects existing tables
2. Applies any pending migrations
3. Skips already-applied migrations

---

## Useful Atlas Commands

### Check Migration Status
```bash
# Inside container
atlas migrate status --url "$DATABASE_URL" --dir "file://atlas/migrations"
```

### Apply Migrations Manually
```bash
atlas migrate apply --url "$DATABASE_URL" --dir "file://atlas/migrations"
```

### View Pending Migrations
```bash
atlas migrate diff --to file://schema/schema.sql --dev-url "docker://postgres/16/dev"
```

### Inspect Current Database Schema
```bash
atlas schema inspect --url "$DATABASE_URL"
```

---

## Rollback (If Needed)

Atlas doesn't auto-generate rollbacks. For rollback:

1. Create a new migration that reverses the change:
```bash
atlas migrate new rollback_feature_x
```

2. Edit the migration file manually:
```sql
-- atlas/migrations/YYYYMMDDHHMMSS_rollback_feature_x.sql
ALTER TABLE runbooks DROP COLUMN new_field;
```

3. Apply the rollback migration:
```bash
atlas migrate apply --url "$DATABASE_URL" --dir "file://atlas/migrations"
```

---

## Troubleshooting

### Migration Failed on Container Start

1. Check logs:
```bash
docker logs remediation-engine 2>&1 | grep -i atlas
```

2. Connect to DB and check state:
```bash
docker exec -it aiops-postgres psql -U aiops -d aiops -c "SELECT * FROM atlas_schema_revisions"
```

3. Manual fix if needed:
```bash
docker exec -it remediation-engine atlas migrate apply --url "$DATABASE_URL" --dir "file://atlas/migrations"
```

### Schema Drift Detection

Check if database matches expected schema:
```bash
atlas schema diff \
  --from "$DATABASE_URL" \
  --to file://schema/schema.sql
```

---

## Key Differences from Alembic

| Feature | Alembic | Atlas |
|---------|---------|-------|
| Approach | Imperative (Python scripts) | Declarative (SQL) |
| Schema source | SQLAlchemy models | SQL file |
| Complexity | High (revision chains) | Low (just SQL files) |
| Rollback | Auto-generated | Manual |
| Language | Python | HCL + SQL |

---

## Configuration

Atlas config is in `atlas.hcl`:

```hcl
env "prod" {
  url = var.database_url
  src = "file://schema/schema.sql"
  migration {
    dir = "file://atlas/migrations"
  }
}
```

Environment variable: `DATABASE_URL` (same as before)

---

## Baseline Migration

The initial schema (20260126000000_initial_schema.sql) contains:
- All ~70+ tables
- PostgreSQL extensions (uuid-ossp, vector)
- Constraints, indexes, foreign keys
- Enum types

This is the baseline - all future changes are incremental migrations.
