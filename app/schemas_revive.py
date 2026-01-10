"""
Pydantic schemas for AI Helper
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

class AIHelperQueryRequest(BaseModel):
    query: str
    page_context: Optional[dict] = None
    session_id: Optional[str] = None
    max_tokens: int = 1000

class AISessionCreate(BaseModel):
    title: str = "New Chat"

class AIMessage(BaseModel):
    role: str  # user, assistant, system
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

class AISessionResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[AIMessage] = []

    class Config:
        from_attributes = True

class AIHelperQueryResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    query_id: Optional[str] = None
    intent: Optional[str] = None
    confidence: float = 0.0
    sources: List[Dict[str, Any]] = []  # References to runbooks, docs, etc.
    suggested_actions: List[Dict[str, Any]] = [] # For buttons like "Execute Runbook"
