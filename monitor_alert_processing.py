#!/usr/bin/env python3
"""
Monitor Alert Processing

Checks if the alert was received and if a runbook execution was triggered.
"""

import requests
import json
import sys
import time

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

def check_alerts(session):
    """Check recent alerts."""
    print("\n" + "="*80)
    print("Checking Recent Alerts")
    print("="*80)
    
    try:
        response = session.get(f"{API_BASE_URL}/api/alerts?limit=10")
        response.raise_for_status()
        alerts_data = response.json()
        
        # Handle both list and dict responses
        if isinstance(alerts_data, dict):
            alerts = alerts_data.get('alerts', [])
        elif isinstance(alerts_data, list):
            alerts = alerts_data
        else:
            alerts = []
        
        nginx_alerts = [a for a in alerts if isinstance(a, dict) and "nginx" in a.get("alert_name", "").lower()]
        
        if nginx_alerts:
            print(f"\n[OK] Found {len(nginx_alerts)} Nginx-related alert(s):")
            for alert in nginx_alerts:
                print(f"\n  Alert: {alert.get('alert_name')}")
                print(f"  Severity: {alert.get('severity')}")
                print(f"  Status: {alert.get('status')}")
                print(f"  Instance: {alert.get('instance')}")
                print(f"  Received: {alert.get('timestamp')}")
                print(f"  Action: {alert.get('action_taken')}")
        else:
            print("\n[INFO] No Nginx-related alerts found yet.")
            print("       The alert may still be in transit from Alertmanager.")
        
        return nginx_alerts
    except Exception as e:
        print(f"[FAIL] Failed to get alerts: {e}")
        import traceback
        traceback.print_exc()
        return []

def check_executions(session):
    """Check recent runbook executions."""
    print("\n" + "="*80)
    print("Checking Recent Executions")
    print("="*80)
    
    try:
        response = session.get(f"{API_BASE_URL}/api/remediation/executions?limit=10")
        response.raise_for_status()
        executions = response.json()
        
        nginx_executions = [e for e in executions if "nginx" in e.get("runbook_name", "").lower()]
        
        if nginx_executions:
            print(f"\n[OK] Found {len(nginx_executions)} Nginx runbook execution(s):")
            for execution in nginx_executions:
                print(f"\n  Runbook: {execution.get('runbook_name')}")
                print(f"  Status: {execution.get('status')}")
                print(f"  Mode: {execution.get('execution_mode')}")
                print(f"  Dry Run: {execution.get('dry_run')}")
                print(f"  Server: {execution.get('server_hostname')}")
                print(f"  Queued: {execution.get('queued_at')}")
                print(f"  Steps: {execution.get('steps_completed')}/{execution.get('steps_total')}")
                
                if execution.get('status') == 'pending':
                    print(f"\n  ⚠️  WAITING FOR APPROVAL")
                    print(f"      Approve at: {API_BASE_URL}/executions")
                elif execution.get('status') == 'running':
                    print(f"\n  ⏳ RUNNING")
                elif execution.get('status') == 'success':
                    print(f"\n  ✅ SUCCESS")
                elif execution.get('status') == 'failed':
                    print(f"\n  ❌ FAILED: {execution.get('error_message')}")
        else:
            print("\n[INFO] No Nginx runbook executions found yet.")
            print("       Check if:")
            print("       1. Alertmanager forwarded the alert to the webhook")
            print("       2. The trigger pattern matches the alert")
            print("       3. The runbook is enabled")
        
        return nginx_executions
    except Exception as e:
        print(f"[FAIL] Failed to get executions: {e}")
        return []

def main():
    """Main monitoring function."""
    print("="*80)
    print("Alert Processing Monitor")
    print("="*80)
    print()
    print("Checking if the NginxDown alert triggered a runbook execution...")
    
    session = login()
    
    # Check alerts
    alerts = check_alerts(session)
    
    # Check executions
    executions = check_executions(session)
    
    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    
    if alerts:
        print(f"\n[OK] Alert received: {len(alerts)} Nginx alert(s)")
    else:
        print(f"\n[WARN] No Nginx alerts found")
        print("   Possible reasons:")
        print("   - Alert still in transit")
        print("   - Webhook not configured in Alertmanager")
        print("   - Check Alertmanager logs")
    
    if executions:
        print(f"[OK] Execution triggered: {len(executions)} execution(s)")
        
        for ex in executions:
            if ex.get('status') == 'pending':
                print(f"\n[NEXT] Next Step: Approve the execution")
                print(f"   URL: {API_BASE_URL}/executions")
                print(f"   Or use API to approve")
    else:
        print(f"[WARN] No executions triggered")
        print("   Possible reasons:")
        print("   - Alert pattern doesn't match trigger")
        print("   - Runbook is disabled")
        print("   - Trigger is disabled")
        print("   - Circuit breaker is open")
    
    print("\n" + "="*80)
    print("Monitoring Links")
    print("="*80)
    print(f"\nAlertmanager: http://172.234.217.11:9093")
    print(f"Alerts: {API_BASE_URL}/alerts")
    print(f"Executions: {API_BASE_URL}/executions")
    print(f"Runbooks: {API_BASE_URL}/runbooks")
    print()

if __name__ == "__main__":
    main()
