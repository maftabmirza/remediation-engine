#!/usr/bin/env python3
"""Post-deploy verification checks with warn or strict behavior."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib import error, request


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def load_env_file(file_path: Path) -> Dict[str, str]:
    """Load simple KEY=VALUE pairs from a dotenv-style file."""
    values: Dict[str, str] = {}
    if not file_path.exists():
        return values

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_admin_credentials(repo_root: Path) -> Tuple[str, Optional[str]]:
    """Resolve admin credentials from env first, then .env."""
    env_values = load_env_file(repo_root / ".env")
    username = os.environ.get("ADMIN_USERNAME") or env_values.get("ADMIN_USERNAME") or "admin"
    password = os.environ.get("ADMIN_PASSWORD") or env_values.get("ADMIN_PASSWORD")
    return username, password


def http_json_request(
    url: str,
    *,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 10,
) -> Tuple[int, str]:
    """Make an HTTP request and return status code plus body."""
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def detect_compose_command() -> Iterable[str]:
    """Return the docker compose command available on this host."""
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]


def check_health(base_url: str) -> CheckResult:
    status_code, _ = http_json_request(f"{base_url.rstrip('/')}/health")
    if status_code == 200:
        return CheckResult("health", "pass", "Application health endpoint returned 200")
    return CheckResult("health", "fail", f"Health endpoint returned {status_code}")


def check_atlas_status(repo_root: Path) -> CheckResult:
    compose_cmd = list(detect_compose_command())
    command = [
        *compose_cmd,
        "exec",
        "-T",
        "remediation-engine",
        "sh",
        "-lc",
        'atlas migrate status --dir "file:///app/atlas/migrations" --url "$DATABASE_URL"',
    ]
    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        detail = output.splitlines()[0] if output else "Atlas migration status is clean"
        return CheckResult("atlas", "pass", detail)
    detail = output.splitlines()[0] if output else "Atlas migration status failed"
    return CheckResult("atlas", "fail", detail)


def check_postmortems_endpoint(
    base_url: str,
    username: str,
    password: Optional[str],
) -> CheckResult:
    if not password:
        return CheckResult(
            "postmortems",
            "warn",
            "ADMIN_PASSWORD is unavailable; skipping authenticated postmortems smoke test",
        )

    login_status, login_body = http_json_request(
        f"{base_url.rstrip('/')}/api/auth/login",
        method="POST",
        payload={"username": username, "password": password},
    )
    if login_status != 200:
        return CheckResult(
            "postmortems",
            "fail",
            f"Login failed with status {login_status}",
        )

    try:
        login_data = json.loads(login_body)
    except json.JSONDecodeError:
        return CheckResult("postmortems", "fail", "Login response was not valid JSON")

    token = login_data.get("access_token") or login_data.get("token")
    if not token:
        return CheckResult("postmortems", "fail", "Login response did not include an access token")

    endpoint_status, _ = http_json_request(
        f"{base_url.rstrip('/')}/api/postmortems/?page_size=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    if endpoint_status == 200:
        return CheckResult("postmortems", "pass", "Authenticated postmortems list returned 200")
    return CheckResult(
        "postmortems",
        "fail",
        f"Authenticated postmortems list returned {endpoint_status}",
    )


def evaluate_results(results: Iterable[CheckResult], mode: str) -> int:
    """Print a deployment verification summary and return the exit code."""
    failed = [result for result in results if result.status == "fail"]
    warned = [result for result in results if result.status == "warn"]

    for result in results:
        prefix = {
            "pass": "PASS",
            "warn": "WARN",
            "fail": "FAIL",
        }.get(result.status, result.status.upper())
        print(f"[{prefix}] {result.name}: {result.detail}")

    if failed and mode == "strict":
        print("Deployment verification failed in strict mode.", file=sys.stderr)
        return 1

    if failed and mode == "warn":
        print("Deployment verification found failures, but continuing because mode=warn.")
        return 0

    if warned:
        print("Deployment verification completed with warnings.")
    else:
        print("Deployment verification passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a deployment after container startup")
    parser.add_argument("--mode", choices=["warn", "strict"], default=os.environ.get("AIOPS_DEPLOY_VERIFY_MODE", "warn"))
    parser.add_argument("--base-url", default=os.environ.get("AIOPS_BASE_URL", "http://localhost:8080"))
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    username, password = resolve_admin_credentials(repo_root)
    results = [
        check_health(args.base_url),
        check_atlas_status(repo_root),
        check_postmortems_endpoint(args.base_url, username, password),
    ]
    return evaluate_results(results, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())