#!/bin/bash
# Deployment script for Alert Clustering feature
# Run on server: 172.234.217.11
# User: aftab

set -e  # Exit on error

echo "========================================="
echo "Alert Clustering Deployment Script"
echo "========================================="
echo ""

# Navigate to project directory
cd /home/aftab/aiops-platform

echo "✓ Current directory: $(pwd)"
echo ""

# Fetch latest changes
echo "📥 Fetching latest changes from remote..."
git fetch origin

# Checkout feature branch
echo "🔀 Switching to feature/alert-clustering branch..."
git checkout feature/alert-clustering

# Pull latest changes
echo "⬇️  Pulling latest changes..."
git pull origin feature/alert-clustering

echo ""
echo "✓ Code updated successfully"
echo ""

# Show current commit
echo "📝 Current commit:"
git log --oneline -1
echo ""

# Run database migration
echo "🗄️  Running database migration..."
docker exec remediation-engine python -m alembic upgrade head

echo ""
echo "✓ Migration completed"
echo ""

# Verify migration
echo "🔍 Verifying alert_clusters table..."
docker exec remediation-engine psql -U postgres -d aiops -c "\d alert_clusters" | head -20

echo ""
echo "🔍 Verifying alerts table clustering columns..."
docker exec remediation-engine psql -U postgres -d aiops -c "\d alerts" | grep cluster

echo ""
echo "✓ Database schema verified"
echo ""

# Restart container
echo "🔄 Restarting remediation-engine container..."
docker-compose restart remediation-engine

echo ""
echo "⏳ Waiting for container to start..."
sleep 10

# Check container status
echo "📊 Container status:"
docker ps | grep remediation-engine

echo ""

# Check logs for clustering jobs
echo "📋 Checking logs for clustering job registration..."
docker logs remediation-engine 2>&1 | grep -i "clustering" | tail -10

echo ""
echo "========================================="
echo "✅ Deployment Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Check logs: docker logs -f remediation-engine"
echo "2. Test API: curl http://172.234.217.11:8080/api/clusters/stats/overview"
echo "3. Access Swagger UI: http://172.234.217.11:8080/docs"
echo ""
