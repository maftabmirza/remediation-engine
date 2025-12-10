#!/usr/bin/env python3
"""
Create t-test-01 Server

This script creates the t-test-01 server in the system before creating runbooks.
"""

import requests
import json
import sys

# Configuration
API_BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def main():
    """Create the t-test-01 server."""
    
    session = requests.Session()
    
    # Login
    print("Logging in...")
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
    
    # Check if server already exists
    print("\\nChecking if server already exists...")
    try:
        response = session.get(f"{API_BASE_URL}/api/servers")
        response.raise_for_status()
        servers = response.json()
        for server in servers:
            if "t-test-01" in server.get("name", ""):
                print(f"[OK] Server with 't-test-01' in name already exists with ID: {server['id']}")
                print(f"    Name: {server['name']}")
                return
    except Exception as e:
        print(f"[FAIL] Failed to check servers: {e}")
        sys.exit(1)
    
    # Create the server
    print("\\nCreating server 't-test-01'...")
    print("NOTE: Using hostname '127.0.0.1' for testing as 't-test-01' may not resolve.")
    print("      The server will still be named 't-test-01' internally.\\n")
    server_data = {
        "name": "Test Server 01 (t-test-01)",
        "hostname": "127.0.0.1",  # Use localhost for testing - remote hostname won't resolve
        "port": 22,
        "username": "root",
        "password": "test-password-123",  # Dummy password for testing
        "os_type": "linux",
        "protocol": "ssh",
        "auth_type": "password",
        "environment": "testing",
        "tags": ["test", "linux","demo", "t-test-01"]
    }
    
    try:
        response = session.post(
            f"{API_BASE_URL}/api/servers",
            json=server_data
        )
        response.raise_for_status()
        data = response.json()
        server_id = data.get("id")
        print(f"[OK] Created server 't-test-01' with ID: {server_id}")
        print(f"\\nYou can now run: python create_test_runbooks.py")
    except Exception as e:
        print(f"[FAIL] Failed to create server: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Response: {e.response.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()
