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

    # Scenario 1: Conditional Logic (simulated via Shell)
    # Step 1: Check a metric/value (Output Var)
    # Step 2: Use that variable in a script with 'if' logic
    runbook_conditional = {
        "name": "Disk Cleanup (Conditional Logic)",
        "description": "Checks disk usage and performs cleanup ONLY IF usage > 80%. Demonstrates conditional logic using variables.",
        "category": "infrastructure",
        "tags": ["advanced", "conditional", "maintenance"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "steps": [
            {
                "step_order": 1,
                "name": "Check Disk Usage",
                "description": "Gets usage percentage for / mount",
                "step_type": "command",
                "target_os": "linux",
                # Simulating a high value for demo purposes. Real command: df -h / | tail -1 | awk '{print $5}' | sed 's/%//'
                "command_linux": "echo '85'", 
                "output_variable": "disk_usage_percent",
                "output_extract_pattern": "(\\d+)"
            },
            {
                "step_order": 2,
                "name": "Conditional Cleanup",
                "description": "Cleans up logs if usage > 80%",
                "step_type": "command",
                "target_os": "linux",
                # The condition happens INSIDE the script using the injected variable
                "command_linux": """
THRESHOLD=80
USAGE={{ disk_usage_percent }}

echo "Checking usage: $USAGE% (Threshold: $THRESHOLD%)"

if [ "$USAGE" -gt "$THRESHOLD" ]; then
    echo "Usage matches condition ($USAGE > $THRESHOLD). Starting cleanup..."
    echo "Removing temporary files..."
    # rm -rf /tmp/junk
    echo "Cleanup complete."
else
    echo "Usage below threshold. No action needed."
fi
"""
            }
        ]
    }

    # Scenario 2: Chained API Requests (Data Flow)
    # Step 1: Create a resource (API) -> Extract ID
    # Step 2: Modify that resource (API) using ID
    runbook_chain = {
        "name": "User Onboarding Chain (API Data Flow)",
        "description": "Creates a user and immediately assigns a role using the new User ID. Demonstrates variable chaining between API steps.",
        "category": "security",
        "tags": ["advanced", "api-chain", "onboarding"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "steps": [
            {
                "step_order": 1,
                "name": "Create Temporary User",
                "step_type": "api",
                "api_endpoint": "/api/users", # Hypothetical endpoint for demo
                "api_method": "POST",
                "api_body_type": "json",
                "api_body": "{\"username\": \"temp_user_01\", \"role\": \"guest\"}",
                "output_variable": "new_user_id",
                # Extract ID from response like {"id": "123-abc", ...}
                "output_extract_pattern": "\"id\":\\s*\"([^\"]+)\""
            },
            {
                "step_order": 2,
                "name": "Assign Admin Role",
                "step_type": "api",
                # Using the extracted variable in the Endpoint URL
                "api_endpoint": "/api/users/{{ new_user_id }}/roles",
                "api_method": "POST",
                "api_body_type": "json",
                "api_body": "{\"role\": \"admin\"}",
                "api_expected_status_codes": [200, 201, 204]
            }
        ]
    }
    
    # Scenario 3: Validation Condition (Success/Fail)
    runbook_validation = {
        "name": "Config Validation (Output Condition)",
        "description": "Fails the step if the output does not match the specific condition (Regex).",
        "category": "application",
        "tags": ["advanced", "validation"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "steps": [
            {
                "step_order": 1,
                "name": "Verify Setting",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo \"app_mode=production\"",
                # This step will FAIL if the regex doesn't match stdout
                "expected_output_pattern": "app_mode=production"
            },
            {
                "step_order": 2,
                "name": "Notify Success",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo \"Configuration is correct.\""
            }
        ]
    }

    create_runbook(token, runbook_conditional)
    create_runbook(token, runbook_chain)
    create_runbook(token, runbook_validation)

if __name__ == "__main__":
    main()
