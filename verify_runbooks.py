
import requests
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

def verify_runbook(token, runbook_id):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"\n--- Verifying Runbook: {runbook_id} ---")
    try:
        resp = requests.get(f"{BASE_URL}/api/remediation/runbooks/{runbook_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        print(f"Name: {data.get('name')}")
        for step in data.get("steps", []):
            print(f"  Step {step['step_order']}: {step['name']}")
            print(f"    Type: {step['step_type']}")
            print(f"    Output Variable: {step.get('output_variable')}")
            print(f"    Extract Pattern: {step.get('output_extract_pattern')}")
    except Exception as e:
        print(f"Error fetching runbook: {e}")

def main():
    token = get_token()
    verify_runbook(token, "40c03e21-b2fd-4301-9d32-33b33fe12b04")
    verify_runbook(token, "2d8b94f0-c200-4878-8fdf-320a5a6b2c5b")

if __name__ == "__main__":
    main()
