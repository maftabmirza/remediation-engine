import asyncio
import sys
import os
import json
from sqlalchemy import select, text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.models import Alert
from app.models_remediation import Runbook, RunbookExecution

# Fix ORM imports
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
import app.models_scheduler

async def main():
    print("--- Inspecting Execution Failure ---")
    async with AsyncSessionLocal() as db:
        # 1. Inspect Execution
        exec_id = "52d84a31-7ba9-4a03-858d-b19e5e7919fe"
        print(f"\n[Execution: {exec_id}]")
        result = await db.execute(select(RunbookExecution).where(RunbookExecution.id == exec_id))
        execution = result.scalar_one_or_none()
        
        if execution:
            print(f"Status: {execution.status}")
            print(f"Server ID: {execution.server_id}")
            print(f"Error: {execution.error_message}")
            print(f"Runbook ID: {execution.runbook_id}")
            print(f"Alert ID: {execution.alert_id}")
        else:
            print("Execution not found!")
            return

        # 2. Inspect Runbook Config
        print(f"\n[Runbook: {execution.runbook_id}]")
        result = await db.execute(select(Runbook).where(Runbook.id == execution.runbook_id))
        runbook = result.scalar_one_or_none()
        if runbook:
            print(f"Name: {runbook.name}")
            print(f"Target From Alert: {runbook.target_from_alert}")
            print(f"Target Alert Label: {runbook.target_alert_label}")
            print(f"Default Server ID: {runbook.default_server_id}")
        
        # 3. Inspect Alert Labels
        print(f"\n[Alert: {execution.alert_id}]")
        result = await db.execute(select(Alert).where(Alert.id == execution.alert_id))
        alert = result.scalar_one_or_none()
        if alert:
            print(f"Labels: {json.dumps(alert.labels_json, indent=2)}")
            print(f"Instance Label: {alert.labels_json.get('instance')}")

if __name__ == "__main__":
    asyncio.run(main())
