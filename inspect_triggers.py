
import requests
import json
import sys

API_BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def main():
    session = requests.Session()
    
    # Login
    try:
        response = session.post(
            f"{API_BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    # Get Runbooks
    try:
        response = session.get(f"{API_BASE_URL}/api/remediation/runbooks")
        response.raise_for_status()
        runbooks = response.json()
        
        print(f"Found {len(runbooks)} runbooks.")
        
        for rb in runbooks:
            print(f"\nRunbook: {rb['name']} (ID: {rb['id']})")
            # Fetch detail
            try:
                detail = session.get(f"{API_BASE_URL}/api/remediation/runbooks/{rb['id']}").json()
                triggers = detail.get('triggers', [])
                print(f"Triggers ({len(triggers)}):")
                for t in triggers:
                    print(f"  - ID: {t['id']}")
                    print(f"    Pattern: {t['alert_name_pattern']}")
            except Exception as e:
                print(f"  Failed to get detail: {e}")
    except Exception as e:
        print(f"Failed to get runbooks: {e}")

if __name__ == "__main__":
    main()
