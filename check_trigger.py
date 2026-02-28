import asyncio
import sys
import os

sys.path.append(os.getcwd())

# Mock env
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
import app.models # Register base models
import app.models_agent # Register ServerCredential
import app.models_remediation # Register Runbook
from app.models_remediation import Runbook, RunbookTrigger
from sqlalchemy import text
from sqlalchemy.future import select

async def main():
    server_name = "t-aiops-01"
    runbook_name_partial = "Web Service Restart"
    alert_name = "ApacheDown"
    
    print(f"--- Checking Trigger for {alert_name} -> {runbook_name_partial} ---")
    
    async with AsyncSessionLocal() as db:
        # 1. Find Runbook
        query = select(Runbook).where(Runbook.name.like(f"%{server_name}%{runbook_name_partial}%"))
        result = await db.execute(query)
        runbook = result.scalar_one_or_none()
        
        if not runbook:
            print(f"Runbook not found for {server_name}")
            return

        print(f"Runbook Found: {runbook.name} (ID: {runbook.id})")
        print(f"  - Auto-Execute: {runbook.auto_execute}")
        print(f"  - Approval Required: {runbook.approval_required}")
        
        # 2. Find Trigger
        query = select(RunbookTrigger).where(
            RunbookTrigger.runbook_id == runbook.id,
            RunbookTrigger.alert_name_pattern == alert_name
        )
        result = await db.execute(query)
        trigger = result.scalar_one_or_none()
        
        if trigger:
            print(f"Trigger Found: {trigger.alert_name_pattern} -> Runbook")
            print(f"  - Enabled: {trigger.enabled}")
        else:
            print("Trigger NOT FOUND.")
            print(f"Action Required: Create trigger linking '{alert_name}' to this runbook.")

if __name__ == "__main__":
    asyncio.run(main())
