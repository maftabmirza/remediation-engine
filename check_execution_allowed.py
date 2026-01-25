import asyncio
import sys
import os

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.services.trigger_matcher import AlertTriggerMatcher
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
from app.models import Alert
from app.models_remediation import Runbook
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def main():
    print("--- Checking Execution Allowed ---")
    async with AsyncSessionLocal() as db:
        # Get the alert
        alert = await db.get(Alert, "f1579498-6ea5-4b04-92ea-24ddae53a44b")
        if not alert:
            print("Alert not found")
            return

        # Get the runbook
        # We need to find the runbook associated with 'ApacheDown'
        # Assuming we know the name or ID, but let's look it up
        stmt = select(Runbook).where(Runbook.name.ilike("%Web Service Restart%"))
        result = await db.execute(stmt)
        runbook = result.scalars().first()
        
        if not runbook:
            print("Runbook not found")
            return
            
        print(f"Checking runbook: {runbook.name} (ID: {runbook.id})")
        
        matcher = AlertTriggerMatcher(db)
        allowed, reason = await matcher._check_execution_allowed(runbook)
        
        print(f"Execution Allowed: {allowed}")
        print(f"Block Reason: {reason}")
        
        if not allowed:
            print("BLOCKER DETECTED!")

if __name__ == "__main__":
    asyncio.run(main())
