"""
Quick test script to verify MCP Grafana server connectivity and tools
"""
import asyncio
import sys
sys.path.append('/app')

from app.services.mcp.pool import get_mcp_client

async def test_mcp_connection():
    """Test MCP client connectivity and tool listing"""
    print("=" * 60)
    print("Testing MCP Grafana Server Connection")
    print("=" * 60)
    
    try:
        # Get MCP client from pool
        print("\n1. Getting MCP client from connection pool...")
        client = await get_mcp_client(
            server_url="http://mcp-grafana:8000"
        )
        print("✅ MCP client obtained successfully")
        
        # List available tools
        print("\n2. Listing available Grafana MCP tools...")
        tools = await client.list_tools()
        print(f"✅ Found {len(tools)} MCP tools:")
        for i, tool in enumerate(tools[:10], 1):  # Show first 10
            print(f"   {i}. {tool.name}: {tool.description}")
        
        if len(tools) > 10:
            print(f"   ... and {len(tools) - 10} more tools")
        
        # Test a simple tool call
        print("\n3. Testing list_alert_rules tool...")
        try:
            result = await client.call_tool("list_alert_rules", {})
            print(f"✅ Tool call successful!")
            print(f"   Result type: {result.isError and 'ERROR' or 'SUCCESS'}")
            if result.content:
                print(f"   Content items: {len(result.content)}")
                if result.content[0].text:
                    preview = result.content[0].text[:200]
                    print(f"   Preview: {preview}...")
        except Exception as e:
            print(f"⚠️  Tool call failed: {e}")
            print("   (This might be expected if GRAFANA_SERVICE_ACCOUNT_TOKEN is not set)")
        
        print("\n" + "=" * 60)
        print("MCP Server Test Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
