# Deploy Scenario 4 Scripts to Remote Server
# This script copies the DB failure simulation scripts to t-aiops-01

$SERVER = "ubuntu@15.204.233.209"
$SCRIPTS = @(
    "accel_tmp_simulate_db_failure.sh",
    "accel_tmp_restore_db_access.sh"
)

Write-Host "`n=== Deploying Scenario 4 Scripts ===" -ForegroundColor Cyan
Write-Host "Target: $SERVER`n" -ForegroundColor Cyan

foreach ($script in $SCRIPTS) {
    if (Test-Path $script) {
        Write-Host "Copying $script..." -ForegroundColor Yellow
        scp $script "${SERVER}:~/"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ $script deployed successfully" -ForegroundColor Green
        } else {
            Write-Host "  ✗ Failed to deploy $script" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "  ✗ $script not found in current directory" -ForegroundColor Red
        exit 1
    }
}

# Make scripts executable
Write-Host "`nMaking scripts executable..." -ForegroundColor Yellow
ssh $SERVER "chmod +x ~/accel_tmp_simulate_db_failure.sh ~/accel_tmp_restore_db_access.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Scripts are now executable" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to set executable permissions" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Green
Write-Host "`nYou can now run:" -ForegroundColor Cyan
Write-Host "  python test_scenario4_db_failure.py" -ForegroundColor White
Write-Host "`nOr manually:" -ForegroundColor Cyan
Write-Host "  ssh $SERVER '~/accel_tmp_simulate_db_failure.sh'" -ForegroundColor White
