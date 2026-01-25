import asyncio
import sys
import os
from sqlalchemy import select

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.models import ServerCredential, Alert
from app.models_remediation import Runbook
from app.services.trigger_matcher import AlertTriggerMatcher

# Fix ORM imports
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
import app.models_scheduler

async def main():
    print("--- Debugging Server Resolution ---")
    async with AsyncSessionLocal() as db:
        # 1. Fetch the actual Server Credential to see what's in DB
        result = await db.execute(select(ServerCredential).where(ServerCredential.hostname == '15.204.233.209'))
        server = result.scalar_one_or_none()
        if not server:
            print("Server 15.204.233.209 NOT FOUND in DB. Trying loose search...")
            result = await db.execute(select(ServerCredential))
            all_servers = result.scalars().all()
            for s in all_servers:
                print(f"Server: {s.hostname} (IP: {s.ip_address})")
                if "15.204.233.209" in str(s.hostname):
                    server = s
                    break
        
        if server:
            print(f"Target Server Found: {server.hostname} (ID: {server.id})")
        else:
            print("CRITICAL: Target server not found at all.")
            return

        # 2. Mock Runbook (Using the real one if possible, or a dummy)
        # We need a dummy object that mimics Runbook behavior for the method
        class MockRunbook:
            target_from_alert = True
            target_alert_label = "instance"
            default_server_id = None
        
        runbook = MockRunbook()

        # 3. Mock Alert with PORT in instance
        class MockAlert:
            labels_json = {
                "instance": "15.204.233.209:9117",  # The problematic value
                "job": "apache-exporter"
            }
        
        alert = MockAlert()

        # 4. Test Resolution
        matcher = AlertTriggerMatcher(db)
        print(f"\nTesting resolution with label: {alert.labels_json['instance']}")
        
        resolved_id = await matcher._resolve_target_server(runbook, alert)
        
        if resolved_id:
            print(f"SUCCESS: Resolved to Server ID {resolved_id}")
        else:
            print("FAILURE: Could not resolve server ID")

        # 5. Test Resolution with CLEAN IP (Expect Success)
        alert.labels_json['instance'] = "15.204.233.209"
        print(f"\nTesting resolution with label: {alert.labels_json['instance']}")
        resolved_id_clean = await matcher._resolve_target_server(runbook, alert)
        if resolved_id_clean:
            print(f"SUCCESS: Resolved to Server ID {resolved_id_clean}")
        else:
            print("FAILURE: Could not resolve server ID (Clean IP)")


if __name__ == "__main__":
    asyncio.run(main())
