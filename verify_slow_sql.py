import asyncio
import sys
import os
import time

sys.path.append(os.getcwd())

# Mock environment
os.environ["LOKI_URL"] = "http://localhost:3100"
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory
from app.services.loki_client import LokiClient
from sqlalchemy import text
from datetime import datetime, timedelta

async def main():
    server_name = "t-aiops-01"
    print(f"--- Triggering Scenario 5: Slow SQL on {server_name} ---")
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        if not server:
            print("Server not found.")
            return

        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            # 1. Simulate Slow SQL
            print("Executing simulate_slow_sql.sh...")
            cmd_sim = f"/home/{server.username}/simulate_slow_sql.sh"
            await executor.execute(f"chmod +x {cmd_sim} && {cmd_sim}")
            print("Slow SQL Logs Injected.")
            
            # 2. Verify in Loki
            print("Waiting 10s for log ingestion...")
            time.sleep(10)
            
            print("Querying Loki for 'Slow SQL'...")
            client = LokiClient(url="http://localhost:3100", timeout=30)
            
            try:
                # Query logs from last 5 mins containing "Slow SQL"
                now = datetime.now()
                # Use a simpler query that just matches the text we injected, regardless of labels
                query = '{filename=~".+"} |= "Slow SQL"'
                
                logs = await client.query_range(
                    logql=query, 
                    start=now - timedelta(minutes=5),
                    end=now,
                    limit=10
                )
                
                print(f"Found {len(logs)} logs.")
                for log in logs:
                    print(f"- {log.line}")
                    
                if len(logs) > 0:
                    print("SUCCESS: Slow SQL logs found in Loki.")
                else:
                    print("FAILURE: No logs found. Check Promtail config.")
                    
            except Exception as e:
                print(f"Loki Check Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
