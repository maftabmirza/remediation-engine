# Fix GPT Provider Authentication Issue
# This script will fix the provider_type case sensitivity issue

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "FIX GPT PROVIDER AUTHENTICATION ISSUE" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

Write-Host "`n1. Checking database providers..." -ForegroundColor Yellow
python check_llm_providers.py

Write-Host "`n2. Fixing provider_type case..." -ForegroundColor Yellow
python urgent_fix_provider_case.py

Write-Host "`n3. Restarting application..." -ForegroundColor Yellow
docker-compose restart engine

Write-Host "`nWaiting for engine to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "`n4. Checking logs..." -ForegroundColor Yellow
docker-compose logs -f engine --tail=20
