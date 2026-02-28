import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal

async def main():
    print("--- Diagnosing Blocker (Raw SQL) ---")
    async with AsyncSessionLocal() as db:
        # Check Runbook Config
        print("\n[Runbook Config]")
        sql = text("SELECT id, name, enabled, auto_execute, approval_required, cooldown_minutes FROM runbooks WHERE name LIKE '%Web Service Restart%'")
        result = await db.execute(sql)
        runbook = result.fetchone()
        if runbook:
            print(f"ID: {runbook[0]}")
            print(f"Name: {runbook[1]}")
            print(f"Enabled: {runbook[2]}")
            print(f"Auto Execute: {runbook[3]}")
            print(f"Approval Required: {runbook[4]}")
            print(f"Cooldown: {runbook[5]}")
            runbook_id = runbook[0]
        else:
            print("Runbook NOT FOUND!")
            return

        # Check Circuit Breakers
        print("\n[Circuit Breakers]")
        sql = text("SELECT state, failure_count FROM circuit_breakers WHERE scope_id = :rid")
        result = await db.execute(sql, {"rid": runbook_id})
        cb = result.fetchone()
        if cb:
            print(f"State: {cb[0]}")
            print(f"Failure Count: {cb[1]}")
        else:
            print("No Circuit Breaker found for this runbook.")

        # Check Rate Limits (last hour)
        print("\n[Rate Limits]")
        # Simplified check: count executions in last hour
        sql = text("SELECT COUNT(*) FROM runbook_executions WHERE runbook_id = :rid AND queued_at > NOW() - INTERVAL '1 hour'")
        result = await db.execute(sql, {"rid": runbook_id})
        count = result.scalar()
        print(f"Executions in last hour: {count}")

if __name__ == "__main__":
    asyncio.run(main())
