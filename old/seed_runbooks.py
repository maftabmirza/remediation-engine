
import requests
import json

BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def get_token():
    print(f"Authenticating to {BASE_URL}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"Failed to authenticate: {e}")
        return None

def create_runbook(token, runbook_data):
    print(f"Creating runbook: {runbook_data['name']}...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/remediation/runbooks",
            headers=headers,
            json=runbook_data
        )
        if response.status_code == 200 or response.status_code == 201:
            print(f"Successfully created '{runbook_data['name']}'")
        else:
            print(f"Failed to create '{runbook_data['name']}': {response.text}")
    except Exception as e:
        print(f"Error creating runbook: {e}")

def create_or_update_runbook(token, runbook_data):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    name = runbook_data["name"]
    # 1. Search for existing runbook
    try:
        response = requests.get(
            f"{BASE_URL}/api/remediation/runbooks",
            headers=headers,
            params={"search": name}
        )
        response.raise_for_status()
        runbooks = response.json()
        
        existing_id = None
        for rb in runbooks:
            if rb["name"] == name:
                existing_id = rb["id"]
                break
        
        if existing_id:
            print(f"Updating existing runbook: {name} ({existing_id})...")
            resp = requests.put(
                f"{BASE_URL}/api/remediation/runbooks/{existing_id}",
                headers=headers,
                json=runbook_data
            )
            if resp.status_code == 200:
                print(f"Successfully updated '{name}'")
            else:
                print(f"Failed to update '{name}': {resp.text}")
        else:
            print(f"Creating new runbook: {name}...")
            resp = requests.post(
                f"{BASE_URL}/api/remediation/runbooks",
                headers=headers,
                json=runbook_data
            )
            if resp.status_code == 200 or resp.status_code == 201:
                print(f"Successfully created '{name}'")
            else:
                print(f"Failed to create '{name}': {resp.text}")

    except Exception as e:
        print(f"Error processing runbook {name}: {e}")

def main():
    token = get_token()
    if not token:
        return

    # Scenario 1: Simple Variable Passing
    runbook1_name = "Demo: Simple Variable Passing"
    runbook1 = {
        "name": runbook1_name,
        "description": "Demonstrates passing a simple output variable from one step to another.",
        "category": "infrastructure",
        "tags": ["demo", "variables"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": False,
        "target_os_filter": ["linux"],
        "steps": [
            {
                "step_order": 1,
                "name": "Generate Value",
                "interaction_type": "command",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Hello_World_Value'",
                "output_variable": "my_val"
            },
            {
                "step_order": 2,
                "name": "Use Value",
                "interaction_type": "command",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'The value from step 1 is: {{ my_val }}'"
            }
        ],
        "triggers": []
    }

    # Scenario 2: Regex Extraction
    runbook2_name = "Demo: Regex Extraction"
    runbook2 = {
        "name": runbook2_name,
        "description": "Demonstrates extracting a Process ID using Regex and using it in a subsequent step.",
        "category": "infrastructure",
        "tags": ["demo", "regex", "variables"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": False,
        "target_os_filter": ["linux"],
        "steps": [
            {
                "step_order": 1,
                "name": "Simulate Process output",
                "interaction_type": "command",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Process [nginx] running with PID: 8877 status: active'",
                "output_variable": "nginx_pid",
                "output_extract_pattern": r"PID: (\d+)"
            },
            {
                "step_order": 2,
                "name": "Simulate Kill",
                "interaction_type": "command",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Would kill process {{ nginx_pid }}'"
            }
        ],
        "triggers": []
    }

    # Scenario 3: Automatic Step Context
    runbook3_name = "Demo: Automatic Step Context"
    runbook3 = {
        "name": runbook3_name,
        "description": "Demonstrates accessing step output automatically without defining variables.",
        "category": "infrastructure",
        "tags": ["demo", "context"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": False,
        "target_os_filter": ["linux"],
        "steps": [
            {
                "step_order": 1,
                "name": "Get Uptime",
                "interaction_type": "command",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "uptime"
            },
            {
                "step_order": 2,
                "name": "Log Uptime",
                "interaction_type": "command",
                "step_type": "command",
                "target_os": "linux",
                "command_linux": "echo 'Previous step said: {{ steps.Get_Uptime.stdout }}'"
            }
        ],
        "triggers": []
    }

    create_or_update_runbook(token, runbook1)
    create_or_update_runbook(token, runbook2)
    create_or_update_runbook(token, runbook3)

if __name__ == "__main__":
    main()
