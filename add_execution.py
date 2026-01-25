import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.models_remediation import RunbookExecution
from app.models import Alert
from app.models_remediation import Runbook
from sqlalchemy import select

# Fix imports
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge

async def main():
    print("--- Adding Manual Test Execution ---")
    async with AsyncSessionLocal() as db:
        # Get runbook
        stmt = select(Runbook).where(Runbook.name.ilike("%Web Service Restart%"))
        result = await db.execute(stmt)
        runbook = result.scalars().first()
        
        if not runbook:
            print("Runbook not found")
            return

        # Create dummy execution
        new_id = uuid.uuid4()
        execution = RunbookExecution(
            id=new_id,
            runbook_id=runbook.id,
            runbook_version=1,
            server_id=None,
            status="success",
            execution_mode="manual",
            queued_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            result_summary="Manual test from fix script"
        )
        
        db.add(execution)
        await db.commit()
        print(f"Added Manual Execution ID: {new_id}")

if __name__ == "__main__":
    asyncio.run(main())
