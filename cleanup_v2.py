import requests

BASE_URL = "http://localhost:8080"

# Login
r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "Passw0rd"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Get all runbooks
runbooks = requests.get(f"{BASE_URL}/api/remediation/runbooks", headers=headers).json()

# Delete V2 runbooks
for rb in runbooks:
    if "V2" in rb["name"]:
        print(f"Deleting {rb['name']} ({rb['id']})")
        requests.delete(f"{BASE_URL}/api/remediation/runbooks/{rb['id']}", headers=headers)

print("Cleanup complete")
