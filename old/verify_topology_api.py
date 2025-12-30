import requests
import sys

BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def login():
    resp = requests.post(f"{BASE_URL}/api/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        sys.exit(1)
    return resp.json()["access_token"]

def verify():
    print("Logging in...")
    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create App
    print("Creating Application...")
    app_data = {
        "name": "auth-service-test",
        "display_name": "Auth Service Test",
        "criticality": "critical",
        "tech_stack": {"language": "python"}
    }
    # Check if exists first to avoid conflict in repeated runs
    list_resp = requests.get(f"{BASE_URL}/api/applications?search=auth-service-test", headers=headers)
    if list_resp.json()['items']:
        app_id = list_resp.json()['items'][0]['id']
        print(f"App already exists: {app_id}")
    else:
        resp = requests.post(f"{BASE_URL}/api/applications", json=app_data, headers=headers)
        if resp.status_code != 201:
            print(f"Failed to create app: {resp.text}")
            sys.exit(1)
        app_id = resp.json()["id"]
        print(f"Created App: {app_id}")

    # 2. Add Component
    print("Adding Component...")
    comp_data = {
        "name": "users-db",
        "component_type": "database",
        "criticality": "high"
    }
    # Check existing
    comps_resp = requests.get(f"{BASE_URL}/api/applications/{app_id}/components", headers=headers)
    existing_comp = next((c for c in comps_resp.json()['items'] if c['name'] == 'users-db'), None)
    
    if existing_comp:
        print("Component already exists")
    else:
        resp = requests.post(f"{BASE_URL}/api/applications/{app_id}/components", json=comp_data, headers=headers)
        if resp.status_code != 201:
            print(f"Failed to create component: {resp.text}")
            sys.exit(1)
        print("Component added")

    # 3. Get Graph
    print("Fetching Graph...")
    resp = requests.get(f"{BASE_URL}/api/applications/{app_id}/dependency-graph", headers=headers)
    if resp.status_code != 200:
        print(f"Failed to get graph: {resp.text}")
        sys.exit(1)
    
    graph = resp.json()
    print(f"Graph Nodes: {len(graph['nodes'])}")
    print(f"Graph Edges: {len(graph['edges'])}")
    
    if len(graph['nodes']) >= 1:
        print("SUCCESS: Topology API verified.")
    else:
        print("FAILURE: Graph empty?")

if __name__ == "__main__":
    verify()
