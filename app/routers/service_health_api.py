"""
Service Health Score & Topology API Router (Feature A2).

Endpoints for querying per-application health scores and the service topology graph.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import User
from app.models_application import Application
from app.schemas_health import (
    ApplicationHealthListResponse,
    ServiceHealthScore,
    TopologyGraph,
)
from app.services.auth_service import get_current_user
from app.services.service_health_service import ServiceHealthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["Service Health"])


@router.get(
    "/applications",
    response_model=ApplicationHealthListResponse,
    summary="Get health scores for all applications",
)
async def list_application_health(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationHealthListResponse:
    """
    Return health scores for all registered applications, sorted by score ascending
    (most critical first).
    """
    # Count total
    total_result = await db.execute(select(func.count()).select_from(Application))
    total = total_result.scalar_one()

    # Load page of applications
    apps_result = await db.execute(
        select(Application)
        .order_by(Application.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    apps = apps_result.scalars().all()

    svc = ServiceHealthService(db)
    scores = []
    for app in apps:
        try:
            score = await svc.calculate_health(app.id)
            scores.append(score)
        except Exception as exc:
            logger.warning("Could not compute health for app %s: %s", app.id, exc)

    # Sort: critical / lowest score first
    scores.sort(key=lambda s: s.score)

    return ApplicationHealthListResponse(items=scores, total=total)


@router.get(
    "/applications/{app_id}",
    response_model=ServiceHealthScore,
    summary="Get detailed health breakdown for a specific application",
)
async def get_application_health(
    app_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> ServiceHealthScore:
    """
    Return a detailed health score with per-factor breakdown for *app_id*.
    """
    svc = ServiceHealthService(db)
    return await svc.calculate_health(app_id)


@router.get(
    "/topology",
    response_model=TopologyGraph,
    summary="Get the full service topology graph",
)
async def get_full_topology(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> TopologyGraph:
    """
    Return the full D3.js-compatible topology graph covering all applications
    and their component dependencies.
    """
    svc = ServiceHealthService(db)
    return await svc.get_topology(app_id=None)


@router.get(
    "/topology/{app_id}",
    response_model=TopologyGraph,
    summary="Get topology graph for a specific application",
)
async def get_app_topology(
    app_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> TopologyGraph:
    """
    Return a D3.js-compatible topology graph for the specified application,
    including its components and direct dependencies.
    """
    svc = ServiceHealthService(db)
    return await svc.get_topology(app_id=app_id)
