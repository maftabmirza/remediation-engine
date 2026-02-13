"""
ITSM Integration API Router

Endpoints for managing ITSM integrations (ServiceNow, Jira, GitHub, etc.)
"""
import logging
import json
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models_itsm import ITSMIntegration, ChangeEvent
from app.schemas_itsm import (
    ITSMConfigCreate, ITSMConfigUpdate, ITSMConfigResponse, ITSMTestResult
)
from app.services.itsm_connector import GenericAPIConnector, get_itsm_templates, get_itsm_template
from app.services.change_impact_service import ChangeImpactService
from app.routers.auth import get_current_user
from app.utils.crypto import encrypt_value, decrypt_value


def utc_now():
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/itsm", tags=["itsm"])


@router.get("/integrations", response_model=List[ITSMConfigResponse])
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all ITSM integrations"""
    integrations = db.query(ITSMIntegration).order_by(
        ITSMIntegration.created_at.desc()
    ).all()
    return integrations


@router.get("/integrations/{integration_id}", response_model=ITSMConfigResponse)
async def get_integration(
    integration_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific ITSM integration with decrypted config for editing"""
    integration = db.query(ITSMIntegration).filter(
        ITSMIntegration.id == integration_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Decrypt config for response
    try:
        config_json = decrypt_value(integration.config_encrypted)
        config = json.loads(config_json)
    except Exception as e:
        logger.error(f"Failed to decrypt config: {e}")
        config = None
    
    # Build response with decrypted config
    return ITSMConfigResponse(
        id=integration.id,
        name=integration.name,
        connector_type=integration.connector_type,
        is_enabled=integration.is_enabled,
        config=config,
        last_sync=integration.last_sync,
        last_sync_status=integration.last_sync_status,
        last_error=integration.last_error,
        created_at=integration.created_at,
        updated_at=integration.updated_at
    )


@router.post("/integrations", response_model=ITSMConfigResponse)
async def create_integration(
    data: ITSMConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new ITSM integration"""
    # Encrypt the configuration
    config_json = json.dumps(data.config)
    encrypted_config = encrypt_value(config_json)
    
    integration = ITSMIntegration(
        name=data.name,
        connector_type=data.connector_type,
        config_encrypted=encrypted_config,
        is_enabled=data.is_enabled
    )
    
    db.add(integration)
    db.commit()
    db.refresh(integration)
    
    logger.info(f"Created ITSM integration: {integration.name}")
    return integration


@router.put("/integrations/{integration_id}", response_model=ITSMConfigResponse)
async def update_integration(
    integration_id: UUID,
    data: ITSMConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an ITSM integration"""
    integration = db.query(ITSMIntegration).filter(
        ITSMIntegration.id == integration_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Update fields
    if data.name is not None:
        integration.name = data.name
    if data.connector_type is not None:
        integration.connector_type = data.connector_type
    if data.is_enabled is not None:
        integration.is_enabled = data.is_enabled
    if data.config is not None:
        config_json = json.dumps(data.config)
        integration.config_encrypted = encrypt_value(config_json)
    
    integration.updated_at = utc_now()
    db.commit()
    db.refresh(integration)
    
    logger.info(f"Updated ITSM integration: {integration.name}")
    return integration


@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an ITSM integration"""
    integration = db.query(ITSMIntegration).filter(
        ITSMIntegration.id == integration_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Delete related change events
    db.query(ChangeEvent).filter(
        ChangeEvent.source == str(integration_id)
    ).delete()
    
    db.delete(integration)
    db.commit()
    
    logger.info(f"Deleted ITSM integration: {integration.name}")
    return {"message": "Integration deleted"}


@router.post("/test-config", response_model=ITSMTestResult)
async def test_config(
    data: ITSMConfigCreate,
    current_user: User = Depends(get_current_user)
):
    """Test an ITSM configuration before saving (no integration required)"""
    try:
        # Create connector with provided config
        connector = GenericAPIConnector(data.config)
        success, message, sample_data = connector.test_connection()
        
        return ITSMTestResult(
            success=success,
            message=message,
            sample_data=sample_data
        )
        
    except Exception as e:
        logger.exception(f"Error testing config: {e}")
        return ITSMTestResult(
            success=False,
            message=f"Error: {str(e)}",
            sample_data=None
        )


@router.post("/integrations/{integration_id}/test", response_model=ITSMTestResult)
async def test_integration(
    integration_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test an ITSM integration connection"""
    integration = db.query(ITSMIntegration).filter(
        ITSMIntegration.id == integration_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    try:
        # Decrypt config
        config_json = decrypt_value(integration.config_encrypted)
        config = json.loads(config_json)
        
        # Create connector and test
        connector = GenericAPIConnector(config)
        success, message, sample_data = connector.test_connection()
        
        return ITSMTestResult(
            success=success,
            message=message,
            sample_data=sample_data
        )
        
    except Exception as e:
        logger.exception(f"Error testing integration: {e}")
        return ITSMTestResult(
            success=False,
            message=f"Error: {str(e)}",
            sample_data=None
        )


@router.post("/integrations/{integration_id}/sync")
async def sync_integration(
    integration_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger manual sync for an ITSM integration"""
    integration = db.query(ITSMIntegration).filter(
        ITSMIntegration.id == integration_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    if not integration.is_enabled:
        raise HTTPException(status_code=400, detail="Integration is disabled")
    
    try:
        # Decrypt config
        config_json = decrypt_value(integration.config_encrypted)
        config = json.loads(config_json)
        
        # Create connector and sync changes
        connector = GenericAPIConnector(config)
        since = integration.last_sync  # Get changes since last sync
        
        # Sync Changes
        created, updated, errors = connector.sync(db, integration_id, since)
        
        # Sync Incidents (if configured)
        inc_created, inc_updated, inc_errors = 0, 0, []
        if 'incident_config' in config:
            inc_created, inc_updated, inc_errors = connector.sync_incidents(db, integration_id, since)
            logger.info(f" synced incidents: {inc_created} created, {inc_updated} updated")
        
        # Update integration status
        integration.last_sync = utc_now()
        integration.last_sync_status = 'success' if not errors and not inc_errors else 'partial'
        
        all_errors = errors + inc_errors
        integration.last_error = '\n'.join(all_errors[:5]) if all_errors else None
        db.commit()
        
        # Analyze new changes
        impact_service = ChangeImpactService(db)
        analyzed = impact_service.analyze_unprocessed_changes()
        
        return {
            "status": "success" if not all_errors else "partial",
            "created": created,
            "updated": updated,
            "incidents_created": inc_created,
            "incidents_updated": inc_updated,
            "analyzed": analyzed,
            "errors": all_errors[:5] if all_errors else []
        }
        
    except Exception as e:
        logger.exception(f"Error syncing integration: {e}")
        integration.last_sync_status = 'failed'
        integration.last_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates(
    current_user: User = Depends(get_current_user)
):
    """Get list of available ITSM configuration templates"""
    return get_itsm_templates()


@router.get("/templates/{template_name}")
async def get_template(
    template_name: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific ITSM configuration template"""
    template = get_itsm_template(template_name)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template
