"""
Runbook Auto-Generation API Router (Feature B2).

Endpoints for discovering, generating, and approving AI-generated runbooks.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import User
from app.models_remediation import Runbook, RunbookStep
from app.schemas_runbook_generation import (
    GeneratedStepPreview,
    GenerationCandidate,
    GenerationCandidateListResponse,
    GenerateRunbookRequest,
    RunbookDraftResponse,
)
from app.services.auth_service import get_current_user, require_admin, require_role
from app.services.runbook_generation_service import (
    RunbookGenerationService,
    _extract_variables,
    _is_non_idempotent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runbook-generation", tags=["Runbook Generation"])


@router.get(
    "/candidates",
    response_model=GenerationCandidateListResponse,
    summary="List runbook generation opportunities",
)
async def list_candidates(
    min_success_count: int = Query(3, ge=1, description="Minimum sessions in a cluster"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> GenerationCandidateListResponse:
    """
    Discover clusters of similar successful agent sessions that can be used to
    auto-generate runbooks.

    Returns clusters sorted by session_count descending.
    """
    svc = RunbookGenerationService(db)
    candidates = await svc.find_generation_candidates(min_success_count=min_success_count)
    return GenerationCandidateListResponse(items=candidates, total=len(candidates))


@router.post(
    "/generate",
    response_model=RunbookDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a runbook from past sessions",
)
async def generate_runbook(
    body: GenerateRunbookRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
) -> RunbookDraftResponse:
    """
    Use the LLM to generate a runbook draft from a set of successful agent sessions.

    The generated runbook starts with ``enabled=False`` — it must be approved
    before it can be used in automated remediation.
    """
    svc = RunbookGenerationService(db)
    try:
        runbook = await svc.generate_runbook(
            session_ids=body.session_ids,
            runbook_name=body.runbook_name,
            app_id=body.app_id,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # Load steps for the response
    steps_result = await db.execute(
        select(RunbookStep)
        .where(RunbookStep.runbook_id == runbook.id)
        .order_by(RunbookStep.step_order)
    )
    steps = steps_result.scalars().all()

    step_previews = [
        GeneratedStepPreview(
            step_number=s.step_order,
            name=s.name,
            step_type=s.step_type or "command",
            command_template=s.command_linux or "",
            variables_required=_extract_variables(s.command_linux or ""),
            is_idempotent=None if _is_non_idempotent(s.command_linux or "") else True,
            requires_human_review=_is_non_idempotent(s.command_linux or ""),
        )
        for s in steps
    ]

    all_variables = list(
        dict.fromkeys(
            v for step in step_previews for v in step.variables_required
        )
    )
    requires_review_reasons = list(
        dict.fromkeys(
            f"Step '{s.name}' contains non-idempotent operation"
            for s in step_previews
            if s.requires_human_review
        )
    )

    return RunbookDraftResponse(
        runbook_id=runbook.id,
        name=runbook.name,
        description=runbook.description or "",
        source="auto_generated",
        auto_trigger_enabled=bool(runbook.auto_execute),
        steps=step_previews,
        variables=all_variables,
        requires_review_reasons=requires_review_reasons,
        session_count=len(body.session_ids),
    )


@router.post(
    "/approve/{runbook_id}",
    response_model=RunbookDraftResponse,
    summary="Approve a draft runbook for use",
)
async def approve_runbook(
    runbook_id: UUID,
    enable_auto_trigger: bool = Query(False, description="Enable automatic execution"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_admin),
) -> RunbookDraftResponse:
    """
    Approve a draft auto-generated runbook.

    Sets ``enabled=True`` so the runbook can be used in remediation workflows.
    Optionally enables automatic execution (``auto_execute``).
    """
    svc = RunbookGenerationService(db)
    runbook = await svc.approve_draft(
        runbook_id=runbook_id,
        approved_by=current_user.id,
        enable_auto_trigger=enable_auto_trigger,
    )

    steps_result = await db.execute(
        select(RunbookStep)
        .where(RunbookStep.runbook_id == runbook.id)
        .order_by(RunbookStep.step_order)
    )
    steps = steps_result.scalars().all()

    step_previews = [
        GeneratedStepPreview(
            step_number=s.step_order,
            name=s.name,
            step_type=s.step_type or "command",
            command_template=s.command_linux or "",
            variables_required=_extract_variables(s.command_linux or ""),
            is_idempotent=None if _is_non_idempotent(s.command_linux or "") else True,
            requires_human_review=_is_non_idempotent(s.command_linux or ""),
        )
        for s in steps
    ]
    all_variables = list(
        dict.fromkeys(v for step in step_previews for v in step.variables_required)
    )
    requires_review_reasons = list(
        dict.fromkeys(
            f"Step '{s.name}' contains non-idempotent operation"
            for s in step_previews
            if s.requires_human_review
        )
    )

    return RunbookDraftResponse(
        runbook_id=runbook.id,
        name=runbook.name,
        description=runbook.description or "",
        source="auto_generated",
        auto_trigger_enabled=bool(runbook.auto_execute),
        steps=step_previews,
        variables=all_variables,
        requires_review_reasons=requires_review_reasons,
        session_count=0,
    )


@router.get(
    "/drafts",
    response_model=GenerationCandidateListResponse,
    summary="List pending auto-generated runbook drafts",
)
async def list_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> GenerationCandidateListResponse:
    """
    List auto-generated runbooks that are awaiting human approval (``enabled=False``).
    """
    svc = RunbookGenerationService(db)
    items, total = await svc.list_drafts(page=page, page_size=page_size)

    # Convert Runbook ORM objects to lightweight candidate-like summary
    summaries = [
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
    return {"items": summaries, "total": total}
