#!/usr/bin/env python
"""
Simple MCP Client Test Script v2
Tests connection to Grafana MCP server - keeps SSE connection open.
"""
import asyncio
import json
import httpx


async def test_mcp_connection():
    """Test the MCP server with concurrent SSE and POST."""
    base_url = "http://mcp-grafana:8000"
    sse_url = f"{base_url}/sse"
    
    print("=" * 60)
    print("MCP GRAFANA CONNECTION TEST v2")
    print("=" * 60)
    
    # We need to:
    # 1. Open SSE connection
    # 2. Get endpoint
    # 3. Send POST while SSE is still open
    # 4. Read responses from SSE
    
    post_endpoint = None
    endpoint_event = asyncio.Event()
    responses = []
    response_event = asyncio.Event()
    
    async def sse_listener(client):
        """Listen to SSE and extract endpoint + responses."""
        nonlocal post_endpoint
        
        try:
            async with client.stream(
                "GET",
                sse_url,
                headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"}
            ) as response:
                print(f"\n[SSE] Status: {response.status_code}")
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith("data:"):
                        data = line.split(":", 1)[1].strip()
                        print(f"[SSE] Data: {data[:100]}..." if len(data) > 100 else f"[SSE] Data: {data}")
                        
                        if data.startswith("/"):
                            post_endpoint = f"{base_url}{data}"
                            print(f"[SSE] ✅ Full POST URL: {post_endpoint}")
                            endpoint_event.set()
                        else:
                            # Try parsing as JSON response
                            try:
                                parsed = json.loads(data)
                                responses.append(parsed)
                                response_event.set()
                            except json.JSONDecodeError:
                                pass
                                
        except asyncio.CancelledError:
            print("[SSE] Listener cancelled")
        except Exception as e:
            print(f"[SSE] Error: {e}")
    
    async def make_request(client, method, params, req_id):
        """Send a JSON-RPC request."""
        await asyncio.wait_for(endpoint_event.wait(), timeout=5.0)
        
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        
        print(f"\n[POST] Sending {method}...")
        
        response = await client.post(
            post_endpoint,
            json=request,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"[POST] Status: {response.status_code}")
        
        if response.status_code == 202:
            # Accepted - response will come via SSE
            print("[POST] Accepted - waiting for SSE response...")
            response_event.clear()
            try:
                await asyncio.wait_for(response_event.wait(), timeout=5.0)
                for resp in responses:
                    if resp.get("id") == req_id:
                        return resp
            except asyncio.TimeoutError:
                print("[POST] Timeout waiting for SSE response")
                return None
        elif response.status_code == 200:
            return response.json()
        else:
            print(f"[POST] Error: {response.text}")
            return None
    
    # Use a single client for both SSE and POST
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Start SSE listener
        print(f"\n[1] Connecting to SSE: {sse_url}")
        sse_task = asyncio.create_task(sse_listener(client))
        
        try:
            # Wait for endpoint
            await asyncio.wait_for(endpoint_event.wait(), timeout=10.0)
            
            # Step 2: Initialize
            print("\n[2] Initializing MCP session...")
            init_result = await make_request(
                client,
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                },
                req_id=1
            )
            
            if init_result:
                print(f"[2] ✅ Initialize response: {json.dumps(init_result, indent=2)[:300]}")
            
            # Small delay
            await asyncio.sleep(0.5)
            
            # Step 3: List tools
            print("\n[3] Listing tools...")
            tools_result = await make_request(
                client,
                "tools/list",
                {},
                req_id=2
            )
            
            if tools_result:
                if "result" in tools_result and "tools" in tools_result["result"]:
                    tools = tools_result["result"]["tools"]
                    for tool in tools:
                        if tool.get("name") == "update_dashboard":
                            print(f"\n✅ Found update_dashboard tool details:\n")
                            print(json.dumps(tool, indent=2))
                            break
                else:
                    print(f"[3] Response: {json.dumps(tools_result, indent=2)[:500]}")
                    
        except asyncio.TimeoutError:
            print("\n❌ Timeout waiting for endpoint")
        finally:
            sse_task.cancel()
            try:
                await sse_task
            except asyncio.CancelledError:
                pass
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
