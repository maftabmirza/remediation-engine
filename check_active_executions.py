import asyncio
import sys
import os
import uuid
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal

async def main():
    print("--- Checking Active Executions for Alert f15... ---")
    async with AsyncSessionLocal() as db:
        sql = text("SELECT id, status, execution_mode FROM runbook_executions WHERE alert_id = 'f1579498-6ea5-4b04-92ea-24ddae53a44b'")
        result = await db.execute(sql)
        rows = result.fetchall()
        print(f"Found {len(rows)} executions for this alert:")
        for row in rows:
            print(f" - ID: {row[0]}, Status: {row[1]}, Mode: {row[2]}")

if __name__ == "__main__":
    asyncio.run(main())
