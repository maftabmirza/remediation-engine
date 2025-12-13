# Deploy updated code to server and restart
$SERVER = "aftab@172.234.217.11"
$APP_DIR = "/home/aftab/aiops-platform"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Deploying Alert Trigger Fix to Server" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[Step 1] Connecting to server and pulling latest code..." -ForegroundColor Yellow

# Execute commands on remote server
ssh $SERVER @"
cd $APP_DIR
echo 'Current directory: '`$(pwd)
echo ''
echo '[Step 2] Pulling latest code from git...'
git pull origin codex/suggest-improvements-for-dashboard-ux
echo ''
echo '[Step 3] Stopping existing container...'
docker-compose stop remediation-engine
echo ''
echo '[Step 4] Rebuilding and starting container...'
docker-compose up --build -d remediation-engine
echo ''
echo '[Step 5] Waiting for container to start (10 seconds)...'
sleep 10
echo ''
echo '[Step 6] Container status:'
docker ps | grep remediation-engine
echo ''
echo '[Step 7] Recent logs:'
docker logs remediation-engine --tail 50
"@

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Check logs above for any errors" -ForegroundColor White
Write-Host "2. Fire test alert: python fire_test_alert.py" -ForegroundColor White
Write-Host "3. Monitor execution: python monitor_alert_processing.py" -ForegroundColor White
Write-Host ""
