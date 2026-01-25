import asyncio
import sys
import os

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    print("--- Fixing DB Schema ---")
    async with AsyncSessionLocal() as db:
        try:
            print("Checking/Adding 'summary' column to alert_correlations...")
            # Check if column exists
            check_sql = text("SELECT column_name FROM information_schema.columns WHERE table_name='alert_correlations' AND column_name='summary'")
            result = await db.execute(check_sql)
            if result.fetchone():
                print("Column 'summary' already exists.")
            else:
                print("Adding column 'summary'...")
                alter_sql = text("ALTER TABLE alert_correlations ADD COLUMN summary VARCHAR(255) DEFAULT 'Auto Correlation' NOT NULL")
                await db.execute(alter_sql)
                await db.commit()
                print("Column added successfully.")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(main())
