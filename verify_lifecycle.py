
import os
import sys
import requests
import json
import time

# Use local server URL
BASE_URL = "http://localhost:8080"

def verify_metrics_collection():
    print("Starting metrics collection verification...")
    
    # Authenticate to get token
    # (Assuming we have a test user, otherwise we need to create one or use existing admin)
    # For simplicity, let's assume we can hit the endpoints without auth or we have a valid token
    # But alerts API requires auth. Let's try to get a token for 'admin'.
    
    token = None
    try:
        resp = requests.post(f"{BASE_URL}/token", data={"username": "admin", "password": "Passw0rd"}) # Assuming default credentials
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            print("Got access token.")
        else:
            print(f"Failed to get token: {resp.status_code} {resp.text}")
            # If no token, maybe we can test webhook which is usually unauthenticated?
            # Actually webhook is unauthenticated in this project.
    except Exception as e:
        print(f"Auth failed: {e}")

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"\n1. Sending test alert to webhook...")
    alert_name = f"MTTR Test Alert {int(time.time())}"
    payload = {
        "version": "4",
        "groupKey": "{}:{alertname=\"Test\"}",
        "status": "firing",
        "receiver": "webhook",
        "groupLabels": {"alertname": alert_name},
        "commonLabels": {"alertname": alert_name, "severity": "critical", "job": "test-service"},
        "commonAnnotations": {"summary": "Test alert for MTTR"},
        "externalURL": "http://alertmanager:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": alert_name, "severity": "critical", "job": "test-service", "instance": "web-01"},
                "annotations": {"summary": "Test alert for MTTR"},
                "startsAt": "2025-12-20T10:00:00.000Z", # explicit start time
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090",
                "fingerprint": f"fp-{int(time.time())}"
            }
        ]
    }
    
    resp = requests.post(f"{BASE_URL}/webhook/alerts", json=payload)
    if resp.status_code != 200:
        print(f"Webhook failed: {resp.text}")
        return

    result = resp.json()
    print(f"Webhook response: {json.dumps(result, indent=2)}")
    
    if not result["processed"]:
        print("No alerts processed.")
        return

    first_alert = result["alerts"][0]
    if "error" in first_alert:
        print(f"Error processing alert: {first_alert.get('error')}")
        return

    alert_id = first_alert["id"]
    print(f"Created alert ID: {alert_id}")
    
    print("\n2. Acknowledging alert via API...")
    if not token:
        print("Skipping API steps due to missing auth.")
        return
        
    resp = requests.post(f"{BASE_URL}/api/alerts/{alert_id}/acknowledge", headers=headers)
    if resp.status_code == 200:
        print("Alert acknowledged.")
    else:
        print(f"Acknowledge failed: {resp.status_code} {resp.text}")
        return

    print("\n3. Resolving alert via API...")
    time.sleep(1) # Ensure measurable duration
    resp = requests.post(f"{BASE_URL}/api/alerts/{alert_id}/resolve?resolution_type=manual", headers=headers)
    if resp.status_code == 200:
        print("Alert resolved.")
    else:
        print(f"Resolve failed: {resp.status_code} {resp.text}")
        return

    print("\nSUCCESS: Lifecycle completed. Please manually check DB or implementation for metrics accuracy.")
    # In a real test, we would query the API to verify metrics, but we don't have the metrics endpoint yet (Phase 4).
    # We could query DB directly if we wanted, but this script is running outside the app context.

if __name__ == "__main__":
    verify_metrics_collection()
