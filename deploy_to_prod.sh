#!/bin/bash
# Deploy with Environment Configuration Script
# This script deploys to p-aiops-01 and sets up required environment variables

set -e

SERVER="ubuntu@15.204.244.73"
APP_DIR="/aiops"

echo "============================================"
echo "Deploying to p-aiops-01 with Env Setup"
echo "============================================"
echo ""

# Step 1: Pull latest code
echo "Step 1: Pulling latest code..."
ssh $SERVER "cd $APP_DIR && git pull origin claude/review-grafana-docs-Xr3H8"
echo ""

# Step 2: Check if .env exists
echo "Step 2: Checking .env configuration..."
ENV_EXISTS=$(ssh $SERVER "[ -f $APP_DIR/.env ] && echo 'yes' || echo 'no'")

if [ "$ENV_EXISTS" = "no" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    ssh $SERVER "cd $APP_DIR && cp .env.example .env"
    
    echo ""
    echo "Generating required secrets on server..."
    
    # Generate ENCRYPTION_KEY
    ENCRYPTION_KEY=$(ssh $SERVER "python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
    ssh $SERVER "cd $APP_DIR && sed -i 's|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|' .env"
    echo "✓ Generated ENCRYPTION_KEY"
    
    # Generate JWT_SECRET
    JWT_SECRET=$(ssh $SERVER "openssl rand -hex 32")
    ssh $SERVER "cd $APP_DIR && sed -i 's|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|' .env"
    echo "✓ Generated JWT_SECRET"
    
    # Generate POSTGRES_PASSWORD
    POSTGRES_PASSWORD=$(ssh $SERVER "openssl rand -base64 32 | tr -d '=+/' | cut -c1-32")
    ssh $SERVER "cd $APP_DIR && sed -i 's|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|' .env"
    echo "✓ Generated POSTGRES_PASSWORD"
    
    echo ""
    echo "✓ .env file configured with generated secrets"
else
    echo "✓ .env file already exists"
    
    # Validate existing .env has required variables
    echo "Validating existing .env..."
    MISSING_VARS=$(ssh $SERVER "cd $APP_DIR && grep -E '^(ENCRYPTION_KEY|JWT_SECRET|POSTGRES_PASSWORD)=$' .env | cut -d= -f1" || echo "")
    
    if [ -n "$MISSING_VARS" ]; then
        echo "⚠️  Warning: The following variables are empty in .env:"
        echo "$MISSING_VARS"
        echo ""
        echo "Generate and set them with:"
        echo "  ENCRYPTION_KEY: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        echo "  JWT_SECRET: openssl rand -hex 32"
        echo "  POSTGRES_PASSWORD: openssl rand -base64 32"
        echo ""
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Deployment cancelled."
            exit 1
        fi
    fi
fi
echo ""

# Step 3: Rebuild and restart containers
echo "Step 3: Rebuilding containers..."
ssh $SERVER "cd $APP_DIR && docker compose build --no-cache remediation-engine"
echo ""

echo "Step 4: Restarting services..."
ssh $SERVER "cd $APP_DIR && docker compose up -d"
echo ""

# Step 5: Wait for services to be healthy
echo "Step 5: Waiting for services to start..."
sleep 15

# Step 6: Check container status
echo "Step 6: Checking container status..."
ssh $SERVER "cd $APP_DIR && docker ps | grep remediation-engine"
echo ""

# Step 7: Check logs for validation
echo "Step 7: Checking startup logs..."
ssh $SERVER "docker logs remediation-engine --tail=30 | grep -A 5 'Environment Validation'" || echo "⚠️  Check logs manually if validation failed"
echo ""

echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Access UI: http://15.204.244.73:8080"
echo "  2. Test API: /tmp/verify_and_setup.sh"
echo "  3. Check logs: docker logs remediation-engine"
echo ""
