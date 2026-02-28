from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict

@dataclass
class ToolParameter:
    """Definition of a tool parameter"""
    name: str
    type: str  # string, integer, boolean, array
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None
    items: Optional[Dict[str, Any]] = None

@dataclass
class Tool:
    """Definition of a tool that can be called by the LLM"""
    name: str
    description: str
    # Added fields from new definition
    category: str = "general"
    risk_level: str = "read"
    requires_confirmation: bool = False
    
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
            if param.items:
                prop["items"] = param.items
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
            if param.items:
                prop["items"] = param.items
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
        params_desc = []
        for param in self.parameters:
            req = " (required)" if param.required else ""
            params_desc.append(f"  - {param.name}: {param.description}{req}")

        params_str = "\n".join(params_desc) if params_desc else "  (no parameters)"
        return f"{self.name}: {self.description}\n  Parameters:\n{params_str}"
