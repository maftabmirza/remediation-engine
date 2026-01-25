import requests
import json
import sys

BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

# The private key content (will be populated by the agent reading the file)
SSH_PRIVATE_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBxTn70SYhA+uf9uMAKXPt4mt2Z6Md5PUAKsXZcr/toOAAAAJj/X743/1++
NwAAAAtzc2gtZWQyNTUxOQAAACBxTn70SYhA+uf9uMAKXPt4mt2Z6Md5PUAKsXZcr/toOA
AAAEDbYA/llS8OCPLjjDbpbqFhjlKoSn9FU4aIqVumiFNannFOfvRJiED65/24wApc+3ia
3Znox3k9QAqxdlyv+2g4AAAAFW1pcnphQExBUFRPUC0wMEEwMU1QUQ==
-----END OPENSSH PRIVATE KEY-----"""

def login():
    try:
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

def get_server_id(token, hostname="t-aiops-01"):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/api/servers", headers=headers)
    resp.raise_for_status()
    for s in resp.json():
        if s["hostname"] == hostname or s["name"] == hostname:
            return s["id"]
    return None

def update_server_credentials(token, server_id, private_key):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Payload to update user to 'ubuntu' and auth method to 'ssh_key'
    payload = {
        "username": "ubuntu",
        "auth_type": "ssh_key",
        "ssh_private_key": private_key,
        "port": 22
    }
    
    # Using PATCH if supported, or PUT with all fields. 
    # Assuming the API endpoint /api/servers/{id} accepts partial updates or validation.
    # Let's try to get full object first to be safe.
    
    # API does not support GET /api/servers/{id}, so we just send the updates via PUT.
    # The API implementation handles partial updates for Optional fields.
    
    data = {
        "username": "ubuntu",
        "auth_type": "key",  # Based on ServerUpdate schema, 'key' is the standard value, not 'ssh_key'
        "ssh_key": private_key,
        "credential_source": "inline",
        "port": 22
    }
    
    print(f"Updating server {server_id} with new credentials...")
    update_resp = requests.put(f"{BASE_URL}/api/servers/{server_id}", headers=headers, json=data)
    
    if update_resp.status_code == 200:
        print("Successfully updated server credentials.")
    else:
        print(f"Failed to update: {update_resp.status_code} {update_resp.text}")

def main():
    if "key_content_here" in SSH_PRIVATE_KEY:
        print("Error: Private key placeholder not replaced.")
        return

    token = login()
    server_id = get_server_id(token, "t-aiops-01")
    if not server_id:
        print("Server t-aiops-01 not found.")
        return
        
    update_server_credentials(token, server_id, SSH_PRIVATE_KEY)

if __name__ == "__main__":
    main()
