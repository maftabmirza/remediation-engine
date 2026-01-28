"""
FastAPI router for PII detection endpoints.
"""
from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.schemas.pii_schemas import (
    DetectionRequest,
    DetectionResponse,
    RedactionRequest,
    RedactionResponse,
    PIIConfigResponse,
    PIIConfigUpdate,
    TestDetectionRequest,
    TestDetectionResponse,
    EntityListResponse,
    PluginListResponse,
    EntityInfo,
    PluginInfo,
    EngineResults
)
from app.services.pii_service import PIIService
from app.services.presidio_service import PresidioService
from app.services.secret_detection_service import SecretDetectionService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pii", tags=["PII Detection"])


# Dependency to get PII service
async def get_pii_service(db: AsyncSession = Depends(get_async_db)) -> PIIService:
    """
    Dependency to create PII service instance.
    
    Args:
        db: Database session
        
    Returns:
        PIIService instance
    """
    presidio = PresidioService()
    secrets = SecretDetectionService()
    return PIIService(db, presidio, secrets)


@router.post("/detect", response_model=DetectionResponse)
async def detect_pii(
    request: DetectionRequest,
    service: PIIService = Depends(get_pii_service)
):
    """
    Detect PII and secrets in text.
    
    Args:
        request: Detection request with text and options
        service: PII service instance
        
    Returns:
        Detection response with all detections found
    """
    try:
        logger.info(f"Detection request for source_type={request.source_type}")
        
        result = await service.detect(
            text=request.text,
            source_type=request.source_type,
            source_id=request.source_id,
            engines=request.engines,
            entity_types=request.entity_types
        )
        
        logger.info(f"Found {result.detection_count} detections")
        return result
        
    except Exception as e:
        logger.error(f"Error detecting PII: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detecting PII: {str(e)}"
        )


@router.post("/redact", response_model=RedactionResponse)
async def redact_pii(
    request: RedactionRequest,
    service: PIIService = Depends(get_pii_service)
):
    """
    Redact PII and secrets from text.
    
    Args:
        request: Redaction request with text and options
        service: PII service instance
        
    Returns:
        Redaction response with redacted text
    """
    try:
        logger.info(f"Redaction request with type={request.redaction_type}")
        
        result = await service.redact(
            text=request.text,
            redaction_type=request.redaction_type,
            mask_char=request.mask_char,
            preserve_length=request.preserve_length
        )
        
        logger.info(f"Applied {result.redactions_applied} redactions")
        return result
        
    except Exception as e:
        logger.error(f"Error redacting PII: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error redacting PII: {str(e)}"
        )


@router.get("/config", response_model=PIIConfigResponse)
async def get_config(
    service: PIIService = Depends(get_pii_service)
):
    """
    Get current PII detection configuration.
    
    Args:
        service: PII service instance
        
    Returns:
        Current configuration
    """
    try:
        config = await service.get_config()
        return config
        
    except Exception as e:
        logger.error(f"Error getting config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting configuration: {str(e)}"
        )


@router.put("/config", response_model=PIIConfigResponse)
async def update_config(
    update: PIIConfigUpdate,
    service: PIIService = Depends(get_pii_service)
):
    """
    Update PII detection configuration.
    
    Args:
        update: Configuration updates
        service: PII service instance
        
    Returns:
        Updated configuration
    """
    try:
        logger.info("Configuration update requested")
        
        config = await service.update_config(update)
        
        logger.info("Configuration updated successfully")
        return config
        
    except Exception as e:
        logger.error(f"Error updating config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating configuration: {str(e)}"
        )


@router.post("/test", response_model=TestDetectionResponse)
async def test_detection(
    request: TestDetectionRequest,
    service: PIIService = Depends(get_pii_service)
):
    """
    Test detection on sample text.
    
    Args:
        request: Test request with sample text
        service: PII service instance
        
    Returns:
        Test results with detections and preview
    """
    try:
        logger.info("Test detection request")
        
        # Run detection
        detection_result = await service.detect(
            text=request.text,
            source_type="test",
            engines=request.engines
        )
        
        # Run redaction for preview
        redaction_result = await service.redact(
            text=request.text,
            redaction_type="replace"
        )
        
        # Build engine results
        engine_results = {}
        
        for engine in request.engines:
            engine_detections = [
                d for d in detection_result.detections 
                if d.engine == engine
            ]
            engine_results[engine] = EngineResults(
                detections=len(engine_detections),
                processing_time_ms=detection_result.processing_time_ms // len(request.engines)
            )
        
        return TestDetectionResponse(
            detections=detection_result.detections,
            redacted_preview=redaction_result.redacted_text,
            engine_results=engine_results
        )
        
    except Exception as e:
        logger.error(f"Error testing detection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing detection: {str(e)}"
        )


@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    service: PIIService = Depends(get_pii_service)
):
    """
    List available entity types.
    
    Args:
        service: PII service instance
        
    Returns:
        List of entity types
    """
    try:
        entities = service.presidio.get_supported_entities()
        
        return EntityListResponse(
            presidio_entities=[
                EntityInfo(**entity) for entity in entities
            ]
        )
        
    except Exception as e:
        logger.error(f"Error listing entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing entities: {str(e)}"
        )


@router.get("/plugins", response_model=PluginListResponse)
async def list_plugins(
    service: PIIService = Depends(get_pii_service)
):
    """
    List available detect-secrets plugins.
    
    Args:
        service: PII service instance
        
    Returns:
        List of plugins
    """
    try:
        plugins = service.secrets.get_available_plugins()
        
        return PluginListResponse(
            detect_secrets_plugins=[
                PluginInfo(**plugin) for plugin in plugins
            ]
        )
        
    except Exception as e:
        logger.error(f"Error listing plugins: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing plugins: {str(e)}"
        )
