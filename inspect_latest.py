import asyncio
import sys
import os
import json
from sqlalchemy import select, text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.models_remediation import RunbookExecution

# Correct import order for ORM validation
import app.models  # Defines ServerCredential
import app.models_remediation
import app.models_application
import app.models_knowledge
import app.models_scheduler

async def main():
    print("--- Inspecting Latest Execution ---")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RunbookExecution)
            .order_by(RunbookExecution.queued_at.desc())
            .limit(1)
        )
        execution = result.scalar_one_or_none()
        
        if execution:
            print(f"ID: {execution.id}")
            print(f"Status: {execution.status}")
            print(f"Server ID: {execution.server_id}")
            print(f"Error: {execution.error_message}")
            if execution.server_id:
                print("SUCCESS: Server ID resolved!")
            else:
                print("FAILURE: Server ID is None")
        else:
            print("No executions found!")

if __name__ == "__main__":
    asyncio.run(main())
