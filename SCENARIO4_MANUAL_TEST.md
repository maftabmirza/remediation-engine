# Scenario 4 - Manual Test Guide

## Quick Deployment (Run Once)

```powershell
# Copy scripts to server
scp accel_tmp_simulate_db_failure.sh ubuntu@15.204.233.209:~/
scp accel_tmp_restore_db_access.sh ubuntu@15.204.233.209:~/

# Make executable
ssh ubuntu@15.204.233.209 "chmod +x ~/accel_tmp_simulate_db_failure.sh ~/accel_tmp_restore_db_access.sh"
```

## Manual Test Procedure

### Step 1: Check Baseline
```powershell
# Test website is working
curl http://15.204.233.209/index.php

# Check Apache is running
ssh ubuntu@15.204.233.209 "systemctl status apache2 | grep Active"
```

### Step 2: Simulate DB Failure
```powershell
# Option A: Run simulation script
ssh ubuntu@15.204.233.209 "~/accel_tmp_simulate_db_failure.sh"

# Option B: Direct iptables block (if script fails)
ssh ubuntu@15.204.233.209 "sudo iptables -A OUTPUT -p tcp --dport 3306 -j DROP"
```

### Step 3: Verify Failure
```powershell
# Website should show error
curl http://15.204.233.209/index.php

# Check error logs
ssh ubuntu@15.204.233.209 "sudo tail -30 /var/log/apache2/error.log"
```

### Step 4: Test AI Troubleshooting
1. Open: http://localhost:8080/ai
2. Enter: "The application at http://15.204.233.209/index.php is broken, please help"
3. Observe AI's response

**Expected AI Behavior:**
- ✅ Checks Apache (should be running)
- ✅ Reads error logs (finds DB connection errors)
- ✅ Identifies: "Database connectivity issue"
- ✅ Suggests DB diagnostics (not just Apache restart)

### Step 5: Restore System
```powershell
# Option A: Run restore script
ssh ubuntu@15.204.233.209 "~/accel_tmp_restore_db_access.sh"

# Option B: Direct restoration (if script fails)
ssh ubuntu@15.204.233.209 "sudo iptables -D OUTPUT -p tcp --dport 3306 -j DROP; sudo systemctl start mysql"

# Verify restoration
curl http://15.204.233.209/index.php
```

## Emergency Recovery
If anything goes wrong:
```powershell
ssh ubuntu@15.204.233.209 "sudo iptables -F OUTPUT; sudo systemctl restart apache2; sudo systemctl start mysql"
```

## Using Automated Script
```powershell
python test_scenario4_db_failure.py
```
(Runs all steps automatically with prompts)
