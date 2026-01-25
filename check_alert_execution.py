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
import app.models_application # Register Application
import app.models_knowledge # Register DesignDocument
from app.models import Alert
from app.models_remediation import RunbookExecution
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def main():
    alert_id_str = "f1579498-6ea5-4b04-92ea-24ddae53a44b"
    print(f"--- Checking Alert {alert_id_str} ---")
    
    async with AsyncSessionLocal() as db:
        # 1. Check Alert
        query = select(Alert).where(Alert.id == uuid.UUID(alert_id_str))
        result = await db.execute(query)
        alert = result.scalar_one_or_none()
        
        if not alert:
            print("Alert NOT FOUND.")
            return

        print(f"Alert Found: {alert.alert_name}")
        print(f"  Actions: {alert.action_taken}")
        
        # 2. Check Executions by Alert ID
        query = select(RunbookExecution).where(RunbookExecution.alert_id == alert.id)
        result = await db.execute(query)
        executions = result.scalars().all()
        
        print(f"Linked Executions: {len(executions)}")
        for ex in executions:
            print(f"  - Execution ID: {ex.id} Status: {ex.status}")

if __name__ == "__main__":
    asyncio.run(main())
