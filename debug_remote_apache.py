import asyncio
import sys
import os
from sqlalchemy import select

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.models import ServerCredential
from app.services.executor_factory import ExecutorFactory
from app.config import get_settings
import app.models 
import app.models_remediation
import app.models_application
import app.models_knowledge
import app.models_scheduler

async def main():
    print("--- Debugging Remote Apache Status ---")
    settings = get_settings()
    
    async with AsyncSessionLocal() as db:
        # 1. Get Server Credential
        result = await db.execute(select(ServerCredential).where(ServerCredential.hostname == '15.204.233.209'))
        server = result.scalar_one_or_none()
        
        if not server:
            # Try finding by name/alias if IP lookup fails
            print("Server 15.204.233.209 not found by hostname, trying to find any server...")
            result = await db.execute(select(ServerCredential))
            servers = result.scalars().all()
            for s in servers:
                print(f"Found Server: {s.hostname} (IP: {s.ip_address})")
                if "15.204.233.209" in str(s.hostname) or "15.204.233.209" in str(s.ip_address):
                    server = s
                    break
        
        if not server:
            print("Target server credential not found in DB!")
            return

        print(f"Connecting to {server.hostname} ({server.username})...")

        # 2. Get Executor
        try:
            executor = ExecutorFactory.get_executor(server, settings.encryption_key)
            async with executor:
                if not await executor.test_connection():
                    print("SSH Connection FAILED!")
                    return
                print("SSH Connection Successful.")

                # 3. Diagnostics
                print("\n[Check 1: Nginx Process]")
                try:
                    res = await executor.execute("ps aux | grep nginx")
                    print(res.stdout)
                except Exception as e:
                    print(f"Check 1 Failed: {e}")
                
                print("\n[Check 2: Nginx Service]")
                try:
                     res = await executor.execute("systemctl is-active nginx")
                     print(f"Status: {res.stdout.strip()}")
                except Exception as e:
                     print(f"Check 2 Failed: {e}")
                
        except Exception as e:
            print(f"Executor failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
