import asyncio
import sys
import os

sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory
from sqlalchemy import text

async def main():
    server_name = "t-aiops-01"
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            res = await executor.execute("date")
            print(f"Remote Date: {res.stdout.strip()}")

if __name__ == "__main__":
    asyncio.run(main())
