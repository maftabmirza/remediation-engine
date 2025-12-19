#!/usr/bin/env python3
"""
Create Nginx Restart Runbook for Testing Alert Triggering

This runbook will be triggered by NginxDown.* alerts from Prometheus.
"""

import requests
import json
import sys

# Configuration
API_BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"
TARGET_SERVER_NAME = "t-test-01"

def main():
    """Create Nginx runbook and test alert firing."""
    
    session = requests.Session()
    
    # Login
    print("Step 1: Logging in...")
    try:
        response = session.post(
            f"{API_BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
            print("[OK] Logged in")
        else:
            print("[FAIL] No token received")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Login failed: {e}")
        sys.exit(1)
    
    # Get server ID
    print(f"\nStep 2: Looking up server '{TARGET_SERVER_NAME}'...")
    try:
        response = session.get(f"{API_BASE_URL}/api/servers")
        response.raise_for_status()
        servers = response.json()
        server_id = None
        for server in servers:
            if server.get("name") == TARGET_SERVER_NAME:
                server_id = server["id"]
                break
        
        if not server_id:
            print(f"[FAIL] Server '{TARGET_SERVER_NAME}' not found")
            sys.exit(1)
        
        print(f"[OK] Found server: {TARGET_SERVER_NAME} (ID: {server_id})")
    except Exception as e:
        print(f"[FAIL] Failed to get server: {e}")
        sys.exit(1)
    
    # Create Nginx runbook
    print("\nStep 3: Creating Nginx restart runbook...")
    
    runbook_data = {
        "name": "Restart Nginx Service (t-test-01)",
        "description": "Restarts Nginx web server when it goes down - triggered by NginxDown alerts",
        "category": "web-services",
        "tags": ["nginx", "webserver", "restart", "http", "test"],
        "enabled": True,
        "auto_execute": False,  # Requires approval for safety
        "approval_required": True,
        "approval_roles": ["operator", "engineer", "admin"],
        "approval_timeout_minutes": 30,
        "max_executions_per_hour": 5,
        "cooldown_minutes": 5,  # Shorter cooldown for testing
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
        "target_from_alert": True,
        "target_alert_label": "instance",
        "notifications_json": {
            "on_start": ["slack"],
            "on_success": ["slack"],
            "on_failure": ["slack", "email"]
        },
        "documentation_url": "https://nginx.org/en/docs/",
        "steps": [
            {
                "step_order": 1,
                "name": "Check Nginx Status",
                "description": "Verify Nginx service status before restart",
                "step_type": "command",
                "command_linux": "systemctl status nginx",
                "command_windows": None,
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 0,
                "retry_delay_seconds": 5,
                "expected_exit_code": 0
            },
            {
                "step_order": 2,
                "name": "Test Nginx Configuration",
                "description": "Validate Nginx config before restart",
                "step_type": "command",
                "command_linux": "nginx -t",
                "command_windows": None,
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": False,
                "retry_count": 0,
                "retry_delay_seconds": 5,
                "expected_exit_code": 0
            },
            {
                "step_order": 3,
                "name": "Restart Nginx",
                "description": "Restart the Nginx web server",
                "step_type": "command",
                "command_linux": "systemctl restart nginx",
                "command_windows": None,
                "target_os": "linux",
                "timeout_seconds": 60,
                "requires_elevation": True,
                "continue_on_fail": False,
                "retry_count": 2,
                "retry_delay_seconds": 10,
                "expected_exit_code": 0,
                "rollback_command_linux": "systemctl start nginx"
            },
            {
                "step_order": 4,
                "name": "Verify Nginx Running",
                "description": "Confirm Nginx is running after restart",
                "step_type": "command",
                "command_linux": "systemctl is-active nginx",
                "command_windows": None,
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": False,
                "retry_count": 2,
                "retry_delay_seconds": 5,
                "expected_exit_code": 0,
                "expected_output_pattern": "active"
            },
            {
                "step_order": 5,
                "name": "Test HTTP Response",
                "description": "Verify Nginx is responding to HTTP requests",
                "step_type": "command",
                "command_linux": "curl -sSf -o /dev/null -w '%{http_code}' http://localhost/ || echo '000'",
                "command_windows": None,
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 2,
                "retry_delay_seconds": 5,
                "expected_exit_code": 0
            }
        ],
        "triggers": [
            {
                "alert_name_pattern": "NginxDown*",
                "severity_pattern": "*",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 80,
                "enabled": True
            },
            {
                "alert_name_pattern": "*nginx*",
                "severity_pattern": "critical",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 85,
                "enabled": True
            }
        ]
    }
    
    try:
        response = session.post(
            f"{API_BASE_URL}/api/remediation/runbooks",
            json=runbook_data
        )
        response.raise_for_status()
        data = response.json()
        runbook_id = data.get("id")
        print(f"[OK] Created runbook: Restart Nginx Service (ID: {runbook_id})")
        print(f"\nRunbook triggers:")
        print(f"  - NginxDown* alerts (any severity)")
        print(f"  - *nginx* alerts (critical)")
        print(f"\nView runbook at: {API_BASE_URL}/runbooks")
        return runbook_id
    except Exception as e:
        print(f"[FAIL] Failed to create runbook: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Response: {e.response.text}")
        sys.exit(1)

if __name__ == "__main__":
    runbook_id = main()
    print(f"\n{'='*80}")
    print("Next: Fire a test alert using fire_test_alert.py")
    print(f"{'='*80}")
