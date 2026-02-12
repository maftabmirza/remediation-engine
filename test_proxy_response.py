"""Test what the Grafana proxy actually returns to the browser."""
import httpx

# Simulate an authenticated browser request to the proxied Grafana page
# First, login to get a token
session = httpx.Client(follow_redirects=True, timeout=15)
login_resp = session.post(
    'http://localhost:8080/api/login',
    json={"username": "admin", "password": "admin"},
)
print("Login:", login_resp.status_code)
token = None
for cookie_name in ['access_token']:
    if cookie_name in session.cookies:
        token = session.cookies[cookie_name]
        break

if not token and login_resp.status_code == 200:
    data = login_resp.json()
    token = data.get('access_token', data.get('token'))

print("Token:", token[:20] + "..." if token else "NONE")

# Now request the Grafana page as the iframe would
headers = {}
cookies = {}
if token:
    cookies['access_token'] = token

resp = session.get(
    'http://localhost:8080/grafana/dashboards?starred',
    headers=headers,
    cookies=cookies,
)

print(f"\n--- RESPONSE ---")
print(f"Status: {resp.status_code}")
print(f"Content-Length: {len(resp.content)}")
print(f"\nResponse Headers:")
for k, v in resp.headers.items():
    print(f"  {k}: {v}")

# Check for potential issues
html = resp.text
print(f"\n--- ANALYSIS ---")
print(f"Has <base href>: {'<base href' in html}")
print(f"Has reactRoot: {'reactRoot' in html}")
print(f"Has grafanaBootData: {'grafanaBootData' in html}")

# Check if content-encoding is set but content is not actually encoded
ce = resp.headers.get('content-encoding', 'none')
print(f"Content-Encoding: {ce}")
if ce not in ('none', 'identity'):
    print(f"WARNING: Content-Encoding is '{ce}' but proxy may have decoded it without removing header!")

# Check for double content-encoding
all_ce = [v for k, v in resp.headers.raw if k.lower() == b'content-encoding']
print(f"All Content-Encoding headers: {all_ce}")

# Check content starts correctly
print(f"\nFirst 100 bytes: {resp.content[:100]}")
gz_magic = b'\x1f\x8b'
print(f"Is gzipped: {resp.content[:2] == gz_magic}")

# Try to load a JS file
js_resp = session.get('http://localhost:8080/grafana/public/build/runtime.836b8524ae0742d60550.js')
print(f"\n--- JS FILE ---")
print(f"Status: {js_resp.status_code}")
print(f"Content-Type: {js_resp.headers.get('content-type', 'missing')}")
print(f"Content-Length: {len(js_resp.content)}")
js_ce = js_resp.headers.get('content-encoding', 'none')
print(f"Content-Encoding: {js_ce}")
print(f"Is gzipped: {js_resp.content[:2] == gz_magic}")
print(f"First 50 chars: {js_resp.text[:50]}")
