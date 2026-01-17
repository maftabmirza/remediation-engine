"""
Pydantic schemas for Application Profiles.

Request/response models for Application Profile API endpoints.
"""
from typing import Optional, Dict, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas_application import ApplicationResponse


class ApplicationProfileCreate(BaseModel):
    """Schema for creating an application profile"""
    app_id: UUID = Field(..., description="Application ID this profile belongs to")
    architecture_type: Optional[str] = Field(None, description="Architecture type: monolith, microservices, serverless, hybrid, other")
    framework: Optional[str] = Field(None, description="Framework: FastAPI, Django, Spring Boot, etc.")
    language: Optional[str] = Field(None, description="Programming language")
    architecture_info: Dict[str, Any] = Field(default_factory=dict, description="Additional architecture details")
    service_mappings: Dict[str, Any] = Field(default_factory=dict, description="Service to metrics mapping")
    default_metrics: List[str] = Field(default_factory=list, description="Default metrics to track")
    slos: Dict[str, Any] = Field(default_factory=dict, description="Service Level Objectives")
    prometheus_datasource_id: Optional[UUID] = Field(None, description="Prometheus datasource ID")
    loki_datasource_id: Optional[UUID] = Field(None, description="Loki datasource ID")
    tempo_datasource_id: Optional[UUID] = Field(None, description="Tempo datasource ID")
    default_time_range: str = Field(default="1h", description="Default time range for queries")
    log_patterns: Dict[str, str] = Field(default_factory=dict, description="Common log patterns")

    class Config:
        from_attributes = True


class ApplicationProfileUpdate(BaseModel):
    """Schema for updating an application profile"""
    architecture_type: Optional[str] = None
    framework: Optional[str] = None
    language: Optional[str] = None
    architecture_info: Optional[Dict[str, Any]] = None
    service_mappings: Optional[Dict[str, Any]] = None
    default_metrics: Optional[List[str]] = None
    slos: Optional[Dict[str, Any]] = None
    prometheus_datasource_id: Optional[UUID] = None
    loki_datasource_id: Optional[UUID] = None
    tempo_datasource_id: Optional[UUID] = None
    default_time_range: Optional[str] = None
    log_patterns: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True


class ApplicationProfileResponse(BaseModel):
    """Schema for application profile response"""
    id: UUID
    app_id: UUID
    architecture_type: Optional[str]
    framework: Optional[str]
    language: Optional[str]
    architecture_info: Dict[str, Any] = Field(default_factory=dict)
    service_mappings: Dict[str, Any] = Field(default_factory=dict)
    default_metrics: List[str] = Field(default_factory=list)
    slos: Dict[str, Any] = Field(default_factory=dict)
    prometheus_datasource_id: Optional[UUID]
    loki_datasource_id: Optional[UUID]
    tempo_datasource_id: Optional[UUID]
    default_time_range: str
    log_patterns: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationProfileWithApplication(ApplicationProfileResponse):
    """Schema for application profile with application details"""
    application: Optional[ApplicationResponse] = None

    class Config:
        from_attributes = True


class ApplicationProfileListResponse(BaseModel):
    """Schema for paginated list of application profiles"""
    items: List[ApplicationProfileResponse]
    total: int
    page: int
    page_size: int

    class Config:
        from_attributes = True
