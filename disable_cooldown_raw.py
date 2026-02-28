import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal

async def main():
    print("--- Disabling Cooldown (Raw SQL) ---")
    async with AsyncSessionLocal() as db:
        # Update runbook config
        sql = text("UPDATE runbooks SET cooldown_minutes = 0, approval_required = 'false', auto_execute = 'true' WHERE name LIKE '%Web Service Restart%'")
        result = await db.execute(sql)
        await db.commit()
        print(f"Update executed. Rows affected: {result.rowcount}")

if __name__ == "__main__":
    asyncio.run(main())
