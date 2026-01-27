# Scenario 4: DB Connection Failure - Quick Reference

## Overview
Simulate and test database connectivity failure to demonstrate AI troubleshooting capabilities.

## Target System
- **Server**: 15.204.233.209 (t-aiops-01)
- **Website**: http://15.204.233.209/index.php
- **SSH**: ubuntu@15.204.233.209 (passwordless)
- **Database Port**: 3306 (MySQL) or 5432 (PostgreSQL)

## Quick Start

### Prerequisites (Run Once)
```powershell
# Deploy scripts to server
scp accel_tmp_simulate_db_failure.sh ubuntu@15.204.233.209:~/
scp accel_tmp_restore_db_access.sh ubuntu@15.204.233.209:~/
ssh ubuntu@15.204.233.209 "chmod +x ~/accel_tmp_*.sh"
```

### Option 1: Automated Test (Recommended)
```powershell
python test_scenario4_db_failure.py
```

### Option 2: Manual Execution

#### Step 1: Verify Prerequisites
```powershell
# Check website is working
curl http://15.204.233.209/index.php

# Check SSH access
ssh ubuntu@15.204.233.209 "echo 'Connected'"
```

#### Step 2: Simulate Failure
```powershell
# Deploy and run simulation script
scp accel_tmp_simulate_db_failure.sh ubuntu@15.204.233.209:~/
ssh ubuntu@15.204.233.209 "chmod +x ~/accel_tmp_simulate_db_failure.sh && ~/accel_tmp_simulate_db_failure.sh"
```

#### Step 3: Verify Failure
```powershell
# Website should return error
curl -I http://15.204.233.209/index.php

# Check error logs
ssh ubuntu@15.204.233.209 "sudo tail -30 /var/log/apache2/error.log"
```

#### Step 4: Test AI Troubleshooting
1. Open AI Chat: http://localhost:8080/ai
2. Enter prompt: "The application at http://15.204.233.209/index.php is broken, please help"
3. Observe AI's diagnostic process

#### Step 5: Restore System
```powershell
# Deploy and run restore script
scp accel_tmp_restore_db_access.sh ubuntu@15.204.233.209:~/
ssh ubuntu@15.204.233.209 "chmod +x ~/accel_tmp_restore_db_access.sh && ~/accel_tmp_restore_db_access.sh"

# Verify restoration
curl http://15.204.233.209/index.php
```

## Expected AI Behavior

### ✅ Correct AI Response:
1. Checks Apache service status → **Running**
2. Reads error logs → Finds database connection errors
3. Identifies issue: "Apache is running but cannot connect to database"
4. Suggests running database connectivity diagnostics
5. Recommends checking database service or network connectivity

### ❌ Incorrect AI Response:
- Immediately suggests restarting Apache (wrong, Apache is fine)
- Doesn't check error logs
- Doesn't identify the database connection problem
- Suggests generic troubleshooting without log analysis

## Troubleshooting

### Website still works after simulation?
```bash
# Check if iptables rule is active
ssh ubuntu@15.204.233.209 "sudo iptables -L OUTPUT -n | grep 3306"

# Check database service status
ssh ubuntu@15.204.233.209 "systemctl status mysql"

# Try alternative simulation (stop DB service)
ssh ubuntu@15.204.233.209 "sudo systemctl stop mysql"
```

### Cannot restore system?
```bash
# Emergency restoration
ssh ubuntu@15.204.233.209 << 'ENDSSH'
sudo iptables -F OUTPUT
sudo systemctl start mysql
sudo systemctl start mariadb
sudo systemctl start postgresql
sudo systemctl restart apache2
ENDSSH
```

### Need to check database type?
```bash
# Check PHP config for database details
ssh ubuntu@15.204.233.209 "sudo cat /var/www/html/index.php | grep -i 'mysql\|pdo\|database'"

# Check running database services
ssh ubuntu@15.204.233.209 "systemctl list-units --type=service | grep -E 'mysql|maria|postgres'"
```

## Files Created/Updated

- ✅ [demo testing.md](demo testing.md) - Updated with full Scenario 4 plan
- ✅ [accel_tmp_simulate_db_failure.sh](accel_tmp_simulate_db_failure.sh) - Enhanced simulation script
- ✅ [accel_tmp_restore_db_access.sh](accel_tmp_restore_db_access.sh) - Enhanced restore script
- ✅ [test_scenario4_db_failure.py](test_scenario4_db_failure.py) - Automated test script
- ✅ SCENARIO4_QUICK_REFERENCE.md - This file

## Success Criteria

- [  ] Website returns 500 error during simulation
- [  ] Apache remains running (systemctl shows "active")
- [  ] Error logs show database connection errors
- [  ] AI correctly identifies database connectivity issue
- [  ] AI doesn't suggest restarting Apache as primary solution
- [  ] System restores within 30 seconds
- [  ] No permanent configuration changes

## Notes

- Simulation uses iptables to block database port (reversible)
- Alternative: Stop database service directly
- Scripts support both MySQL (3306) and PostgreSQL (5432)
- Always test restoration before live demo
- Keep this reference open during demo for quick troubleshooting
