import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal

async def main():
    print("--- Counting Executions (Raw SQL) ---")
    async with AsyncSessionLocal() as db:
        # Count
        result = await db.execute(text("SELECT COUNT(*) FROM runbook_executions"))
        count = result.scalar()
        print(f"Total Runbook Executions: {count}")
        
        # Last 5
        result = await db.execute(text("SELECT id, status, queued_at FROM runbook_executions ORDER BY queued_at DESC LIMIT 5"))
        rows = result.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Queued: {row[2]} | Status: {row[1]}")

if __name__ == "__main__":
    asyncio.run(main())
