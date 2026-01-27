# Demo Implementation Plan - Apache on t-aiops-01

## Goal

Setup a complete demo environment on t-aiops-01 (15.204.233.209) to showcase:

- AI-driven Remediation: Detecting and fixing a stopped web server.
- Observability Integration: Correlating data from Prometheus, Loki, and Grafana (Simulated or Real).
- Change Management: Linking incidents to recent deployments or config changes.

## User Review Required

> **IMPORTANT**  
> Prometheus Trigger: Scenario 1a requires mocking a Prometheus webhook to the t-aiops-01 endpoint to trigger the Apache Down alert.

> **NOTE**  
> Change Simulation: We will simulate a "Bad Deployment" by creating a dummy "Recent Deployments" log or entry for the AI to find.

> **IMPORTANT**  
> Database Fix: Added summary column to alert_correlations table to fix application crash. If you see schema errors, run `alembic upgrade head`.

> **NOTE**  
> SOP Document: I will create a new SOP file `docs/SOP_Apache_Maintenance.md` to demonstrate the AI's ability to read custom instructions.

## Proposed Changes

### Setup Environment

#### Install Apache on t-aiops-01

- SSH into 15.204.233.209.
- Run: `sudo apt-get update && sudo apt-get install -y apache2`.
- Verify: `systemctl status apache2`.

#### Seed Runbooks

- Run `scripts/seed_demo_runbooks_for_hosts.py` targeting t-aiops-01.
- This will create:
  - [t-aiops-01] Web Service Restart (Apache/Nginx)
  - [t-aiops-01] Host Diagnostics Bundle
  - [t-aiops-01] Disk Space Quick Check

#### Create Custom SOP (Modified)

- [modify] `SOP_Apache_Maintenance.md`
- Change: Remove Slack/Email/On-Call integration references.
- New Policy: "Manual Escalation Only". Operator must physically log in or call the shift supervisor (manual phone tree).
- Reasoning: AI will advise the user on who to call, rather than trying to trigger a nonexistent Slack integration.

#### Simulation Scripts (New)

- `scripts/simulate_db_failure.sh`: Blocks access to the DB port to simulate "Connection Refused".
- `scripts/simulate_slow_sql.sh`: Injects a sleep(5) into the backend logic (or mockup).

## Demo Scenarios (Test Cases)

### Scenario 1a: Automated Self-Healing (Prometheus Trigger)

**Trigger:** Prometheus detects Apache Down (Simulated via webhook payload).

**System Action:**
- Rules Engine receives alert.
- Matches Apache Down alert to [t-aiops-01] Web Service Restart runbook.
- Auto-Executes the runbook (if configured) or creates a Pending Investigation.
- Notifications sent to "Slack" (Simulated log).

**Demo Payoff:** Zero-touch resolution. The system fixes itself before the user even logs in.

### Scenario 1b: Assisted Remediation (AI Chat)

**Trigger:** User notices "Apache is down" (Manual observation, no alert yet).

**User Action:** Chats with AI: "Fix the web server."

**AI Action:**
- Finds relevant runbook.
- Executes it interactively.
- Verifies the fix.

**Demo Payoff:** Human-in-the-loop resolution for non-alerted issues.

### Scenario 2: Diagnostics & Performance (The "Deep Dive")

**Trigger:** User says "The server feels slow" or "Run a health check on t-aiops-01".

**What happens under the hood:**
- Intent Recognition: AI determines this is a "Diagnostics" request.
- Tool Selection: AI selects the [t-aiops-01] Host Diagnostics Bundle runbook.
- Execution: The runbook executes multiple commands continuously on the server:
  - `uptime` (System load)
  - `free -h` (Memory usage)
  - `journalctl -p err -S -5m` (Recent error logs)
  - `netstat -tulpn` (Active network connections)
- AI Analysis: The AI receives the raw text output. It doesn't just display it; it analyzes it.
  - If load > 2.0: "High system load detected."
  - If memory < 500MB free: "Memory is critically low."
  - If logs contain 'Error': "Found recent application errors..."

**Demo Payoff:** Shows how the AI aggregates multiple data points into a concise health summary, saving the user from running 5 separate manual commands.

### Scenario 3: Knowledge Retrieval (RAG/SOP) (The "Policy Expert")

**Status:** ✅ **IMPLEMENTED & READY FOR DEMO**

**Trigger:** User asks a procedural question: "Who do I notify if I need to restart Apache?" or "What is the maintenance window?"

