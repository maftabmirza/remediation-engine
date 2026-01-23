
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

def verify_session_listing():
    db = SessionLocal()
    try:
        # Get a test user
        user = db.query(User).first()
        if not user:
            print("No users found to test with.")
            return

        print(f"Testing with user: {user.username} ({user.id})")

        # Create a dummy session
        new_session = AISession(
            id=uuid4(),
            user_id=user.id,
            pillar="troubleshooting",
            title="Verification Test Session Listing",
            created_at=datetime.utcnow()
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        print(f"Created session {new_session.id} for testing")

        # Test querying with the fix logic
        print("Attempting to list sessions ordered by created_at.desc()...")
        sessions = db.query(AISession).filter(
            AISession.user_id == user.id
        ).order_by(AISession.created_at.desc()).limit(5).all()
        
        print(f"Successfully retrieved {len(sessions)} sessions.")
        for s in sessions:
            print(f"- {s.title} (created: {s.created_at})")
            # Verify accessing attributes doesn't crash
            _ = s.created_at

        # Verify updated_at is NOT accessed since it doesn't exist
        try:
            _ = sessions[0].updated_at
            print("WARNING: Accessed updated_at successfully (unexpected if column deleted, but maybe mapped in ORM?)")
        except AttributeError:
            print("Confirmed: updated_at attribute does not exist on model (EXPECTED)")


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
    verify_session_listing()
