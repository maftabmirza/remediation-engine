#!/bin/bash
# simulate_db_failure.sh
# Purpose: Simulate a "Database Connection Refused" error for the demo.
# Method: Appends specific error patterns to the Apache/App error log.

LOG_FILE="/var/log/apache2/error.log"

echo "Simulating Database Failure..."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] PHP Fatal error:  Uncaught PDOException: SQLSTATE[HY000] [2002] Connection refused in /var/www/html/db.php:12" | sudo tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] Stack trace:" | sudo tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] #0 /var/www/html/index.php(5): connect_db()" | sudo tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] #1 {main}" | sudo tee -a "$LOG_FILE"
echo "  thrown in /var/www/html/db.php on line 12" | sudo tee -a "$LOG_FILE"

echo "Failure injected into $LOG_FILE. The AI should now detect 'Connection refused'."
