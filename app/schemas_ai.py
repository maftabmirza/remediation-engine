"""
Unified AI Response Schemas

Provides consistent response formats across all LLM interaction modes:
- RE-VIVE (side panel widget)
- Inquiry (observability investigation)  
- Troubleshooting (interactive terminal + AI)

This ensures the frontend can handle responses uniformly while allowing
mode-specific payload extensions.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class AIMode(str, Enum):
    """The AI interaction mode for the response"""
    REVIVE = "revive"           # Side panel quick queries
    INQUIRY = "inquiry"         # Deep observability investigation
    TROUBLESHOOT = "troubleshoot"  # Interactive troubleshooting with terminal


class ToolCall(BaseModel):
    """Record of a tool that was called during the response"""
    name: str
    arguments: Dict[str, Any] = {}
    result: Optional[str] = None
    duration_ms: Optional[int] = None


class AISource(BaseModel):
    """A source document or reference used in generating the response"""
    type: str  # "runbook", "knowledge", "alert", "log", "metric"
    title: str
    id: Optional[str] = None
    url: Optional[str] = None
    relevance: float = 0.0


class SuggestedAction(BaseModel):
    """An action the user can take based on the AI response"""
    action_type: str  # "run_command", "execute_runbook", "view_dashboard", "navigate"
    label: str
    payload: Dict[str, Any] = {}
    dangerous: bool = False  # If True, requires user confirmation


class CommandCard(BaseModel):
    """A command suggestion that can be executed by the user"""
    server: str
    command: str
    explanation: str
    card_id: Optional[str] = None


class AIResponseBase(BaseModel):
    """
    Base AI response schema used by all modes.
    
    Provides a consistent structure that the frontend can rely on,
    with optional fields for mode-specific data.
    """
    # Core response content
    response: str = Field(..., description="The AI's response text (supports markdown)")
    message: Optional[str] = Field(None, description="Alias for response (backwards compatibility)")
    
    # Mode identification
    mode: AIMode = Field(default=AIMode.TROUBLESHOOT, description="Which AI mode generated this response")
    
    # Session tracking
    session_id: Optional[str] = None
    query_id: Optional[str] = None
    
    # Response metadata
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    intent: Optional[str] = None
    
    # Tool usage (for Troubleshooting and future Inquiry)
    tool_calls: List[str] = Field(default_factory=list, description="Names of tools that were called")
    tool_details: List[ToolCall] = Field(default_factory=list, description="Detailed tool call records")
    
    # Sources and references
    sources: List[AISource] = Field(default_factory=list)
    
    # Command cards (for Troubleshooting mode)
    command_cards: List[CommandCard] = Field(default_factory=list)
    
    # Suggested actions
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    
    # Timing
    processing_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True  # Serialize enums as strings


class ReviveResponse(AIResponseBase):
    """
    Response schema for RE-VIVE mode (side panel widget).
    
    Focused on quick answers and observability queries.
    """
    mode: AIMode = AIMode.REVIVE
    
    # Page context that was used
    page_context: Optional[Dict[str, Any]] = None
    
    # Observability data (if query was about metrics/logs)
    observability_data: Optional[Dict[str, Any]] = None


class InquiryResponse(AIResponseBase):
    """
    Response schema for Inquiry mode (deep investigation).
    
    Includes detailed observability results from queries.
    """
    mode: AIMode = AIMode.INQUIRY
    
    # Query execution results
    logs_count: int = 0
    traces_count: int = 0
    metrics_count: int = 0
    
    # Raw data from observability queries
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    traces: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Generated queries
    generated_queries: Optional[Dict[str, Any]] = None


class TroubleshootResponse(AIResponseBase):
    """
    Response schema for Troubleshooting mode (terminal + AI).
    
    Includes command cards and terminal context.
    """
    mode: AIMode = AIMode.TROUBLESHOOT
    
    # Terminal context (if provided)
    terminal_context_used: bool = False
    
    # Number of agent iterations
    iterations: int = 0
    
    # Whether the agent has more work to do
    finished: bool = True
    
    # Error info if something went wrong
    error: Optional[str] = None


class AIErrorResponse(BaseModel):
    """Standardized error response for AI endpoints"""
    error: str
    error_code: Optional[str] = None
    mode: Optional[AIMode] = None
    session_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# Helper function to create responses
def create_ai_response(
    response: str,
    mode: AIMode = AIMode.TROUBLESHOOT,
    session_id: Optional[str] = None,
    tool_calls: Optional[List[str]] = None,
    **kwargs
) -> AIResponseBase:
    """
    Helper factory to create AI response objects.
    
    Automatically selects the appropriate response class based on mode.
    """
    response_classes = {
        AIMode.REVIVE: ReviveResponse,
        AIMode.INQUIRY: InquiryResponse,
        AIMode.TROUBLESHOOT: TroubleshootResponse,
    }
    
    cls = response_classes.get(mode, AIResponseBase)
    
    return cls(
        response=response,
        message=response,  # Backwards compatibility
        mode=mode,
        session_id=session_id,
        tool_calls=tool_calls or [],
        **kwargs
    )
