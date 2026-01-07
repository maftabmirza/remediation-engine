"""
Agentic RAG System for AI-powered Alert Troubleshooting

This module provides an agentic approach to troubleshooting where the LLM
can dynamically request information through tools rather than receiving
all context upfront.

Components:
- ToolRegistry: Defines available tools and their schemas
- NativeToolAgent: Uses native function calling (OpenAI, Anthropic, Google)
- ReActAgent: Text-based ReAct pattern for Ollama/local LLMs
- AgenticOrchestrator: Routes to appropriate agent based on provider
"""

from app.services.agentic.orchestrator import AgenticOrchestrator
from app.services.agentic.tool_registry import ToolRegistry, Tool
from app.services.agentic.native_agent import NativeToolAgent
from app.services.agentic.react_agent import ReActAgent

__all__ = [
    "AgenticOrchestrator",
    "ToolRegistry",
    "Tool",
    "NativeToolAgent",
    "ReActAgent",
]
