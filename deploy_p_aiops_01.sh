#!/bin/bash
# Deploy AIOps Remediation Engine to p-aiops-01 server
# Deploys to /aiops directory with ui-1.0 branch

set -e  # Exit on any error

echo "========================================="
echo "Deploying AIOps to p-aiops-01"
echo "========================================="
echo ""

# Server details
SERVER="root@p-aiops-01"
APP_DIR="/aiops"
BRANCH="ui-1.0"
REPO_URL="${REPO_URL:-https://github.com/maftabmirza/remediation-engine.git}"

echo "Target Server: $SERVER"
echo "Deployment Directory: $APP_DIR"
echo "Branch: $BRANCH"
echo ""

# Deploy via SSH
ssh $SERVER << ENDSSH
set -e

echo "========================================="
echo "Step 1: Prepare Deployment Directory"
echo "========================================="

# Check if directory exists
if [ -d "$APP_DIR" ]; then
    echo "Directory $APP_DIR exists. Checking if it's a git repository..."
    
    if [ -d "$APP_DIR/.git" ]; then
        echo "Git repository found. Updating existing deployment..."
        cd $APP_DIR
        
        # Stash any local changes
        echo "Stashing local changes (if any)..."
        git stash
        
        # Fetch latest
        echo "Fetching latest from remote..."
        git fetch --all
        
        # Checkout the target branch
        echo "Checking out branch: $BRANCH..."
        git checkout $BRANCH
        
        # Pull latest changes
        echo "Pulling latest changes..."
        git pull origin $BRANCH
    else
        echo "Directory exists but is not a git repository."
        echo "Backing up existing directory..."
        mv $APP_DIR ${APP_DIR}_backup_\$(date +%Y%m%d_%H%M%S)
        
        echo "Cloning fresh repository..."
        git clone $REPO_URL $APP_DIR
        cd $APP_DIR
        git checkout $BRANCH
    fi
else
    echo "Directory does not exist. Creating and cloning..."
    mkdir -p $APP_DIR
    git clone $REPO_URL $APP_DIR
    cd $APP_DIR
    git checkout $BRANCH
fi

echo ""
echo "Current directory: \$(pwd)"
echo "Current branch: \$(git branch --show-current)"
echo "Latest commit: \$(git log -1 --oneline)"
echo ""

echo "========================================="
echo "Step 2: Atlas Migration Pre-checks"
echo "========================================="

# Check if Atlas migrations directory exists
if [ ! -d "atlas/migrations" ]; then
    echo "⚠️  WARNING: atlas/migrations directory not found!"
    echo "Atlas migrations may not be configured properly."
else
    echo "✓ Atlas migrations directory found"
    echo "Migration files:"
    ls -lh atlas/migrations/ | head -10
fi

# Check if schema file exists
if [ ! -f "schema/schema.sql" ]; then
    echo "⚠️  WARNING: schema/schema.sql not found!"
    echo "Schema file is missing - Atlas migrations may fail."
else
    echo "✓ Schema file found: schema/schema.sql"
fi

# Check if atlas.hcl exists
if [ ! -f "atlas.hcl" ]; then
    echo "⚠️  WARNING: atlas.hcl not found!"
    echo "Atlas configuration is missing."
else
    echo "✓ Atlas configuration found: atlas.hcl"
fi

# Check if entrypoint.sh has Atlas migration logic
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
echo "========================================="
echo "Step 3: Check Docker and Docker Compose"
echo "========================================="

# Check Docker
if command -v docker &> /dev/null; then
    echo "✓ Docker installed: \$(docker --version)"
    docker ps > /dev/null 2>&1
    if [ \$? -eq 0 ]; then
        echo "✓ Docker daemon is running"
    else
        echo "❌ Docker daemon is not running!"
        echo "Starting Docker..."
        systemctl start docker
    fi
else
    echo "❌ Docker is not installed!"
    exit 1
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    echo "✓ Docker Compose installed: \$(docker-compose --version)"
elif docker compose version &> /dev/null; then
    echo "✓ Docker Compose (v2) available: \$(docker compose version)"
else
    echo "❌ Docker Compose is not available!"
    exit 1
fi

echo ""
echo "========================================="
echo "Step 4: Environment Configuration"
echo "========================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  IMPORTANT: Review and update .env file with production values!"
        echo ""
        echo "Key settings to review:"
        echo "  - TESTING=false (must be false for production)"
        echo "  - DEBUG=false"
        echo "  - Database credentials"
        echo "  - JWT_SECRET"
        echo "  - ENCRYPTION_KEY"
        echo ""
    else
        echo "❌ Neither .env nor .env.example found!"
        exit 1
    fi
else
    echo "✓ .env file exists"
fi

# Verify critical environment settings
echo "Checking critical environment variables..."
if grep -q "TESTING=true" .env; then
    echo "❌ ERROR: TESTING=true in .env - must be false for production!"
    echo "Please update .env and re-run deployment."
    exit 1
else
    echo "✓ TESTING not set to true"
fi

echo ""
echo "========================================="
echo "Step 5: Stop Existing Containers"
echo "========================================="

# Stop existing containers
if docker-compose ps | grep -q "Up"; then
    echo "Stopping existing containers..."
    docker-compose down
else
    echo "No running containers found"
fi

echo ""
echo "========================================="
echo "Step 6: Build and Start Containers"
echo "========================================="

echo "Building containers..."
docker-compose build --no-cache

echo ""
echo "Starting containers..."
docker-compose up -d

echo ""
echo "Waiting for containers to be healthy..."
sleep 10

echo ""
echo "========================================="
echo "Step 7: Verify Deployment"
echo "========================================="

echo "Container status:"
docker-compose ps

echo ""
echo "Checking remediation-engine logs for errors..."
docker-compose logs remediation-engine --tail 50 | grep -i "error\|exception\|failed" || echo "No errors found in recent logs"

echo ""
echo "Checking for successful startup..."
docker-compose logs remediation-engine --tail 20

echo ""
echo "========================================="
echo "Step 8: Atlas Migration Status"
echo "========================================="

echo "Checking if migrations were applied..."
docker-compose logs remediation-engine | grep -i "atlas\|migration" || echo "No Atlas migration logs found"

ENDSSH

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Verify application is accessible"
echo "2. Check logs: ssh $SERVER 'cd $APP_DIR && docker-compose logs -f remediation-engine'"
echo "3. Verify database migrations: ssh $SERVER 'cd $APP_DIR && docker-compose exec remediation-engine atlas migrate status --url \"\$DATABASE_URL\" --dir \"file://atlas/migrations\"'"
echo ""
echo "If Atlas migrations failed:"
echo "  - Check atlas/migrations directory exists"
echo "  - Verify schema/schema.sql is present"
echo "  - Review entrypoint.sh for Atlas migration logic"
echo "  - Check database connectivity"
echo ""
