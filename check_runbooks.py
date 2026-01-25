import asyncio
import sys
import os
sys.path.append(os.getcwd())

# Mock environment
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    server_name = "t-aiops-01"
    print(f"Checking runbooks for: {server_name}")
    
    async with AsyncSessionLocal() as db:
        # Check if server exists to get ID
        query = text("SELECT id, hostname FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        if not server:
            print("Server not found.")
            return

        print(f"Server ID: {server.id}")
        
        # Check runbooks
        # Assuming runbooks might be linked by name convention or explicit relationship? 
        # The schema isn't fully visible here, but looking at seed script logic would clarify.
        # Usually seed script creates runbooks with specific names.
        
        query = text("SELECT id, name, description FROM runbooks WHERE name LIKE :pattern")
        result = await db.execute(query, {"pattern": f"%{server_name}%"})
        runbooks = result.fetchall()
        
        if runbooks:
            print(f"Found {len(runbooks)} runbooks matching '{server_name}':")
            for r in runbooks:
                print(f"- {r.name} (ID: {r.id})")
        else:
            print(f"No runbooks found with name containing '{server_name}'.")

if __name__ == "__main__":
    asyncio.run(main())
