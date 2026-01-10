"""
Audit API endpoints
"""
import os
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel

from app.database import get_db
from app.models import User, AuditLog, TerminalSession, ServerCredential

from app.services.auth_service import require_admin

router = APIRouter(prefix="/api/audit", tags=["Audit"])

class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    details_json: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TerminalSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    server_name: str
    started_at: datetime
    ended_at: Optional[datetime]
    has_recording: bool

    class Config:
        from_attributes = True


