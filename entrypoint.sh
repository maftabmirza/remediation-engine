#!/bin/sh
set -e


# Run pre-flight checks
echo "Running pre-flight checks..."
MAX_ATTEMPTS=${PREFLIGHT_MAX_ATTEMPTS:-30}
SLEEP_SECONDS=${PREFLIGHT_SLEEP_SECONDS:-2}

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
	set +e
	python app/check_deps.py
	rc=$?
	set -e

	if [ "$rc" -eq 0 ]; then
		break
	fi

	echo "Pre-flight checks failed (attempt ${attempt}/${MAX_ATTEMPTS}). Retrying in ${SLEEP_SECONDS}s..."
	attempt=$((attempt + 1))
	sleep "$SLEEP_SECONDS"
done

if [ "$attempt" -gt "$MAX_ATTEMPTS" ]; then
	echo "Pre-flight checks failed after ${MAX_ATTEMPTS} attempts."
	exit 1
fi

# Run database migrations with Atlas
echo "Running database migrations with Atlas..."

# Check if this is a fresh database or existing
set +e
python -c "
import os
import sys
from sqlalchemy import create_engine, inspect, text

db_url = os.environ.get('DATABASE_URL', 'postgresql://aiops:aiops@postgres:5432/aiops')
engine = create_engine(db_url)

with engine.connect() as conn:
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    # Check if main tables exist
    has_tables = 'users' in tables or 'alerts' in tables or 'runbooks' in tables
    
    # Check if Atlas tracking table exists
    has_atlas = 'atlas_schema_revisions' in tables
    
    if has_tables and has_atlas:
        print('ATLAS: Existing database with Atlas tracking')
        sys.exit(0)  # Existing DB with Atlas
    elif has_tables and not has_atlas:
        print('ATLAS: Existing database without Atlas tracking (baseline needed)')
        sys.exit(2)  # Existing DB needs baseline
    else:
        print('ATLAS: Fresh database detected')
        sys.exit(1)  # Fresh DB
"
DB_CHECK=$?
set -e

if [ "$DB_CHECK" -eq 1 ]; then
    echo "Fresh database - applying initial schema directly..."
    # Apply the full initial schema SQL using Python/psycopg2 (psql not available in container)
    python3 - <<'PYEOF'
import os, psycopg2, sys
db_url = os.environ.get('DATABASE_URL', 'postgresql://aiops:aiops@postgres:5432/aiops')
schema_file = '/app/atlas/migrations/20260126000000_initial_schema.sql'
try:
    with open(schema_file, 'r', encoding='utf-8-sig') as f:
        sql = f.read()
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    cur.close()
    conn.close()
    print('Initial schema applied successfully')
except Exception as e:
    print(f'Error applying initial schema: {e}', file=sys.stderr)
    sys.exit(1)
PYEOF
    # The initial schema dump already includes objects from migrations up to 20260131000000.
    # Set Atlas baseline to that version so only newer migrations are applied.
    echo "Setting Atlas baseline to 20260131000000 (included in initial schema dump)..."
    atlas migrate set --url "$DATABASE_URL" --dir "file://atlas/migrations" "20260131000000" 2>&1 || {
        echo "Warning: Atlas baseline set failed"
    }
    echo "Applying remaining migrations..."
    atlas migrate apply --url "$DATABASE_URL" --dir "file://atlas/migrations" 2>&1 || true
elif [ "$DB_CHECK" -eq 2 ]; then
    echo "Existing database needs Atlas baseline..."
    # Mark the initial migration as applied (baseline) without actually running it
    atlas migrate set --url "$DATABASE_URL" --dir "file://atlas/migrations" "20260126000000" 2>&1 || {
        echo "Warning: Atlas baseline set failed, database may already be configured"
    }
    echo "Applying any pending migrations..."
    atlas migrate apply --url "$DATABASE_URL" --dir "file://atlas/migrations" 2>&1 || true
else
    echo "Existing database - applying pending migrations..."
    # For existing DB, apply any pending migrations
    atlas migrate apply --url "$DATABASE_URL" --dir "file://atlas/migrations" 2>&1 || true
fi

echo "Database migrations complete."

# Start application
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
