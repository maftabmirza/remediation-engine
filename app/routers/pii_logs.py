"""
FastAPI router for PII detection logs endpoints.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
import logging
import csv
import io
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.schemas.pii_schemas import (
    DetectionLogListResponse,
    DetectionLogQuery,
    DetectionLogSearchResponse,
    DetectionStatsResponse,
    DetectionLogDetailResponse,
    DetectionLogResponse
)
from app.services.pii_service import PIIService
from app.services.presidio_service import PresidioService
from app.services.secret_detection_service import SecretDetectionService
from app.models.pii_models import PIIDetectionLog
from app.services.auth_service import require_permission


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pii/logs", tags=["PII Detection Logs"])


# Global instances for caching
_presidio_instance = None
_secret_service_instance = None

def get_presidio_service() -> PresidioService:
    """Get cached Presidio service instance to avoid reloading models."""
    global _presidio_instance
    if _presidio_instance is None:
        logger.info("Creating new PresidioService instance (Cache Miss)")
        _presidio_instance = PresidioService()
    else:
        logger.info("Using cached PresidioService instance")
    return _presidio_instance


def get_secret_service() -> SecretDetectionService:
    """Get cached Secret detection service instance."""
    global _secret_service_instance
    if _secret_service_instance is None:
        _secret_service_instance = SecretDetectionService()
    return _secret_service_instance


# Dependency to get PII service
async def get_pii_service(db: AsyncSession = Depends(get_async_db)) -> PIIService:
    """
    Dependency to create PII service instance.
    
    Args:
        db: Database session
        
    Returns:
        PIIService instance
    """
    from app.services.pii_whitelist_service import PIIWhitelistService
    whitelist_service = PIIWhitelistService(db)
    return PIIService(db, get_presidio_service(), get_secret_service(), whitelist_service=whitelist_service)


@router.get("", response_model=DetectionLogListResponse)
async def get_logs(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=1000, description="Items per page"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    engine: Optional[str] = Query(None, description="Filter by detection engine"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    service: PIIService = Depends(get_pii_service),
    _: object = Depends(require_permission(["pii_read_logs"]))
):
    """
    Get detection logs with filtering and pagination.
    
    Args:
        page: Page number
        limit: Items per page
        entity_type: Filter by entity type
        engine: Filter by detection engine
        source_type: Filter by source type
        start_date: Filter by start date
        end_date: Filter by end date
        service: PII service instance
        
    Returns:
        Paginated list of detection logs
    """
    try:
        query = DetectionLogQuery(
            page=page,
            limit=limit,
            entity_type=entity_type,
            engine=engine,
            source_type=source_type,
            start_date=start_date,
            end_date=end_date
        )
        
        result = await service.get_logs(query)
        
        logger.info(f"Retrieved {len(result.logs)} logs (page {page}/{result.pages})")
        return result
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving logs: {str(e)}"
        )


@router.get("/search", response_model=DetectionLogSearchResponse)
async def search_logs(
    q: str = Query(..., description="Search query"),
    engine: Optional[str] = Query(None, description="Filter by engine"),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence"),
    confidence_max: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum confidence"),
    service: PIIService = Depends(get_pii_service),
    _: object = Depends(require_permission(["pii_read_logs"]))
):
    """
    Search detection logs with filters.
    
    Args:
        q: Search query
        engine: Filter by engine
        confidence_min: Minimum confidence score
        confidence_max: Maximum confidence score
        service: PII service instance
        
    Returns:
        Search results
    """
    try:
        logger.info(f"Search logs: query={q}")
        
        # TODO: Implement actual search functionality
        # For now, return empty results
        
        return DetectionLogSearchResponse(
            results=[],
            total=0,
            query=q,
            filters_applied={
                "engine": engine,
                "confidence_min": confidence_min,
                "confidence_max": confidence_max
            }
        )
        
    except Exception as e:
        logger.error(f"Error searching logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching logs: {str(e)}"
        )


@router.get("/stats", response_model=DetectionStatsResponse)
async def get_stats(
    period: str = Query("7d", description="Time period (7d, 30d, 90d)"),
    service: PIIService = Depends(get_pii_service),
    _: object = Depends(require_permission(["pii_read_logs"]))
):
    """
    Get detection statistics.
    
    Args:
        period: Time period for stats
        service: PII service instance
        
    Returns:
        Detection statistics
    """
    try:
        stats = await service.get_stats(period)
        
        logger.info(f"Retrieved stats for period {period}")
        return stats
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving statistics: {str(e)}"
        )


# NOTE: /export MUST be defined BEFORE /{log_id} to prevent "export" being matched as a UUID
@router.get("/export", response_class=StreamingResponse)
async def export_logs(
    format: str = Query("csv", description="Export format (csv, json)"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    service: PIIService = Depends(get_pii_service),
    _: object = Depends(require_permission(["pii_read_logs"]))
):
    """
    Export detection logs.
    
    Args:
        format: Export format (csv or json)
        start_date: Start date filter
        end_date: End date filter
        service: PII service instance
        
    Returns:
        File download response
    """
    try:
        # Get all logs matching filters - fetch in batches of 1000
        all_logs = []
        page = 1
        
        while True:
            query = DetectionLogQuery(
                page=page,
                limit=1000,  # Maximum allowed
                start_date=start_date,
                end_date=end_date
            )
            
            result = await service.get_logs(query)
            all_logs.extend(result.logs)
            
            if page >= result.pages:
                break
            page += 1
        
        if format.lower() == "csv":
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "Detected At", "Entity Type", "Detection Engine",
                "Confidence Score", "Source Type", "Source ID",
                "Was Redacted", "Original Hash"
            ])
            
            # Write data
            for log in all_logs:
                writer.writerow([
                    str(log.id),
                    log.detected_at.isoformat(),
                    log.entity_type,
                    log.detection_engine,
                    log.confidence_score,
                    log.source_type,
                    str(log.source_id) if log.source_id else "",
                    log.was_redacted,
                    ""  # Don't export hash for security
                ])
            
            # Prepare response
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=pii_detection_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {format}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting logs: {str(e)}"
        )


@router.get("/{log_id}", response_model=DetectionLogDetailResponse)
async def get_log_detail(
    log_id: UUID,
    service: PIIService = Depends(get_pii_service)
):
    """
    Get detailed view of a single detection log.
    
    Args:
        log_id: Log entry ID
        service: PII service instance
        
    Returns:
        Detailed log information
    """
    try:
        from sqlalchemy import select
        
        # Query for the specific log
        stmt = select(PIIDetectionLog).where(PIIDetectionLog.id == log_id)
        result = await service.db.execute(stmt)
        log = result.scalar_one_or_none()
        
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log entry {log_id} not found"
            )
        
        return DetectionLogDetailResponse.from_orm(log)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting log detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving log detail: {str(e)}"
        )
