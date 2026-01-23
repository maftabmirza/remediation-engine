
import sys
import os
from uuid import uuid4
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath("d:/remediate-engine-antigravity"))

# FORCE SETTINGS FOR LOCALHOST execution
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import SessionLocal
from app.models import User
# Ensure all models are loaded to avoid registry errors
import app.models_application
import app.models_knowledge
from app.models_ai import AISession

def verify_session_creation():
    db = SessionLocal()
    try:
        # Get a test user (assuming one exists, or get the first one)
        user = db.query(User).first()
        if not user:
            print("No users found to test with.")
            return

        print(f"Testing with user: {user.username} ({user.id})")

        # Simulate the patched code logic
        session_id = uuid4()
        new_session = AISession(
            id=session_id,
            user_id=user.id,
            pillar="troubleshooting",
            title="Verification Test Session",
            created_at=datetime.utcnow()
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        print(f"Successfully created session: {new_session.id}")
        print(f"Pillar: {new_session.pillar}")
        
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
    verify_session_creation()
