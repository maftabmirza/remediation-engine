
import requests
import time
import json
import sys

BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def get_token():
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"Failed to authenticate: {e}")
        sys.exit(1)

def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Get Runbook ID for "Demo: Regex Extraction"
    params = {"search": "Demo: Regex Extraction"}
    resp = requests.get(f"{BASE_URL}/api/remediation/runbooks", headers=headers, params=params)
    resp.raise_for_status()
    runbooks = resp.json()
    if not runbooks:
        print("Runbook not found")
        sys.exit(1)
    
    runbook_id = runbooks[0]["id"]
    print(f"Triggering Runbook: {runbooks[0]['name']} ({runbook_id})")
    
    # 1.5 Get Server
    resp = requests.get(f"{BASE_URL}/api/servers", headers=headers)
    resp.raise_for_status()
    servers = resp.json()
    if not servers:
        print("No servers found")
        sys.exit(1)
    server_id = servers[0]["id"]
    print(f"Using Server: {servers[0]['hostname']} ({server_id})")

    # 2. Trigger
    try:
        resp = requests.post(
            f"{BASE_URL}/api/remediation/executions", 
            headers=headers, 
            params={"runbook_id": runbook_id},
            json={"server_id": server_id}
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"Error triggering execution: {e}")
        print(f"Response: {resp.text}")
        sys.exit(1)
    
    exec_id = resp.json()["id"]
    print(f"Execution started: {exec_id}")
    
    # 3. Poll for completion
    for _ in range(10):
        time.sleep(2)
        resp = requests.get(f"{BASE_URL}/api/remediation/executions/{exec_id}", headers=headers)
        data = resp.json()
        status = data["status"]
        print(f"Status: {status}")
        if status in ["success", "failed"]:
            print("Execution finished.")
            if data.get("error_message"):
                print(f"Error Message: {data['error_message']}")
            # Print step outputs
            for step in data.get("step_executions", []):
                print(f"Step: {step['step_name']}")
                print(f"  Stdout: {step['stdout']}")
            break
    
if __name__ == "__main__":
    main()
