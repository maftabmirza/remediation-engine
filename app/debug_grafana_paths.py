import httpx
import asyncio
import os

async def check_paths():
    base_url = "http://grafana:3000"
    paths = [
        "/api/health",
        "/grafana/api/health",
        "/public/build/runtime.js", # Need to find a real file, usually there's some manifest or something. 
        "/grafana/public/build/runtime.js",
        "/login",
        "/grafana/login"
    ]
    
    print(f"Checking Grafana at {base_url}...")
    
    async with httpx.AsyncClient() as client:
        for path in paths:
            url = f"{base_url}{path}"
            try:
                resp = await client.get(url, follow_redirects=False)
                print(f"GET {url} -> {resp.status_code}")
                if resp.status_code == 200:
                    print(f"Content-Type: {resp.headers.get('content-type')}")
                    if "text/html" in resp.headers.get('content-type', ''):
                        print(f"Title: {resp.text[:200]}") # First 200 chars
            except Exception as e:
                print(f"GET {url} -> ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_paths())
