import requests
import json
import time
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def login():
    print("Logging in...", flush=True)
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"Login failed: {e}")
        return None

def execute_runbook():
    token = login()
    if not token: return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Find Runbook
    target_name = "Service Recovery (Legacy Mode vs Native) V2"
    resp = requests.get(f"{BASE_URL}/api/remediation/runbooks", headers=headers)
    runbooks = resp.json()
    target = next((r for r in runbooks if r["name"] == target_name), None)
    
    if not target:
        print(f"Runbook '{target_name}' not found!")
        return

    print(f"Found Runbook: {target['name']} (ID: {target['id']})")

    # 1.5 Find a valid server
    server_resp = requests.get(f"{BASE_URL}/api/servers", headers=headers)
    servers = server_resp.json()
    
    if not servers:
        print("No servers found. Creating a dummy server for testing...")
        create_server_resp = requests.post(
            f"{BASE_URL}/api/servers", 
            headers=headers,
            json={
                "name": "test-server-01",
                "hostname": "127.0.0.1",
                "port": 8080, # Use open port to pass validation
                "username": "root",
                "password": "password123", # Dummy
                "auth_type": "password",
                "os_type": "linux",
                "environment": "test"
            }
        )
        if create_server_resp.status_code == 201:
            server_id = create_server_resp.json()["id"]
            print(f"Created Dummy Server: {server_id}")
        else:
            print(f"Failed to create dummy server: {create_server_resp.text}")
            return
    else:
        server_id = servers[0]["id"]
        print(f"Using Server: {servers[0]['hostname']} ({server_id})")

    # 2. Execute Runbook
    print("Triggering execution...")
    exec_resp = requests.post(
        f"{BASE_URL}/api/remediation/executions",
        headers=headers,
        params={"runbook_id": target['id']},
        json={"server_id": server_id} 
    )
    
    if exec_resp.status_code not in [200, 201]:
        print(f"Failed to trigger execution: {exec_resp.text}")
        return

    execution = exec_resp.json()
    exec_id = execution["id"]
    print(f"Execution started! ID: {exec_id}")
    print("Waiting for completion...")

    # 3. Poll for status
    while True:
        status_resp = requests.get(f"{BASE_URL}/api/remediation/executions/{exec_id}", headers=headers)
        if status_resp.status_code != 200:
            print("Error polling status")
            break
        
        exec_data = status_resp.json()
        status = exec_data["status"]
        print(f"Status: {status}")
        
        if status in ["success", "failed", "cancelled", "timeout"]:
             # Print final details
            print("\n--- Execution Results ---")
            steps = exec_data.get("step_executions", [])
            steps.sort(key=lambda x: x["step_order"])
            
            for step in steps:
                print(f"[Step {step['step_order']}] {step['step_name']}")
                print(f"  Status: {step['status']}")
                if step['status'] == 'skipped':
                     print("  -> SKIPPED (Condition not met)")
                elif step['status'] == 'success':
                     print(f"  Output: {step.get('stdout', '').strip()}")
                elif step['status'] == 'failed':
                     print(f"  Error: {step.get('stderr', '').strip()}")
                print("-" * 30)
            break
        
        time.sleep(2)

if __name__ == "__main__":
    execute_runbook()
