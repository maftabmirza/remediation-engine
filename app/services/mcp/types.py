from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field

class MCPToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Optional[Any] = None

class MCPTool(BaseModel):
    name: str
    description: str = ""
    # Grafana MCP uses 'inputSchema' while some others use 'input_schema'
    # Make both optional to handle different server implementations
    input_schema: Optional[Dict[str, Any]] = Field(default=None, alias="inputSchema")
    # For compatibility, also accept these alternate fields
    annotations: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True  # Allow both field name and alias
        extra = "allow"  # Allow additional fields from server

class MCPContent(BaseModel):
    type: Literal["text", "image", "resource"]
    text: Optional[str] = None
    data: Optional[str] = None
    mimeType: Optional[str] = None
    resource: Optional[Any] = None

class MCPToolResult(BaseModel):
    content: List[MCPContent]
    isError: bool = False

class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None  # None for notifications per JSON-RPC 2.0

class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Union[str, int]
