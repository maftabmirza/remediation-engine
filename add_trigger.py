import asyncio
import sys
import os
import uuid

sys.path.append(os.getcwd())

# Mock env
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
import app.models # Register base
import app.models_agent # Register ServerCredential
import app.models_application # Register Application
import app.models_knowledge # Register DesignDocument
import app.models_remediation # Register Runbook
from app.models_remediation import Runbook, RunbookTrigger
from sqlalchemy import text, update
from sqlalchemy.future import select

async def main():
    runbook_id_str = "7ebb4403-6c2a-4079-ac23-db9438f5a0fe"
    alert_name = "ApacheDown"
    
    print(f"--- Configuring Automation for Runbook {runbook_id_str} ---")
    
    async with AsyncSessionLocal() as db:
        # 1. Get Runbook
        query = select(Runbook).where(Runbook.id == uuid.UUID(runbook_id_str))
        result = await db.execute(query)
        runbook = result.scalar_one_or_none()
        
        if not runbook:
            print("Runbook not found!")
            return

        print(f"Found Runbook: {runbook.name}")
        
        # 2. Check if Trigger exists
        query_trig = select(RunbookTrigger).where(
            RunbookTrigger.runbook_id == runbook.id,
            RunbookTrigger.alert_name_pattern == alert_name
        )
        result_trig = await db.execute(query_trig)
        trigger = result_trig.scalar_one_or_none()
        
        if trigger:
            print("Trigger already exists.")
        else:
            print("Creating new Trigger...")
            new_trigger = RunbookTrigger(
                runbook_id=runbook.id,
                alert_name_pattern=alert_name,
                severity_pattern="critical",
                enabled=True,
                priority=10
            )
            db.add(new_trigger)
            print("Trigger created.")

        # 3. Enable Auto-Execution on Runbook
        if not runbook.auto_execute:
            print("Enabling Auto-Execute on Runbook...")
            # We can't modify the ORM object directly if it's not in the session cleanly or sometimes async issues
            # Using specific update statement is safer
            stmt = update(Runbook).where(Runbook.id == runbook.id).values(
                auto_execute=True,
                enabled=True
            )
            await db.execute(stmt)
            print("Runbook updated to Auto-Execute.")
        else:
            print("Runbook is already set to Auto-Execute.")
            
        await db.commit()
        print("Configuration Complete.")

if __name__ == "__main__":
    asyncio.run(main())
