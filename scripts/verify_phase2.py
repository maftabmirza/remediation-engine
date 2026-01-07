import requests
import sys
import os
import json
import logging
from time import sleep

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Direct DB imports for verification
from app.database import SessionLocal
# Import ALL models to ensure SQLAlchemy registry is fully populated
try:
    from app.models import *
    from app.models_agent import *
    from app.models_ai_helper import *
    from app.models_application import *
    from app.models_chat import *
    from app.models_dashboards import *
    from app.models_group import *
    from app.models_itsm import *
    from app.models_knowledge import *
    from app.models_learning import *
    from app.models_remediation import *
    from app.models_runbook_acl import *
    from app.models_scheduler import *
    from app.models_troubleshooting import *
except ImportError as e:
    pass

BASE_URL = "http://localhost:8080"
# Credentials from docker-compose/envs
USERNAME = "admin"
PASSWORD = "admin"

def run_test():
    print("--- STARTING PHASE 2 VERIFICATION ---")
    
    # 1. Login
    print(f"\n[1] Logging in as {USERNAME}...")
    try:
        # Use correct endpoint /api/auth/login and JSON payload
        auth_resp = requests.post(
            f"{BASE_URL}/api/auth/login", 
            json={"username": USERNAME, "password": PASSWORD}
        )
        if auth_resp.status_code != 200:
            print(f"Login failed: {auth_resp.text}")
            return
        
        token = auth_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login success.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 2. Send Chat Query (Troubleshooting)
    # We use a query likely to trigger runbook search
    query = "How do I check disk space?"
    print(f"\n[2] Sending query: '{query}'")
    
    try:
        chat_resp = requests.post(
            f"{BASE_URL}/api/ai-helper/query", 
            json={"query": query, "page_context": {"os": "linux"}},
            headers=headers
        )
        
        if chat_resp.status_code != 200:
            print(f"Chat failed: {chat_resp.text}")
            return

        data = chat_resp.json()
        query_id = data.get("query_id")
        print(f"Got query_id: {query_id}")
        
        if not query_id:
            print("Error: No query_id returned")
            return
    except Exception as e:
        print(f"Chat request error: {e}")
        return

    # 3. Verify Database (Audit Log - Solutions Presented)
    print("\n[3] Verifying solutions_presented in Audit Log (DB)...")
    db = SessionLocal()
    try:
        # We need to import AIHelperAuditLog explicitly or find it
        # It's in app.models_ai_helper
        log = db.query(AIHelperAuditLog).filter(AIHelperAuditLog.id == query_id).first()
        if not log:
            print("Error: Audit log not found in DB")
            return
            
        details = log.ai_action_details
        print(f"Log Details Keys: {details.keys() if details else 'None'}")
        
        if details and "solutions_presented" in details:
            solutions = details['solutions_presented']
            print("SUCCESS: solutions_presented found in audit log!")
            print(f"Count: {len(solutions)}")
            if len(solutions) > 0:
                print(f"First Solution: {solutions[0].get('title', 'Unknown')}")
        else:
            print("WARNING: solutions_presented NOT found. Maybe no runbooks matched or search not triggered.")
            # This might happen if 'disk space' doesn't match the mock runbooks created
            pass

        # 4. Verify Tracking Endpoint
        print("\n[4] Testing /track-choice endpoint...")
        choice_payload = {
            "audit_log_id": query_id,
            "choice_data": {
                "solution_chosen_id": "test-runbook-id",
                "solution_chosen_type": "runbook",
                "user_action": "clicked_link",
                "feedback_text": "Verified by script"
            }
        }
        
        track_resp = requests.post(
            f"{BASE_URL}/api/ai-helper/track-choice",
            json=choice_payload,
            headers=headers
        )
        
        if track_resp.status_code != 200:
             print(f"Track choice failed: {track_resp.text}")
        else:
             print("Track choice endpoint succeeded (200 OK)")
             
        # 5. Verify Choice in DB
        print("\n[5] Verifying user_modifications in DB...")
        db.expire(log) # Refresh
        db.refresh(log)
        
        formatted_mods = json.dumps(log.user_modifications, indent=2)
        print(f"User Modifications: {formatted_mods}")
        
        if log.user_modifications and log.user_modifications.get("solution_chosen_type") == "runbook":
             print("SUCCESS: Choice tracked correctly in DB.")
        else:
             print("FAILURE: Choice NOT tracked in DB.")
             
    except Exception as e:
        print(f"DB Verification failed: {e}")
    finally:
        db.close()
    
    print("\n--- END VERIFICATION ---")

if __name__ == "__main__":
    run_test()
