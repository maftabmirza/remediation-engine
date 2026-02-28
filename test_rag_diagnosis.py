import asyncio
import sys
import os
import json
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.services.troubleshooting_manager import TroubleshootingManager

async def main():
    print("--- Testing RAG Diagnosis ---")
    
    # 1. Initialize Troubleshooter
    async with AsyncSessionLocal() as db:
        TroubleshootingManager.db = db
        # We need a user ID and Server ID
        # Find user
        from app.models import User, ServerCredential
        user_res = await db.execute(text("SELECT id FROM users LIMIT 1"))
        user_id = user_res.scalar_one()
        
        # Find server
        server_res = await db.execute(text("SELECT id FROM server_credentials WHERE hostname='15.204.233.209'"))
        server_id = server_res.scalar_one()
        
        # 2. Simulate User Query
        query_text = "The website is broken. I see database errors in the logs."
        print(f"User Query: {query_text}")
        
        manager = TroubleshootingManager(db)
        
        # Create a session context
        session_id = await manager.create_session(user_id, server_id, "Manual Diagnosis Test")
        
        # Analyze
        print("Running Analysis (RAG)...")
        response = await manager.analyze_input(session_id, query_text)
        
        print("\n--- AI Response ---")
        print(response.get('answer', 'No answer provided'))
        
        print("\n--- Recommended Actions ---")
        for action in response.get('actions', []):
            print(f"- {action['type']}: {action['name']}")

if __name__ == "__main__":
    asyncio.run(main())
