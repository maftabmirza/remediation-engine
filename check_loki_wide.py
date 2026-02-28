import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

# Mock environment
os.environ["LOKI_URL"] = "http://localhost:3100"

from app.services.loki_client import LokiClient

async def main():
    print("Querying Loki (Last 24h)...")
    client = LokiClient(url="http://localhost:3100", timeout=30)
    
    try:
        now = datetime.now()
        # Query logs containing "Slow SQL"
        logs = await client.query_range(
            logql='{filename=~".+"} |= "Slow SQL"', 
            start=now - timedelta(hours=24),
            end=now,
            limit=20
        )
        
        print(f"Found {len(logs)} logs.")
        for log in logs:
            print(f"[{log.timestamp}] {log.line}")
            
    except Exception as e:
        print(f"Loki Query Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
