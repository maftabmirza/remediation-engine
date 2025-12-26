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
    
    # Check if exists and delete
    list_resp = requests.get(f"{BASE_URL}/api/remediation/runbooks?search={runbook_data['name']}", headers=headers)
    if list_resp.status_code == 200:
        for rb in list_resp.json():
            if rb["name"] == runbook_data["name"]:
                print(f"Deleting existing runbook: {rb['id']}")
                requests.delete(f"{BASE_URL}/api/remediation/runbooks/{rb['id']}", headers=headers)
    
    response = requests.post(
        f"{BASE_URL}/api/remediation/runbooks",
        json=runbook_data,
        headers=headers
    )
    
    if response.status_code == 201:
        print(f"Successfully created: {runbook_data['name']}")
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

    # Scenario: Native Conditional Logic
    # This runbook relies on the Engine to skip steps, not shell scripts.
    
    runbook_data = {
        "name": "Service Recovery (Legacy Mode vs Native)",
        "description": "Demonstrates native conditionals. Step 2 only runs if service is inactive.",
        "category": "infrastructure",
        "tags": ["native-conditions", "demo"],
        "enabled": True,
        "auto_execute": False,
        "steps": [
            {
                "step_order": 1,
                "name": "Check Service Status",
                "description": "Checks if service is running. Returns 'inactive' for demo.",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'inactive'", 
                "output_variable": "current_status",
                "output_extract_pattern": "([a-z]+)"
            },
            {
                "step_order": 2,
                "name": "Restart Service (Native Condition)",
                "description": "This step runs ONLY if current_status == 'inactive'",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Service restarted successfully.'",
                # Native Conditional Fields
                "run_if_variable": "current_status",
                "run_if_value": "inactive"
            },
            {
                "step_order": 3,
                "name": "Verify Healthy (Native Condition)",
                "description": "This step runs ONLY if current_status == 'active'",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Service is healthy.'",
                # Native Conditional Fields
                "run_if_variable": "current_status",
                "run_if_value": "active"
            }
        ]
    }

    create_runbook(token, runbook_data)

if __name__ == "__main__":
    main()
