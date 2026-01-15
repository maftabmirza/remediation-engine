"""
Runbook View Routes - Read-only views for runbooks
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy. orm import Session
from uuid import UUID

from app.database import get_db
from app. models import User, ServerCredential
from app.models_remediation import Runbook, RunbookStep, RunbookTrigger
from app.services. auth_service import get_current_user

router = APIRouter(tags=["runbook-views"])
templates = Jinja2Templates(directory="templates")


@router.get("/runbooks/{runbook_id}/view", response_class=HTMLResponse)
async def view_runbook(
    request: Request,
    runbook_id:  UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    View runbook details page.
    Shows full runbook information, steps, triggers, and execution options.
    """
    # Load runbook with relationships
    runbook = db.query(Runbook).filter(Runbook.id == runbook_id).first()
    
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    # Load steps ordered by step_order
    steps = db.query(RunbookStep).filter(
        RunbookStep.runbook_id == runbook_id
    ).order_by(RunbookStep.step_order).all()
    
    # Load triggers
    triggers = db. query(RunbookTrigger).filter(
        RunbookTrigger. runbook_id == runbook_id
    ).order_by(RunbookTrigger.priority).all()
    
    # Load available servers for execution
    servers = db.query(ServerCredential).filter(
        ServerCredential.is_active == True
    ).all()
    
    return templates.TemplateResponse("runbook_view.html", {
        "request":  request,
        "user": current_user,
        "runbook": runbook,
        "steps": steps,
        "triggers": triggers,
        "servers": servers
    })