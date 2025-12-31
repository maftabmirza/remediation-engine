#!/usr/bin/env python3
"""
Live API Test Script for AIOps Remediation Engine

Tests the production API at p-aiops-01 (15.204.244.73:8080)
Using t-aiops-01 (15.204.233.209) as the lab server for SSH tests

Run: python tests/live_api_tests.py
"""

import requests
import json
import time
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://15.204.244.73:8080"
LAB_SERVER_HOST = "15.204.233.209"
ADMIN_USER = "admin"
ADMIN_PASS = "Passw0rd"

# Test counters
passed = 0
failed = 0
skipped = 0

def log_test(name: str, status: str, details: str = ""):
    """Log test result with formatting"""
    global passed, failed, skipped
    
    icons = {"PASS": "[OK]  ", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}
    icon = icons.get(status, "")
    
    print(f"{icon} {status}: {name}")
    if details:
        print(f"       {details[:200]}")
    
    if status == "PASS":
        passed += 1
    elif status == "FAIL":
        failed += 1
    else:
        skipped += 1

def get_auth_token():
    """Get authentication token"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
        return None
    except Exception as e:
        print(f"Auth error: {e}")
        return None

def auth_headers(token):
    """Return auth headers"""
    return {"Authorization": f"Bearer {token}"}

# =============================================================================
# TEST CASES
# =============================================================================

def test_health_check():
    """Test 1: Health Check Endpoint"""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            log_test("Health Check", "PASS", f"Status: {resp.json()}")
        else:
            log_test("Health Check", "FAIL", f"Status code: {resp.status_code}")
    except Exception as e:
        log_test("Health Check", "FAIL", str(e))

def test_authentication():
    """Test 2: Authentication - Login"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            timeout=10
        )
        if resp.status_code == 200 and "access_token" in resp.json():
            log_test("Authentication - Login", "PASS")
            return resp.json()["access_token"]
        else:
            log_test("Authentication - Login", "FAIL", f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Authentication - Login", "FAIL", str(e))
        return None

def test_auth_invalid_credentials():
    """Test 3: Authentication - Invalid Credentials"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "baduser", "password": "badpass"},
            timeout=10
        )
        if resp.status_code == 401:
            log_test("Authentication - Invalid Credentials Rejected", "PASS")
        else:
            log_test("Authentication - Invalid Credentials Rejected", "FAIL", 
                    f"Expected 401, got {resp.status_code}")
    except Exception as e:
        log_test("Authentication - Invalid Credentials Rejected", "FAIL", str(e))

def test_auth_protected_endpoint_no_token():
    """Test 4: Protected Endpoint Without Token"""
    try:
        resp = requests.get(f"{BASE_URL}/api/alerts", timeout=5)
        if resp.status_code == 401:
            log_test("Protected Endpoint - No Token Rejected", "PASS")
        else:
            log_test("Protected Endpoint - No Token Rejected", "FAIL",
                    f"Expected 401, got {resp.status_code}")
    except Exception as e:
        log_test("Protected Endpoint - No Token Rejected", "FAIL", str(e))

def test_list_servers(token):
    """Test 5: List Servers"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/servers",
            headers=auth_headers(token),
            timeout=10
        )
        if resp.status_code == 200:
            servers = resp.json()
            log_test("List Servers", "PASS", f"Found {len(servers)} server(s)")
            return servers
        else:
            log_test("List Servers", "FAIL", f"Status: {resp.status_code}")
            return []
    except Exception as e:
        log_test("List Servers", "FAIL", str(e))
        return []

