
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
        
        for rb in runbooks:
            if "Nginx" not in rb['name']:
                continue
                
            print(f"Checking Runbook: {rb['name']} (ID: {rb['id']})")
            
            detail = session.get(f"{API_BASE_URL}/api/remediation/runbooks/{rb['id']}").json()
            triggers = detail.get('triggers', [])
            
            seen_patterns = {}
            duplicates = []
            
            for t in triggers:
                key = (t['alert_name_pattern'], t['instance_pattern'], t['severity_pattern'])
                if key in seen_patterns:
                    duplicates.append(t['id'])
                else:
                    seen_patterns[key] = t['id']
            
            unique_triggers = []
            
            for t in triggers:
                key = (t['alert_name_pattern'], t['instance_pattern'], t['severity_pattern'])
                if key in seen_patterns:
                    duplicates.append(t['id'])
                else:
                    seen_patterns[key] = t['id']
                    # Prepare for update payload (strip ID/created_at)
                    t_payload = {
                        "alert_name_pattern": t['alert_name_pattern'],
                        "instance_pattern": t['instance_pattern'],
                        "severity_pattern": t['severity_pattern'],
                        "job_pattern": t.get('job_pattern', '*'),
                        "priority": t.get('priority', 100),
                        "enabled": t.get('enabled', True)
                    }
                    unique_triggers.append(t_payload)
            
            if duplicates:
                print(f"Found {len(duplicates)} duplicate triggers.")
                print("Updating runbook with unique triggers...")
                
                # Construct update payload
                # We need to send other fields too if PUT replaces everything? 
                # Or PATCH?
                # The router code in remediation.py suggests it's a PUT that updates provided fields
                # but deletes all triggers/steps if included in payload?
                # Actually it deletes ALL triggers if 'triggers' key is present?
                # Let's assume PUT requires full fields or partial but handles triggers comprehensively.
                
                # Based on previous review of update_runbook:
                # It copies fields from runbook_data to runbook.
                # Then deletes old triggers.
                # Then creates new triggers from runbook_data.triggers.
                
                # So we must provide ALL runbook fields to avoid data loss?
                # Or does RunbookUpdate allow optional fields?
                # Usually Pydantic Update schemas have Optional fields.
                # But triggers are replaced.
                
                # Safest approach: Use data from GET, stick it into PUT.
                
                payload = detail.copy()
                payload['triggers'] = unique_triggers
                # Remove read-only fields
                for k in ['id', 'created_at', 'updated_at', 'created_by_user', 'default_server', 'executions', 'schedules', 'steps']:
                     if k in payload:
                         del payload[k]
                
                # Steps must be included or they are wiped! 
                # Step 788 code: "Delete existing steps... Create new steps"
                # So we MUST include steps too.
                
                # Re-construct steps payload
                steps_payload = []
                for s in detail.get('steps', []):
                    sp = s.copy()
                    # Remove read-only
                    for k in ['id', 'runbook_id', 'created_at', 'updated_at']:
                        if k in sp: del sp[k]
                    steps_payload.append(sp)
                payload['steps'] = steps_payload

                try:
                    res = session.put(f"{API_BASE_URL}/api/remediation/runbooks/{rb['id']}", json=payload)
                    res.raise_for_status()
                    print("  Runbook updated successfully. Duplicates removed.")
                except Exception as e:
                    print(f"  Update failed: {e}")
                    if hasattr(e, 'response') and e.response: 
                        print(e.response.text)
            else:
                print("No exact duplicates found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
