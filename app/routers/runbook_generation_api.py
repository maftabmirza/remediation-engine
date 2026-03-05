"""
Runbook Auto-Generation API Router (Feature B2)

Endpoints for generating runbook drafts from successful agent sessions.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import User
from app.schemas_runbook_generation import (
    GenerationCandidateListResponse,
    GenerateRunbookRequest,
    RunbookDraftResponse,
    GeneratedStepPreview,
)
from app.services.auth_service import get_current_user, require_admin, require_role
from app.services.runbook_generation_service import RunbookGenerationService

router = APIRouter(prefix="/api/runbook-generation", tags=["Runbook Auto-Generation"])


@router.get(
    "/candidates",
    response_model=GenerationCandidateListResponse,
)
async def list_generation_candidates(
    min_success_count: int = Query(3, ge=1, description="Minimum successful sessions to qualify"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> GenerationCandidateListResponse:
    """
    List clusters of similar successful sessions that can be turned into runbooks.

    Returns only clusters with at least *min_success_count* sessions.
    """
    svc = RunbookGenerationService(db)
    candidates = await svc.find_generation_candidates(min_success_count=min_success_count)
    return GenerationCandidateListResponse(items=candidates, total=len(candidates))


@router.post(
    "/generate",
    response_model=RunbookDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_runbook(
    payload: GenerateRunbookRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> RunbookDraftResponse:
    """
    Generate an auto-generated runbook draft from the provided sessions.

    Requires *admin* or *engineer* role.  The runbook is created with
    ``enabled=False`` and ``auto_execute=False`` until explicitly approved.
    """
    svc = RunbookGenerationService(db)
    try:
        runbook = await svc.generate_runbook(
            session_ids=payload.session_ids,
            runbook_name=payload.runbook_name,
            app_id=payload.app_id,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Build step previews from the saved steps
    step_previews = []
    for s in (runbook.steps or []):
        preview = RunbookGenerationService.build_step_previews(
            [{"command_template": s.command_linux or ""}]
        )[0]
        step_previews.append(
            GeneratedStepPreview(
                step_number=s.step_order,
                name=s.name,
                step_type=s.step_type or "command",
                command_template=s.command_linux or "",
                variables_required=preview.variables_required,
                is_idempotent=None,
                requires_human_review=preview.requires_human_review,
            )
        )

    all_vars: list[str] = sorted(
        {v for sp in step_previews for v in sp.variables_required}
    )
    review_reasons = [
        f"Step '{sp.name}' contains non-idempotent pattern"
        for sp in step_previews
        if sp.requires_human_review
    ]

    return RunbookDraftResponse(
        runbook_id=runbook.id,
        name=runbook.name,
        description=runbook.description or "",
        source=runbook.source or "auto_generated",
        auto_trigger_enabled=runbook.auto_execute or False,
        steps=step_previews,
        variables=all_vars,
        requires_review_reasons=review_reasons,
        session_count=len(payload.session_ids),
    )


@router.post(
    "/approve/{runbook_id}",
    response_model=RunbookDraftResponse,
)
async def approve_draft(
    runbook_id: UUID,
    enable_auto_trigger: bool = Query(False),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> RunbookDraftResponse:
    """
    Approve an auto-generated runbook draft for use.

    Only *admin* users can approve.  Optionally sets ``auto_execute = True``.
    """
    svc = RunbookGenerationService(db)
    try:
        runbook = await svc.approve_draft(
            runbook_id=runbook_id,
            approved_by=current_user.id,
            enable_auto_trigger=enable_auto_trigger,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    step_previews = []
    for s in (runbook.steps or []):
        preview = RunbookGenerationService.build_step_previews(
            [{"command_template": s.command_linux or ""}]
        )[0]
        step_previews.append(
            GeneratedStepPreview(
                step_number=s.step_order,
                name=s.name,
                step_type=s.step_type or "command",
                command_template=s.command_linux or "",
                variables_required=preview.variables_required,
                is_idempotent=None,
                requires_human_review=preview.requires_human_review,
            )
        )

    return RunbookDraftResponse(
        runbook_id=runbook.id,
        name=runbook.name,
        description=runbook.description or "",
        source=runbook.source or "auto_generated",
        auto_trigger_enabled=runbook.auto_execute or False,
        steps=step_previews,
        variables=sorted({v for sp in step_previews for v in sp.variables_required}),
        requires_review_reasons=[],
        session_count=0,
    )


@router.get(
    "/drafts",
    response_model=GenerationCandidateListResponse,
)
async def list_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> GenerationCandidateListResponse:
    """
    List auto-generated runbook drafts pending human review.

    Returns runbooks with ``source='auto_generated'`` and ``enabled=False``.
    """
    svc = RunbookGenerationService(db)
    items, total = await svc.list_drafts(page=page, page_size=page_size)

    # Convert Runbook records to GenerationCandidate summaries
    from app.schemas_runbook_generation import GenerationCandidate

    candidates = [
        GenerationCandidate(
            session_ids=[],
            session_count=0,
            goal_summary=r.description or r.name,
            app_id=None,
            success_rate=0.0,
            avg_resolution_minutes=None,
            representative_commands=[],
        )
        for r in items
    ]
    return GenerationCandidateListResponse(items=candidates, total=total)
