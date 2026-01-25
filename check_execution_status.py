import asyncio
import sys
import os

sys.path.append(os.getcwd())

# Mock env
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
import app.models # Register base
import app.models_agent
import app.models_application
import app.models_knowledge
import app.models_remediation
from app.models_remediation import RunbookExecution, Runbook
from sqlalchemy import text
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

async def main():
    print("--- Checking Recent Runbook Executions ---")
    
    async with AsyncSessionLocal() as db:
        # Get executions from last 24h
        from datetime import datetime, timedelta, timezone
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        
        query = select(RunbookExecution).options(
            selectinload(RunbookExecution.runbook)
        ).where(RunbookExecution.queued_at >= since).order_by(RunbookExecution.queued_at.desc())
        
        result = await db.execute(query)
        executions = result.scalars().all()
        
        if not executions:
            print("No executions found.")
            return

        for ex in executions:
            print(f"ID: {ex.id}")
            print(f"  Runbook: {ex.runbook.name if ex.runbook else 'Unknown'}")
            print(f"  Status: {ex.status}")
            print(f"  Queued: {ex.queued_at}")
            print(f"  Started: {ex.started_at}")
            print(f"  Completed: {ex.completed_at}")
            print(f"  Error: {ex.error_message}")
            print(f"  Result: {ex.result_summary}")
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())
