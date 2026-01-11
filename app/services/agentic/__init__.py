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
- ProgressMessages: User-facing progress indicators for each phase
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import importlib


_EXPORTS: dict[str, tuple[str, str]] = {
    "AgenticOrchestrator": ("app.services.agentic.orchestrator", "AgenticOrchestrator"),
    "ToolRegistry": ("app.services.agentic.tool_registry", "ToolRegistry"),
    "Tool": ("app.services.agentic.tool_registry", "Tool"),
    "NativeToolAgent": ("app.services.agentic.native_agent", "NativeToolAgent"),
    "ReActAgent": ("app.services.agentic.react_agent", "ReActAgent"),

    # Progress messages
    "TroubleshootingPhase": ("app.services.agentic.progress_messages", "TroubleshootingPhase"),
    "PhaseProgress": ("app.services.agentic.progress_messages", "PhaseProgress"),
    "PHASE_MESSAGES": ("app.services.agentic.progress_messages", "PHASE_MESSAGES"),
    "TOOL_PROGRESS_MESSAGES": ("app.services.agentic.progress_messages", "TOOL_PROGRESS_MESSAGES"),
    "COMMAND_VALIDATION_MESSAGES": ("app.services.agentic.progress_messages", "COMMAND_VALIDATION_MESSAGES"),
    "get_phase_message": ("app.services.agentic.progress_messages", "get_phase_message"),
    "get_tool_message": ("app.services.agentic.progress_messages", "get_tool_message"),
    "format_phase_display": ("app.services.agentic.progress_messages", "format_phase_display"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(_EXPORTS.keys())))


__all__ = sorted(_EXPORTS.keys())


if TYPE_CHECKING:
    from app.services.agentic.orchestrator import AgenticOrchestrator
    from app.services.agentic.tool_registry import ToolRegistry, Tool
    from app.services.agentic.native_agent import NativeToolAgent
    from app.services.agentic.react_agent import ReActAgent
    from app.services.agentic.progress_messages import (
        TroubleshootingPhase,
        PhaseProgress,
        PHASE_MESSAGES,
        TOOL_PROGRESS_MESSAGES,
        COMMAND_VALIDATION_MESSAGES,
        get_phase_message,
        get_tool_message,
        format_phase_display,
    )
