import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal

async def main():
    print("--- Updating Detection Step ---")
    step_id = "7c447909-01c6-4c84-b6cc-680dde7982e4"
    
    # New command: Check existence instead of active status
    # 'systemctl cat' returns 0 if unit file exists, regardless of state
    new_command = (
        "(systemctl cat apache2 > /dev/null 2>&1 && echo apache2) || "
        "(systemctl cat httpd > /dev/null 2>&1 && echo httpd) || "
        "(systemctl cat nginx > /dev/null 2>&1 && echo nginx) || "
        "echo none"
    )
    
    async with AsyncSessionLocal() as db:
        sql = text("UPDATE runbook_steps SET command_linux = :cmd WHERE id = :sid")
        await db.execute(sql, {"cmd": new_command, "sid": step_id})
        await db.commit()
        print(f"Updated Step {step_id}")
        print(f"New Command: {new_command}")

if __name__ == "__main__":
    asyncio.run(main())
