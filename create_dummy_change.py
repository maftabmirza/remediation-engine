import requests
import json
from datetime import datetime, timezone

def create_dummy_change():
    url = "http://localhost:8080/api/changes/webhook"
    
    # Deployment v2.4 applied at 10:15 AM
    # Scenario: User asks "Why did the server crash?"
    # Trigger: Deployment v2.4: Change Apache port to 8088
    
    payload = {
        "change_id": "DEPLOY-V2.4",
        "change_type": "Deployment",
        "service_name": "t-aiops-01",
        "description": "Deployment v2.4: Change Apache port to 8088",
        "timestamp": "2026-01-25T10:15:00Z",
        "start_time": "2026-01-25T10:10:00Z",
        "end_time": "2026-01-25T10:15:00Z",
        "associated_cis": ["apache2", "t-aiops-01"],
        "application": "Apache Web Server",
        "source": "CI/CD Pipeline",
        "metadata": {
            "version": "2.4",
            "environment": "Lab",
            "performed_by": "Automation Bot",
            "config_change": "Listen 80 -> Listen 8088"
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        print(f"Success! Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Error Response: {e.response.text}")

if __name__ == "__main__":
    create_dummy_change()
