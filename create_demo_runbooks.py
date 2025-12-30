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
        print("Login successful.")
        return token
    except Exception as e:
        print(f"Login failed: {e}")
        # Try finding if port is different or service is down
        return None

def create_runbook(token, runbook_data):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Check if exists first to avoid conflict (by name)
    # Ideally search but for now just try create and handle 409
    
    print(f"Creating runbook: {runbook_data['name']}...")
    response = requests.post(
        f"{BASE_URL}/api/remediation/runbooks",
        json=runbook_data,
        headers=headers
    )
    
    if response.status_code == 201:
        print(f"Successfully created runbook: {runbook_data['name']}")
        return response.json()
    elif response.status_code == 409:
        print(f"Runbook {runbook_data['name']} already exists. Skipping.")
        return None
    else:
        print(f"Failed to create runbook. Status: {response.status_code}")
        print(response.text)
        return None

def main():
    token = login()
    if not token:
        print("Aborting.")
        return

    # Runbook 1: API Extraction Demo
    runbook1 = {
        "name": "API Health Check (Extraction Demo)",
        "description": "Demonstrates extracting variables from API response and using them.",
        "category": "application",
        "tags": ["demo", "api", "health"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "steps": [
            {
                "step_order": 1,
                "name": "Check Service Health",
                "description": "Calls API to check health status",
                "step_type": "api",
                "api_endpoint": "/api/health",
                "api_method": "GET",
                "api_expected_status_codes": [200],
                "output_variable": "service_status",
                "output_extract_pattern": "\"status\":\\s*\"([^\"]+)\"" 
            },
            {
                "step_order": 2,
                "name": "Log Status",
                "description": "Logs the extracted status",
                "step_type": "command",
                "target_os": "linux",
                # Note: The usage of variable depends on how the backend replaces it. 
                # runbook_form.html suggests Jinja2: {{ service_status }}
                "command_linux": "echo \"Service status is: {{ service_status }}\"",
                "output_variable": "log_output"
            }
        ],
        "triggers": []
    }

    # Runbook 2: Conditional/Variable Demo
    runbook2 = {
        "name": "Process Remediation (Variable Demo)",
        "description": "Finds a process ID and kills it (simulation).",
        "category": "infrastructure",
        "tags": ["demo", "variables", "process"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "steps": [
            {
                "step_order": 1,
                "name": "Find Nginx PID",
                "description": "Simulate getting PID via API (using echo for demo)",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo '{\"pid\": 12345, \"name\": \"nginx\"}'",
                "output_variable": "process_info",
                "output_extract_pattern": "\"pid\":\\s*(\\d+)"
            },
            {
                "step_order": 2,
                "name": "Restart Process",
                "description": "Uses the extracted PID",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo \"Killing process {{ process_info }}\" && echo \"Restarting...\""
            }
        ],
        "triggers": []
    }

    create_runbook(token, runbook1)
    create_runbook(token, runbook2)

if __name__ == "__main__":
    main()
