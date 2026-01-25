import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

# Correct import order for ORM verification
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
import app.models_scheduler

from app.database import AsyncSessionLocal
from app.models_remediation import RunbookExecution, StepExecution

async def main():
    exec_id = "d1524ed8-baea-43d2-ac1e-757282e0ccda"
    print(f"--- Inspecting Execution {exec_id} ---")
    
    async with AsyncSessionLocal() as db:
        # Load Execution with Runbook
        result = await db.execute(
            select(RunbookExecution)
            .options(selectinload(RunbookExecution.runbook))
            .where(RunbookExecution.id == exec_id)
        )
        execution = result.scalar_one_or_none()
        
        if not execution:
            print("Execution NOT FOUND!")
            return
            
        print(f"Status: {execution.status}")
        print(f"Server ID: {execution.server_id}")
        print(f"Result Summary: {execution.result_summary}")
        print(f"Error Message: {execution.error_message}")
        print("-" * 40)
        
        # Load Steps
        result = await db.execute(
            select(StepExecution)
            .where(StepExecution.execution_id == exec_id)
            .order_by(StepExecution.step_order)
        )
        steps = result.scalars().all()
        
        for step in steps:
            print(f"Step {step.step_order}: {step.step_name} [{step.status}]")
            print(f"  Command: {step.command_executed}")
            print(f"  Exit Code: {step.exit_code}")
            if step.stdout:
                print(f"  STDOUT: {step.stdout.strip()}")
            if step.stderr:
                print(f"  STDERR: {step.stderr.strip()}")
            if step.error_message:
                print(f"  Error: {step.error_message}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
