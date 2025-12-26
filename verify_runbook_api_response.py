import requests
import json

BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def login():
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

def verify_runbook():
    token = login()
    if not token: return

    # List runbooks to find the one we verify
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/api/remediation/runbooks", headers=headers)
    runbooks = resp.json()
    
    target = next((r for r in runbooks if r["name"] == "Service Recovery (Legacy Mode vs Native) V2"), None)
    
    if not target:
        print("Runbook not found in list")
        return

    # Get full details
    detail_resp = requests.get(f"{BASE_URL}/api/remediation/runbooks/{target['id']}", headers=headers)
    detail = detail_resp.json()
    
    print("\n--- Runbook Steps ---")
    for step in detail["steps"]:
        print(f"Step {step['step_order']}: {step['name']}")
        print(f"  run_if_variable: {step.get('run_if_variable')}")
        print(f"  run_if_value: {step.get('run_if_value')}")
    print("---------------------")

if __name__ == "__main__":
    verify_runbook()
