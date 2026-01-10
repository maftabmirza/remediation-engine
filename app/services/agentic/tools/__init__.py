"""
Tool Base Classes and Registry Interface

Contains the core Tool and ToolParameter dataclasses used by all tool modules,
as well as the base ToolModule class for creating modular tool collections.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """Definition of a tool parameter"""
    name: str
    type: str  # "string", "integer", "boolean", etc.
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class Tool:
    """Definition of a tool that can be called by the LLM"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema"""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Convert to Anthropic tool schema"""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    def to_react_description(self) -> str:
        """Convert to text description for ReAct prompting"""
        params_desc = ", ".join([
            f"{p.name}: {p.type}" + (" (required)" if p.required else "")
            for p in self.parameters
        ])
        return f"- {self.name}({params_desc}): {self.description}"


class ToolModule(ABC):
    """
    Base class for modular tool collections.
    
    Each module provides a set of related tools (e.g., knowledge tools,
    observability tools, troubleshooting tools).
    """
    
    def __init__(self, db: Session, alert_id: Optional[UUID] = None):
        self.db = db
        self.alert_id = alert_id
        self._tools: Dict[str, Tool] = {}
        self._handlers: Dict[str, Callable] = {}
        self._register_tools()
    
    @abstractmethod
    def _register_tools(self):
        """Register all tools provided by this module. Override in subclasses."""
        pass
    
    def _register_tool(self, tool: Tool, handler: Callable):
        """Register a tool with its handler"""
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
    
    def get_tools(self) -> List[Tool]:
        """Get all tools from this module"""
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a specific tool by name"""
        return self._tools.get(name)
    
    def get_handler(self, name: str) -> Optional[Callable]:
        """Get the handler for a tool"""
        return self._handlers.get(name)
    
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string"""
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"Error: Tool '{tool_name}' not found in this module"
        
        try:
            result = handler(arguments)
            return str(result)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
