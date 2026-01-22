"""
Admin AI API Router

Provides administrative endpoints for managing AI permissions, viewing usage statistics,
and monitoring AI activity across all three pillars.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User
from app.models_ai import AIPermission, AISession, AIToolExecution
from app.services.ai_permission_service import AIPermissionService
from app.services.ai_audit_service import AIAuditService

router = APIRouter(prefix="/api/v1/admin/ai", tags=["Admin - AI"])


# Request/Response Models
class AIPermissionUpdate(BaseModel):
    permission: str  # 'allow', 'deny', 'confirm'
    
class AIPermissionResponse(BaseModel):
    id: UUID
    role_id: UUID
    pillar: str
    tool_category: Optional[str]
    tool_name: Optional[str]
    permission: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class AIPermissionListResponse(BaseModel):
    permissions: List[AIPermissionResponse]
    total: int

class ToolUsageItem(BaseModel):
    name: str
    count: int
    avg_time_ms: float
    success_rate: float

class AIUsageStatsResponse(BaseModel):
    total_sessions: int
    active_sessions: int
    total_tool_executions: int
    unique_tools_used: int
    avg_execution_time_ms: float
    success_rate: float
    top_tools: List[ToolUsageItem]
    by_pillar: dict
    by_user: dict

class AIAuditLogEntry(BaseModel):
    id: UUID
    timestamp: datetime
    user: str
    pillar: str
    action: str
    tool_name: Optional[str]
    status: str
    execution_time_ms: Optional[int]
    
class AIAuditLogResponse(BaseModel):
    logs: List[AIAuditLogEntry]
    total: int

class ActiveSessionInfo(BaseModel):
    session_id: UUID
    user: str
    pillar: str
    mode: Optional[str]
    started_at: datetime
    message_count: int
    duration_seconds: int

class ActiveSessionsResponse(BaseModel):
    sessions: List[ActiveSessionInfo]
    total: int


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure user is admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/permissions", response_model=AIPermissionListResponse)
async def list_permissions(
    role: Optional[str] = Query(None),
    pillar: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all AI permissions with optional filters.
    
    Query Parameters:
    - role: Filter by role name
    - pillar: Filter by pillar (inquiry, troubleshooting, revive)
    - limit: Max results per page
    - offset: Pagination offset
    """
    query = db.query(AIPermission)
    
    if pillar:
        query = query.filter(AIPermission.pillar == pillar)
    
    total = query.count()
    permissions = query.offset(offset).limit(limit).all()
    
    return AIPermissionListResponse(
        permissions=[AIPermissionResponse.from_orm(p) for p in permissions],
        total=total
    )


