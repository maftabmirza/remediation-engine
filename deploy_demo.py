
import base64
import subprocess
import time

# The Bash script to run on the Lab VM
BASH_SCRIPT = r"""#!/bin/bash
set -e
# Install jq if needed
if ! command -v jq &> /dev/null; then
    sudo apt-get update && sudo apt-get install -y jq
fi

echo "Environment Prep Complete"

# 1. Login to Remediation Engine
echo "Logging in..."
LOGIN_RES=$(curl -s -v -X POST http://127.0.0.1:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Passw0rd"}')
  
TOKEN=$(echo "$LOGIN_RES" | jq -r .access_token)

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "Failed to get token. Response:"
    echo "$LOGIN_RES"
    exit 1
fi
echo "Got Token"

# 2. Get Private Key from Container
echo "Fetching Key..."
KEY=$(docker exec remediation-engine cat /home/appuser/.ssh/id_rsa)
# Safely format for JSON
KEY_JSON=$(jq -n --arg k "$KEY" '$k')

# 3. Create Server Credential
SERVER_NAME="Lab Host $(date +%s)"
# Use jq to build payload safely
SERVER_PAYLOAD=$(jq -n \
  --arg name "$SERVER_NAME" \
  --arg host "15.204.244.73" \
  --arg user "ubuntu" \
  --arg key "$KEY" \
  '{name: $name, hostname: $host, username: $user, auth_type: "key", ssh_key: $key}')

echo "Creating Server..."
SERVER_RES=$(curl -s -X POST http://127.0.0.1:8080/api/servers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$SERVER_PAYLOAD")

SERVER_ID=$(echo $SERVER_RES | jq -r .id)
echo "Server ID: $SERVER_ID"

if [ -z "$SERVER_ID" ] || [ "$SERVER_ID" == "null" ]; then
    echo "Failed to create server: $SERVER_RES"
    exit 1
fi

# 4. Create Runbook
RB_NAME="Auto Fix Nginx $(date +%s)"
RB_PAYLOAD=$(jq -n \
  --arg name "$RB_NAME" \
  --arg sid "$SERVER_ID" \
  '{name: $name, enabled: true, auto_execute: true, target_from_alert: false, default_server_id: $sid, steps: [{name: "Restart", step_order: 1, step_type: "command", command_linux: "sudo systemctl restart nginx", target_os: "linux", requires_elevation: true}]}')

echo "Creating Runbook..."
RB_RES=$(curl -s -X POST http://127.0.0.1:8080/api/remediation/runbooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$RB_PAYLOAD")

RB_ID=$(echo $RB_RES | jq -r .id)
echo "Runbook ID: $RB_ID"

if [ -z "$RB_ID" ] || [ "$RB_ID" == "null" ]; then
    echo "Failed to create runbook: $RB_RES"
    exit 1
fi

# 5. Create Trigger
echo "Creating Trigger..."
curl -s -X POST "http://127.0.0.1:8080/api/remediation/runbooks/$RB_ID/triggers" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"alert_name_pattern": "NginxDown", "enabled": true, "priority": 1}'

# 6. Simulate Failure
echo "Stopping Nginx..."
sudo systemctl stop nginx

# 7. Fire Alert
echo "Firing Alert..."
curl -s -X POST http://127.0.0.1:8080/webhook/alerts \
  -H "Content-Type: application/json" \
  -d '{"status":"firing","receiver":"webhook","version":"4","groupKey":"key","alerts":[{"status":"firing","labels":{"alertname":"NginxDown","instance":"15.204.244.73","severity":"critical"},"annotations":{"summary":"Nginx is Down","description":"Nginx service is down on 15.204.244.73"},"startsAt":"2023-01-01T00:00:00Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://prom","fingerprint":"12345"}],"groupLabels":{"alertname":"NginxDown"},"commonLabels":{"alertname":"NginxDown"},"commonAnnotations":{},"externalURL":"http://test"}'

# 8. Verify
echo "Waiting for remediation (60s)..."
sleep 60
STATUS=$(sudo systemctl is-active nginx || true)
echo "Nginx Status: $STATUS"

# Debug
echo "Fetching Execution Logs..."
EXECS=$(curl -s http://127.0.0.1:8080/api/remediation/executions \
  -H "Authorization: Bearer $TOKEN")
echo "Executions: $EXECS"

if [ "$STATUS" == "active" ]; then
    echo "SUCCESS: Nginx was remediated!"
    # Ensure exit 0
    exit 0
else
    echo "FAILURE: Nginx is $STATUS"
    exit 1
fi
"""

def main():
    encoded_script = base64.b64encode(BASH_SCRIPT.encode('utf-8')).decode('utf-8')
    
    # Construct the remote command
    # decode -> save -> chmod -> run
    remote_cmd = f"echo {encoded_script} | base64 -d > demo.sh; chmod +x demo.sh; ./demo.sh"
    
    # Execute via SSH
    # shell=False means args are passed directly to CreateProcess (Windows)
    # ssh will take the last arg as the command to execute on remote
    cmd = ["ssh", "ubuntu@15.204.244.73", remote_cmd]
    
    print(f"Executing remote script via SSH...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    
    if result.returncode == 0:
        print("Demo Script Completed Successfully")
    else:
        print(f"Demo Script Failed with code {result.returncode}")

if __name__ == "__main__":
    main()
