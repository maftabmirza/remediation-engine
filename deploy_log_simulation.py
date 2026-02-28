import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory

# The Log Injection Script (from scripts/simulate_db_failure.sh)
SCRIPT_CONTENT = """#!/bin/bash
# simulate_db_failure.sh
# Purpose: Simulate a "Database Connection Refused" error for the demo.
# Method: Appends specific error patterns to the Apache/App error log.

LOG_FILE="/var/log/apache2/error.log"

echo "Simulating Database Failure (Log Injection)..."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] PHP Fatal error:  Uncaught PDOException: SQLSTATE[HY000] [2002] Connection refused in /var/www/html/db.php:12" | sudo tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] Stack trace:" | sudo tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] #0 /var/www/html/index.php(5): connect_db()" | sudo tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] [client 10.0.0.1] #1 {main}" | sudo tee -a "$LOG_FILE"
echo "  thrown in /var/www/html/db.php on line 12" | sudo tee -a "$LOG_FILE"

echo "Failure injected into $LOG_FILE."
"""

async def main():
    # Use IP as identifier since we renamed the server record
    server_identifier = "15.204.233.209"
    print(f"Deploying and Executing Log Injection on: {server_identifier}")
    
    async with AsyncSessionLocal() as db:
        # Find server by hostname or IP (in hostname column)
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR ip_address = :name")
        # Note: Model doesn't have ip_address column in my view, but hostname holds the IP usually.
        # Let's try matching hostname.
        query = text("SELECT * FROM server_credentials WHERE hostname = :name")
        result = await db.execute(query, {"name": server_identifier})
        server = result.fetchone()
        
        if not server:
            print(f"Server {server_identifier} not found in DB.")
            return

        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            remote_path = f"/home/{server.username}/simulate_db_failure_logs.sh"
            
            # Write temp file locally
            local_path = "temp_deploy_script.sh"
            with open(local_path, "w", newline='\n') as f:
                f.write(SCRIPT_CONTENT)
            
            # Upload
            if hasattr(executor, 'upload_file'):
                print(f"Uploading script to {remote_path}...")
                await executor.upload_file(local_path, remote_path)
                await executor.execute(f"chmod +x {remote_path}")
                print("Upload complete.")
                
                # Execute
                print("Executing simulation...")
                result = await executor.execute(f"sudo {remote_path}")
                print(f"Execution Result (Exit {result.exit_code}):")
                print(result.stdout)
                if result.stderr:
                    print(f"Stderr: {result.stderr}")
            else:
                print("Executor does not support upload_file.")

if __name__ == "__main__":
    asyncio.run(main())
