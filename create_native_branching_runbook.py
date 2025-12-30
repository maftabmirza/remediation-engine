import requests
import json
import uuid

BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def login():
    print(f"Logging in to {BASE_URL}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        return token
    except Exception as e:
        print(f"Login failed: {e}")
        return None

def create_runbook(token, runbook_data):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Creating runbook: {runbook_data['name']}...")
    response = requests.post(
        f"{BASE_URL}/api/remediation/runbooks",
        json=runbook_data,
        headers=headers
    )
    
    if response.status_code == 201:
        print(f"Successfully created runbook. ID: {response.json()['id']}")
        return response.json()
    elif response.status_code == 409:
        print(f"Runbook exists: {runbook_data['name']}")
        return None
    else:
        print(f"Failed to create. Status: {response.status_code}")
        print(response.text)
        return None

def main():
    token = login()
    if not token: return

    # Scenario: Native Conditional Execution
    runbook_data = {
        "name": "Native Conditional Execution Test",
        "description": "Demonstrates native 'run_if' logic without shell scripts.",
        "category": "testing",
        "tags": ["feature-test", "conditional"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": False,
        "steps": [
            {
                "step_order": 1,
                "name": "Check Service",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'active'", 
                "output_variable": "svc_status",
                "output_extract_pattern": "([a-z]+)"
            },
            {
                "step_order": 2,
                "name": "Verify (Run if active)",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Verification running because status is active'",
                "run_if_variable": "svc_status",
                "run_if_value": "active"
            },
            {
                "step_order": 3,
                "name": "Recover (Run if inactive)",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Recovery running because status is inactive'",
                "run_if_variable": "svc_status",
                "run_if_value": "inactive"
            }
        ]
    }

    create_runbook(token, runbook_data)

if __name__ == "__main__":
    main()
