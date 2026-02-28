"""
Test script for MCP SDK connection
"""
import asyncio
from app.services.mcp.client_sdk import MCPClient

async def test_mcp():
    """Test MCP connection using SDK client"""
    print("\n" + "="*60)
    print("Testing MCP Grafana Server Connection (Python SDK)")
    print("="*60 + "\n")
    
    client = MCPClient('http://mcp-grafana:8000/sse')
    
    try:
        # Connect
        print("1. Connecting to MCP server...")
        await client.connect()
        print("✅ Connected successfully!\n")
        
        # List tools
        print("2. Listing available Grafana MCP tools...")
        tools = await client.list_tools()
        print(f"✅ Found {len(tools)} tools:\n")
        
        for i, tool in enumerate(tools[:20], 1):
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            print(f"  {i}. {tool.name}")
            print(f"     {desc}")
        
        if len(tools) > 20:
            print(f"\n  ... and {len(tools) - 20} more tools")
        
        print("\n" + "="*60)
        print("✅✅✅ SDK CONNECTION TEST PASSED! ✅✅✅")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_mcp())
