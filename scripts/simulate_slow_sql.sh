#!/bin/bash
# simulate_slow_sql.sh
# Purpose: Simulate a "Slow SQL Query" performance issue.
# Method: Appends slow query warnings to the application log.

# Assuming a custom app log or reusing apache error log for visibility
LOG_FILE="/var/log/apache2/error.log"

echo "Simulating Slow SQL Performance Issue..."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [warn] [client 10.0.0.1] [PERF_WARN] Slow Query Detected: SELECT * FROM transaction_history WHERE date > '2020-01-01' ORDER BY id DESC (Time: 5.023s)" | sudo tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [warn] [client 10.0.0.1] [PERF_WARN] Memory usage peak: 128MB during query execution." | sudo tee -a "$LOG_FILE"

echo "Slow SQL warning injected into $LOG_FILE. The AI should now detect 'Slow Query'."