@router.get("/permissions/{permission_id}", response_model=AIPermissionResponse)
async def get_permission(
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get specific AI permission by ID."""
    permission = db.query(AIPermission).filter(AIPermission.id == permission_id).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    return AIPermissionResponse.from_orm(permission)


@router.put("/permissions/{permission_id}", response_model=AIPermissionResponse)
async def update_permission(
    permission_id: UUID,
    update: AIPermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update specific AI permission.
    
    Body:
    - permission: New permission level ('allow', 'deny', 'confirm')
    """
    permission = db.query(AIPermission).filter(AIPermission.id == permission_id).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    permission.permission = update.permission
    permission.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(permission)
    
    return AIPermissionResponse.from_orm(permission)


@router.get("/usage/stats", response_model=AIUsageStatsResponse)
async def get_usage_stats(
    days: int = Query(30, ge=1, le=365),
    pillar: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get AI usage statistics.
    
    Query Parameters:
    - days: Number of days to look back (default: 30)
    - pillar: Optional filter by pillar
    """
    audit_service = AIAuditService(db)
    
    # Get tool usage stats
    tool_stats = audit_service.get_tool_usage_stats(pillar=pillar, days=days)
    
    # Get session stats
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(AISession).filter(AISession.started_at >= since)
    
    if pillar:
        query = query.filter(AISession.pillar == pillar)
    
    total_sessions = query.count()
    active_sessions = query.filter(AISession.ended_at == None).count()
    
    # By user stats
    user_query = db.query(
        User.username,
        db.func.count(AISession.id).label('session_count')
    ).join(AISession).filter(
        AISession.started_at >= since
    ).group_by(User.username).order_by(
        db.func.count(AISession.id).desc()
    ).limit(10)
    
    by_user = {row.username: row.session_count for row in user_query.all()}
    
    # Format top tools
    top_tools = [
        ToolUsageItem(
            name=tool['name'],
            count=tool['count'],
            avg_time_ms=tool_stats.avg_execution_time_ms,
            success_rate=tool_stats.success_rate
        )
        for tool in tool_stats.top_tools[:10]
    ]
    
    return AIUsageStatsResponse(
        total_sessions=total_sessions,
        active_sessions=active_sessions,
        total_tool_executions=tool_stats.total_executions,
        unique_tools_used=tool_stats.unique_tools,
        avg_execution_time_ms=tool_stats.avg_execution_time_ms,
        success_rate=tool_stats.success_rate,
        top_tools=top_tools,
        by_pillar=tool_stats.by_pillar,
        by_user=by_user
    )


@router.get("/audit", response_model=AIAuditLogResponse)
async def get_audit_logs(
    user_id: Optional[UUID] = Query(None),
    pillar: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Query AI audit logs with filters.
    
    Query Parameters:
    - user_id: Filter by user UUID
    - pillar: Filter by pillar
    - tool_name: Filter by tool name
    - status: Filter by execution status
    - days: Number of days to look back
    - limit/offset: Pagination
    """
    since = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(AIToolExecution).join(AISession).join(User).filter(
        AIToolExecution.created_at >= since
    )
    
    if user_id:
        query = query.filter(AISession.user_id == user_id)
    
    if pillar:
        query = query.filter(AISession.pillar == pillar)
    
    if tool_name:
        query = query.filter(AIToolExecution.tool_name == tool_name)
    
    if status:
        query = query.filter(AIToolExecution.result_status == status)
    
    total = query.count()
    executions = query.order_by(AIToolExecution.created_at.desc()).offset(offset).limit(limit).all()
    
    logs = []
    for execution in executions:
        session = execution.session
        user = db.query(User).filter(User.id == session.user_id).first()
        
        logs.append(AIAuditLogEntry(
            id=execution.id,
            timestamp=execution.created_at,
            user=user.username if user else "Unknown",
            pillar=session.pillar,
            action=f"tool_execution:{execution.tool_name}",
            tool_name=execution.tool_name,
            status=execution.result_status,
            execution_time_ms=execution.execution_time_ms
        ))
    
    return AIAuditLogResponse(logs=logs, total=total)


@router.get("/sessions/active", response_model=ActiveSessionsResponse)
async def get_active_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get all currently active AI sessions."""
    active_sessions = db.query(AISession).filter(
        AISession.ended_at == None
    ).order_by(AISession.started_at.desc()).all()
    
    sessions_info = []
    for session in active_sessions:
        user = db.query(User).filter(User.id == session.user_id).first()
        duration = (datetime.utcnow() - session.started_at).total_seconds()
        
        sessions_info.append(ActiveSessionInfo(
            session_id=session.id,
            user=user.username if user else "Unknown",
            pillar=session.pillar,
            mode=session.revive_mode,
            started_at=session.started_at,
            message_count=session.message_count,
            duration_seconds=int(duration)
        ))
    
    return ActiveSessionsResponse(
        sessions=sessions_info,
        total=len(sessions_info)
    )


@router.post("/sessions/{session_id}/terminate")
async def terminate_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Forcefully terminate an active AI session."""
    session = db.query(AISession).filter(AISession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.ended_at is not None:
        raise HTTPException(status_code=400, detail="Session already ended")
    
    session.ended_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "session_id": str(session_id)}
