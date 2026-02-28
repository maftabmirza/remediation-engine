
import requests

GRAFANA_URL = "http://localhost:8080/grafana/dashboards?orgId=1"
# We need an auth cookie or header if we were outside, but here we can rely on the proxy handling the internal call? 
# Wait, I need to call the PROXY from the outside (localhost:8080) to see what the browser sees.
# I need to simulate being a user.

S_URL = "http://localhost:8080/login"
API_URL = "http://localhost:8080/grafana/dashboards?orgId=1"

# Since I can't easily login via script without credentials (well I have admin/admin123 in docker-compose), 
# I will try to hit the internal container directly first to see what Grafana returns, 
# and then hit the proxy if possible (but I need a JWT).

# Actually, I can use the `check_url` script I made earlier but adapted to run inside the container 
# and hit the INTERNAL Grafana first, then maybe I can try to use a mock user header if I call the proxy function directly? 
# No, easier to just check internal grafana first.

import os
import sys

def check_internal_grafana():
    url = "http://grafana:3000/grafana/dashboards?orgId=1"
    headers = {"X-WEBAUTH-USER": "admin"} # Simulate what proxy sends
    print(f"--- Requesting Internal {url} ---")
    try:
        r = requests.get(url, headers=headers, allow_redirects=False)
        print(f"Status: {r.status_code}")
        print(f"Headers: {r.headers}")
        print(f"Content Length: {len(r.text)}")
        print(f"Content Preview: {r.text[:500]!r}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_internal_grafana()
