import asyncio
import sys
import os
from sqlalchemy import select, text

# Correct import order
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
import app.models_scheduler

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.models import ServerCredential

async def main():
    print("--- Updating Server Name for Matching Workaround ---")
    async with AsyncSessionLocal() as db:
        # Find server by hostname
        result = await db.execute(select(ServerCredential).where(ServerCredential.hostname == '15.204.233.209'))
        server = result.scalar_one_or_none()
        
        if server:
            print(f"Found Server: {server.name} (ID: {server.id})")
            # Update name to match instance label with port
            server.name = "15.204.233.209:9117"
            await db.commit()
            print(f"Updated Name to: {server.name}")
        else:
            print("Server not found!")

if __name__ == "__main__":
    asyncio.run(main())
