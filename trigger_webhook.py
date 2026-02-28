import asyncio
import json
import httpx
import uuid
from datetime import datetime, timezone

WEBHOOK_URL = "http://localhost:8080/webhook/alerts"

async def main():
    alert_id = str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).isoformat(timespec='seconds') + "Z"

    ALERT_PAYLOAD = {
        "receiver": "webhook",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "ApacheDown",
                    "severity": "critical",
                    "instance": "15.204.233.209:9117",
                    "job": "apache-exporter"
                },
                "annotations": {
                    "summary": "Apache Service Down",
                    "description": "Apache web server is down on 15.204.233.209:9117"
                },
                "startsAt": current_time,
                "endsAt": None,
                "generatorURL": "http://prometheus:9090/graph?g0.expr=apache_up%20%3D%3D%200",
                "fingerprint": "a1b2c3d4e5f6",
                "id": alert_id  # Unique ID
            }
        ],
        "groupLabels": {
            "alertname": "ApacheDown"
        },
        "commonLabels": {
            "alertname": "ApacheDown",
            "severity": "critical"
        },
        "commonAnnotations": {
            "summary": "Apache is down on t-aiops-01"
        },
        "externalURL": "http://alertmanager:9093",
        "version": "4",
        "groupKey": "{}:{alertname=\"ApacheDown\"}",
        "truncatedAlerts": 0
    }

    print(f"Sending webhook with Alert ID: {alert_id}...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(WEBHOOK_URL, json=ALERT_PAYLOAD)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error sending webhook: {e}")

if __name__ == "__main__":
    asyncio.run(main())
