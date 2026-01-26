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
# Upgrade to the latest single head (or merge point)
python -m alembic upgrade head

# Start application
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
