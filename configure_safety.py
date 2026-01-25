import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal

async def main():
    print("--- Configuring Safety Settings (Raw SQL) ---")
    async with AsyncSessionLocal() as db:
        # Update runbook config: Cooldown 1 min, Approval Required True, Auto Execute False
        sql = text("UPDATE runbooks SET cooldown_minutes = 1, approval_required = 'true', auto_execute = 'false' WHERE name LIKE '%Web Service Restart%'")
        result = await db.execute(sql)
        await db.commit()
        print(f"Update executed. Rows affected: {result.rowcount}")
        
        # Verify
        sql_check = text("SELECT name, cooldown_minutes, approval_required, auto_execute FROM runbooks WHERE name LIKE '%Web Service Restart%'")
        row = (await db.execute(sql_check)).fetchone()
        print(f"Config: Cooldown={row[1]}, Approval={row[2]}, Auto={row[3]}")

if __name__ == "__main__":
    asyncio.run(main())
