import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal

async def main():
    print("--- Fixing Runbook Configuration ---")
    async with AsyncSessionLocal() as db:
        runbook_id = "7ebb4403-6c2a-4079-ac23-db9438f5a0fe"
        
        # Enable target_from_alert
        sql = text("UPDATE runbooks SET target_from_alert = 'true' WHERE id = :rid")
        await db.execute(sql, {"rid": runbook_id})
        await db.commit()
        
        print(f"Updated Runbook {runbook_id}: target_from_alert = True")
        
        # Verify
        sql_check = text("SELECT name, target_from_alert FROM runbooks WHERE id = :rid")
        result = await db.execute(sql_check, {"rid": runbook_id})
        row = result.fetchone()
        print(f"Verification: {row[0]} -> target_from_alert={row[1]}")

if __name__ == "__main__":
    asyncio.run(main())
