#!/bin/bash
# Deployment script for p-aiops-01
set -e

echo "=== Starting Deployment ==="
cd /aiops

echo "=== Checking Docker ==="
docker --version
docker-compose --version

echo "=== Setting up .env file ==="
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env file created from .env.example"
else
    echo ".env file already exists"
fi

echo "=== Building and starting containers ==="
docker-compose up -d

echo "=== Waiting for containers to start ==="
sleep 10

echo "=== Checking container status ==="
docker ps | grep -E "postgres|remediation"

echo "=== Checking migration logs ==="
docker logs remediation-engine 2>&1 | grep -i alembic | tail -20

echo "=== Checking current migration version ==="
docker exec remediation-engine alembic current

echo "=== Deployment Complete ==="
