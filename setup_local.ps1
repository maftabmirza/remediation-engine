# Local Setup Script for Remediation Engine
# This script automates the setup process for running the container locally.

Write-Host "Starting local setup..." -ForegroundColor Cyan

# 1. Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}
else {
    Write-Host ".env file already exists." -ForegroundColor Green
}

# 2. Create external network if it doesn't exist
# The docker-compose.yml expects 'aiops_aiops-network' to exist
$networkExists = docker network ls --filter name=aiops_aiops-network -q
if (-not $networkExists) {
    Write-Host "Creating Docker network 'aiops_aiops-network'..." -ForegroundColor Yellow
    docker network create aiops_aiops-network
}
else {
    Write-Host "Docker network 'aiops_aiops-network' already exists." -ForegroundColor Green
}

# 3. Build and Start Containers
Write-Host "Building and starting containers..." -ForegroundColor Cyan
docker-compose up -d --build

# 4. Wait for Postgres to be ready
Write-Host "Waiting for database to initialize (10 seconds)..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# 5. Run Migrations
Write-Host "Running database migrations..." -ForegroundColor Cyan
docker-compose exec remediation-engine python run_migrations.py

Write-Host "`nSetup Complete!" -ForegroundColor Green
Write-Host "You can access the application at: http://localhost:8080"
Write-Host "Default Admin User: admin"
Write-Host "Default Password: admin"
