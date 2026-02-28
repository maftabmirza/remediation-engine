import asyncio
import sys
import os
import time

sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory
from sqlalchemy import text

async def main():
    server_name = "t-aiops-01"
    print(f"--- Triggering Scenario 4: DB Failure on {server_name} ---")
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        if not server:
            print("Server not found.")
            return

        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            # 1. Simulate Failure
            print("Executing simulate_db_failure.sh...")
            cmd_sim = f"/home/{server.username}/simulate_db_failure.sh"
            await executor.execute(f"chmod +x {cmd_sim} && {cmd_sim}")
            print("DB Failure Simulated (Port 5432 Blocked).")
            
            # 2. Verify Imact (Optional - check connection locally?)
            # Since we don't have an app running on t-aiops-01 that uses local DB (except maybe apache logging to db?), 
            # we can verify by trying to telnet or nc to localhost 5432 on the remote server
            print("Verifying port block...")
            # Timeout of 2s because it should reject/drop
            res = await executor.execute("timeout 2 nc -zv localhost 5432 || echo 'Connection Failed'")
            print(f"Verification Output: {res.stdout.strip()}")

            print("Waiting 10s...")
            time.sleep(10)
            
            # 3. Restore
            print("Restoring DB Access...")
            cmd_res = f"/home/{server.username}/restore_db_access.sh"
            await executor.execute(f"chmod +x {cmd_res} && {cmd_res}")
            print("DB Access Restored.")
            
            # Verify again
            res_after = await executor.execute("timeout 2 nc -zv localhost 5432 || echo 'Connection Failed'")
            # Note: If no DB is running on 5432, it will say Connection Refused anyway, but blocked is different usually?
            # Or assume postgres is running.
            print(f"Post-Restore Verification: {res_after.stdout.strip()}")

if __name__ == "__main__":
    asyncio.run(main())
