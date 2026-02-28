import httpx
import asyncio
import os
import sys

# Constants
PROXY_URL = "http://localhost:8080/grafana/dashboards"
INTERNAL_URL = "http://grafana:3000/grafana/dashboards"

async def check_proxy():
    print(f"--- Checking Proxy via {PROXY_URL} ---")
    # We need a valid JWT to pass the auth check in the proxy, OR we can try to hit a public URL.
    # But dashboards requires auth.
    # Let's hit the internal URL directly first to see what 'raw' Grafana returns.
    
    print(f"--- Checking Internal Grafana via {INTERNAL_URL} ---")
    async with httpx.AsyncClient() as client:
        try:
            # Add headers that the proxy would add
            headers = {
                "X-WEBAUTH-USER": "admin",
                "Host": "grafana:3000"
            }
            resp = await client.get(INTERNAL_URL, headers=headers, follow_redirects=True)
            print(f"Status: {resp.status_code}")
            print(f"Content-Type: {resp.headers.get('content-type')}")
            print(f"Title in HTML: {'<title>' in resp.text}")
            if '<title>' in resp.text:
                start = resp.text.find('<title>')
                end = resp.text.find('</title>') + 8
                print(f"Title Tag: {resp.text[start:end]}")
            
            print(f"Base Tag in HTML: {'<base' in resp.text}")
            print(f"Scripts in HTML: {resp.text.count('<script')}")
            
            # Print first 500 chars to see structure
            print("--- HTML HEAD ---")
            print(resp.text[:1000])
            print("--- END HEAD ---")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_proxy())
