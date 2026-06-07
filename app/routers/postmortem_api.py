"""
Post-Incident Postmortem API Router

Endpoints for generating, editing, and publishing AI-powered postmortem reports.

Incident-first endpoints:
  GET  /api/postmortems/incidents              — list eligible resolved incidents
  GET  /api/postmortems/incidents/{id}/evidence — preview evidence for an incident
  POST /api/postmortems/generate-by-incident   — generate from a resolved incident

Alert-compatibility endpoints (retained for backward compatibility):
  POST /api/postmortems/generate               — generate from an alert
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
    ChangeEventSummary,
    IncidentEvidenceResponse,
    IncidentListResponse,
    IncidentResponse,
    OutOfBandContextAdd,
    PostmortemGenerateByIncident,
    PostmortemListResponse,
    PostmortemReportCreate,
    PostmortemReportResponse,
    PostmortemReportUpdate,
    RunbookExecutionSummary,
)
from app.services.auth_service import get_current_user, require_role
from app.services.incident_service import IncidentService
from app.services.postmortem_service import PostmortemService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/postmortems", tags=["Postmortems"])


# ---------------------------------------------------------------------------
# Incident-first: list eligible resolved incidents
# ---------------------------------------------------------------------------

@router.get(
    "/incidents",
    response_model=IncidentListResponse,
    summary="List resolved incidents eligible for postmortem generation",
)
async def list_eligible_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_with_postmortem: bool = Query(
        False,
        description="Include incidents that already have a postmortem",
    ),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> IncidentListResponse:
    """
    Return a paginated list of resolved incidents that are eligible for
    postmortem generation (grace period elapsed, not yet cancelled/closed).

    By default incidents that already have a postmortem are excluded.
    Pass ``include_with_postmortem=true`` to include them.
    """
    svc = IncidentService(db)
    items, total = await svc.list_eligible_for_postmortem(
        page=page,
        page_size=page_size,
        include_with_postmortem=include_with_postmortem,
    )
    return IncidentListResponse(
        items=[IncidentResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Incident-first: evidence preview
# ---------------------------------------------------------------------------

@router.get(
    "/incidents/{incident_id}/evidence",
    response_model=IncidentEvidenceResponse,
    summary="Preview the evidence that will be used to generate a postmortem",
)
async def get_incident_evidence(
    incident_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> IncidentEvidenceResponse:
    """
    Gather and return the complete evidence bundle for the given incident
    so that users can review it before triggering postmortem generation.
    """
    svc = IncidentService(db)
    evidence = await svc.get_evidence(incident_id)
    incident = evidence["incident"]

    runbook_summaries = []
    for ex in evidence.get("runbook_executions", []):
        duration = None
        if ex.started_at and ex.completed_at:
            delta = ex.completed_at - ex.started_at
            duration = round(delta.total_seconds() / 60, 2)
        runbook_summaries.append(
            RunbookExecutionSummary(
                id=ex.id,
                runbook_id=ex.runbook_id,
                status=ex.status,
                started_at=ex.started_at,
                completed_at=ex.completed_at,
                duration_minutes=duration,
            )
        )

    change_summaries = [
        ChangeEventSummary.model_validate(ce)
        for ce in evidence.get("change_events", [])
    ]

    return IncidentEvidenceResponse(
        incident=IncidentResponse.model_validate(incident),
        alert_count=len(evidence.get("alerts", [])),
        timeline=evidence.get("timeline", []),
        runbook_executions=runbook_summaries,
        change_events=change_summaries,
        affected_services=evidence.get("affected_services", []),
        mttr_minutes=evidence.get("mttr_minutes"),
    )


# ---------------------------------------------------------------------------
# Incident-first: generate postmortem from a resolved incident
# ---------------------------------------------------------------------------

@router.post(
    "/generate-by-incident",
    response_model=PostmortemReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a postmortem from a resolved incident (incident-first path)",
)
async def generate_postmortem_by_incident(
    data: PostmortemGenerateByIncident,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> PostmortemReportResponse:
    """
    AI-generate a draft postmortem report anchored to the given incident.

    Gathers the full evidence bundle for the incident (all correlated alerts,
    runbook executions, agent troubleshooting sessions, change events, and
    ITSM data) then calls the LLM to produce a structured postmortem.
    """
    svc = PostmortemService(db)
    report = await svc.generate_by_incident(
        incident_id=data.incident_id,
        created_by=current_user.id,
        app_id=data.app_id,
    )
    return PostmortemReportResponse.model_validate(report)


# ---------------------------------------------------------------------------
# Generate (alert compatibility path)
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
    current_user: User = Depends(require_role(["admin", "engineer"])),
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
    "",
    response_model=PostmortemListResponse,
    summary="List postmortem reports (paginated)",
)
@router.get(
    "/",
    response_model=PostmortemListResponse,
    summary="List postmortem reports (paginated)",
    include_in_schema=False,
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
    current_user: User = Depends(require_role(["admin", "engineer"])),
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
    current_user: User = Depends(require_role(["admin", "engineer"])),
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
    current_user: User = Depends(require_role(["admin", "engineer"])),
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
