
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

    # Get Runbook
    try:
        response = session.get(f"{API_BASE_URL}/api/remediation/runbooks")
        runbooks = response.json()
        target_rb = None
        for rb in runbooks:
            if "Restart Nginx" in rb['name']:
                target_rb = rb
                break
        
        if not target_rb:
            print("Runbook not found.")
            sys.exit(1)

        print(f"Restoring triggers for: {target_rb['name']} (ID: {target_rb['id']})")
        
        # Get full detail (for steps)
        detail = session.get(f"{API_BASE_URL}/api/remediation/runbooks/{target_rb['id']}").json()
        
        # New Triggers (Deduplicated)
        new_triggers = [
            {
                "alert_name_pattern": "NginxDown*",
                "severity_pattern": "*",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 80,
                "enabled": True
            },
            {
                "alert_name_pattern": "*nginx*",
                "severity_pattern": "critical",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 85,
                "enabled": True
            }
        ]
        
        # Construct payload
        payload = detail.copy()
        
        # Remove read-only
        for k in ['id', 'created_at', 'updated_at', 'created_by_user', 'default_server', 'executions', 'schedules']:
             if k in payload: del payload[k]

        # Prepare steps
        steps_payload = []
        for s in detail.get('steps', []):
            sp = s.copy()
            for k in ['id', 'runbook_id', 'created_at', 'updated_at']:
                if k in sp: del sp[k]
            steps_payload.append(sp)
            
        payload['steps'] = steps_payload
        payload['triggers'] = new_triggers
        
        # Update
        res = session.put(f"{API_BASE_URL}/api/remediation/runbooks/{target_rb['id']}", json=payload)
        res.raise_for_status()
        print("Triggers restored successfully.")
        
    except Exception as e:
        print(f"Failed: {e}")
        if hasattr(e, 'response') and e.response:
            print(e.response.text)

if __name__ == "__main__":
    main()
