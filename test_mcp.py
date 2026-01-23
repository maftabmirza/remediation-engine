#!/usr/bin/env python
import asyncio
from app.services.mcp.client_sdk import MCPClient

async def main():
    print("\n" + "="*60)
    print("Testing Grafana MCP SDK Connection")
    print("="*60 + "\n")
    
    client = MCPClient('http://mcp-grafana:8000/sse')
    
    try:
        print("Connecting...")
        await client.connect()
        print("\u2705 Connected!\n")
        
        print("Listing tools...")
        tools = await client.list_tools()
        print(f"\u2705 Found {len(tools)} Grafana MCP tools:\n")
        
        for i, t in enumerate(tools[:15], 1):
            print(f"  {i}. {t.name}")
        
        if len(tools) > 15:
            print(f"\n  ... and {len(tools) - 15} more")
        
        print("\n" + "="*60)
        print("\u2705\u2705\u2705 SUCCESS! \u2705\u2705\u2705")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\u274c Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
