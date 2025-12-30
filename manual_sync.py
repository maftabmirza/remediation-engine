import asyncio
import os
from dotenv import load_dotenv
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.services.itsm_sync_worker import sync_itsm_changes

load_dotenv()

async def manual_sync():
    print("Starting manual sync...")
    await sync_itsm_changes()
    print("Sync complete")

if __name__ == "__main__":
    asyncio.run(manual_sync())
