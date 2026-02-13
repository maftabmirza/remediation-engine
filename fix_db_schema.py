import asyncio
import sys
import os

sys.path.append(os.getcwd())
# Use POSTGRES_HOST from env (postgres in Docker, localhost when running from host)

from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    print("--- Fixing DB Schema ---")
    async with AsyncSessionLocal() as db:
        columns_to_add = [
            ("summary", "VARCHAR(255) DEFAULT 'Auto Correlation' NOT NULL"),
            ("root_cause_analysis", "TEXT"),
            ("confidence_score", "DOUBLE PRECISION"),
        ]
        for col_name, col_def in columns_to_add:
            try:
                print(f"Checking/Adding '{col_name}' column to alert_correlations...")
                check_sql = text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='alert_correlations' AND column_name=:col"
                )
                result = await db.execute(check_sql, {"col": col_name})
                if result.fetchone():
                    print(f"  Column '{col_name}' already exists.")
                else:
                    print(f"  Adding column '{col_name}'...")
                    alter_sql = text(f"ALTER TABLE alert_correlations ADD COLUMN {col_name} {col_def}")
                    await db.execute(alter_sql)
                    await db.commit()
                    print(f"  Column '{col_name}' added successfully.")
            except Exception as e:
                print(f"  Error: {e}")
                await db.rollback()

if __name__ == "__main__":
    asyncio.run(main())
