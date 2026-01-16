"""
Agent Mode Models - For autonomous troubleshooting sessions

Enhanced with IVIPA workflow support:
- Identify: What is the problem?
- Verify: Where is it happening?
- Investigate: Gather evidence before fixing
- Plan: Synthesize hypothesis, validate against SOPs
- Act: Execute with safety validation
"""
import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AgentStatus(str, Enum):
    """Status of an agent session"""
    IDLE = "idle"
    THINKING = "thinking"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class IVIPAPhase(str, Enum):
    """
    IVIPA Workflow Phases for structured troubleshooting.

    This ensures the agent follows a disciplined approach:
    1. IDENTIFY - Understand what the problem is
    2. VERIFY - Confirm environment and context
    3. INVESTIGATE - Gather evidence (minimum 2 tools required)
    4. PLAN - Create hypothesis and validate against SOPs
    5. ACT - Execute remediation with safety checks
    """
    IDENTIFY = "identify"
    VERIFY = "verify"
    INVESTIGATE = "investigate"
    PLAN = "plan"
    ACT = "act"
    COMPLETE = "complete"


class StepType(str, Enum):
    """Type of agent step"""
    COMMAND = "command"
    ANALYSIS = "analysis"
    QUESTION = "question"
    COMPLETE = "complete"
    FAILED = "failed"
    # New types for IVIPA workflow
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    PLAN = "plan"


class StepStatus(str, Enum):
    """Status of an individual step"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"


class AgentSession(Base):
    """
    Represents an agent troubleshooting session.

    An agent session is created when the user starts "Agent Mode" with a goal.
    The agent then autonomously works through steps to achieve the goal.

    Enhanced with IVIPA workflow tracking for structured troubleshooting.
    """
    __tablename__ = "agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=True)

    # The goal the agent is trying to achieve
    goal = Column(Text, nullable=False)

    # Current status
    status = Column(String(50), default=AgentStatus.IDLE.value)

    # IVIPA Workflow Tracking
    current_phase = Column(String(20), default=IVIPAPhase.IDENTIFY.value)
    investigation_tool_count = Column(Integer, default=0)  # Must reach 2 before PLAN phase
    phase_history = Column(JSON, default=list)  # Track phase transitions with timestamps

    # Current plan (created during PLAN phase)
    current_plan = Column(JSON, nullable=True)  # Structured plan with steps
    plan_step_index = Column(Integer, default=0)  # Current step in the plan

    # Configuration
    auto_approve = Column(Boolean, default=False)
    max_steps = Column(Integer, default=30)  # Increased from 20 to support IVIPA workflow
    autonomy_level = Column(Integer, default=1)  # 0=Manual, 1=Guided, 2=Supervised, 3=Autonomous

    # Progress tracking
    current_step_number = Column(Integer, default=0)

    # Task list for tracking progress
    task_list = Column(JSON, default=list)  # List of {id, description, status, phase}

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Error message if failed
    error_message = Column(Text, nullable=True)

    # Final summary when completed
    summary = Column(Text, nullable=True)

    # Relationships
    user = relationship("User")
    chat_session = relationship("ChatSession")
    server = relationship("ServerCredential")
    steps = relationship("AgentStep", back_populates="agent_session", cascade="all, delete-orphan", order_by="AgentStep.step_number")


class AgentStep(Base):
    """
    Represents a single step in an agent's troubleshooting process.

    Each step can be:
    - A command to execute
    - An analysis/observation
    - A question for the user
    - A thinking block (visible reasoning)
    - A tool call
    - A plan
    - A completion message

    Enhanced with IVIPA phase tracking and visible thinking.
    """
    __tablename__ = "agent_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_session_id = Column(UUID(as_uuid=True), ForeignKey("agent_sessions.id"), nullable=False)

    # Step ordering
    step_number = Column(Integer, nullable=False)

    # IVIPA Phase this step belongs to
    ivipa_phase = Column(String(20), nullable=True)  # identify, verify, investigate, plan, act

    # Step type and content
    step_type = Column(String(20), nullable=False)  # command, analysis, question, complete, thinking, tool_call, plan
    content = Column(Text, nullable=False)  # The command or message

    # Visible Thinking - shown to user before action
    thinking = Column(Text, nullable=True)  # The agent's reasoning process (visible to user)
    reasoning = Column(Text, nullable=True)  # Brief explanation (backward compatibility)

    # Tool information (for tool_call step type)
    tool_name = Column(String(100), nullable=True)  # Name of tool being called
    tool_input = Column(JSON, nullable=True)  # Input parameters for the tool
    tool_output = Column(JSON, nullable=True)  # Structured output from the tool

    # Execution results
    output = Column(Text, nullable=True)  # Command output or user response
    exit_code = Column(Integer, nullable=True)  # Command exit code
    status = Column(String(20), default=StepStatus.PENDING.value)

    # Analysis of output (AI interpretation)
    output_analysis = Column(Text, nullable=True)  # AI's analysis of the output

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    agent_session = relationship("AgentSession", back_populates="steps")
