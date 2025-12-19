#!/usr/bin/env python3
"""
Add Missing Triggers to Nginx Runbook

The runbook was created but triggers weren't persisted.
This script adds the triggers separately.
"""

import requests
import json
import sys

API_BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def main():
    """Add triggers to Nginx runbook."""
    
    session = requests.Session()
    
    # Login
    print("Step 1: Logging in...")
    try:
        response = session.post(
            f"{API_BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
            print("[OK] Logged in")
        else:
            print("[FAIL] No token received")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Login failed: {e}")
        sys.exit(1)
    
    # Find the Nginx runbook
    print("\nStep 2: Finding Nginx runbook...")
    try:
        response = session.get(f"{API_BASE_URL}/api/remediation/runbooks")
        response.raise_for_status()
        runbooks = response.json()
        
        nginx_runbook = None
        for rb in runbooks:
            if "nginx" in rb.get("name", "").lower():
                nginx_runbook = rb
                break
        
        if not nginx_runbook:
            print("[FAIL] Nginx runbook not found")
            sys.exit(1)
        
        runbook_id = nginx_runbook["id"]
        print(f"[OK] Found runbook: {nginx_runbook['name']} (ID: {runbook_id})")
    except Exception as e:
        print(f"[FAIL] Failed to find runbook: {e}")
        sys.exit(1)
    
    # Create triggers
    print("\nStep 3: Adding triggers...")
    
    triggers = [
        {
            "runbook_id": runbook_id,
            "alert_name_pattern": "NginxDown*",
            "severity_pattern": "*",
            "instance_pattern": "t-test-01*",
            "job_pattern": "*",
            "priority": 80,
            "enabled": True
        },
        {
            "runbook_id": runbook_id,
            "alert_name_pattern": "*nginx*",
            "severity_pattern": "critical",
            "instance_pattern": "t-test-01*",
            "job_pattern": "*",
            "priority": 85,
            "enabled": True
        }
    ]
    
    created_triggers = []
    for i, trigger_data in enumerate(triggers, 1):
        try:
            response = session.post(
                f"{API_BASE_URL}/api/remediation/runbooks/{runbook_id}/triggers",
                json=trigger_data
            )
            response.raise_for_status()
            trigger = response.json()
            created_triggers.append(trigger)
            print(f"[OK] Created trigger {i}: {trigger_data['alert_name_pattern']} (ID: {trigger.get('id')})")
        except Exception as e:
            print(f"[WARN] Failed to create trigger {i}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"  Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    print(f"  Response: {e.response.text}")
    
    print(f"\n{'='*80}")
    print(f"Summary: Created {len(created_triggers)} trigger(s)")
    print(f"{'='*80}")
    print()
    print("Triggers added successfully!")
    print()
    print("Now test the alert:")
    print("  python fire_test_alert.py")
    print()

if __name__ == "__main__":
    main()
