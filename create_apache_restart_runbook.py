import requests
import json

BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "admin"

def login():
    print(f"Logging in to {BASE_URL}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        print("Login successful.")
        return token
    except Exception as e:
        print(f"Login failed: {e}")
        return None

def create_runbook(token, runbook_data):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Creating runbook: {runbook_data['name']}...")
    response = requests.post(
        f"{BASE_URL}/api/remediation/runbooks",
        json=runbook_data,
        headers=headers
    )
    
    if response.status_code == 201:
        print(f"Successfully created runbook: {runbook_data['name']}")
        return response.json()
    elif response.status_code == 409:
        print(f"Runbook {runbook_data['name']} already exists. Skipping.")
        return None
    else:
        print(f"Failed to create runbook. Status: {response.status_code}")
        print(response.text)
        return None

def main():
    token = login()
    if not token:
        print("Aborting.")
        return

    # Runbook: Apache Restart on t-aiops-01
    apache_restart_runbook = {
        "name": "Restart Apache on t-aiops-01",
        "description": "Restarts the Apache web server on t-aiops-01 (15.204.233.209). Use this runbook when Apache is unresponsive, experiencing high load, or after configuration changes. This runbook checks the Apache status, attempts a graceful restart, and verifies the service is running.",
        "category": "application",
        "tags": ["apache", "webserver", "t-aiops-01", "restart", "service-recovery", "http", "httpd"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "steps": [
            {
                "step_order": 1,
                "name": "Check Apache Status",
                "description": "Check current Apache service status before restart",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl status apache2 || sudo systemctl status httpd",
                "output_variable": "apache_status_before",
                "timeout_seconds": 30
            },
            {
                "step_order": 2,
                "name": "Stop Apache Service",
                "description": "Stop Apache service gracefully",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl stop apache2 2>/dev/null || sudo systemctl stop httpd",
                "output_variable": "apache_stop_output",
                "timeout_seconds": 60
            },
            {
                "step_order": 3,
                "name": "Wait for Cleanup",
                "description": "Wait for Apache to fully stop and release resources",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sleep 5",
                "timeout_seconds": 10
            },
            {
                "step_order": 4,
                "name": "Start Apache Service",
                "description": "Start Apache service",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl start apache2 2>/dev/null || sudo systemctl start httpd",
                "output_variable": "apache_start_output",
                "timeout_seconds": 60
            },
            {
                "step_order": 5,
                "name": "Verify Apache is Running",
                "description": "Verify that Apache service is running and active",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl is-active apache2 || sudo systemctl is-active httpd",
                "output_variable": "apache_verify",
                "expected_output": "active",
                "timeout_seconds": 30
            },
            {
                "step_order": 6,
                "name": "Check Apache Ports",
                "description": "Verify Apache is listening on expected ports (80, 443)",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo netstat -tlnp | grep -E ':(80|443) ' || sudo ss -tlnp | grep -E ':(80|443) '",
                "output_variable": "apache_ports",
                "timeout_seconds": 30
            },
            {
                "step_order": 7,
                "name": "Get Apache Status After Restart",
                "description": "Get detailed Apache status after restart",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl status apache2 || sudo systemctl status httpd",
                "output_variable": "apache_status_after",
                "timeout_seconds": 30
            }
        ],
        "triggers": [
            {
                "trigger_type": "alert",
                "alert_name": "Apache Down",
                "priority": 3
            },
            {
                "trigger_type": "alert",
                "alert_name": "High HTTP Response Time",
                "priority": 2
            },
            {
                "trigger_type": "alert",
                "alert_name": "Apache High Memory",
                "priority": 2
            }
        ]
    }

    result = create_runbook(token, apache_restart_runbook)
    if result:
        print(f"\n✓ Apache restart runbook created successfully!")
        print(f"  - Name: {apache_restart_runbook['name']}")
        print(f"  - Description: {apache_restart_runbook['description']}")
        print(f"  - Tags: {', '.join(apache_restart_runbook['tags'])}")
        print(f"  - Steps: {len(apache_restart_runbook['steps'])}")
        print(f"  - Target: t-aiops-01 (15.204.233.209)")
        print(f"\nThis runbook will be searchable by AI troubleshoot tool using keywords:")
        print(f"  apache, webserver, restart, t-aiops-01, service-recovery, http, httpd")

if __name__ == "__main__":
    main()
