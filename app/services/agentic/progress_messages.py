"""
Progress Messages for AI Troubleshooting Agent

Defines the user-facing progress messages displayed during each phase
of the troubleshooting workflow.
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass


class TroubleshootingPhase(str, Enum):
    """Phases of the troubleshooting workflow"""
    IDENTIFY = "identify"
    VERIFY = "verify"
    INVESTIGATE = "investigate"
    PLAN = "plan"
    ACT = "act"
    WAITING = "waiting"
    COMPLETE = "complete"


@dataclass
class PhaseProgress:
    """Progress information for a phase"""
    phase: TroubleshootingPhase
    emoji: str
    title: str
    subtitle: Optional[str] = None
    details: Optional[Dict[str, str]] = None


# Phase display configuration with order numbers for enforcement
PHASE_ORDER = {
    TroubleshootingPhase.IDENTIFY: 1,
    TroubleshootingPhase.VERIFY: 2,
    TroubleshootingPhase.INVESTIGATE: 3,
    TroubleshootingPhase.PLAN: 4,
    TroubleshootingPhase.ACT: 5,
    TroubleshootingPhase.WAITING: 6,
    TroubleshootingPhase.COMPLETE: 7,
}

PHASE_MESSAGES: Dict[TroubleshootingPhase, PhaseProgress] = {
    TroubleshootingPhase.IDENTIFY: PhaseProgress(
        phase=TroubleshootingPhase.IDENTIFY,
        emoji="🔍",
        title="Phase 1: Identifying target...",
        subtitle="Determining what we're troubleshooting"
    ),
    TroubleshootingPhase.VERIFY: PhaseProgress(
        phase=TroubleshootingPhase.VERIFY,
        emoji="✅",
        title="Phase 2: Verifying environment...",
        subtitle="Confirming target server and OS"
    ),
    TroubleshootingPhase.INVESTIGATE: PhaseProgress(
        phase=TroubleshootingPhase.INVESTIGATE,
        emoji="📊",
        title="Phase 3: Gathering evidence...",
        subtitle="Querying metrics, logs, and history (minimum 2 tools)"
    ),
    TroubleshootingPhase.PLAN: PhaseProgress(
        phase=TroubleshootingPhase.PLAN,
        emoji="🧠",
        title="Phase 4: Analyzing findings...",
        subtitle="Forming hypothesis based on evidence"
    ),
    TroubleshootingPhase.ACT: PhaseProgress(
        phase=TroubleshootingPhase.ACT,
        emoji="🛠️",
        title="Phase 5: Suggesting command...",
        subtitle="Preparing recommended action"
    ),
    TroubleshootingPhase.WAITING: PhaseProgress(
        phase=TroubleshootingPhase.WAITING,
        emoji="⏳",
        title="Waiting for your output...",
        subtitle="Please run the command and share the result"
    ),
    TroubleshootingPhase.COMPLETE: PhaseProgress(
        phase=TroubleshootingPhase.COMPLETE,
        emoji="✨",
        title="Complete",
        subtitle="Task finished successfully"
    ),
}


# Tool-specific progress messages
TOOL_PROGRESS_MESSAGES: Dict[str, str] = {
    # Knowledge tools
    "search_knowledge": "📚 Searching knowledge base...",
    "get_runbook": "📘 Looking for runbooks...",
    "get_similar_incidents": "📜 Searching for similar incidents...",
    "get_proven_solutions": "💡 Looking for past solutions...",
    "get_feedback_history": "💬 Checking past feedback...",
    
    # Observability tools
    "query_grafana_metrics": "📈 Querying metrics...",
    "query_grafana_logs": "📝 Querying logs...",
    "get_alert_details": "🚨 Getting alert details...",
    
    # Investigation tools
    "get_recent_changes": "📋 Checking recent changes...",
    "get_correlated_alerts": "🔗 Finding correlated alerts...",
    "get_service_dependencies": "🔌 Checking service dependencies...",
    
    # Action tool
    "suggest_ssh_command": "🛠️ Preparing command suggestion...",
}


# Validation result messages for commands
COMMAND_VALIDATION_MESSAGES = {
    "allowed": {
        "emoji": "✅",
        "label": "Safe",
        "description": "Read-only or low-risk command"
    },
    "suspicious": {
        "emoji": "⚠️",
        "label": "Warning",
        "description": "This command requires elevated privileges or modifies system state"
    },
    "blocked": {
        "emoji": "⛔",
        "label": "COMMAND BLOCKED",
        "description": "This command has been blocked by the safety filter"
    }
}


# Data classification labels
DATA_CLASSIFICATION = {
    "fact": {
        "label": "FACT",
        "description": "Current state, verified and trustworthy",
        "tools": ["query_grafana_metrics", "query_grafana_logs", "get_recent_changes", "get_alert_details"]
    },
    "hint": {
        "label": "HINT",
        "description": "Historical reference, may or may not apply",
        "tools": ["get_similar_incidents", "get_proven_solutions"]
    },
    "reference": {
        "label": "REFERENCE",
        "description": "Documentation, may need adaptation",
        "tools": ["get_runbook", "search_knowledge"]
    }
}


def get_phase_message(phase: TroubleshootingPhase) -> PhaseProgress:
    """Get the progress message for a phase"""
    return PHASE_MESSAGES.get(phase, PHASE_MESSAGES[TroubleshootingPhase.IDENTIFY])


def get_tool_message(tool_name: str) -> str:
    """Get the progress message for a tool call"""
    return TOOL_PROGRESS_MESSAGES.get(tool_name, f"🔧 Calling {tool_name}...")


def get_data_classification(tool_name: str) -> str:
    """Get the data classification for a tool's output"""
    for classification, info in DATA_CLASSIFICATION.items():
        if tool_name in info["tools"]:
            return info["label"]
    return "INFO"


