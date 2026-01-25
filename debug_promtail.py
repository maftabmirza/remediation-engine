import asyncio
import sys
import os

sys.path.append(os.getcwd())
# Force UTF-8 stdout
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory
from sqlalchemy import text

async def main():
    server_name = "t-aiops-01"
    print(f"--- Debugging Promtail on {server_name} ---")
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            print("1. Service Status:")
            res = await executor.execute("systemctl status promtail --no-pager")
            print(res.stdout)
            
            print("\n2. Configuration:")
            res = await executor.execute("cat /etc/promtail/config.yaml")
            print(res.stdout)
            
            print("\n3. Recent Logs:")
            res = await executor.execute("journalctl -u promtail -n 20 --no-pager")
            print(res.stdout)

if __name__ == "__main__":
    asyncio.run(main())
