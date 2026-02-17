#!/bin/bash
# Simple deployment script for p-aiops-01 (execute ON the server)

set -e

APP_DIR="/aiops"
BRANCH="ui-1.0"
REPO_URL="https://github.com/maftabmirza/remediation-engine.git"

echo "========================================="
echo "AIOps Deployment to /aiops"
echo "========================================="
echo ""

echo "Step 1: Prepare Deployment Directory"
echo "-------------------------------------"

if [ -d "$APP_DIR" ]; then
    echo "Directory $APP_DIR exists. Checking if it's a git repository..."
    
    if [ -d "$APP_DIR/.git" ]; then
        echo "✓ Git repository found. Updating..."
        cd $APP_DIR
        
        git stash
        git fetch --all
        echo "Checking out branch: $BRANCH..."
        git checkout $BRANCH
        git pull origin $BRANCH
    else
        echo "Directory exists but is not a git repository."
        echo "Backing up and cloning fresh..."
        mv $APP_DIR ${APP_DIR}_backup_$(date +%Y%m%d_%H%M%S)
        
        git clone $REPO_URL $APP_DIR
        cd $APP_DIR
        git checkout $BRANCH
    fi
else
    echo "Directory does not exist. Creating and cloning..."
    git clone $REPO_URL $APP_DIR
    cd $APP_DIR
    git checkout $BRANCH
fi

echo ""
echo "Current directory: $(pwd)"
echo "Current branch: $(git branch --show-current)"
echo "Latest commit: $(git log -1 --oneline)"
echo ""

echo "Step 2: Atlas Migration Pre-checks"
echo "-----------------------------------"

cd $APP_DIR

if [ ! -d "atlas/migrations" ]; then
    echo "⚠️  WARNING: atlas/migrations directory not found!"
else
    echo "✓ Atlas migrations directory found"
    echo "Migration files:"
    ls -lh atlas/migrations/ 2>/dev/null | head -10 || echo "  (none)"
fi

if [ ! -f "schema/schema.sql" ]; then
    echo "⚠️  WARNING: schema/schema.sql not found!"
else
    echo "✓ Schema file found: schema/schema.sql"
    echo "  Size: $(ls -lh schema/schema.sql | awk '{print $5}')"
fi

if [ ! -f "atlas.hcl" ]; then
    echo "⚠️  WARNING: atlas.hcl not found!"
else
    echo "✓ Atlas configuration found: atlas.hcl"
fi

if [ -f "entrypoint.sh" ]; then
    if grep -q "atlas" entrypoint.sh; then
        echo "✓ entrypoint.sh contains Atlas migration logic"
    else
        echo "⚠️  WARNING: entrypoint.sh may not run Atlas migrations"
    fi
else
    echo "⚠️  WARNING: entrypoint.sh not found"
fi

echo ""
echo "Step 3: Docker Environment Check"
echo "---------------------------------"

if command -v docker &> /dev/null; then
    echo "✓ Docker: $(docker --version)"
    if docker ps > /dev/null 2>&1; then
        echo "✓ Docker daemon is running"
    else
        echo "❌ Docker daemon is not running!"
        exit 1
    fi
else
    echo "❌ Docker is not installed!"
    exit 1
fi

if command -v docker-compose &> /dev/null; then
    echo "✓ Docker Compose: $(docker-compose --version)"
elif docker compose version &> /dev/null; then
    echo "✓ Docker Compose v2: $(docker compose version)"
    alias docker-compose='docker compose'
else
    echo "❌ Docker Compose is not available!"
    exit 1
fi

echo ""
echo "Step 4: Environment Configuration"
echo "----------------------------------"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  IMPORTANT: Review .env file for production settings!"
    else
        echo "❌ Neither .env nor .env.example found!"
        exit 1
    fi
else
    echo "✓ .env file exists"
fi

if grep -q "TESTING=true" .env 2>/dev/null; then
    echo "❌ ERROR: TESTING=true in .env - must be false for production!"
    exit 1
else
    echo "✓ TESTING not set to true"
fi

echo ""
echo "Step 5: Stop Existing Containers"
echo "---------------------------------"

if docker-compose ps 2>/dev/null | grep -q "Up"; then
    echo "Stopping existing containers..."
    docker-compose down
else
    echo "No running containers found"
fi

echo ""
echo "Step 6: Build and Start Containers"
echo "-----------------------------------"

echo "Building containers (this may take a few minutes)..."
docker-compose build --no-cache

echo ""
echo "Starting containers..."
docker-compose up -d

echo ""
echo "Waiting for containers to initialize..."
sleep 10

echo ""
echo "Step 7: Verify Deployment"
echo "-------------------------"

echo "Container status:"
docker-compose ps

echo ""
echo "Recent logs (checking for errors):"
docker-compose logs remediation-engine --tail 30

echo ""
echo "Step 8: Atlas Migration Status"
echo "-------------------------------"

echo "Checking for Atlas migration logs..."
docker-compose logs remediation-engine | grep -i "atlas\|migration" | tail -10 || echo "No Atlas logs found yet"

echo ""
echo "========================================="
echo "✅ Deployment Complete!"
echo "========================================="
echo ""
echo "Application deployed to: $APP_DIR"
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git log -1 --oneline)"
echo ""
echo "Next steps:"
echo "  1. Check logs: docker-compose logs -f remediation-engine"
echo "  2. Verify migrations: docker-compose exec remediation-engine atlas migrate status --url \"\$DATABASE_URL\" --dir \"file://atlas/migrations\""
echo "  3. Test application endpoints"
echo ""