def format_phase_display(phase: TroubleshootingPhase, details: Optional[Dict[str, str]] = None) -> str:
    """Format a phase for display in the UI"""
    progress = get_phase_message(phase)
    output = f"{progress.emoji} {progress.title}"
    
    if progress.subtitle:
        output += f"\n   └─ {progress.subtitle}"
    
    if details:
        for key, value in details.items():
            output += f"\n   └─ {key}: {value}"
    
    return output


def format_evidence_section(
    current_state: Dict[str, str],
    historical: Dict[str, str]
) -> str:
    """Format the evidence gathered section with proper FACT/HINT labels"""
    output = ["**Evidence Gathered:**\n"]
    
    output.append("Current State (verified):")
    for tool, result in current_state.items():
        classification = get_data_classification(tool)
        output.append(f"- {tool}: {result} ← {classification}")
    
    output.append("\nHistorical Reference (may or may not apply):")
    for tool, result in historical.items():
        classification = get_data_classification(tool)
        output.append(f"- {tool}: {result} ← {classification}")
    
    return "\n".join(output)


def format_tool_result(tool_name: str, result: str) -> str:
    """Format a single tool result with classification label"""
    classification = get_data_classification(tool_name)
    return f"{tool_name}: {result} ← {classification}"


def get_phase_order(phase: TroubleshootingPhase) -> int:
    """Get the order number of a phase for enforcement"""
    return PHASE_ORDER.get(phase, 0)


def can_proceed_to_phase(current: TroubleshootingPhase, target: TroubleshootingPhase) -> bool:
    """Check if transition from current to target phase is valid"""
    current_order = get_phase_order(current)
    target_order = get_phase_order(target)
    # Can only advance by one phase or stay at same phase
    return target_order <= current_order + 1


def format_phase_progress(phase: TroubleshootingPhase, tool_calls_made: int = 0) -> str:
    """Format phase progress with tool call count for investigate phase"""
    progress = get_phase_message(phase)
    output = f"{progress.emoji} {progress.title}"
    
    if phase == TroubleshootingPhase.INVESTIGATE:
        output += f" [{tool_calls_made}/2 minimum tools]"
    
    if progress.subtitle:
        output += f"\n   └─ {progress.subtitle}"
    
    return output
