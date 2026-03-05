"""
Service Health Score & Topology API Router (Feature A2)

Endpoints for per-application health scores and D3.js topology graphs.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import User
from app.schemas_health import (
    ApplicationHealthListResponse,
    ServiceHealthScore,
    TopologyGraph,
)
from app.services.auth_service import get_current_user
from app.services.service_health_service import ServiceHealthService

router = APIRouter(prefix="/api/health", tags=["Service Health"])


@router.get(
    "/applications",
    response_model=ApplicationHealthListResponse,
)
async def list_application_health(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationHealthListResponse:
    """
    Return health scores for all registered applications (paginated).
    """
    from sqlalchemy import select, func
    from app.models_application import Application

    # Count total applications
    count_result = await db.execute(select(func.count(Application.id)))
    total = count_result.scalar_one()

    # Fetch only the requested page
    offset = (page - 1) * page_size
    page_result = await db.execute(
        select(Application).offset(offset).limit(page_size)
    )
    paged_apps = page_result.scalars().all()

    svc = ServiceHealthService(db)
    scores: list[ServiceHealthScore] = []
    for app in paged_apps:
        try:
            score = await svc.calculate_health(app.id)
            scores.append(score)
        except Exception:
            pass

    return ApplicationHealthListResponse(items=scores, total=total)


@router.get(
    "/applications/{app_id}",
    response_model=ServiceHealthScore,
)
async def get_application_health(
    app_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> ServiceHealthScore:
    """
    Return detailed health breakdown (per-factor scores) for a single application.
    """
    svc = ServiceHealthService(db)
    try:
        return await svc.calculate_health(app_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/topology",
    response_model=TopologyGraph,
)
async def get_full_topology(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> TopologyGraph:
    """
    Return the full service topology graph in D3.js-compatible format.

    Includes all registered components and their dependency edges with health
    colours derived from the current health scores.
    """
    svc = ServiceHealthService(db)
    return await svc.get_topology()


@router.get(
    "/topology/{app_id}",
    response_model=TopologyGraph,
)
async def get_app_topology(
    app_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> TopologyGraph:
    """
    Return the topology graph for a specific application (includes dependencies).
    """
    svc = ServiceHealthService(db)
    return await svc.get_topology(app_id=app_id)
