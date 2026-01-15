"""
Knowledge Base Application Management Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
import logging

from app.database import get_db
from app.models import User
from app.models_application import Application
from app. models_application_knowledge import ApplicationKnowledgeConfig
from app.services. auth_service import get_current_user, require_permission
from app.services.git_sync_service import GitSyncService, GitCredentials, GitSyncConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge/apps", tags=["knowledge-apps"])


# Schemas
class AppKnowledgeConfigCreate(BaseModel):
    app_id: UUID
    git_repo_url: Optional[str] = None
    git_branch: str = "main"
    git_auth_type: str = "none"
    git_token: Optional[str] = None  # Will be encrypted
    sync_docs: bool = True
    sync_code: bool = False
    doc_patterns: List[str] = ["*.md", "docs/**/*"]
    auto_sync_enabled: bool = False
    sync_interval_hours: int = 24


class AppKnowledgeConfigUpdate(BaseModel):
    git_repo_url:  Optional[str] = None
    git_branch: Optional[str] = None
    git_auth_type: Optional[str] = None
    git_token:  Optional[str] = None
    sync_docs: Optional[bool] = None
    sync_code: Optional[bool] = None
    doc_patterns: Optional[List[str]] = None
    auto_sync_enabled: Optional[bool] = None
    sync_interval_hours: Optional[int] = None


class GitSyncRequest(BaseModel):
    sync_docs: bool = True
    sync_code: bool = False


# Endpoints
@router.get("/")
async def list_app_knowledge_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all applications with their knowledge config."""
    apps = db.query(Application).all()
    
    result = []
    for app in apps: 
        config = db.query(ApplicationKnowledgeConfig).filter(
            ApplicationKnowledgeConfig.app_id == app. id
        ).first()
        
        # Count documents for this app
        from app.models_knowledge import DesignDocument
        doc_count = db. query(DesignDocument).filter(
            DesignDocument.app_id == app. id
        ).count()
        
        result.append({
            "app_id": str(app.id),
            "app_name": app. name,
            "doc_count": doc_count,
            "git_configured": config is not None and config.git_repo_url is not None,
            "auto_sync":  config. auto_sync_enabled if config else False,
            "last_sync": config. last_sync_at. isoformat() if config and config.last_sync_at else None,
            "last_sync_status":  config.last_sync_status if config else None
        })
    
    return {"apps": result}


@router.get("/{app_id}/config")
async def get_app_knowledge_config(
    app_id: UUID,
    db:  Session = Depends(get_db),
    current_user:  User = Depends(get_current_user)
):
    """Get knowledge configuration for an application."""
    config = db.query(ApplicationKnowledgeConfig).filter(
        ApplicationKnowledgeConfig.app_id == app_id
    ).first()
    
    if not config:
        return {"configured": False}
    
    return {
        "configured": True,
        "git_repo_url": config.git_repo_url,
        "git_branch": config. git_branch,
        "git_auth_type": config. git_auth_type,
        "sync_docs": config. sync_docs,
        "sync_code": config.sync_code,
        "doc_patterns": config.doc_patterns,
        "auto_sync_enabled": config.auto_sync_enabled,
        "sync_interval_hours": config.sync_interval_hours,
        "last_sync_at": config.last_sync_at. isoformat() if config. last_sync_at else None,
        "last_sync_status": config.last_sync_status,
        "last_sync_stats": config.last_sync_stats
    }