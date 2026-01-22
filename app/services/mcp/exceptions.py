class MCPError(Exception):
    """Base exception for MCP errors"""
    pass

class MCPConnectionError(MCPError):
    """Failed to connect to MCP server"""
    pass

class MCPRequestError(MCPError):
    """Error making request to MCP server"""
    pass

class MCPProtocolError(MCPError):
    """Protocol violation or invalid response"""
    pass

class MCPToolError(MCPError):
    """Error executing a tool"""
    pass
