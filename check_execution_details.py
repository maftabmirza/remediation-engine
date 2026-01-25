import asyncio
import sys
import os
import uuid

sys.path.append(os.getcwd())

# Mock env
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
from app.models_remediation import RunbookExecution, StepExecution
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def main():
    print(f"--- Checking Last Execution Details ---")
    
    async with AsyncSessionLocal() as db:
        # Get last execution
        query = select(RunbookExecution).options(
            selectinload(RunbookExecution.step_executions)
        ).order_by(RunbookExecution.queued_at.desc()).limit(1)
        
        result = await db.execute(query)
        execution = result.scalar_one_or_none()
        
        if not execution:
            print("No executions found.")
            return

        print(f"Execution ID: {execution.id}")
        print(f"Status: {execution.status}")
        print(f"Steps Completed: {execution.steps_completed}/{execution.steps_total}")

if __name__ == "__main__":
    asyncio.run(main())