**What happens under the hood:**
- Retrieval: The AI calls `search_knowledge` tool which queries the vector database
- Search: Finds the `docs/SOP_Apache_Maintenance.md` document uploaded to knowledge base (ID: 8717ed1c-ff70-4bdd-a15c-d97ea28472ed)
- Synthesis: The AI constructs an answer based on the SOP's manual escalation policy

**Expected Interaction:**
- User: "Can I restart Apache right now?"
- AI: "According to the SOP, you must manually notify the Shift Supervisor at ext 1234 before proceeding. Automated alerting is not available."

**Implementation Details:**
- ✅ SOP document created at [docs/SOP_Apache_Maintenance.md](docs/SOP_Apache_Maintenance.md)
- ✅ Document uploaded to knowledge base via API
- ✅ Document chunked into 8 searchable segments with vector embeddings
- ✅ Enhanced with prominent "MANDATORY NOTIFICATION REQUIRED" section
- ✅ Includes: Shift Supervisor contact (Ext 1234), maintenance windows (Tue/Thu 02:00-04:00 AM EST)
- ✅ Knowledge search API endpoint tested and working: `/api/knowledge/search`
- ✅ AI troubleshooting agent has `search_knowledge` tool available

**Testing Commands:**
```powershell
# Test knowledge search directly
$searchPayload = @{ query = "Apache restart notification policy"; doc_types = @("sop"); limit = 3 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8080/api/knowledge/search" -Method POST -Headers @{"Authorization"="Bearer $token"} -Body $searchPayload -ContentType "application/json"
```

