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

    # Scenario: Branching Logic (Guarded Steps)
    # Goal: "if variable output is matched perform step x else perform step y"
    # Limitation: Helper engine is linear.
    # Solution: We "guard" steps X and Y with shell logic using the variable.
    
    runbook_branching = {
        "name": "Service Recovery (Branching Logic)",
        "description": "Demonstrates 'If X else Y' logic. If service is 'active', verify. If 'inactive', restart.",
        "category": "infrastructure",
        "tags": ["advanced", "branching", "if-else"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "steps": [
            {
                "step_order": 1,
                "name": "Check Service Status",
                "description": "Simulates checking status (Returns 'active' or 'inactive')",
                "step_type": "command",
                "target_os": "linux",
                # Change this echo to "inactive" to test the other branch
                "command_linux": "echo 'inactive'", 
                "output_variable": "svc_status",
                "output_extract_pattern": "([a-z]+)"
            },
            {
                "step_order": 2,
                "name": "Branch A: Verify (If Active)",
                "description": "Executes ONLY if status is 'active'",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": """
STATUS="{{ svc_status }}"
if [ "$STATUS" == "active" ]; then
    echo "Service is active. Performing verification..."
    echo "Health check passed."
else
    echo "Skipping Branch A (Condition: status!=active)"
fi
"""
            },
            {
                "step_order": 3,
                "name": "Branch B: Restart (If Inactive)",
                "description": "Executes ONLY if status is 'inactive'",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": """
STATUS="{{ svc_status }}"
if [ "$STATUS" != "active" ]; then
    echo "Service is INACTIVE. Starting recovery..."
    echo "Restarting service..."
    # systemctl restart myservice
    echo "Service restarted."
else
    echo "Skipping Branch B (Condition: status==active)"
fi
"""
            }
        ]
    }

    create_runbook(token, runbook_branching)

if __name__ == "__main__":
    main()
