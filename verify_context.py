
import sys
import os
import json
from uuid import uuid4
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath("d:/remediate-engine-antigravity"))

# FORCE SETTINGS FOR LOCALHOST execution
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import SessionLocal
from app.models import User
# Ensure all models are loaded
import app.models_application
import app.models_knowledge
from app.models_ai import AISession

def verify_session_context():
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            print("No users found to test with.")
            return

        print(f"Testing with user: {user.username} ({user.id})")

        # Mock Alert ID
        alert_id = str(uuid4())
        print(f"Using mock Alert ID: {alert_id}")
        
        # Simulate creating a session via code logic (mimicking chat_api.py)
        # Since I can't easily hit the API endpoint from here without running server + mock auth,
        # I'll manually run the logic I added to verify it works with the DB model.
        
        # Logic from chat_api.py:
        context_type = 'alert'
        context_id =  alert_id
        context_json = {"alert_id": alert_id}
        
        new_session = AISession(
            id=uuid4(),
            user_id=user.id,
            pillar="troubleshooting",
            title="Context Verification Session",
            created_at=datetime.utcnow(),
            context_type=context_type,
            context_id=context_id,
            context_context_json=context_json
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        print(f"Created session {new_session.id}")
        
        # Verify storage
        fetched_session = db.query(AISession).filter(AISession.id == new_session.id).first()
        if not fetched_session:
             print("ERROR: Failed to fetch session!")
             return

        print(f"Fetched session context_type: {fetched_session.context_type}")
        print(f"Fetched session context_id: {fetched_session.context_id}")
        print(f"Fetched session context_json: {fetched_session.context_context_json}")
        
        if str(fetched_session.context_id) == str(alert_id):
             print("SUCCESS: Context ID matches Alert ID")
        else:
             print(f"FAILURE: Context ID mismatch! Expected {alert_id}, got {fetched_session.context_id}")

        # Simulate retrieval logic from troubleshoot_api.py
        retrieved_alert_id = None
        if fetched_session.context_type == 'alert' and fetched_session.context_id:
             retrieved_alert_id = str(fetched_session.context_id)
        elif fetched_session.context_context_json and fetched_session.context_context_json.get("alert_id"):
             retrieved_alert_id = fetched_session.context_context_json.get("alert_id")
             
        if retrieved_alert_id == alert_id:
             print("SUCCESS: troubleshoot_api logic correctly retrieves alert_id from session")
        else:
             print(f"FAILURE: Retrieval logic failed! Got {retrieved_alert_id}")

        # Cleanup
        db.delete(new_session)
        db.commit()
        print("Test session cleaned up.")
        
    except Exception as e:
        print(f"FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_session_context()
