#!/usr/bin/env python3
"""Seed a handful of demo runbooks for one or more servers.

This script:
- logs in to the AIOps API
- ensures target servers exist (best-effort; requires SSH port reachable)
- creates several safe, demo-friendly runbooks per host

Usage:
  python scripts/seed_demo_runbooks_for_hosts.py --base-url http://t-aiops-01:8080 --hosts t-aiops-02,t-aiops-03

Notes:
- Server creation performs a TCP probe to host:port; if the port is closed/unreachable,
  the API will reject creation. In that case we still create runbooks without
  default_server_id (tagged with the hostname).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional

import requests


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def login(base_url: str, username: str, password: str) -> str:
    resp = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=20,
    )
    if resp.status_code != 200:
        _die(f"Login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        _die(f"Login succeeded but no access_token in response: {data}")
    return token


def api_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def list_servers(base_url: str, token: str) -> List[Dict[str, Any]]:
    resp = requests.get(f"{base_url}/api/servers", headers=api_headers(token), timeout=30)
    if resp.status_code != 200:
        _die(f"List servers failed: {resp.status_code} {resp.text}")
    return resp.json()


def ensure_server(
    base_url: str,
    token: str,
    *,
    name: str,
    hostname: str,
    port: int,
    username: str,
    password: str,
) -> Optional[str]:
    """Return server_id if existing/created, else None (if create rejected)."""

    existing = list_servers(base_url, token)
    for s in existing:
        if (s.get("hostname") or "").strip().lower() == hostname.strip().lower() or (s.get("name") or "").strip().lower() == name.strip().lower():
            return s.get("id")

    payload = {
        "name": name,
        "hostname": hostname,
        "port": port,
        "username": username,
        "auth_type": "password",
        "password": password,
        "credential_source": "inline",
        "environment": "production",
        "os_type": "linux",
        "protocol": "ssh",
        "tags": ["demo"],
    }

    resp = requests.post(
        f"{base_url}/api/servers",
        headers=api_headers(token),
        json=payload,
        timeout=45,
    )

    if resp.status_code in (200, 201):
        return resp.json().get("id")

    # Most common: 400 if TCP probe failed
    print(f"WARN: could not create server '{hostname}': {resp.status_code} {resp.text}")
    return None


def create_runbook(base_url: str, token: str, runbook: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    resp = requests.post(
        f"{base_url}/api/remediation/runbooks",
        headers=api_headers(token),
        json=runbook,
        timeout=60,
    )

    if resp.status_code == 201:
        return resp.json()
    if resp.status_code == 409:
        # Name conflict (already exists)
        return None

    _die(f"Create runbook failed ({runbook.get('name')}): {resp.status_code} {resp.text}")


def get_runbook_id_by_name(base_url: str, token: str, name: str) -> Optional[str]:
    # List endpoint supports search, but we still filter by exact name.
    resp = requests.get(
        f"{base_url}/api/remediation/runbooks",
        headers=api_headers(token),
        params={"search": name, "limit": 100},
        timeout=30,
    )
    if resp.status_code != 200:
        _die(f"List runbooks failed: {resp.status_code} {resp.text}")
    for rb in resp.json():
        if (rb.get("name") or "") == name:
            return rb.get("id")
    return None


def update_runbook(base_url: str, token: str, runbook_id: str, runbook: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.put(
        f"{base_url}/api/remediation/runbooks/{runbook_id}",
        headers=api_headers(token),
        json=runbook,
        timeout=60,
    )
    if resp.status_code != 200:
        _die(f"Update runbook failed ({runbook.get('name')}): {resp.status_code} {resp.text}")
    return resp.json()


def demo_runbooks_for_host(host: str, server_id: Optional[str]) -> List[Dict[str, Any]]:
    tags = ["demo", host]

    common = {
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "tags": tags,
        "target_from_alert": False,
        "default_server_id": server_id,
        "target_os_filter": ["linux"],
    }

    runbooks: List[Dict[str, Any]] = []

    runbooks.append(
        {
            **common,
            "name": f"[{host}] Disk Space Quick Check",
            "category": "infrastructure",
            "description": "Demo: checks disk usage and highlights largest directories (read-only).",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Show disk usage",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "df -h || true",
                    "timeout_seconds": 30,
                },
                {
                    "step_order": 2,
                    "name": "Largest directories (top 10)",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "sudo du -xhd1 / 2>/dev/null | sort -hr | head -n 10 || true",
                    "timeout_seconds": 60,
                    "requires_elevation": True,
                },
            ],
            "triggers": [],
        }
    )

    runbooks.append(
        {
            **common,
            "name": f"[{host}] Web Service Restart (Apache/Nginx)",
            "category": "application",
            "description": "Demo: checks service status then restarts Apache or Nginx (best-effort).",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Detect service",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "(systemctl is-active apache2 && echo apache2) || (systemctl is-active httpd && echo httpd) || (systemctl is-active nginx && echo nginx) || echo none",
                    "output_variable": "svc",
                    "output_extract_pattern": "^(apache2|httpd|nginx|none)$",
                    "timeout_seconds": 30,
                },
                {
                    "step_order": 2,
                    "name": "Restart detected service",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "if [ \"{{ svc }}\" = \"none\" ]; then echo 'No web service detected'; exit 0; fi; sudo systemctl restart {{ svc }}",
                    "timeout_seconds": 90,
                    "requires_elevation": True,
                },
                {
                    "step_order": 3,
                    "name": "Verify service",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "if [ \"{{ svc }}\" = \"none\" ]; then exit 0; fi; systemctl is-active {{ svc }}",
                    "timeout_seconds": 30,
                },
            ],
            "triggers": [],
        }
    )

    runbooks.append(
        {
            **common,
            "name": f"[{host}] Host Diagnostics Bundle",
            "category": "diagnostics",
            "description": "Demo: collects basic host diagnostics (read-only).",
            "steps": [
                {
                    "step_order": 1,
                    "name": "System summary",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "echo '=== uname ===' && uname -a; echo '=== uptime ===' && uptime; echo '=== cpu/mem ===' && free -h || true",
                    "timeout_seconds": 60,
                },
                {
                    "step_order": 2,
                    "name": "Recent journal errors (last 5m)",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "sudo journalctl -p err -S -5m --no-pager | tail -n 200 || true",
                    "timeout_seconds": 60,
                    "requires_elevation": True,
                },
                {
                    "step_order": 3,
                    "name": "Network sockets",
                    "step_type": "command",
                    "target_os": "linux",
                    "command_linux": "ss -tulpn | head -n 200 || netstat -tulpn | head -n 200 || true",
                    "timeout_seconds": 60,
                },
            ],
            "triggers": [],
        }
    )

    return runbooks


def demo_runbooks_windows_for_host(host: str, server_id: Optional[str]) -> List[Dict[str, Any]]:
    tags = ["demo", host, "windows"]

    common = {
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "tags": tags,
        "target_from_alert": False,
        "default_server_id": server_id,
        "target_os_filter": ["windows"],
    }

    runbooks: List[Dict[str, Any]] = []

    runbooks.append(
        {
            **common,
            "name": f"[{host}] Windows Disk Space Report",
            "category": "infrastructure",
            "description": "Demo (Windows): reports logical disk size/free space (read-only).",
            "steps": [
                {
                    "step_order": 1,
                    "name": "Logical disk free space",
                    "step_type": "command",
                    "target_os": "windows",
                    # NOTE: WinRM executor already runs PowerShell by default (run_ps).
                    "command_windows": (
                        "Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | "
                        "Select-Object DeviceID,VolumeName,"
                        "@{Name='SizeGB';Expression={[math]::Round($_.Size/1GB,1)}},"
                        "@{Name='FreeGB';Expression={[math]::Round($_.FreeSpace/1GB,1)}},"
                        "@{Name='FreePct';Expression={[math]::Round(($_.FreeSpace/$_.Size)*100,1)}} | "
                        "Format-Table -AutoSize"
                    ),
                    "timeout_seconds": 60,
                }
            ],
            "triggers": [],
        }
    )

    runbooks.append(
        {
            **common,
            "name": f"[{host}] Windows Event Log Errors (Last 30m)",
            "category": "diagnostics",
            "description": "Demo (Windows): shows recent System/Application errors (read-only).",
            "steps": [
                {
                    "step_order": 1,
                    "name": "System log errors",
                    "step_type": "command",
                    "target_os": "windows",
                    "command_windows": (
                        "$Start=(Get-Date).AddMinutes(-30); "
                        "$Events = Get-WinEvent -FilterHashtable @{LogName='System'; Level=2,3; StartTime=$Start} -MaxEvents 20 -ErrorAction SilentlyContinue; "
                        "if (-not $Events) { 'No System errors/warnings found in the last 30 minutes.'; exit 0 }; "
                        "$Events | Select-Object TimeCreated,Id,ProviderName,Message | Format-Table -AutoSize -Wrap"
                    ),
                    "timeout_seconds": 90,
                },
                {
                    "step_order": 2,
                    "name": "Application log errors",
                    "step_type": "command",
                    "target_os": "windows",
                    "command_windows": (
                        "$Start=(Get-Date).AddMinutes(-30); "
                        "$Events = Get-WinEvent -FilterHashtable @{LogName='Application'; Level=2,3; StartTime=$Start} -MaxEvents 20 -ErrorAction SilentlyContinue; "
                        "if (-not $Events) { 'No Application errors/warnings found in the last 30 minutes.'; exit 0 }; "
                        "$Events | Select-Object TimeCreated,Id,ProviderName,Message | Format-Table -AutoSize -Wrap"
                    ),
                    "timeout_seconds": 90,
                },
            ],
            "triggers": [],
        }
    )

    return runbooks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://t-aiops-01:8080")
    parser.add_argument("--hosts", required=True, help="Comma-separated hostnames, e.g. t-aiops-02,t-aiops-03")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--target-os", choices=["linux", "windows", "both"], default="linux")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--ssh-username", default="demo")
    parser.add_argument("--ssh-password", default="demo")
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="If runbook already exists (name conflict), update it in-place (replaces steps/triggers).",
    )

    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    if not hosts:
        _die("No hosts provided")

    # De-dupe while preserving order
    seen = set()
    unique_hosts: List[str] = []
    for h in hosts:
        if h.lower() not in seen:
            unique_hosts.append(h)
            seen.add(h.lower())

    token = login(base_url, args.username, args.password)

    created = 0
    skipped = 0

    for host in unique_hosts:
        server_id = ensure_server(
            base_url,
            token,
            name=host,
            hostname=host,
            port=args.ssh_port,
            username=args.ssh_username,
            password=args.ssh_password,
        )

        if not server_id:
            print(f"INFO: creating runbooks for {host} without default_server_id (server not present/creatable).")
        else:
            print(f"INFO: using server_id={server_id} for host={host}")

        runbooks: List[Dict[str, Any]] = []
        if args.target_os in ("linux", "both"):
            runbooks.extend(demo_runbooks_for_host(host, server_id))
        if args.target_os in ("windows", "both"):
            runbooks.extend(demo_runbooks_windows_for_host(host, server_id))

        for rb in runbooks:
            res = create_runbook(base_url, token, rb)
            if res is None:
                if not args.upsert:
                    skipped += 1
                    print(f"SKIP: {rb['name']} (already exists)")
                    continue

                existing_id = get_runbook_id_by_name(base_url, token, rb["name"])
                if not existing_id:
                    _die(f"Runbook exists but could not resolve id by name: {rb['name']}")
                update_runbook(base_url, token, existing_id, rb)
                print(f"OK: updated {rb['name']}")
                continue

            created += 1
            print(f"OK: created {rb['name']}")

    print(f"Done. created={created} skipped={skipped}")


if __name__ == "__main__":
    main()
