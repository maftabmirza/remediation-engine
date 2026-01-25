import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

# Correct import order
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
import app.models_scheduler

from app.database import AsyncSessionLocal
from app.models_remediation import Runbook, RunbookStep

async def main():
    print("--- Finding Runbook Steps ---")
    async with AsyncSessionLocal() as db:
        # Find the runbook
        result = await db.execute(select(Runbook).where(Runbook.name.like("%Web Service Restart%")))
        runbook = result.scalar_one_or_none()
        
        if not runbook:
            print("Runbook not found!")
            return
            
        print(f"Runbook: {runbook.name} (ID: {runbook.id})")
        
        # Get steps
        result = await db.execute(
            select(RunbookStep)
            .where(RunbookStep.runbook_id == runbook.id)
            .order_by(RunbookStep.step_order)
        )
        steps = result.scalars().all()
        
        for step in steps:
            print(f"Step {step.step_order}: {step.name} (ID: {step.id})")
            print(f"  Current Command: {step.command}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
