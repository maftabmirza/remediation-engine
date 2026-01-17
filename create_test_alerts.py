import requests
import json
import time
from datetime import datetime, timezone

WEBHOOK_URL = "http://localhost:8080/webhook/alerts"

def send_alert(alert_name, severity, instance, description, summary, job="node-exporter"):
    payload = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": alert_name,
                    "severity": severity,
                    "instance": instance,
                    "job": job
                },
                "annotations": {
                    "summary": summary,
                    "description": description
                },
                "startsAt": datetime.now(timezone.utc).isoformat(),
                "fingerprint": f"{alert_name}-{instance}-{int(time.time())}"
            }
        ]
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print(f"Alert sent: {alert_name} on {instance}")
        return response.json()
    except Exception as e:
        print(f"Failed to send alert {alert_name}: {str(e)}")
        return None

if __name__ == "__main__":
    print("Sending test alerts to local API...")
    
    alerts = [
        ("HighCPUUsage", "critical", "web-server-01", "CPU usage is above 95%", "Critical CPU usage on web-server-01"),
        ("HighMemoryUsage", "warning", "db-server-01", "Memory usage is above 85%", "High memory on db-server-01"),
        ("DiskSpaceLow", "warning", "storage-01", "Disk usage is above 90%", "Low disk space on storage-01"),
        ("ServiceDown", "critical", "api-gateway", "HTTP probe failed for api-gateway", "Service down on api-gateway"),
        ("SlowQueries", "info", "db-server-01", "Slow queries detected in last 5m", "Slow queries on db-server-01")
    ]
    
    for alert in alerts:
        send_alert(*alert)
        time.sleep(0.5)
    
    print("\nDone! Check the dashboard at http://localhost:8080")
