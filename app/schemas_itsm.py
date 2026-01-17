"""
ITSM Integration Schemas

Pydantic schemas for ITSM integrations and change events.
"""
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID


# ========== ITSM Integration Schemas ==========

class ITSMConfigBase(BaseModel):
    """Base ITSM configuration"""
    name: str
    connector_type: str = 'generic_api'
    is_enabled: bool = True


class ITSMConfigCreate(ITSMConfigBase):
    """Create ITSM integration"""
    config: Dict[str, Any]  # Unencrypted config (will be encrypted before storage)


class ITSMConfigUpdate(BaseModel):
    """Update ITSM integration"""
    name: Optional[str] = None
    connector_type: Optional[str] = None
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class ITSMConfigResponse(ITSMConfigBase):
    """ITSM integration response"""
    id: UUID
    config: Optional[Dict[str, Any]] = None  # Decrypted config (for editing)
    last_sync: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ITSMTestResult(BaseModel):
    """Result of testing ITSM connection"""
    success: bool
    message: str
    sample_data: Optional[Dict[str, Any]] = None


# ========== Change Event Schemas ==========

class ChangeEventBase(BaseModel):
    """Base change event"""
    change_id: str
    change_type: str
    service_name: Optional[str] = None
    description: Optional[str] = None
    timestamp: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    associated_cis: Optional[List[str]] = []  # Configuration Items affected
    application: Optional[str] = None          # Application affected by change


class ChangeEventCreate(ChangeEventBase):
    """Create change event (via webhook)"""
    source: str = 'webhook'
    metadata: Dict[str, Any] = {}


class ChangeEventResponse(ChangeEventBase):
    """Change event response"""
    id: UUID
    source: str
    metadata: Dict[str, Any]
    correlation_score: Optional[float] = None
    impact_level: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangeEventDetail(ChangeEventResponse):
    """Change event with impact analysis"""
    impact_analysis: Optional['ChangeImpactResponse'] = None


# ========== Impact Analysis Schemas ==========

class ChangeImpactResponse(BaseModel):
    """Change impact analysis result"""
    id: UUID
    change_event_id: UUID
    incidents_after: int
    critical_incidents: int
    correlation_score: float
    impact_level: str  # high, medium, low, none
    recommendation: Optional[str] = None
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangeImpactSummary(BaseModel):
    """Summary of change impact for dashboard"""
    change_id: str
    change_description: Optional[str]
    timestamp: datetime
    correlation_score: float
    impact_level: str
    incidents_after: int
    critical_incidents: int
    recommendation: Optional[str] = None


# ========== Timeline Schemas ==========

class ChangeTimelineEntry(BaseModel):
    """Entry in change timeline"""
    id: UUID
    change_id: str
    change_type: str
    service_name: Optional[str]
    description: Optional[str]
    timestamp: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    associated_cis: Optional[List[str]] = []
    application: Optional[str] = None
    impact_level: Optional[str]
    incidents_after: int = 0


class ChangeTimelineResponse(BaseModel):
    """Change timeline response"""
    entries: List[ChangeTimelineEntry]
    total_changes: int
    high_impact_count: int


# ========== Configuration Templates ==========

class ITSMConfigTemplate(BaseModel):
    """Pre-configured ITSM template"""
    name: str  # ServiceNow, Jira, GitHub
    description: str
    config_template: Dict[str, Any]
    field_mapping_example: Dict[str, str]


# Rebuild models for forward references
ChangeEventDetail.model_rebuild()
