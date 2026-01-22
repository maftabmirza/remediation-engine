from typing import List, Optional, Dict
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.services.agent_orchestrator import AgentOrchestrator
from app.models_agent_pool import AgentTask, AgentPool

# Auth & Models for Standalone Session handling
from app.models import User
from app.services.auth_service import get_current_user
from app.models_revive import AISession

router = APIRouter(prefix="/api/agents", tags=["agents"])
orchestrator = AgentOrchestrator()

# Schemas
class PoolCreate(BaseModel):
    session_id: UUID
    name: str
    max_concurrent: int = 3

class AgentSpawnRequest(BaseModel):
    pool_id: UUID
    goal: str
    agent_type: str = "background"
    priority: int = 10
    auto_iterate: bool = False
    max_iterations: int = 5

class AgentTaskResponse(BaseModel):
    id: UUID
    pool_id: UUID
    status: str
    goal: str
    agent_type: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    iteration_count: int = 0
    max_iterations: int = 5

    class Config:
        orm_mode = True


class AgentPoolResponse(BaseModel):
    id: UUID
    name: str
    active_tasks: List[AgentTaskResponse]
    queued_tasks: List[AgentTaskResponse]
    completed_tasks: List[AgentTaskResponse] # Limit to recent?

    class Config:
        orm_mode = True

class HQStatusResponse(BaseModel):
    pools: List[AgentPoolResponse]


# Endpoints

@router.post("/pools")
def create_pool(request: PoolCreate, db: Session = Depends(get_db)):
    pool = orchestrator.create_pool(db, request.session_id, request.name, request.max_concurrent)
    return {"id": pool.id, "name": pool.name}

@router.post("/spawn")
async def spawn_agent(request: AgentSpawnRequest, db: Session = Depends(get_db)):
    task = await orchestrator.spawn_agent(
        request.pool_id,
        request.goal,
        request.agent_type,
        request.priority,
        auto_iterate=request.auto_iterate,
        max_iterations=request.max_iterations
    )
    return {"task_id": task.id, "status": task.status}

@router.get("/hq/{session_id}")
def get_hq_status(
    session_id: UUID, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Handle Standalone Mode:
    # If the session_id passed matches the current user's ID (stripped of prefix by frontend),
    # it means we are in standalone chat. We need to map this to a real persistent session
    # in the database to satisfy Foreign Key constraints for the Agent Pool.
    real_session_id = session_id
    
    if session_id == current_user.id:
        # Find existing "Agent HQ Default" session
        existing_session = db.query(AISession).filter(
            AISession.user_id == current_user.id,
            AISession.title == "Agent HQ Default"
        ).first()

        if existing_session:
            real_session_id = existing_session.id
        else:
            # Create new persistent session for Agent HQ
            new_session = AISession(
                id=uuid4(),
                user_id=current_user.id,
                title="Agent HQ Default",
                pillar="revive", # Required field
                created_at=datetime.utcnow()
            )
            db.add(new_session)
            db.commit()
            real_session_id = new_session.id

    pool = orchestrator.get_pool_by_session(db, real_session_id)
    if not pool:
        # Auto-create pool if missing
        pool = orchestrator.create_pool(db, real_session_id, "Default Pool")
    
    # Fetch tasks
    tasks = db.query(AgentTask).filter(AgentTask.pool_id == pool.id).all()
    
    active = [t for t in tasks if t.status == 'running']
    queued = [t for t in tasks if t.status == 'queued']
    completed = [t for t in tasks if t.status in ['completed', 'failed']]
    
    return {
        "pool": {
            "id": pool.id,
            "name": pool.name,
            "max_concurrent": pool.max_concurrent_agents
        },
        "tasks": {
            "active": active,
            "queued": queued,
            "completed": completed
        }
    }

@router.post("/tasks/{task_id}/stop")
async def stop_agent(task_id: UUID):
    success = await orchestrator.stop_agent(task_id)
    return {"success": success}
