import json
import time
from datetime import datetime, timedelta, timezone
import requests

BASE_URL = 'http://localhost:8080'

# 1) Build realistic Jira-style payload
base = datetime.now(timezone.utc) - timedelta(days=1, hours=2)
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
    created = (base + timedelta(minutes=29 * i)).isoformat()
    status = statuses[i % len(statuses)]
    resolved = None
    if status in {"Resolved", "Done"}:
        resolved = (base + timedelta(minutes=29 * i + 160)).isoformat()

    issues.append({
        "id": str(14000 + i + 1),
        "key": f"OPS-{701 + i}",
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

payload = {"startAt": 0, "maxResults": 50, "total": len(issues), "issues": issues}
with open('/aiops/tmp/mock-jira/issues.json', 'w', encoding='utf-8') as f:
    json.dump(payload, f)
print('payload_issues', len(issues))

# 2) Ensure mock-jira container is running on app network
import subprocess
subprocess.run("docker rm -f mock-jira >/dev/null 2>&1 || true", shell=True, check=False)
subprocess.run(
    "docker run -d --name mock-jira --network aiops_aiops-network -v /aiops/tmp/mock-jira:/usr/share/nginx/html:ro nginx:alpine >/dev/null",
    shell=True,
    check=True,
)

# 3) Login
for user, pwd in (("admin", "Passw0rd"), ("admin", "admin123")):
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": user, "password": pwd}, timeout=20)
    if res.status_code == 200:
        token = res.json()["access_token"]
        break
else:
    raise SystemExit("auth_failed")

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 4) Create integration + sync
config = {
  'api_config': {
    'base_url': 'http://mock-jira/issues.json',
    'method': 'GET',
    'headers': {'Accept': 'application/json'},
    'query_params': {}
  },
  'auth': {'type': 'none'},
  'pagination': {'type': 'none'},
  'field_mapping': {
    'change_id': '$.issues[*].key',
    'change_type': '$.issues[*].fields.issuetype.name',
    'service_name': '$.issues[*].fields.components[0].name',
    'description': '$.issues[*].fields.summary',
    'timestamp': '$.issues[*].fields.created'
  },
  'transformations': {
    'timestamp': {'type': 'datetime', 'format': 'iso8601'}
  },
  'incident_config': {
    'api_config': {
      'base_url': 'http://mock-jira/issues.json',
      'method': 'GET',
      'headers': {'Accept': 'application/json'},
      'query_params': {}
    },
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

integration_name = f"Jira Incident Seed Realistic {int(time.time())}"
create_res = requests.post(
    f"{BASE_URL}/api/itsm/integrations",
    headers=headers,
    json={"name": integration_name, "connector_type": "generic_api", "is_enabled": True, "config": config},
    timeout=30,
)
print('create_integration_status', create_res.status_code)
if create_res.status_code >= 300:
    print(create_res.text)
    raise SystemExit(1)

integration_id = create_res.json()['id']
print('integration_id', integration_id)

sync_res = requests.post(f"{BASE_URL}/api/itsm/integrations/{integration_id}/sync", headers=headers, timeout=60)
print('sync_status', sync_res.status_code)
print('sync_body', sync_res.text)
if sync_res.status_code >= 300:
    raise SystemExit(1)

query_res = requests.get(
    f"{BASE_URL}/api/incidents",
    headers=headers,
    params={"time_range": "7d", "search": "OPS-7", "page": 1, "page_size": 100},
    timeout=30,
)
print('query_status', query_res.status_code)
incidents = query_res.json() if query_res.status_code == 200 else []
ops7 = [i for i in incidents if str(i.get('incident_id', '')).startswith('OPS-7')]
print('ops7_count', len(ops7))
print('sample_titles', [i.get('title') for i in ops7[:5]])
print('contains_dummy_word', any('dummy' in (i.get('title','') or '').lower() for i in ops7))
