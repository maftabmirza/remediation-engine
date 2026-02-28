import asyncio
import sys
import os

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.models_remediation import RunbookExecution
from sqlalchemy import select, func

async def main():
    print("--- Counting Executions ---")
    async with AsyncSessionLocal() as db:
        query = select(func.count(RunbookExecution.id))
        result = await db.execute(query)
        count = result.scalar()
        print(f"Total Runbook Executions: {count}")
        
        # List last 5 sorted by queued_at desc
        query = select(RunbookExecution).order_by(RunbookExecution.queued_at.desc()).limit(5)
        result = await db.execute(query)
        executions = result.scalars().all()
        for ex in executions:
            print(f"ID: {ex.id} | Queued: {ex.queued_at} | Status: {ex.status}")

if __name__ == "__main__":
    asyncio.run(main())
