#!/usr/bin/env python3
"""
Diagnostic: Check Runbook and Trigger Configuration

Helps debug why alerts aren't triggering runbook executions.
"""

import requests
import json
import sys

API_BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def login():
    """Login and get token."""
    session = requests.Session()
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
            return session
    except Exception as e:
        print(f"[FAIL] Login failed: {e}")
        sys.exit(1)

def check_runbooks(session):
    """Check runbook configuration."""
    print("="*80)
    print("Checking Runbooks")
    print("="*80)
    
    try:
        response = session.get(f"{API_BASE_URL}/api/remediation/runbooks")
        response.raise_for_status()
        runbooks = response.json()
        
        nginx_runbooks = [r for r in runbooks if "nginx" in r.get("name", "").lower()]
        
        if not nginx_runbooks:
            print("\n[WARN] No Nginx runbooks found!")
            return
        
        for rb in nginx_runbooks:
            print(f"\nRunbook: {rb.get('name')}")
            print(f"  ID: {rb.get('id')}")
            print(f"  Enabled: {rb.get('enabled')}")
            print(f"  Auto Execute: {rb.get('auto_execute')}")
            print(f"  Approval Required: {rb.get('approval_required')}")
            print(f"  Category: {rb.get('category')}")
            print(f"  Max Executions/Hour: {rb.get('max_executions_per_hour')}")
            print(f"  Cooldown Minutes: {rb.get('cooldown_minutes')}")
            
            # Check triggers
            print(f"\n  Triggers:")
            if rb.get('triggers'):
                for trigger in rb['triggers']:
                    print(f"    - ID: {trigger.get('id')}")
                    print(f"      Alert Name Pattern: {trigger.get('alert_name_pattern')}")
                    print(f"      Severity Pattern: {trigger.get('severity_pattern')}")
                    print(f"      Instance Pattern: {trigger.get('instance_pattern')}")
                    print(f"      Job Pattern: {trigger.get('job_pattern')}")
                    print(f"      Priority: {trigger.get('priority')}")
                    print(f"      Enabled: {trigger.get('enabled')}")
                    print()
            else:
                print("    [WARN] No triggers configured!")
        
    except Exception as e:
        print(f"[FAIL] Failed to check runbooks: {e}")
        import traceback
        traceback.print_exc()

def check_latest_alert(session):
    """Check the latest NginxDown alert details."""
    print("="*80)
    print("Checking Latest Alert Details")
    print("="*80)
    
    try:
        response = session.get(f"{API_BASE_URL}/api/alerts?limit=10")
        response.raise_for_status()
        alerts_data = response.json()
        
        if isinstance(alerts_data, dict):
            alerts = alerts_data.get('alerts', [])
        else:
            alerts = alerts_data
        
        nginx_alerts = [a for a in alerts if isinstance(a, dict) and "nginx" in a.get("alert_name", "").lower()]
        
        if not nginx_alerts:
            print("\n[WARN] No Nginx alerts found")
            return
        
        latest = nginx_alerts[0]
        print(f"\nLatest NginxDown Alert:")
        print(f"  ID: {latest.get('id')}")
        print(f"  Alert Name: {latest.get('alert_name')}")
        print(f"  Severity: {latest.get('severity')}")
        print(f"  Instance: {latest.get('instance')}")
        print(f"  Job: {latest.get('job')}")
        print(f"  Status: {latest.get('status')}")
        print(f"  Action: {latest.get('action_taken')}")
        print(f"  Received: {latest.get('timestamp')}")
        
        # Check labels
        labels = latest.get('labels_json', {})
        print(f"\n  Labels:")
        if labels:
            for key, value in labels.items():
                print(f"    {key}: {value}")
        else:
            print("    [No labels]")
        
    except Exception as e:
        print(f"[FAIL] Failed to check alert: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main diagnostic function."""
    print("="*80)
    print("Runbook Trigger Diagnostic")
    print("="*80)
    print()
    
    session = login()
    
    check_runbooks(session)
    check_latest_alert(session)
    
    print("\n" + "="*80)
    print("Diagnostic Summary")
    print("="*80)
    print()
    print("Check if:")
    print("1. Runbook is enabled: true")
    print("2. Trigger is enabled: true")
    print("3. Alert name 'NginxDown' matches pattern 'NginxDown*'")
    print("4. Instance 't-test-01' matches pattern (check above)")
    print("5. Auto-execute or approval required is configured")
    print()
    print("If all checks pass but no execution is created,")
    print("check the server logs for trigger matching details:")
    print("  ssh aftab@172.234.217.11 'docker logs remediation-engine --tail 200 | grep -i trigger'")
    print()

if __name__ == "__main__":
    main()
