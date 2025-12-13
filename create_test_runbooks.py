#!/usr/bin/env python3
"""
Create Multiple Test Runbooks for t-test-01 Server

This script creates various types of runbooks to test the remediation engine functionality.
It uses the REST API to create runbooks with different characteristics:
- Service restart runbooks
- Disk cleanup runbooks
- System health check runbooks
- Process management runbooks
- Network diagnostics runbooks
"""

import requests
import json
import sys
from typing import Dict, Any, Optional
from uuid import UUID

# =============================================================================
# Configuration
# =============================================================================

API_BASE_URL = "http://172.234.217.11:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"
# The server is named "t-test-01"
TARGET_SERVER_NAME_PATTERN = "t-test-01"

# =============================================================================
# API Client
# =============================================================================

class RemediationAPIClient:
    """Client for interacting with the Remediation Engine API."""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.token = None
        
    def login(self) -> bool:
        """Authenticate with the API and get a session token."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json={"username": self.username, "password": self.password}
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get("access_token")
            if self.token:
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                print(f"[OK] Logged in as {self.username}")
                return True
            return False
        except Exception as e:
            print(f"[FAIL] Login failed: {e}")
            return False
    
    def get_server_by_name(self, name: str) -> Optional[str]:
        """Get server ID by name."""
        try:
            response = self.session.get(f"{self.base_url}/api/servers")
            response.raise_for_status()
            servers = response.json()
            for server in servers:
                if server.get("name") == name:
                    return server["id"]
            print(f"[FAIL] Server '{name}' not found")
            return None
        except Exception as e:
            print(f"[FAIL] Failed to get server: {e}")
            return None
    
    def create_runbook(self, runbook_data: Dict[str, Any]) -> Optional[str]:
        """Create a runbook and return its ID."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/remediation/runbooks",
                json=runbook_data
            )
            response.raise_for_status()
            data = response.json()
            runbook_id = data.get("id")
            runbook_name = data.get("name")
            print(f"[OK] Created runbook: {runbook_name} (ID: {runbook_id})")
            return runbook_id
        except Exception as e:
            print(f"[FAIL] Failed to create runbook '{runbook_data.get('name')}': {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"  Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    print(f"  Response: {e.response.text}")
            return None
    
    def list_runbooks(self) -> list:
        """List all runbooks."""
        try:
            response = self.session.get(f"{self.base_url}/api/remediation/runbooks")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[FAIL] Failed to list runbooks: {e}")
            return []

# =============================================================================
# Runbook Templates
# =============================================================================

def create_apache_restart_runbook(server_id: str) -> Dict[str, Any]:
    """Create a runbook to restart Apache web server."""
    return {
        "name": "Restart Apache Service (t-test-01)",
        "description": "Restarts the Apache web server when it becomes unresponsive or crashes",
        "category": "web-services",
        "tags": ["apache", "webserver", "restart", "http"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "approval_roles": ["operator", "engineer", "admin"],
        "approval_timeout_minutes": 30,
        "max_executions_per_hour": 3,
        "cooldown_minutes": 10,
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
        "target_from_alert": True,
        "target_alert_label": "instance",
        "notifications_json": {
            "on_start": ["slack"],
            "on_success": ["slack"],
            "on_failure": ["slack", "email"]
        },
        "documentation_url": "https://httpd.apache.org/docs/",
        "steps": [
            {
                "step_order": 1,
                "name": "Check Apache Status",
                "description": "Verify Apache service status before restart",
                "step_type": "command",
                "command_linux": "systemctl status apache2 || systemctl status httpd",
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
                "name": "Restart Apache",
                "description": "Restart the Apache web server",
                "step_type": "command",
                "command_linux": "systemctl restart apache2 || systemctl restart httpd",
                "command_windows": None,
                "target_os": "linux",
                "timeout_seconds": 60,
                "requires_elevation": True,
                "continue_on_fail": False,
                "retry_count": 2,
                "retry_delay_seconds": 10,
                "expected_exit_code": 0,
                "rollback_command_linux": "systemctl start apache2 || systemctl start httpd"
            },
            {
                "step_order": 3,
                "name": "Verify Apache Running",
                "description": "Confirm Apache is running after restart",
                "step_type": "command",
                "command_linux": "systemctl is-active apache2 || systemctl is-active httpd",
                "command_windows": None,
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": False,
                "retry_count": 1,
                "retry_delay_seconds": 5,
                "expected_exit_code": 0,
                "expected_output_pattern": "active"
            },
            {
                "step_order": 4,
                "name": "Test HTTP Response",
                "description": "Verify web server is responding to HTTP requests",
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
                "alert_name_pattern": "*Apache*",
                "severity_pattern": "critical",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 90,
                "enabled": True
            },
            {
                "alert_name_pattern": "*httpd*",
                "severity_pattern": "critical",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 90,
                "enabled": True
            }
        ]
    }


def create_disk_cleanup_runbook(server_id: str) -> Dict[str, Any]:
    """Create a runbook to clean up disk space."""
    return {
        "name": "Disk Space Cleanup (t-test-01)",
        "description": "Automated disk cleanup procedure to free up space on critical filesystems",
        "category": "infrastructure",
        "tags": ["disk", "cleanup", "storage", "maintenance"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "approval_roles": ["engineer", "admin"],
        "approval_timeout_minutes": 45,
        "max_executions_per_hour": 2,
        "cooldown_minutes": 60,
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
        "target_from_alert": True,
        "target_alert_label": "instance",
        "notifications_json": {
            "on_start": ["slack"],
            "on_success": ["slack"],
            "on_failure": ["slack", "email"]
        },
        "steps": [
            {
                "step_order": 1,
                "name": "Check Disk Usage Before",
                "description": "Report current disk usage",
                "step_type": "command",
                "command_linux": "df -h",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": False,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 2,
                "name": "Clean Package Manager Cache",
                "description": "Remove cached packages from apt/yum",
                "step_type": "command",
                "command_linux": "apt-get clean || yum clean all",
                "target_os": "linux",
                "timeout_seconds": 120,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 1,
                "expected_exit_code": 0
            },
            {
                "step_order": 3,
                "name": "Remove Old Log Files",
                "description": "Delete log files older than 30 days",
                "step_type": "command",
                "command_linux": "find /var/log -type f -name '*.log' -mtime +30 -delete",
                "target_os": "linux",
                "timeout_seconds": 180,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 4,
                "name": "Clean Temporary Files",
                "description": "Remove files from /tmp older than 7 days",
                "step_type": "command",
                "command_linux": "find /tmp -type f -atime +7 -delete",
                "target_os": "linux",
                "timeout_seconds": 120,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 5,
                "name": "Check Disk Usage After",
                "description": "Report disk usage after cleanup",
                "step_type": "command",
                "command_linux": "df -h",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": False,
                "retry_count": 0,
                "expected_exit_code": 0
            }
        ],
        "triggers": [
            {
                "alert_name_pattern": "*DiskSpace*",
                "severity_pattern": "warning",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 100,
                "enabled": True
            },
            {
                "alert_name_pattern": "*HighDiskUsage*",
                "severity_pattern": "*",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 95,
                "enabled": True
            }
        ]
    }


def create_system_health_check_runbook(server_id: str) -> Dict[str, Any]:
    """Create a runbook to perform comprehensive system health checks."""
    return {
        "name": "System Health Check (t-test-01)",
        "description": "Comprehensive system health diagnostics including CPU, memory, disk, and network",
        "category": "diagnostics",
        "tags": ["health-check", "diagnostics", "monitoring"],
        "enabled": True,
        "auto_execute": True,  # Safe to auto-execute as it's read-only
        "approval_required": False,
        "approval_roles": ["operator", "engineer", "admin"],
        "approval_timeout_minutes": 15,
        "max_executions_per_hour": 10,
        "cooldown_minutes": 5,
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
        "target_from_alert": True,
        "target_alert_label": "instance",
        "notifications_json": {
            "on_start": [],
            "on_success": ["slack"],
            "on_failure": ["slack"]
        },
        "steps": [
            {
                "step_order": 1,
                "name": "Check CPU Usage",
                "description": "Display current CPU usage",
                "step_type": "command",
                "command_linux": "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 2,
                "name": "Check Memory Usage",
                "description": "Display memory usage statistics",
                "step_type": "command",
                "command_linux": "free -m",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 3,
                "name": "Check Disk I/O",
                "description": "Display disk I/O statistics",
                "step_type": "command",
                "command_linux": "iostat -x 1 2 || echo 'iostat not available'",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 4,
                "name": "Check Network Connectivity",
                "description": "Test network connectivity to common endpoints",
                "step_type": "command",
                "command_linux": "ping -c 3 8.8.8.8",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 1,
                "expected_exit_code": 0
            },
            {
                "step_order": 5,
                "name": "Check Running Services",
                "description": "List all active systemd services",
                "step_type": "command",
                "command_linux": "systemctl list-units --type=service --state=running",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 6,
                "name": "Check System Uptime",
                "description": "Display system uptime and load average",
                "step_type": "command",
                "command_linux": "uptime",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            }
        ],
        "triggers": [
            {
                "alert_name_pattern": "*SystemCheck*",
                "severity_pattern": "*",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 200,
                "enabled": True
            }
        ]
    }


def create_process_kill_runbook(server_id: str) -> Dict[str, Any]:
    """Create a runbook to kill hung processes."""
    return {
        "name": "Kill Hung Process (t-test-01)",
        "description": "Identifies and terminates hung or zombie processes consuming excessive resources",
        "category": "process-management",
        "tags": ["process", "kill", "hung", "zombie"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "approval_roles": ["engineer", "admin"],
        "approval_timeout_minutes": 20,
        "max_executions_per_hour": 5,
        "cooldown_minutes": 15,
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
        "target_from_alert": True,
        "target_alert_label": "instance",
        "notifications_json": {
            "on_start": ["slack"],
            "on_success": ["slack"],
            "on_failure": ["slack", "email"]
        },
        "steps": [
            {
                "step_order": 1,
                "name": "Identify High CPU Processes",
                "description": "List top CPU consuming processes",
                "step_type": "command",
                "command_linux": "ps aux --sort=-%cpu | head -10",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": False,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 2,
                "name": "List Zombie Processes",
                "description": "Find zombie processes (state Z)",
                "step_type": "command",
                "command_linux": "ps aux | grep 'Z' | grep -v grep",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 3,
                "name": "Graceful Termination",
                "description": "Send SIGTERM to hung processes (manual PID substitution required)",
                "step_type": "command",
                "command_linux": "echo 'Manual step: kill -15 <PID>'",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 4,
                "name": "Force Kill if Needed",
                "description": "Send SIGKILL if process doesn't respond to SIGTERM",
                "step_type": "command",
                "command_linux": "echo 'Manual step: kill -9 <PID>'",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 5,
                "name": "Verify Process Terminated",
                "description": "Check that the process is no longer running",
                "step_type": "command",
                "command_linux": "ps aux --sort=-%cpu | head -10",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": False,
                "retry_count": 0,
                "expected_exit_code": 0
            }
        ],
        "triggers": [
            {
                "alert_name_pattern": "*ProcessHung*",
                "severity_pattern": "critical",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 85,
                "enabled": True
            },
            {
                "alert_name_pattern": "*HighCPU*",
                "severity_pattern": "*",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 110,
                "enabled": True
            }
        ]
    }


def create_network_diagnostics_runbook(server_id: str) -> Dict[str, Any]:
    """Create a runbook for network diagnostics."""
    return {
        "name": "Network Diagnostics (t-test-01)",
        "description": "Comprehensive network diagnostics including connectivity, routing, and DNS resolution",
        "category": "network",
        "tags": ["network", "diagnostics", "connectivity", "dns"],
        "enabled": True,
        "auto_execute": True,  # Safe diagnostic commands
        "approval_required": False,
        "approval_roles": ["operator", "engineer", "admin"],
        "approval_timeout_minutes": 15,
        "max_executions_per_hour": 8,
        "cooldown_minutes": 5,
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
        "target_from_alert": True,
        "target_alert_label": "instance",
        "notifications_json": {
            "on_start": [],
            "on_success": ["slack"],
            "on_failure": ["slack"]
        },
        "steps": [
            {
                "step_order": 1,
                "name": "Check Network Interfaces",
                "description": "List all network interfaces and their status",
                "step_type": "command",
                "command_linux": "ip addr show",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": False,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 2,
                "name": "Test DNS Resolution",
                "description": "Test DNS resolution for common domains",
                "step_type": "command",
                "command_linux": "nslookup google.com || dig google.com",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 1,
                "expected_exit_code": 0
            },
            {
                "step_order": 3,
                "name": "Check Default Gateway",
                "description": "Display routing table and default gateway",
                "step_type": "command",
                "command_linux": "ip route show",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": False,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 4,
                "name": "Ping Gateway",
                "description": "Test connectivity to default gateway",
                "step_type": "command",
                "command_linux": "ping -c 3 $(ip route | grep default | awk '{print $3}')",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 1,
                "expected_exit_code": 0
            },
            {
                "step_order": 5,
                "name": "Traceroute to 8.8.8.8",
                "description": "Trace route to Google DNS",
                "step_type": "command",
                "command_linux": "traceroute -m 10 8.8.8.8 || echo 'traceroute not available'",
                "target_os": "linux",
                "timeout_seconds": 60,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 6,
                "name": "Check Active Connections",
                "description": "List established network connections",
                "step_type": "command",
                "command_linux": "ss -tuln | head -20",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": False,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            }
        ],
        "triggers": [
            {
                "alert_name_pattern": "*NetworkDown*",
                "severity_pattern": "*",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 80,
                "enabled": True
            },
            {
                "alert_name_pattern": "*DNSFailure*",
                "severity_pattern": "*",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 90,
                "enabled": True
            }
        ]
    }


def create_database_restart_runbook(server_id: str) -> Dict[str, Any]:
    """Create a runbook to restart PostgreSQL database."""
    return {
        "name": "Restart PostgreSQL Database (t-test-01)",
        "description": "Safely restart PostgreSQL database service with pre and post checks",
        "category": "database",
        "tags": ["postgresql", "database", "restart"],
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "approval_roles": ["engineer", "admin"],
        "approval_timeout_minutes": 30,
        "max_executions_per_hour": 2,
        "cooldown_minutes": 30,
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
        "target_from_alert": True,
        "target_alert_label": "instance",
        "notifications_json": {
            "on_start": ["slack", "email"],
            "on_success": ["slack"],
            "on_failure": ["slack", "email"]
        },
        "steps": [
            {
                "step_order": 1,
                "name": "Check PostgreSQL Status",
                "description": "Verify current PostgreSQL service status",
                "step_type": "command",
                "command_linux": "systemctl status postgresql",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 2,
                "name": "Check Active Connections",
                "description": "Count active database connections",
                "step_type": "command",
                "command_linux": "sudo -u postgres psql -c 'SELECT count(*) FROM pg_stat_activity;'",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": True,
                "retry_count": 0,
                "expected_exit_code": 0
            },
            {
                "step_order": 3,
                "name": "Restart PostgreSQL",
                "description": "Restart the PostgreSQL service",
                "step_type": "command",
                "command_linux": "systemctl restart postgresql",
                "target_os": "linux",
                "timeout_seconds": 90,
                "requires_elevation": True,
                "continue_on_fail": False,
                "retry_count": 1,
                "retry_delay_seconds": 10,
                "expected_exit_code": 0,
                "rollback_command_linux": "systemctl start postgresql"
            },
            {
                "step_order": 4,
                "name": "Verify PostgreSQL Running",
                "description": "Confirm PostgreSQL is running after restart",
                "step_type": "command",
                "command_linux": "systemctl is-active postgresql",
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
                "name": "Test Database Connection",
                "description": "Test connection to PostgreSQL",
                "step_type": "command",
                "command_linux": "sudo -u postgres psql -c 'SELECT version();'",
                "target_os": "linux",
                "timeout_seconds": 30,
                "requires_elevation": True,
                "continue_on_fail": False,
                "retry_count": 2,
                "retry_delay_seconds": 5,
                "expected_exit_code": 0
            }
        ],
        "triggers": [
            {
                "alert_name_pattern": "*PostgreSQL*",
                "severity_pattern": "critical",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 75,
                "enabled": True
            },
            {
                "alert_name_pattern": "*DatabaseDown*",
                "severity_pattern": "critical",
                "instance_pattern": "t-test-01*",
                "job_pattern": "*",
                "priority": 70,
                "enabled": True
            }
        ]
    }


# =============================================================================
# Main Script
# =============================================================================

def main():
    """Main script entry point."""
    print("=" * 80)
    print("Remediation Engine - Test Runbook Creator")
    print("=" * 80)
    print()
    
    # Initialize API client
    client = RemediationAPIClient(API_BASE_URL, USERNAME, PASSWORD)
    
    # Login
    print("Step 1: Authenticating...")
    if not client.login():
        print("\n[FAIL] Failed to authenticate. Exiting.")
        sys.exit(1)
    print()
    
    # Get server ID for t-test-01
    print(f"Step 2: Looking up server '{TARGET_SERVER_NAME_PATTERN}'...")
    server_id = client.get_server_by_name(TARGET_SERVER_NAME_PATTERN)
    if not server_id:
        print(f"\n[FAIL] Server '{TARGET_SERVER_NAME_PATTERN}' not found.")
        print("   Please create the server first using: python create_test_server.py")
        sys.exit(1)
    print(f"[OK] Found server: {TARGET_SERVER_NAME_PATTERN} (ID: {server_id})")
    print()
    
    # Create runbooks
    print("Step 3: Creating test runbooks...")
    print()
    
    runbook_templates = [
        ("Apache Restart", create_apache_restart_runbook),
        ("Disk Cleanup", create_disk_cleanup_runbook),
        ("System Health Check", create_system_health_check_runbook),
        ("Process Kill", create_process_kill_runbook),
        ("Network Diagnostics", create_network_diagnostics_runbook),
        ("PostgreSQL Restart", create_database_restart_runbook),
    ]
    
    created_runbooks = []
    failed_runbooks = []
    
    for name, template_func in runbook_templates:
        print(f"Creating '{name}' runbook...")
        runbook_data = template_func(server_id)
        runbook_id = client.create_runbook(runbook_data)
        if runbook_id:
            created_runbooks.append((name, runbook_id))
        else:
            failed_runbooks.append(name)
        print()
    
    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"[OK] Successfully created: {len(created_runbooks)} runbook(s)")
    print(f"[FAIL] Failed to create: {len(failed_runbooks)} runbook(s)")
    print()
    
    if created_runbooks:
        print("Created Runbooks:")
        for name, runbook_id in created_runbooks:
            print(f"  - {name}: {runbook_id}")
        print()
    
    if failed_runbooks:
        print("Failed Runbooks:")
        for name in failed_runbooks:
            print(f"  - {name}")
        print()
    
    print(f"View runbooks at: {API_BASE_URL}/runbooks")
    print()


if __name__ == "__main__":
    main()
