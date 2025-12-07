#!/bin/bash
set -e

echo "Starting automated fix deployment..."

echo "[1/4] Pulling latest changes..."
git pull

echo "[2/4] Rebuilding remediation-engine container..."
docker compose up -d --build remediation-engine

echo "[3/4] Running database migrations..."
# Wait a moment for container to be ready
sleep 2
docker compose exec -T remediation-engine python3 run_migrations.py

echo "[4/4] Restarting service..."
docker compose restart remediation-engine

echo "Deployment complete! Application should be healthy."
