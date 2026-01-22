"""
Inquiry API Router

API endpoints for the Inquiry Pillar.
Enables the frontend to send natural language queries and receive analytical responses.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.agentic.inquiry_orchestrator import InquiryOrchestrator, InquiryResponse

router = APIRouter(
    prefix="/api/v1/inquiry",
    tags=["inquiry"],
    responses={404: {"description": "Not found"}},
)

# --- Request/Response Models ---

class InquiryRequest(BaseModel):
    query: str
    session_id: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = None

class InquiryAPIResponse(BaseModel):
    session_id: UUID
    answer: str
    tools_used: List[str]
    error: Optional[str] = None

# --- Endpoints ---

@router.post("/query", response_model=InquiryAPIResponse)
async def query_inquiry(
    request: InquiryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a natural language query to the Inquiry agent.
    """
    # Initialize orchestrator
    orchestrator = InquiryOrchestrator(
        db=db,
        user=current_user
    )
    
    # Process query
    result = await orchestrator.process_query(
        query=request.query,
        session_id=request.session_id,
        context=request.context
    )
    
    # Check for access denied or error in result
    if result.error == "AccessDenied":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.answer
        )
        
    return InquiryAPIResponse(
        session_id=result.session_id,
        answer=result.answer,
        tools_used=result.tools_used,
        error=result.error
    )

@router.get("/suggestions")
async def get_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get suggested inquiry questions based on user role and history.
    """
    # For now, return static suggestions. 
    # Future: Use AI or frequency analysis.
    return [
        "How many critical alerts occurred last week?",
        "Show me the MTTR for payment-service.",
        "Are alert volumes increasing for the frontend?",
        "List resolved incidents from yesterday."
    ]

# --- Streaming Endpoint ---

from fastapi.responses import StreamingResponse
import json
import asyncio

@router.post("/stream")
async def stream_inquiry(
    request: InquiryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream the inquiry response using Server-Sent Events (SSE).
    """
    async def event_generator():
        # 1. Send session ID (if provided or new one will be generated)
        # We'll just send a "connected" status first
        yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing query...'})}\n\n"
        
        try:
            # Initialize orchestrator
            orchestrator = InquiryOrchestrator(
                db=db,
                user=current_user
            )
            
            # 2. Process query (We await the full result for now as Agent doesn't stream yet)
            # Use asyncio.to_thread if it was sync, but it is async
            # yield "thinking" status
            yield f"data: {json.dumps({'type': 'status', 'content': 'Consulting knowledge base & tools...'})}\n\n"
            
            result = await orchestrator.process_query(
                query=request.query,
                session_id=request.session_id,
                context=request.context
            )
            
            # 3. Check error
            if result.error:
                yield f"data: {json.dumps({'type': 'error', 'content': result.answer})}\n\n"
                return

            # 4. Stream information about tools
            if result.tools_used:
                yield f"data: {json.dumps({'type': 'tools_used', 'content': result.tools_used})}\n\n"

            # 5. Stream the answer (simulate chunks for better UX if it's long, or just one chunk)
            # Since we have the full answer, we can just send it.
            # Splitting by lines or chunks to simulate stream feeling
            chunk_size = 50
            for i in range(0, len(result.answer), chunk_size):
                chunk = result.answer[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0.01) # Slight delay for effect

            # 6. Send session info update
            if result.session_id:
                yield f"data: {json.dumps({'type': 'session', 'session_id': str(result.session_id)})}\n\n"

            # 7. Done
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Streaming error: {traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Internal Server Error: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
