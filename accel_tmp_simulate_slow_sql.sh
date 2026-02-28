#!/bin/bash
echo "Simulating Slow SQL Logs..."
# Append fake slow query logs to application log (using apache error log as carrier for now or a custom app log)
# Assuming Promtail scrapes /var/log/*.log
LOG_FILE="/var/log/apache2/error.log"

for i in {1..10}
do
   echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] [db_driver] Slow SQL detected: Query took 5.02s: SELECT * FROM larger_table WHERE unindexed_col = 'test'" | sudo tee -a $LOG_FILE
   sleep 2
done
echo "Slow SQL logs injected."
