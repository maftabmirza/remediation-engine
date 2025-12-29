#!/bin/bash
set -e


# Run pre-flight checks
echo "Running pre-flight checks..."
python app/check_deps.py

# Run database migrations
echo "Running database migrations..."
python -m alembic upgrade head

# Start application
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
