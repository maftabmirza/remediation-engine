"""Application Registry Schemas

Pydantic models for request/response validation.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID


# ============== Application Schemas ==============

class ApplicationBase(BaseModel):
    name: str = Field(..., max_length=100, description="Unique application identifier")
    display_name: Optional[str] = Field(None, max_length=200, description="Human-readable name")
    description: Optional[str] = None
    team_owner: Optional[str] = Field(None, max_length=100)
    criticality: Optional[str] = Field(None, pattern="^(critical|high|medium|low)$")
    tech_stack: Dict[str, Any] = Field(default_factory=dict)
    alert_label_matchers: Dict[str, str] = Field(default_factory=dict, description="Label patterns to match alerts")


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    team_owner: Optional[str] = None
    criticality: Optional[str] = Field(None, pattern="^(critical|high|medium|low)$")
    tech_stack: Optional[Dict[str, Any]] = None
    alert_label_matchers: Optional[Dict[str, str]] = None


class ApplicationResponse(ApplicationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationWithComponents(ApplicationResponse):
    components: List['ComponentResponse'] = []
    alert_count: Optional[int] = 0


# ============== Component Schemas ==============

class ComponentBase(BaseModel):
    name: str = Field(..., max_length=100)
    component_type: Optional[str] = Field(
        None,
        pattern="^(compute|container|vm|database|cache|queue|storage|load_balancer|firewall|switch|router|cloud_function|cloud_storage|cloud_db|external|monitoring|cdn|api_gateway)$"
    )
    subtype: Optional[str] = Field(None, max_length=50)
    hostname: Optional[str] = Field(None, max_length=255)
    ip_address: Optional[str] = Field(None, max_length=45)
    description: Optional[str] = None
    endpoints: Dict[str, Any] = Field(default_factory=dict)
    alert_label_matchers: Dict[str, str] = Field(default_factory=dict)
    criticality: str = Field(default="high", pattern="^(critical|high|medium|low)$")


class ComponentCreate(ComponentBase):
    pass


class ComponentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    component_type: Optional[str] = None
    subtype: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    description: Optional[str] = None
    endpoints: Optional[Dict[str, Any]] = None
    alert_label_matchers: Optional[Dict[str, str]] = None
    criticality: Optional[str] = None


class ComponentResponse(ComponentBase):
    id: UUID
    app_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComponentWithDependencies(ComponentResponse):
    """Component with its upstream and downstream dependencies."""
    upstream: List['ComponentResponse'] = Field(default_factory=list, description="Components this depends on")
    downstream: List['ComponentResponse'] = Field(default_factory=list, description="Components that depend on this")


# ============== Dependency Schemas ==============

class DependencyBase(BaseModel):
    from_component_id: UUID = Field(..., description="Component that has the dependency")
    to_component_id: UUID = Field(..., description="Component being depended upon")
    dependency_type: Optional[str] = Field(None, pattern="^(sync|async|optional)$")
    failure_impact: Optional[str] = Field(None, description="What happens when dependency fails")


class DependencyCreate(DependencyBase):
    pass


class DependencyResponse(DependencyBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Graph Schemas ==============

class GraphNode(BaseModel):
    """Node in dependency graph."""
    id: str
    name: str
    type: str
    criticality: Optional[str] = None
    app_id: Optional[str] = None


class GraphEdge(BaseModel):
    """Edge in dependency graph."""
    id: str  # Dependency ID for editing/deleting
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    type: Optional[str] = None
    
    class Config:
        populate_by_name = True


class DependencyGraphResponse(BaseModel):
    """Complete dependency graph for an application."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# ============== List Response Schemas ==============

class ApplicationListResponse(BaseModel):
    """Paginated list of applications."""
    items: List[ApplicationResponse]
    total: int
    page: int = 1
    page_size: int = 50


class ComponentListResponse(BaseModel):
    """List of components for an application."""
    items: List[ComponentResponse]
    total: int


# Update forward references
ApplicationWithComponents.model_rebuild()
ComponentWithDependencies.model_rebuild()
