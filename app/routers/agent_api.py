"""
Agent API endpoints (REST)
"""
import logging
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import User, LLMProvider
from app.models_chat import ChatSession
from app.models_agent import AgentSession, AgentStep, AgentStatus, StepStatus
from app.services.auth_service import get_current_user
from app.services.agent_service import AgentService
from app.services.ssh_service import get_ssh_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["Agent"])


# --- Request/Response Models ---

class StartAgentRequest(BaseModel):
    chat_session_id: UUID
    server_id: UUID
    goal: str
    auto_approve: bool = False
    max_steps: int = 20


class AgentStepResponse(BaseModel):
    id: UUID
    step_number: int
    step_type: str
    content: str
    reasoning: Optional[str] = None
    output: Optional[str] = None
    exit_code: Optional[int] = None
    status: str
    created_at: datetime
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentSessionResponse(BaseModel):
    id: UUID
    goal: str
    status: str
    auto_approve: bool
    max_steps: int
    current_step_number: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True


class AgentStatusResponse(BaseModel):
    id: UUID
    status: str
    goal: str
    current_step: int
    max_steps: int
    pending_step: Optional[AgentStepResponse] = None
    is_auto_approve: bool


class AnswerQuestionRequest(BaseModel):
    answer: str


# --- API Endpoints ---

@router.post("/start", response_model=AgentSessionResponse)
async def start_agent(
    request: StartAgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new agent session with a goal.
    
    The agent will begin working toward the goal, executing commands
    and analyzing output until the goal is achieved.
    """
    # Validate chat session exists and belongs to user
    chat_session = db.query(ChatSession).filter(
        ChatSession.id == request.chat_session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Check for existing active agent session
    existing = db.query(AgentSession).filter(
        AgentSession.chat_session_id == request.chat_session_id,
        AgentSession.status.in_([
            AgentStatus.IDLE.value,
            AgentStatus.THINKING.value,
            AgentStatus.AWAITING_APPROVAL.value,
            AgentStatus.EXECUTING.value,
            AgentStatus.ANALYZING.value
        ])
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="An active agent session already exists for this chat"
        )
    
    # Create agent session
    service = AgentService(db)
    session = await service.create_session(
        chat_session_id=request.chat_session_id,
        user_id=current_user.id,
        server_id=request.server_id,
        goal=request.goal,
        auto_approve=request.auto_approve,
        max_steps=request.max_steps
    )
    
    logger.info(f"Started agent session {session.id} for user {current_user.username}")
    
    return session


@router.get("/{session_id}", response_model=AgentSessionResponse)
async def get_agent_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get an agent session by ID."""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    return session


@router.get("/{session_id}/status", response_model=AgentStatusResponse)
async def get_agent_status(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the current status of an agent session including any pending step."""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    # Get pending step if any
    pending_step = db.query(AgentStep).filter(
        AgentStep.agent_session_id == session_id,
        AgentStep.status == StepStatus.PENDING.value
    ).first()
    
    return AgentStatusResponse(
        id=session.id,
        status=session.status,
        goal=session.goal,
        current_step=session.current_step_number,
        max_steps=session.max_steps,
        pending_step=pending_step,
        is_auto_approve=session.auto_approve
    )


@router.get("/{session_id}/steps", response_model=List[AgentStepResponse])
async def get_agent_steps(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all steps for an agent session."""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    steps = db.query(AgentStep).filter(
        AgentStep.agent_session_id == session_id
    ).order_by(AgentStep.step_number.asc()).all()
    
    return steps


@router.post("/{session_id}/approve")
async def approve_step(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve the pending command and allow it to execute."""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    if session.status != AgentStatus.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Agent is not awaiting approval (status: {session.status})"
        )
    
    service = AgentService(db)
    step = await service.approve_step(session)
    
    if not step:
        raise HTTPException(status_code=404, detail="No pending step found")
    
    return {"status": "approved", "step_id": str(step.id)}


@router.post("/{session_id}/reject")
async def reject_step(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject/skip the pending command."""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    if session.status != AgentStatus.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Agent is not awaiting approval (status: {session.status})"
        )
    
    service = AgentService(db)
    step = await service.reject_step(session)
    
    if not step:
        raise HTTPException(status_code=404, detail="No pending step found")
    
    return {"status": "rejected", "step_id": str(step.id)}


@router.post("/{session_id}/answer")
async def answer_question(
    session_id: UUID,
    request: AnswerQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Provide an answer to the agent's question."""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    # Find the question step
    question_step = db.query(AgentStep).filter(
        AgentStep.agent_session_id == session_id,
        AgentStep.step_type == "question",
        AgentStep.status == StepStatus.PENDING.value
    ).first()
    
    if not question_step:
        raise HTTPException(status_code=400, detail="No pending question found")
    
    # Store the answer
    question_step.output = request.answer
    question_step.status = StepStatus.EXECUTED.value
    question_step.executed_at = datetime.utcnow()
    db.commit()
    
    return {"status": "answered", "step_id": str(question_step.id)}


@router.post("/{session_id}/stop")
async def stop_agent(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop the agent session."""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    # If already finished, just return success (idempotent)
    if session.status in [
        AgentStatus.COMPLETED.value,
        AgentStatus.FAILED.value,
        AgentStatus.STOPPED.value
    ]:
        return {"status": session.status, "session_id": str(session.id), "already_finished": True}
    
    service = AgentService(db)
    await service.stop_session(session)
    
    return {"status": "stopped", "session_id": str(session.id)}


@router.get("/by-chat/{chat_session_id}", response_model=Optional[AgentSessionResponse])
async def get_agent_by_chat(
    chat_session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the most recent agent session for a chat session."""
    session = db.query(AgentSession).filter(
        AgentSession.chat_session_id == chat_session_id,
        AgentSession.user_id == current_user.id
    ).order_by(AgentSession.created_at.desc()).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="No agent session found")
    
    return session
