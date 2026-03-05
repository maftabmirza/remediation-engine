"""
Postmortem Reports API Router
Endpoints for generating, editing, and publishing post-incident reviews.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import User
from app.schemas_postmortem import (
    OutOfBandContextAdd,
    PostmortemListResponse,
    PostmortemReportCreate,
    PostmortemReportResponse,
    PostmortemReportUpdate,
)
from app.services.auth_service import get_current_user, require_admin, require_role
from app.services.postmortem_service import PostmortemService

router = APIRouter(prefix="/api/postmortems", tags=["Postmortems"])


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    response_model=PostmortemReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_postmortem(
    payload: PostmortemReportCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """
    Generate a draft postmortem from an alert.

    Gathers incident data (executions, metrics, feedback) and calls the LLM
    to produce structured content.
    """
    if payload.alert_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="alert_id is required to generate a postmortem",
        )

    svc = PostmortemService(db)
    report = await svc.generate(alert_id=payload.alert_id, created_by=current_user.id)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/", response_model=PostmortemListResponse)
async def list_postmortems(
    app_id: Optional[UUID] = None,
    report_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemListResponse:
    """List postmortem reports with optional filtering by app_id or status."""
    svc = PostmortemService(db)
    items, total = await svc.list_reports(
        app_id=app_id, status=report_status, page=page, page_size=page_size
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

@router.get("/{postmortem_id}", response_model=PostmortemReportResponse)
async def get_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """Retrieve a single postmortem report by ID."""
    svc = PostmortemService(db)
    report = await svc.get_by_id(postmortem_id)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Update (manual edits)
# ---------------------------------------------------------------------------

@router.put("/{postmortem_id}", response_model=PostmortemReportResponse)
async def update_postmortem(
    postmortem_id: UUID,
    data: PostmortemReportUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """Edit postmortem fields (title, timeline, root cause, action items, etc.)."""
    svc = PostmortemService(db)
    report = await svc.update(postmortem_id, data)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Regenerate
# ---------------------------------------------------------------------------

@router.post("/{postmortem_id}/regenerate", response_model=PostmortemReportResponse)
async def regenerate_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """Re-run AI generation, preserving manually-added context entries."""
    svc = PostmortemService(db)
    report = await svc.regenerate(postmortem_id)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Out-of-band context
# ---------------------------------------------------------------------------

@router.post("/{postmortem_id}/out-of-band", response_model=PostmortemReportResponse)
async def add_out_of_band_context(
    postmortem_id: UUID,
    entry: OutOfBandContextAdd,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> PostmortemReportResponse:
    """Append a manual context entry (Slack thread, vendor note, etc.)."""
    svc = PostmortemService(db)
    report = await svc.add_out_of_band_context(postmortem_id, entry)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

@router.post("/{postmortem_id}/publish", response_model=PostmortemReportResponse)
async def publish_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> PostmortemReportResponse:
    """Publish the postmortem, marking it as reviewed."""
    svc = PostmortemService(db)
    report = await svc.publish(postmortem_id, reviewed_by=current_user.id)
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{postmortem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_postmortem(
    postmortem_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Delete a draft postmortem. Only admins may delete; only drafts can be deleted."""
    svc = PostmortemService(db)
    await svc.delete(postmortem_id)
