
import asyncio
import uuid
import sys
import os
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Add app to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models_remediation import Runbook, RunbookExecution, RunbookStep, StepExecution
from app.routers.remediation import list_executions, get_execution

async def main():
    async with AsyncSessionLocal() as db:
        print("Creating test runbook...")
        runbook_id = uuid.uuid4()
        runbook = Runbook(
            id=runbook_id,
            name=f"Test Runbook {runbook_id}",
            description="Test runbook for repro",
            steps=[
                RunbookStep(
                    step_order=1,
                    name="Test Step",
                    step_type="command",
                    command_linux="echo 'Hello World'",
                    target_os="linux"
                )
            ]
        )
        db.add(runbook)
        await db.commit()

        print(f"Created runbook: {runbook.name} ({runbook.id})")

        print("Creating test execution...")
        execution_id = uuid.uuid4()
        execution = RunbookExecution(
            id=execution_id,
            runbook_id=runbook_id,
            runbook_version=1,
            status="success",
            queued_at=runbook.created_at,
            step_executions=[
                StepExecution(
                    step_order=1,
                    step_name="Test Step",
                    status="success",
                    stdout="Hello World",
                    stderr=""
                )
            ]
        )
        db.add(execution)
        await db.commit()

        print(f"Created execution: {execution.id}")

        # Test list_executions logic (simulating what the API does)
        print("\n--- Testing list_executions logic ---")
        query = select(RunbookExecution).options(
            selectinload(RunbookExecution.runbook),
            selectinload(RunbookExecution.server)
        ).where(RunbookExecution.id == execution_id)
        
        result = await db.execute(query)
        ex = result.scalar_one_or_none()
        
        if ex:
            print(f"Loaded execution: {ex.id}")
            print(f"Runbook relation: {ex.runbook}")
            if ex.runbook:
                print(f"Runbook Name from relation: {ex.runbook.name}")
            else:
                print("Runbook relation is NONE!")
        else:
            print("Execution not found via query")

        # Clean up
        print("\nCleaning up...")
        await db.delete(execution)
        await db.delete(runbook)
        await db.commit()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