**Demo Script:**
1. Navigate to AI Chat interface (http://localhost:8080/ai)
2. Ask: "Can I restart Apache right now?"
3. Expected: AI searches knowledge base and cites the SOP requirement to notify Shift Supervisor
4. Ask: "What is the maintenance window for Apache?"
5. Expected: AI responds with "Tuesdays and Thursdays, 02:00 AM - 04:00 AM EST"
6. Ask: "Who do I contact for Apache issues?"
7. Expected: AI responds with "Shift Supervisor at Extension 1234"

**Known Issue & Workaround:**
- Current behavior: AI may prioritize runbook execution over SOP consultation
- Improvement needed: Adjust tool selection logic to check SOPs before suggesting actions
- Workaround for demo: Phrase questions as "What does the SOP say about..." to force knowledge retrieval

### Scenario 4: The "Unknown" Problem (DB Connection Failure)

**Status:** 🔧 **PLANNING IN PROGRESS**

**Trigger:** User reports "Website is showing error 500" (Simulated by failing DB connect).

**Prompt:** "The application is broken, please help."

**Expected AI Behavior:**
- Initial Check: AI checks Apache status. It is UP. (So standard restart runbook isn't the primary fix).
- Log Analysis: AI reads error.log and finds Connection refused or SQLSTATE[HY000].
- Deduction: "Apache is running, but it cannot talk to the Database."
- Recommendation: "I recommend checking the Database Server status or network connectivity."
- Action: User allows AI to run [t-aiops-01] Check DB Connectivity (We need to ensure this runbook exists or AI constructs a ping/netcat check).

#### Implementation Plan

**Prerequisites:**
- ✅ Website accessible: http://15.204.233.209/index.php
- ✅ SSH access: ubuntu@15.204.233.209 (passwordless)
- ⏳ Database connection details (host, port, credentials)
- ⏳ Apache error log location: `/var/log/apache2/error.log`
- ⏳ PHP error log location: `/var/log/apache2/php_error.log` or `/var/log/php/error.log`

**Step 1: Pre-Demo Verification**

```bash
# SSH to the server
ssh ubuntu@15.204.233.209

# Verify website is working
curl -I http://15.204.233.209/index.php
# Expected: HTTP/1.1 200 OK

# Identify database details from PHP config
sudo cat /var/www/html/index.php | grep -E "host|dbname|user" || \
sudo cat /var/www/html/config.php | grep -E "host|dbname|user"

# Check current DB connectivity
php -r "new PDO('mysql:host=DB_HOST;dbname=DB_NAME', 'DB_USER', 'DB_PASS');"
# Expected: No output = success, or connection confirmed
```

**Step 2: Create Simulation Scripts**

Create script to block database access:
```bash
# Create simulation script on t-aiops-01
cat > ~/simulate_db_failure.sh << 'EOF'
#!/bin/bash
# simulate_db_failure.sh - Blocks database connectivity

DB_HOST="${1:-localhost}"
DB_PORT="${2:-3306}"

echo "Blocking database access to $DB_HOST:$DB_PORT"

# Method 1: Block with iptables (requires sudo)
if command -v iptables &> /dev/null; then
    sudo iptables -A OUTPUT -p tcp --dport $DB_PORT -d $DB_HOST -j DROP
    echo "✓ iptables rule added to block port $DB_PORT"
fi

# Method 2: Alternative - stop database service if local
if [ "$DB_HOST" = "localhost" ] || [ "$DB_HOST" = "127.0.0.1" ]; then
    if systemctl is-active --quiet mysql; then
        sudo systemctl stop mysql
        echo "✓ MySQL service stopped"
    elif systemctl is-active --quiet postgresql; then
        sudo systemctl stop postgresql
        echo "✓ PostgreSQL service stopped"
    fi
fi

echo "Database failure simulation active!"
echo "To restore, run: ./restore_db_access.sh"
EOF

chmod +x ~/simulate_db_failure.sh
```

Create script to restore database access:
```bash
# Create restore script on t-aiops-01
cat > ~/restore_db_access.sh << 'EOF'
#!/bin/bash
# restore_db_access.sh - Restores database connectivity

DB_HOST="${1:-localhost}"
DB_PORT="${2:-3306}"

echo "Restoring database access..."

# Method 1: Remove iptables rule
if command -v iptables &> /dev/null; then
    sudo iptables -D OUTPUT -p tcp --dport $DB_PORT -d $DB_HOST -j DROP 2>/dev/null
    echo "✓ iptables rule removed"
fi

# Method 2: Start database service if local
if [ "$DB_HOST" = "localhost" ] || [ "$DB_HOST" = "127.0.0.1" ]; then
    if systemctl list-units --type=service | grep -q mysql; then
        sudo systemctl start mysql
        echo "✓ MySQL service started"
    elif systemctl list-units --type=service | grep -q postgresql; then
        sudo systemctl start postgresql
        echo "✓ PostgreSQL service started"
    fi
fi

echo "Database access restored!"
EOF

chmod +x ~/restore_db_access.sh
```

**Step 3: Create DB Connectivity Runbook**

Need to create or verify existence of runbook: `[t-aiops-01] Check DB Connectivity`

```python
# Add to create_demo_runbooks.py or run separately
runbook = {
    "name": "[t-aiops-01] Check DB Connectivity",
    "description": "Diagnose database connection issues on t-aiops-01",
    "steps": [
        {
            "name": "Check Apache Status",
            "command": "systemctl status apache2 | grep Active"
        },
        {
            "name": "Check Recent Error Logs",
            "command": "sudo tail -50 /var/log/apache2/error.log"
        },
        {
            "name": "Check Database Service",
            "command": "systemctl status mysql || systemctl status postgresql || echo 'No local DB service found'"
        },
        {
            "name": "Test DB Port Connectivity",
            "command": "nc -zv localhost 3306 || nc -zv 127.0.0.1 5432 || echo 'Database port not accessible'"
        },
        {
            "name": "Check Network Connections",
            "command": "netstat -tunlp | grep -E '3306|5432' || ss -tunlp | grep -E '3306|5432'"
        }
    ],
    "host": "t-aiops-01"
}
```

**Step 4: Demo Execution Steps**

**4.1 Start Demo - Baseline Check**
```bash
# From your local machine
curl http://15.204.233.209/index.php
# Expected: Website loads successfully with 200 OK
```

**4.2 Simulate the Failure**
```bash
# SSH to server and run simulation
ssh ubuntu@15.204.233.209 "~/simulate_db_failure.sh localhost 3306"
# Or from your local machine:
ssh ubuntu@15.204.233.209 'bash -s' < accel_tmp_simulate_db_failure.sh
```

**4.3 Verify Failure is Active**
```bash
# Test website now shows error
curl http://15.204.233.209/index.php
# Expected: HTTP 500 or connection error message

# Check error logs
ssh ubuntu@15.204.233.209 "sudo tail -20 /var/log/apache2/error.log"
# Expected: Shows "Connection refused" or "SQLSTATE[HY000]" errors
```

**4.4 Trigger AI Troubleshooting**
- Navigate to AI Chat: http://localhost:8080/ai or http://localhost:8080/troubleshoot
- Enter prompt: "The application at http://15.204.233.209/index.php is broken, please help"

**Expected AI Flow:**
1. AI asks for symptoms or checks service status
2. AI detects Apache is running (service active)
3. AI reads error logs and finds database connection errors
4. AI identifies: "Apache is running but cannot connect to database"
5. AI suggests running "[t-aiops-01] Check DB Connectivity" runbook
6. User approves execution
7. AI executes diagnostics and reports findings
8. AI recommends: "Database service is down or unreachable. Recommend checking DB server status or network connectivity."

**4.5 Restore System**
```bash
# Restore database access
ssh ubuntu@15.204.233.209 "~/restore_db_access.sh localhost 3306"

# Verify restoration
curl http://15.204.233.209/index.php
# Expected: Website loads successfully again
```

#### Alternative Failure Simulation Methods

**Option A: Using iptables (Network-level block)**
```bash
# Block outbound connection to DB
sudo iptables -A OUTPUT -p tcp --dport 3306 -j DROP
# Restore: sudo iptables -D OUTPUT -p tcp --dport 3306 -j DROP
```

**Option B: Stop DB Service (If database is local)**
```bash
# Stop MySQL/MariaDB
sudo systemctl stop mysql
# Restore: sudo systemctl start mysql
```

**Option C: Break DB Config (Application-level)**
```bash
# Backup current config
sudo cp /var/www/html/config.php /var/www/html/config.php.bak
# Change DB host to invalid value
sudo sed -i 's/DB_HOST = .*/DB_HOST = "192.0.2.1"/' /var/www/html/config.php
# Restore: sudo mv /var/www/html/config.php.bak /var/www/html/config.php
```

#### Success Criteria

- ✅ Website returns 500 error during simulation
- ✅ Apache error logs show database connection errors
- ✅ Apache service remains active (systemctl shows "running")
- ✅ AI correctly identifies the issue as database connectivity problem
- ✅ AI suggests database-specific diagnostics (not just Apache restart)
- ✅ System can be restored within 30 seconds
- ✅ No permanent damage to configuration files

#### Rollback Plan

If anything goes wrong:
```bash
# Emergency restoration commands
ssh ubuntu@15.204.233.209 << 'ENDSSH'
# Remove all iptables rules
sudo iptables -F OUTPUT
# Start all database services
sudo systemctl start mysql 2>/dev/null
sudo systemctl start postgresql 2>/dev/null
# Restore config backups
sudo cp /var/www/html/config.php.bak /var/www/html/config.php 2>/dev/null
# Restart Apache
sudo systemctl restart apache2
ENDSSH
```

#### Next Steps

1. ⏳ Identify exact database type and connection details on t-aiops-01
2. ⏳ Create and test simulation scripts on the server
3. ⏳ Create/verify "[t-aiops-01] Check DB Connectivity" runbook exists
4. ⏳ Test full scenario end-to-end
5. ⏳ Document expected error messages for demo script

### Scenario 5: Performance Bottleneck (Slow SQL & Loki)

**Trigger:** "Why is the application so slow?"

**AI Behavior:**
- Metrics (Grafana/Prometheus): Checks CPU/RAM -> "Normal utilization."
- Logs (Loki): Queries application logs. Finds [WARN] Query took 5.02s.
- Conclusion: "Loki logs indicate a slow SQL query in the backend."

### Scenario 6: The "Bad Deploy" (Change Management)

**Trigger:** User asks "Why did the server crash?"

**AI Behavior:**
- Checks Active Alerts -> None.
- Checks Change Log (Simulated): Finds "Deployment v2.4 applied at 10:15 AM".
- Correlation: "The instability started 2 minutes after Deployment v2.4 was applied."
- Recommendation: "Rollback Deployment v2.4."

### Scenario 7: Existing Alerts Correlation

**Trigger:** User: "Is the system healthy?"

**AI Behavior:**
- Checks Prometheus/Alertmanager.
- Finds an active alert: High Memory Usage (95%) triggered 20 mins ago.
- Response: "No, I found an active 'High Memory' alert from Prometheus that started 20 minutes ago. This might be affecting performance."

## Verification Plan

### Automated Verification

- Verify Apache: `curl http://15.204.233.209` (Should return 200 OK after setup).
- Verify Runbooks: `python scripts/seed_demo_runbooks_for_hosts.py --hosts t-aiops-01` (Should report "OK: updated" or "already exists").

### Manual Verification

Walkthrough: I will perform the actions for Scenario 1 manually via the AI chat interface (if accessible) or simulate the steps via terminal to ensure the runbooks work as expected.