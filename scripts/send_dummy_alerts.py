#!/usr/bin/env python3
"""Send dummy Alertmanager-style alerts to the AIOps webhook.

Posts to: {base_url}/webhook/alerts

Uses only Python stdlib (no external deps).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def utc_now_iso() -> str:
    # Alertmanager typically sends RFC3339-ish with Z
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def post_json(url: str, payload: dict, timeout: int = 10) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        return e.code, body


def build_alert(
    alertname: str,
    severity: str,
    instance: str,
    job: str,
    summary: str,
    description: str,
    status: str,
) -> dict:
    # Fingerprint doesn't need to be real, just unique enough for testing.
    fp = f"dummy-{alertname}-{severity}-{instance}-{int(time.time())}-{random.randint(1000, 9999)}"
    return {
        "status": status,
        "labels": {
            "alertname": alertname,
            "severity": severity,
            "instance": instance,
            "job": job,
        },
        "annotations": {
            "summary": summary,
            "description": description,
        },
        "startsAt": utc_now_iso(),
        "endsAt": None,
        "generatorURL": "http://dummy.local/graph?g0.expr=up",
        "fingerprint": fp,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080", help="AIOps base URL")
    parser.add_argument("--count", type=int, default=3, help="Number of alerts to send")
    parser.add_argument("--status", choices=["firing", "resolved"], default="firing")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/webhook/alerts"

    examples = [
        ("HighCPUUsage", "warning", "t-aiops-01:9100", "node-exporter", "CPU usage high", "CPU > 85% for 5m"),
        ("DiskSpaceLow", "critical", "t-aiops-01:9100", "node-exporter", "Disk space low", "/var < 10% free"),
        ("ServiceDown", "critical", "t-aiops-01:9100", "blackbox", "Service down", "HTTP probe failed"),
        ("WinRMUnreachable", "warning", "t-aiops-02:5985", "winrm", "WinRM unreachable", "WSMan connection error"),
    ]

    alerts = []
    for i in range(args.count):
        alertname, severity, instance, job, summary, desc = examples[i % len(examples)]
        alerts.append(build_alert(alertname, severity, instance, job, summary, desc, args.status))

    payload = {
        "version": "4",
        "groupKey": "{}",
        "status": args.status,
        "receiver": "aiops-webhook",
        "groupLabels": {},
        "commonLabels": {},
        "commonAnnotations": {},
        "externalURL": "http://dummy.local/alertmanager",
        "alerts": alerts,
    }

    code, body = post_json(url, payload, timeout=args.timeout)
    print(f"POST {url} -> HTTP {code}")
    print(body)
    return 0 if 200 <= code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
