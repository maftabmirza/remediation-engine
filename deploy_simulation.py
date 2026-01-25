import asyncio
import sys
import os

sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory
from sqlalchemy import text

# Scripts
SCRIPT_DB_BLOCK = """#!/bin/bash
echo "Simulating DB Failure (Blocking port 5432)..."
# Block access to default Postgres port
sudo iptables -A OUTPUT -p tcp --dport 5432 -j REJECT
echo "DB Access Blocked."
"""

SCRIPT_DB_RESTORE = """#!/bin/bash
echo "Restoring DB Access..."
sudo iptables -D OUTPUT -p tcp --dport 5432 -j REJECT
echo "DB Access Restored."
"""

SCRIPT_SLOW_SQL = """#!/bin/bash
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
"""

async def main():
    server_name = "t-aiops-01"
    print(f"Deploying simulation scripts to: {server_name}")
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        if not server:
            print("Server not found.")
            return

        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            # Helper to write
            async def upload(name, content):
                local_path = f"accel_tmp_{name}"
                remote_path = f"/home/{server.username}/{name}"
                with open(local_path, "w", newline='\n') as f:
                    f.write(content)
                    
                if hasattr(executor, 'upload_file'):
                     print(f"Uploading {name}...")
                     await executor.upload_file(local_path, remote_path)
                     await executor.execute(f"chmod +x {remote_path}")
                
            await upload("simulate_db_failure.sh", SCRIPT_DB_BLOCK)
            await upload("restore_db_access.sh", SCRIPT_DB_RESTORE)
            await upload("simulate_slow_sql.sh", SCRIPT_SLOW_SQL)
            
            print("Scripts deployed to home directory.")

if __name__ == "__main__":
    asyncio.run(main())
