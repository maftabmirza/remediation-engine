#!/usr/bin/env python3
"""
Fire Test Alert to Alertmanager

This script sends a test alert to Alertmanager that will be forwarded to the
remediation engine, triggering the NginxDown runbook.
"""

import requests
import json
import sys
from datetime import datetime, timezone

# Configuration
ALERTMANAGER_URL = "http://172.234.217.11:9093"
ALERT_NAME = "NginxDown"
INSTANCE = "t-test-01"

def fire_test_alert():
    """Send a test alert to Alertmanager."""
    
    print("="*80)
    print("Firing Test Alert to Alertmanager")
    print("="*80)
    print()
    
    # Build alert payload
    # Alertmanager expects an array of alerts
    now = datetime.now(timezone.utc).isoformat()
    
    alert = {
        "labels": {
            "alertname": ALERT_NAME,
            "severity": "critical",
            "instance": INSTANCE,
            "job": "nginx-exporter",
            "service": "nginx",
            "environment": "testing"
        },
        "annotations": {
            "summary": "Nginx is down on t-test-01",
            "description": f"Nginx service on {INSTANCE} has been down for more than 1 minute",
            "runbook_url": "http://172.234.217.11:8080/runbooks"
        },
        "startsAt": now,
        "generatorURL": "http://prometheus:9090/graph"
    }
    
    alerts_payload = [alert]
    
    print(f"Alert Details:")
    print(f"  Name: {ALERT_NAME}")
    print(f"  Severity: critical")
    print(f"  Instance: {INSTANCE}")
    print(f"  Job: nginx-exporter")
    print()
    
    # Send to Alertmanager
    print(f"Sending alert to Alertmanager at {ALERTMANAGER_URL}...")
    
    try:
        response = requests.post(
            f"{ALERTMANAGER_URL}/api/v1/alerts",
            json=alerts_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [200, 202]:
            print(f"[OK] Alert sent successfully!")
            print(f"     Status Code: {response.status_code}")
            print()
            print("Alert is now in Alertmanager. It will be forwarded to the remediation engine.")
            print()
            print("Next Steps:")
            print("1. Check Alertmanager UI: http://172.234.217.11:9093")
            print("2. Check remediation engine for triggered execution:")
            print("   http://172.234.217.11:8080/executions")
            print("3. Monitor runbook execution in real-time")
            print()
            print("The alert should trigger the 'Restart Nginx Service' runbook")
            print("which will require approval before execution.")
            
            return True
        else:
            print(f"[FAIL] Failed to send alert")
            print(f"       Status Code: {response.status_code}")
            print(f"       Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error sending alert: {e}")
        return False

def resolve_test_alert():
    """Send a resolve notification for the test alert."""
    
    print("\n" + "="*80)
    print("Resolving Test Alert")
    print("="*80)
    print()
    
    now = datetime.now(timezone.utc).isoformat()
    
    alert = {
        "labels": {
            "alertname": ALERT_NAME,
            "severity": "critical",
            "instance": INSTANCE,
            "job": "nginx-exporter",
            "service": "nginx",
            "environment": "testing"
        },
        "annotations": {
            "summary": "Nginx is down on t-test-01",
            "description": f"Nginx service on {INSTANCE} has been down for more than 1 minute",
            "runbook_url": "http://172.234.217.11:8080/runbooks"
        },
        "endsAt": now,  # This marks it as resolved
        "generatorURL": "http://prometheus:9090/graph"
    }
    
    alerts_payload = [alert]
    
    try:
        response = requests.post(
            f"{ALERTMANAGER_URL}/api/v1/alerts",
            json=alerts_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [200, 202]:
            print(f"[OK] Alert resolved successfully!")
            return True
        else:
            print(f"[FAIL] Failed to resolve alert")
            print(f"       Status Code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error resolving alert: {e}")
        return False

def check_alertmanager_config():
    """Check if Alertmanager is configured to forward to remediation engine."""
    
    print("\n" + "="*80)
    print("Checking Alertmanager Configuration")
    print("="*80)
    print()
    
    try:
        response = requests.get(f"{ALERTMANAGER_URL}/api/v1/status")
        if response.status_code == 200:
            print("[OK] Alertmanager is reachable")
            
            # Try to get config
            try:
                config_response = requests.get(f"{ALERTMANAGER_URL}/api/v1/status")
                if config_response.status_code == 200:
                    print("[OK] Alertmanager API is working")
            except:
                pass
                
        else:
            print(f"[WARN] Alertmanager returned status {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Cannot reach Alertmanager: {e}")
        print(f"\nMake sure Alertmanager is running at {ALERTMANAGER_URL}")
        print("You mentioned it's running in the docker setup.")
        return False
    
    print()
    print("IMPORTANT: Make sure the remediation engine is configured")
    print("to receive alerts from Alertmanager!")
    print()
    print("The webhook URL should be:")
    print("  http://172.234.217.11:8080/api/alerts/webhook")
    print()
    
    return True

if __name__ == "__main__":
    # Check configuration first
    if not check_alertmanager_config():
        print("\n[WARN] Proceeding anyway, but check config if alert doesn't work")
        print()
    
    # Fire the alert
    if fire_test_alert():
        print()
        input("Press Enter to resolve the alert (or Ctrl+C to keep it firing)...")
        resolve_test_alert()
        print()
        print("Alert lifecycle complete!")
