import asyncio
import sys
import os
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
    print("--- Debugging Trigger Matcher ---")
    async with AsyncSessionLocal() as db:
        # Create a transient Alert object (not saved to DB)
        alert = Alert(
            id="f1579498-6ea5-4b04-92ea-24ddae53a44b",
            alert_name="ApacheDown",
            severity="critical",
            instance="15.204.233.209:9117",
            job="apache-exporter",
            status="firing",
            labels_json={"severity": "critical", "instance": "15.204.233.209:9117"}
        )
        
        matcher = AlertTriggerMatcher(db)
        print(f"Matching Alert: {alert.alert_name}")
        
        result = await matcher.match_alert(alert)
        
        print("\n[Match Results]")
        print(f"Matches Found: {len(result.matches)}")
        for m in result.matches:
            print(f" - Runbook: {m.runbook.name}")
            print(f" - Execution Mode: {m.execution_mode}")
            print(f" - Can Execute: {m.can_execute}")
            print(f" - Block Reason: {m.block_reason}")
            
        print("\n[Categorized]")
        print(f"Auto Execute: {len(result.auto_execute)}")
        print(f"Needs Approval: {len(result.needs_approval)}")
        print(f"Blocked: {len(result.blocked)}")

if __name__ == "__main__":
    asyncio.run(main())
