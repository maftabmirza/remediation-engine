import asyncio
import sys
import os

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
import app.models 
import app.models_remediation
import app.models_scheduler
from app.models_remediation import Runbook
from sqlalchemy import select, update

async def main():
    print("--- Disabling Runbook Cooldown ---")
    async with AsyncSessionLocal() as db:
        stmt = select(Runbook).where(Runbook.name.ilike("%Web Service Restart%"))
        result = await db.execute(stmt)
        runbook = result.scalars().first()
        
        if not runbook:
            print("Runbook not found")
            return
            
        print(f"Updating runbook: {runbook.name}")
        print(f"Old Cooldown: {runbook.cooldown_minutes}")
        
        runbook.cooldown_minutes = 0
        await db.commit()
        print("New Cooldown: 0")

if __name__ == "__main__":
    asyncio.run(main())
