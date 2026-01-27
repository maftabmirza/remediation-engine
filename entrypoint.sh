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

# Run database migrations
echo "Running database migrations..."

# Check if alembic_version table exists and has entries
# If tables exist but no alembic_version, stamp the current migration
python -c "
import os
import sys
sys.path.insert(0, '/aiops')
from sqlalchemy import create_engine, text, inspect

db_url = os.environ.get('DATABASE_URL', 'postgresql://aiops:aiops@postgres:5432/aiops')
engine = create_engine(db_url)

with engine.connect() as conn:
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    # Check if this is an existing database with tables but no alembic tracking
    has_tables = 'users' in tables or 'alerts' in tables or 'runbooks' in tables
    has_alembic = 'alembic_version' in tables
    
    if has_tables and has_alembic:
        result = conn.execute(text('SELECT version_num FROM alembic_version'))
        versions = [r[0] for r in result]
        if versions:
            print(f'ALEMBIC: Existing migrations found: {versions}')
            sys.exit(0)  # Normal upgrade path
        else:
            print('ALEMBIC: Table exists but empty, will stamp')
            sys.exit(1)  # Need to stamp
    elif has_tables and not has_alembic:
        print('ALEMBIC: Existing database without migration tracking, will stamp')
        sys.exit(1)  # Need to stamp
    else:
        print('ALEMBIC: Fresh database, will run migrations')
        sys.exit(0)  # Normal upgrade path
"
ALEMBIC_CHECK=$?

if [ "$ALEMBIC_CHECK" -eq 1 ]; then
    echo "Stamping existing database with base migration..."
    python -m alembic stamp 001_initial_base
fi

# Upgrade to the latest migration
python -m alembic upgrade head

# Start application
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
