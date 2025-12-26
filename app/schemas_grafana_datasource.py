"""
Pydantic Schemas for Grafana Datasources API

Request and response models for managing observability datasources
(Loki, Tempo, Prometheus, Mimir, etc.)
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class GrafanaDatasourceCreate(BaseModel):
    """Schema for creating a new Grafana datasource"""
    name: str = Field(..., min_length=1, max_length=100, description="Datasource name")
    datasource_type: str = Field(
        ...,
        description="Type of datasource",
        pattern="^(loki|tempo|prometheus|mimir|alertmanager|jaeger|zipkin|elasticsearch)$"
    )
    url: str = Field(..., min_length=1, max_length=512, description="Datasource URL")
    description: Optional[str] = Field(None, description="Description of the datasource")

    # Authentication
    auth_type: str = Field(
        default="none",
        description="Authentication type",
        pattern="^(none|basic|bearer|oauth2|api_key)$"
    )
    username: Optional[str] = Field(None, max_length=255, description="Username for basic auth")
    password: Optional[str] = Field(None, max_length=512, description="Password (will be encrypted)")
    bearer_token: Optional[str] = Field(None, max_length=512, description="Bearer token")

    # Configuration
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    is_default: bool = Field(default=False, description="Set as default datasource for this type")
    is_enabled: bool = Field(default=True, description="Enable this datasource")
    config_json: Dict[str, Any] = Field(default_factory=dict, description="Type-specific configuration")
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "production-loki",
            "datasource_type": "loki",
            "url": "http://loki:3100",
            "description": "Production Loki instance for log aggregation",
            "auth_type": "none",
            "timeout": 30,
            "is_default": True,
            "is_enabled": True,
            "config_json": {"max_lines": 5000},
            "custom_headers": {}
        }
    })


class GrafanaDatasourceUpdate(BaseModel):
    """Schema for updating a Grafana datasource"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    auth_type: Optional[str] = Field(None, pattern="^(none|basic|bearer|oauth2|api_key)$")
    username: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, max_length=512)
    bearer_token: Optional[str] = Field(None, max_length=512)
    timeout: Optional[int] = Field(None, ge=1, le=300)
    is_default: Optional[bool] = None
    is_enabled: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None
    custom_headers: Optional[Dict[str, str]] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "timeout": 60,
            "is_enabled": True,
            "config_json": {"max_lines": 10000}
        }
    })


class GrafanaDatasourceResponse(BaseModel):
    """Schema for Grafana datasource response"""
    id: UUID
    name: str
    datasource_type: str
    url: str
    description: Optional[str]
    auth_type: str
    username: Optional[str]
    # Note: password and bearer_token are not returned for security
    timeout: int
    is_default: bool
    is_enabled: bool
    config_json: Dict[str, Any]
    custom_headers: Dict[str, str]
    last_health_check: Optional[datetime]
    is_healthy: bool
    health_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "production-loki",
                "datasource_type": "loki",
                "url": "http://loki:3100",
                "description": "Production Loki instance",
                "auth_type": "none",
                "username": None,
                "timeout": 30,
                "is_default": True,
                "is_enabled": True,
                "config_json": {"max_lines": 5000},
                "custom_headers": {},
                "last_health_check": "2025-12-26T10:00:00Z",
                "is_healthy": True,
                "health_message": None,
                "created_at": "2025-12-26T09:00:00Z",
                "updated_at": "2025-12-26T09:00:00Z",
                "created_by": "admin"
            }
        }
    )


class GrafanaDatasourceListResponse(BaseModel):
    """Schema for paginated list of datasources"""
    items: List[GrafanaDatasourceResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [],
            "total": 5,
            "page": 1,
            "page_size": 50
        }
    })


class DatasourceHealthCheckResponse(BaseModel):
    """Schema for datasource health check response"""
    datasource_id: UUID
    datasource_name: str
    datasource_type: str
    is_healthy: bool
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    message: Optional[str] = Field(None, description="Health check message or error")
    checked_at: datetime

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "datasource_id": "550e8400-e29b-41d4-a716-446655440000",
            "datasource_name": "production-loki",
            "datasource_type": "loki",
            "is_healthy": True,
            "response_time_ms": 45.3,
            "message": "Loki is ready",
            "checked_at": "2025-12-26T10:00:00Z"
        }
    })


class DatasourceTestConnectionRequest(BaseModel):
    """Schema for testing datasource connection before creating"""
    datasource_type: str = Field(..., pattern="^(loki|tempo|prometheus|mimir|alertmanager|jaeger|zipkin|elasticsearch)$")
    url: str = Field(..., min_length=1, max_length=512)
    auth_type: str = Field(default="none", pattern="^(none|basic|bearer|oauth2|api_key)$")
    username: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, max_length=512)
    bearer_token: Optional[str] = Field(None, max_length=512)
    timeout: int = Field(default=30, ge=1, le=300)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "datasource_type": "loki",
            "url": "http://loki:3100",
            "auth_type": "none",
            "timeout": 30
        }
    })


class DatasourceTestConnectionResponse(BaseModel):
    """Schema for test connection response"""
    success: bool
    message: str
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional details about the connection test"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "Connection successful",
            "response_time_ms": 52.1,
            "details": {"version": "2.9.0"}
        }
    })
