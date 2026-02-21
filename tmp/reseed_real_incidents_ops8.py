import json
import time
from datetime import datetime, timedelta, timezone
import requests
import subprocess

BASE_URL = 'http://localhost:8080'
base = datetime.now(timezone.utc) - timedelta(days=1, hours=1)
services = ["Payments API", "Auth Service", "Order Processor", "Inventory Sync", "Checkout Gateway"]
summaries = [
    "Payment authorization latency spike in production",
    "Intermittent login failures for SSO users",
    "Order confirmations delayed beyond SLA",
    "Inventory mismatch between cache and primary DB",
    "Checkout timeout errors from upstream gateway",
    "API 5xx burst on customer profile service",
    "Background worker backlog causing notification delays",
    "Regional DNS resolution issues affecting service discovery",
    "Message queue lag increasing end-to-end processing time",
    "Elevated database connection saturation during peak traffic",
    "Critical alert storm from node memory pressure",
    "Webhook delivery retries exceeding threshold",
    "TLS certificate validation errors on external dependency",
    "Cache eviction spike causing read amplification",
    "Synthetic monitoring detects elevated checkout failures",
]
statuses = ["To Do", "In Progress", "Investigating", "Resolved", "Done"]
priorities = ["Highest", "High", "High", "Medium", "Low"]
severities = ["Critical", "High", "High", "Medium", "Low"]
assignees = ["Ava Patel", "Noah Kim", "Mia Chen", "Liam Ortiz", "Emma Shah"]

issues = []
for i in range(15):
    created = (base + timedelta(minutes=31 * i)).isoformat()
    status = statuses[i % len(statuses)]
    resolved = (base + timedelta(minutes=31 * i + 150)).isoformat() if status in {"Resolved", "Done"} else None
    issues.append({
        "id": str(15000 + i + 1),
        "key": f"OPS-{801 + i}",
        "fields": {
            "summary": summaries[i],
            "description": f"Realistic seeded incident for ITSM validation. Observed impact on {services[i % len(services)]}.",
            "issuetype": {"name": "Incident"},
            "status": {"name": status},
            "customfield_severity": {"value": severities[i % len(severities)]},
            "priority": {"name": priorities[i % len(priorities)]},
            "components": [{"name": services[i % len(services)]}],
            "created": created,
            "resolutiondate": resolved,
            "assignee": {"displayName": assignees[i % len(assignees)]}
        }
    })

with open('/aiops/tmp/mock-jira/issues.json', 'w', encoding='utf-8') as f:
    json.dump({"startAt": 0, "maxResults": 50, "total": len(issues), "issues": issues}, f)

subprocess.run("docker rm -f mock-jira >/dev/null 2>&1 || true", shell=True, check=False)
subprocess.run("docker run -d --name mock-jira --network aiops_aiops-network -v /aiops/tmp/mock-jira:/usr/share/nginx/html:ro nginx:alpine >/dev/null", shell=True, check=True)

for user, pwd in (("admin", "Passw0rd"), ("admin", "admin123")):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": user, "password": pwd}, timeout=20)
    if r.status_code == 200:
        token = r.json()["access_token"]
        break
else:
    raise SystemExit("auth_failed")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

config = {
  'api_config': {'base_url': 'http://mock-jira/issues.json', 'method': 'GET', 'headers': {'Accept': 'application/json'}, 'query_params': {}},
  'auth': {'type': 'none'},
  'pagination': {'type': 'none'},
  'field_mapping': {
    'change_id': '$.issues[*].key',
    'change_type': '$.issues[*].fields.issuetype.name',
    'service_name': '$.issues[*].fields.components[0].name',
    'description': '$.issues[*].fields.summary',
    'timestamp': '$.issues[*].fields.created'
  },
  'transformations': {'timestamp': {'type': 'datetime', 'format': 'iso8601'}},
  'incident_config': {
    'api_config': {'base_url': 'http://mock-jira/issues.json', 'method': 'GET', 'headers': {'Accept': 'application/json'}, 'query_params': {}},
    'auth': {'type': 'none'},
    'pagination': {'type': 'none'},
    'field_mapping': {
      'change_id': '$.issues[*].key',
      'timestamp': '$.issues[*].fields.created',
      'incident_id': '$.issues[*].key',
      'title': '$.issues[*].fields.summary',
      'description': '$.issues[*].fields.description',
      'status': '$.issues[*].fields.status.name',
      'severity': '$.issues[*].fields.customfield_severity.value',
      'priority': '$.issues[*].fields.priority.name',
      'service_name': '$.issues[*].fields.components[0].name',
      'created_at': '$.issues[*].fields.created',
      'resolved_at': '$.issues[*].fields.resolutiondate',
      'assignee': '$.issues[*].fields.assignee.displayName'
    },
    'transformations': {
      'timestamp': {'type': 'datetime', 'format': 'iso8601'},
      'created_at': {'type': 'datetime', 'format': 'iso8601'},
      'resolved_at': {'type': 'datetime', 'format': 'iso8601'}
    }
  }
}

name = f"Jira Incident Seed Realistic {int(time.time())}"
cr = requests.post(f"{BASE_URL}/api/itsm/integrations", headers=headers, json={"name": name, "connector_type": "generic_api", "is_enabled": True, "config": config}, timeout=30)
print('create_status', cr.status_code)
if cr.status_code >= 300:
    print(cr.text)
    raise SystemExit(1)
int_id = cr.json()['id']
print('integration_id', int_id)

sr = requests.post(f"{BASE_URL}/api/itsm/integrations/{int_id}/sync", headers=headers, timeout=60)
print('sync_status', sr.status_code)
print('sync_body', sr.text)

qr = requests.get(f"{BASE_URL}/api/incidents", headers=headers, params={"time_range": "7d", "search": "OPS-8", "page": 1, "page_size": 100}, timeout=30)
ops8 = [i for i in (qr.json() if qr.status_code == 200 else []) if str(i.get('incident_id','')).startswith('OPS-8')]
print('ops8_count', len(ops8))
print('contains_dummy', any('dummy' in (x.get('title','') or '').lower() for x in ops8))
print('sample_titles', [x.get('title') for x in ops8[:4]])
