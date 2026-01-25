import asyncio
import sys
import os

sys.path.append(os.getcwd())

# Mock env
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory
from sqlalchemy import text

async def main():
    server_name = "t-aiops-01"
    print(f"--- Starting Tunnel for {server_name} ---")
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        executor = ExecutorFactory.get_executor(server, None)
        
        # We need to manually manage connection to keep it open
        if not await executor.connect():
            print("Failed to connect.")
            return

        print("Connected via SSH.")
        
        try:
            # Forward Remote 3100 -> Local 3100
            # listen_host, listen_port, dest_host, dest_port
            # On remote (server), listen on localhost:3100, forward to client's localhost:3100
            listener = await executor._conn.forward_remote_port('127.0.0.1', 3100, '127.0.0.1', 3100)
            print(f"Reverse Tunnel Established: Remote 3100 -> Local 3100")
            print("Accessing http://localhost:3100 on remote should reach local Loki.")
            
            # Keep alive
            print("Tunnel active. Running keepalive loop (Ctrl+C to stop)...")
            while True:
                await asyncio.sleep(60)
                
        except Exception as e:
            print(f"Tunnel error: {e}")
        finally:
            await executor.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
