import sys
import socket
import os
import asyncio
import httpx
from urllib.parse import urlparse

async def check_service(name, host, port):
    print(f"Checking {name} ({host}:{port})...", end=" ")
    try:
        # 1. DNS Check
        ip = socket.gethostbyname(host)
        
        # 2. TCP Connect Check
        # specific check for postgres
        sock = socket.create_connection((host, port), timeout=3)
        sock.close()
        print(f"✅ OK (Resolved {ip})")
        return True
    except socket.gaierror:
        print(f"❌ DNS FAILED. Could not resolve hostname '{host}'.")
        return False
    except (ConnectionRefusedError, socket.timeout, OSError):
        print(f"❌ CONNECT FAILED. Could not connect to {host}:{port}.")
        return False

async def check_url(name, url):
    print(f"Checking HTTP {name} ({url})...", end=" ")
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            resp = await client.get(url)
            
            # 301/302 -> Redirect loop or bad config
            if resp.status_code in [301, 302, 307, 308]:
                print(f"❌ FAILED. Redirect detected ({resp.status_code}). Possible loop.")
                print(f"   Location: {resp.headers.get('location')}")
                return False
                
            # 404 -> Bad config / path mismatch
            if resp.status_code == 404:
                print(f"❌ FAILED. 404 Not Found. Check serve_from_sub_path.")
                return False
            
            # 200 or 401 (Auth Required) are good
            if resp.status_code in [200, 401]:
                print(f"✅ OK ({resp.status_code})")
                return True
                
            print(f"⚠️  WARNING. Unexpected status {resp.status_code}.")
            return True # Don't block strictly on this
            
    except Exception as e:
        print(f"❌ FAILED. {str(e)}")
        return False

async def main():
    print("--- 🔍 PRE-FLIGHT CHECKS ---")
    
    # Critical Services
    checks = [
        check_service("Postgres", os.getenv("POSTGRES_HOST", "postgres"), int(os.getenv("POSTGRES_PORT", 5432))),
    ]
    
    # Optional / Feature Services (but we want to check them if configured)
    grafana_url = os.getenv("GRAFANA_URL")
    if grafana_url:
        parsed = urlparse(grafana_url)
        checks.append(check_service("Grafana Host", parsed.hostname, parsed.port or 80))
        checks.append(check_url("Grafana URL", f"{grafana_url}/login"))

    prom_url = os.getenv("PROMETHEUS_URL")
    if prom_url:
        parsed = urlparse(prom_url)
        checks.append(check_service("Prometheus Host", parsed.hostname, parsed.port or 9090))

    results = await asyncio.gather(*checks)
    
    if all(results):
        print("--- ✅ ALL CHECKS PASSED ---")
        sys.exit(0)
    else:
        print("--- ❌ CHECKS FAILED ---")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
