import httpx
import asyncio

async def test_asset():
    # URL found in user debug output
    path = "public/build/runtime.js" # This redirected 302 before
    url = f"http://localhost:8080/grafana/{path}"
    print(f"Fetching {url}...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, follow_redirects=False)
        print(f"Status: {resp.status_code}")
        print(f"Location: {resp.headers.get('location')}")
        print(f"Content-Type: {resp.headers.get('content-type')}")
        # if 200, it should be javascript
        if resp.status_code == 200:
            print("Success! Asset loaded.")

if __name__ == "__main__":
    asyncio.run(test_asset())