def test_server_connection(token, server_id):
    """Test 6: Test Server Connection"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/servers/{server_id}/test",
            headers=auth_headers(token),
            timeout=30
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get("status") == "success":
                log_test("Server Connection Test", "PASS", 
                        f"Latency: {result.get('latency_ms')}ms")
            else:
                log_test("Server Connection Test", "FAIL", result.get("message"))
        else:
            log_test("Server Connection Test", "FAIL", f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Server Connection Test", "FAIL", str(e))

def test_execute_command_on_server(token, server_id):
    """Test 7: Execute Command on Server"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/servers/{server_id}/execute",
            headers=auth_headers(token),
            json={"command": "hostname && uptime", "timeout": 30},
            timeout=35
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get("success"):
                log_test("Execute Command on Server", "PASS",
                        f"Output: {result.get('stdout', '')[:100]}...")
            else:
                log_test("Execute Command on Server", "FAIL", result.get("error"))
        else:
            log_test("Execute Command on Server", "FAIL", f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Execute Command on Server", "FAIL", str(e))

def test_list_alerts(token):
    """Test 8: List Alerts"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/alerts",
            headers=auth_headers(token),
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            count = len(data.get("items", data)) if isinstance(data, dict) else len(data)
            log_test("List Alerts", "PASS", f"Found {count} alert(s)")
            return data
        else:
            log_test("List Alerts", "FAIL", f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("List Alerts", "FAIL", str(e))
        return None

def test_ingest_test_alert(token):
    """Test 9: Ingest Test Alert via Webhook (unauthenticated endpoint)"""
    try:
        test_alert = {
            "receiver": "test",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "TestAlert_LiveAPITest",
                        "severity": "warning",
                        "instance": "test-instance:9090",
                        "job": "live-api-test"
                    },
                    "annotations": {
                        "summary": "Test alert from live API test",
                        "description": "This is a test alert created by live_api_tests.py"
                    },
                    "startsAt": datetime.utcnow().isoformat() + "Z",
                    "fingerprint": f"test-{int(time.time())}"
                }
            ]
        }
        
        # Webhook is usually unauthenticated - try without auth first
        resp = requests.post(
            f"{BASE_URL}/webhook/alertmanager",
            json=test_alert,
            timeout=10
        )
        
        if resp.status_code in [200, 201, 202]:
            log_test("Ingest Test Alert", "PASS", "Alert webhook processed")
            return True
        elif resp.status_code == 404:
            # Try alternate endpoint
            resp = requests.post(
                f"{BASE_URL}/api/webhooks/alertmanager",
                json=test_alert,
                timeout=10
            )
            if resp.status_code in [200, 201, 202]:
                log_test("Ingest Test Alert", "PASS", "Alert webhook processed")
                return True
            else:
                log_test("Ingest Test Alert", "SKIP", "Webhook endpoint not found")
                return False
        else:
            log_test("Ingest Test Alert", "FAIL", f"Status: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Ingest Test Alert", "FAIL", str(e))
        return False

def test_list_runbooks(token):
    """Test 10: List Runbooks"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/remediation/runbooks",
            headers=auth_headers(token),
            timeout=10
        )
        if resp.status_code == 200:
            runbooks = resp.json()
            count = len(runbooks.get("items", runbooks)) if isinstance(runbooks, dict) else len(runbooks)
            log_test("List Runbooks", "PASS", f"Found {count} runbook(s)")
            return runbooks
        else:
            log_test("List Runbooks", "FAIL", f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("List Runbooks", "FAIL", str(e))
        return None

def test_create_test_runbook(token, server_id):
    """Test 11: Create Test Runbook"""
    try:
        runbook_data = {
            "name": f"Test Runbook - {int(time.time())}",
            "description": "Test runbook created by live API tests",
            "category": "diagnostic",
            "enabled": True,
            "steps": [
                {
                    "name": "Check System Info",
                    "action_type": "command",
                    "command": "uname -a && uptime",
                    "target_server_id": server_id,
                    "timeout_seconds": 30,
                    "continue_on_failure": True,
                    "step_order": 1
                },
                {
                    "name": "Check Disk Usage",
                    "action_type": "command",
                    "command": "df -h",
                    "target_server_id": server_id,
                    "timeout_seconds": 30,
                    "continue_on_failure": True,
                    "step_order": 2
                }
            ]
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/remediation/runbooks",
            headers=auth_headers(token),
            json=runbook_data,
            timeout=15
        )
        
        if resp.status_code in [200, 201]:
            runbook = resp.json()
            log_test("Create Test Runbook", "PASS", f"ID: {runbook.get('id')}")
            return runbook.get("id")
        else:
            log_test("Create Test Runbook", "FAIL", 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test("Create Test Runbook", "FAIL", str(e))
        return None

def test_execute_runbook(token, runbook_id):
    """Test 12: Execute Runbook"""
    try:
        # Correct endpoint is POST /api/remediation/executions?runbook_id=<uuid>
        resp = requests.post(
            f"{BASE_URL}/api/remediation/executions",
            headers=auth_headers(token),
            params={"runbook_id": str(runbook_id)},
            json={},
            timeout=60
        )
        
        if resp.status_code in [200, 201, 202]:
            result = resp.json()
            log_test("Execute Runbook", "PASS", 
                    f"Execution ID: {result.get('id', result.get('execution_id', 'started'))}")
            return result
        else:
            log_test("Execute Runbook", "FAIL", 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test("Execute Runbook", "FAIL", str(e))
        return None

def test_list_rules(token):
    """Test 13: List Rules"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/rules",
            headers=auth_headers(token),
            timeout=10
        )
        if resp.status_code == 200:
            rules = resp.json()
            count = len(rules.get("items", rules)) if isinstance(rules, dict) else len(rules)
            log_test("List Rules", "PASS", f"Found {count} rule(s)")
        else:
            log_test("List Rules", "FAIL", f"Status: {resp.status_code}")
    except Exception as e:
        log_test("List Rules", "FAIL", str(e))

def test_alert_stats(token):
    """Test 14: Get Alert Stats"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/alerts/stats",
            headers=auth_headers(token),
            params={"time_range": "24h"},
            timeout=10
        )
        if resp.status_code == 200:
            stats = resp.json()
            log_test("Get Alert Stats", "PASS", f"Stats: {json.dumps(stats)[:100]}...")
        else:
            log_test("Get Alert Stats", "FAIL", f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Get Alert Stats", "FAIL", str(e))

def test_current_user(token):
    """Test 15: Get Current User"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers(token),
            timeout=10
        )
        if resp.status_code == 200:
            user = resp.json()
            log_test("Get Current User", "PASS", f"User: {user.get('username')}")
        else:
            log_test("Get Current User", "FAIL", f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Get Current User", "FAIL", str(e))

def test_list_roles(token):
    """Test 16: List Roles"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/roles",
            headers=auth_headers(token),
            timeout=10
        )
        if resp.status_code == 200:
            roles = resp.json()
            log_test("List Roles", "PASS", f"Found {len(roles)} role(s)")
        else:
            log_test("List Roles", "FAIL", f"Status: {resp.status_code}")
    except Exception as e:
        log_test("List Roles", "FAIL", str(e))

def test_cleanup_runbook(token, runbook_id):
    """Cleanup: Delete test runbook"""
    if not runbook_id:
        return
    try:
        resp = requests.delete(
            f"{BASE_URL}/api/remediation/runbooks/{runbook_id}",
            headers=auth_headers(token),
            timeout=10
        )
        if resp.status_code in [200, 204]:
            log_test("Cleanup - Delete Test Runbook", "PASS")
        else:
            log_test("Cleanup - Delete Test Runbook", "SKIP", f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Cleanup - Delete Test Runbook", "SKIP", str(e))

# =============================================================================
# MAIN
# =============================================================================

def main():
    global passed, failed, skipped
    
    print("\n" + "=" * 60)
    print("  LIVE API TESTS - AIOps Remediation Engine")
    print(f"  Target: {BASE_URL}")
    print(f"  Lab Server: {LAB_SERVER_HOST}")
    print(f"  Time: {datetime.now().isoformat()}")
    print("=" * 60 + "\n")
    
    # Test 1: Health check
    test_health_check()
    
    # Test 2-4: Authentication
    token = test_authentication()
    if not token:
        print("\n❌ Authentication failed! Cannot continue tests.")
        sys.exit(1)
    
    test_auth_invalid_credentials()
    test_auth_protected_endpoint_no_token()
    
    # Test 5-7: Server management
    servers = test_list_servers(token)
    server_id = None
    if servers:
        # Find lab server
        for s in servers:
            if LAB_SERVER_HOST in s.get("hostname", ""):
                server_id = s.get("id")
                break
        if not server_id and servers:
            server_id = servers[0].get("id")
    
    if server_id:
        test_server_connection(token, server_id)
        test_execute_command_on_server(token, server_id)
    else:
        log_test("Server Connection Test", "SKIP", "No servers configured")
        log_test("Execute Command on Server", "SKIP", "No servers configured")
    
    # Test 8-9: Alerts
    test_list_alerts(token)
    test_ingest_test_alert(token)
    test_alert_stats(token)
    
    # Test 10-12: Runbooks
    test_list_runbooks(token)
    runbook_id = None
    if server_id:
        runbook_id = test_create_test_runbook(token, server_id)
        if runbook_id:
            test_execute_runbook(token, runbook_id)
    else:
        log_test("Create Test Runbook", "SKIP", "No server for runbook")
        log_test("Execute Runbook", "SKIP", "No runbook created")
    
    # Test 13-16: Other endpoints
    test_list_rules(token)
    test_current_user(token)
    test_list_roles(token)
    
    # Cleanup
    print("\n--- Cleanup ---")
    test_cleanup_runbook(token, runbook_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    print(f"  [OK]   Passed:  {passed}")
    print(f"  [FAIL] Failed:  {failed}")
    print(f"  [SKIP] Skipped: {skipped}")
    print(f"  [ALL]  Total:   {passed + failed + skipped}")
    print("=" * 60 + "\n")
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
