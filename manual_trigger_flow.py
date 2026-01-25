import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.services.trigger_matcher import AlertTriggerMatcher
from app.models import Alert

# Fix imports
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge

async def main():
    print("--- Manual Remediation Flow Verification ---")
    async with AsyncSessionLocal() as db:
        matcher = AlertTriggerMatcher(db)
        
        # Test 1: First Trigger (Expect Pending Approval)
        print("\n[Trigger 1]")
        alert1 = Alert(
            id=uuid.uuid4(),
            alert_name="ApacheDown",
            severity="critical",
            instance="15.204.233.209:9117",
            job="apache-exporter",
            status="firing",
            timestamp=datetime.now(timezone.utc),
            fingerprint="manual_verification_1",
            labels_json={"severity": "critical", "instance": "15.204.233.209:9117"}
        )
        db.add(alert1)
        await db.commit()
        await db.refresh(alert1)
        
        result1 = await matcher.process_alert_for_remediation(alert1)
        print(f"Result: {result1}")
        
        # Test 2: Second Trigger (Expect Cooldown Block)
        print("\n[Trigger 2]")
        alert2 = Alert(
            id=uuid.uuid4(),
            alert_name="ApacheDown",
            severity="critical",
            instance="15.204.233.209:9117",
            job="apache-exporter",
            status="firing",
            timestamp=datetime.now(timezone.utc),
            fingerprint="manual_verification_2",
            labels_json={"severity": "critical", "instance": "15.204.233.209:9117"}
        )
        db.add(alert2)
        await db.commit()
        await db.refresh(alert2)

        result2 = await matcher.process_alert_for_remediation(alert2)
        print(f"Result: {result2}")

if __name__ == "__main__":
    asyncio.run(main())
