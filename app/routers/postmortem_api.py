"""
Post-Incident Postmortem API Router

Endpoints for generating, editing, and publishing AI-powered postmortem reports.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import User
from app.models_postmortem import PostmortemReport
from app.schemas_postmortem import (
    OutOfBandContextAdd,
    PostmortemListResponse,
    PostmortemReportCreate,
    PostmortemReportResponse,
    PostmortemReportUpdate,
)
from app.services.auth_service import get_current_user, require_role
from app.services.postmortem_service import PostmortemService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/postmortems", tags=["Postmortems"])


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    response_model=PostmortemReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a postmortem from alert data",
)
async def generate_postmortem(
    data: PostmortemReportCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """
    AI-generate a draft postmortem report for the specified alert.

    Gathers alert details, runbook executions, step outputs, and feedback,
    then calls the LLM to produce: impact summary, root cause, contributing
    factors, lessons learned, and action items.
    """
    if data.alert_id is None and data.app_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of alert_id or app_id must be provided",
        )

    if data.alert_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="alert_id is required for AI generation",
        )

    svc = PostmortemService(db)
    report = await svc.generate(
        alert_id=data.alert_id,
        created_by=current_user.id,
        app_id=data.app_id,
    )
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=PostmortemListResponse,
    summary="List postmortem reports (paginated)",
)
async def list_postmortems(
    app_id: Optional[UUID] = Query(None),
    report_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemListResponse:
    """List postmortem reports with optional filters."""
    svc = PostmortemService(db)
    items, total = await svc.list_reports(
        app_id=app_id,
        report_status=report_status,
        page=page,
        page_size=page_size,
    )
    return PostmortemListResponse(
        items=[PostmortemReportResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------

@router.get(
    "/{postmortem_id}",
    response_model=PostmortemReportResponse,
    summary="Get a postmortem report by ID",
)
async def get_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """Return a single postmortem report."""
    svc = PostmortemService(db)
    report = await svc.get(postmortem_id)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@router.put(
    "/{postmortem_id}",
    response_model=PostmortemReportResponse,
    summary="Update / edit a postmortem report",
)
async def update_postmortem(
    postmortem_id: UUID,
    data: PostmortemReportUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """Partially update an existing postmortem report."""
    svc = PostmortemService(db)
    report = await svc.update(postmortem_id, data)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Regenerate
# ---------------------------------------------------------------------------

@router.post(
    "/{postmortem_id}/regenerate",
    response_model=PostmortemReportResponse,
    summary="Re-generate AI sections (preserves manual edits)",
)
async def regenerate_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """
    Re-run AI generation for all narrative sections.

    Manual out-of-band context entries and manually added timeline events
    are preserved; AI-generated sections are refreshed.
    """
    svc = PostmortemService(db)
    report = await svc.regenerate(postmortem_id)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Out-of-band context
# ---------------------------------------------------------------------------

@router.post(
    "/{postmortem_id}/out-of-band",
    response_model=PostmortemReportResponse,
    summary="Add out-of-band context (Slack, vendor, customer notes)",
)
async def add_out_of_band_context(
    postmortem_id: UUID,
    entry: OutOfBandContextAdd,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """Append a manual context entry to the postmortem."""
    svc = PostmortemService(db)
    report = await svc.add_out_of_band_context(postmortem_id, entry)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

@router.post(
    "/{postmortem_id}/publish",
    response_model=PostmortemReportResponse,
    summary="Publish a reviewed postmortem",
)
async def publish_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> PostmortemReportResponse:
    """Mark a postmortem as published after review."""
    svc = PostmortemService(db)
    report = await svc.publish(postmortem_id, reviewed_by=current_user.id)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete(
    "/{postmortem_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a draft postmortem",
)
async def delete_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin"])),
) -> None:
    """Delete a postmortem (only drafts can be deleted)."""
    svc = PostmortemService(db)
    await svc.delete(postmortem_id)
