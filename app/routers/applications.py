"""Application Registry API Router

REST API endpoints for managing applications, components, and dependencies.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models_application import Application, ApplicationComponent, ComponentDependency
from app.models import Alert, User
from app.schemas_application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationWithComponents,
    ApplicationListResponse,
    ComponentCreate,
    ComponentUpdate,
    ComponentResponse,
    ComponentWithDependencies,
    ComponentListResponse,
    DependencyCreate,
    DependencyResponse,
    DependencyGraphResponse,
)
from app.services.application_service import ApplicationService
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/applications", tags=["applications"])


# ============== Statistics Endpoint ==============

@router.get("/stats")
def get_application_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get application statistics for dashboard."""
    total_apps = db.query(Application).count()
    critical_apps = db.query(Application).filter(Application.criticality == 'critical').count()
    total_components = db.query(ApplicationComponent).count()
    
    return {
        "total": total_apps,
        "critical": critical_apps,
        "total_components": total_components
    }


# ============== Application Endpoints ==============

@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application(
    app_data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new application."""
    # Check if application name already exists
    existing = db.query(Application).filter(Application.name == app_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Application '{app_data.name}' already exists")

    app = Application(**app_data.model_dump())
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    criticality: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all applications with optional filtering."""
    query = db.query(Application)

    # Apply filters
    if search:
        query = query.filter(
            (Application.name.ilike(f"%{search}%")) |
            (Application.display_name.ilike(f"%{search}%"))
        )
    
    if criticality:
        query = query.filter(Application.criticality == criticality)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/{app_id}", response_model=ApplicationWithComponents)
def get_application(
    app_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single application with its components."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Get alert count
    alert_count = db.query(func.count(Alert.id)).filter(Alert.app_id == app_id).scalar()

    # Build response
    response = ApplicationWithComponents.model_validate(app)
    response.alert_count = alert_count
    return response


@router.put("/{app_id}", response_model=ApplicationResponse)
def update_application(
    app_id: UUID,
    app_data: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an application."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Update only provided fields
    update_data = app_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(app, field, value)

    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204)
def delete_application(
    app_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an application and all its components."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(app)
    db.commit()
    return None


# ============== Component Endpoints ==============

@router.post("/{app_id}/components", response_model=ComponentResponse, status_code=201)
def create_component(
    app_id: UUID,
    comp_data: ComponentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new component for an application."""
    # Verify application exists
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Check if component name already exists in this app
    existing = db.query(ApplicationComponent).filter(
        ApplicationComponent.app_id == app_id,
        ApplicationComponent.name == comp_data.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Component '{comp_data.name}' already exists in this application")

    component = ApplicationComponent(app_id=app_id, **comp_data.model_dump())
    db.add(component)
    db.commit()
    db.refresh(component)
    return component


@router.get("/{app_id}/components", response_model=ComponentListResponse)
def list_components(
    app_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all components for an application."""
    # Verify application exists
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    components = db.query(ApplicationComponent).filter(
        ApplicationComponent.app_id == app_id
    ).all()

    return {
        "items": components,
        "total": len(components)
    }


@router.get("/{app_id}/components/{component_id}", response_model=ComponentWithDependencies)
def get_component(
    app_id: UUID,
    component_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a component with its dependencies."""
    component = db.query(ApplicationComponent).filter(
        ApplicationComponent.id == component_id,
        ApplicationComponent.app_id == app_id
    ).first()
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")

    # Get dependencies
    app_service = ApplicationService(db)
    deps = app_service.get_component_dependencies(component_id)

    response = ComponentWithDependencies.model_validate(component)
    response.upstream = deps["upstream"]
    response.downstream = deps["downstream"]
    return response


@router.put("/{app_id}/components/{component_id}", response_model=ComponentResponse)
def update_component(
    app_id: UUID,
    component_id: UUID,
    comp_data: ComponentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a component."""
    component = db.query(ApplicationComponent).filter(
        ApplicationComponent.id == component_id,
        ApplicationComponent.app_id == app_id
    ).first()
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")

    # Update only provided fields
    update_data = comp_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(component, field, value)

    db.commit()
    db.refresh(component)
    return component


@router.delete("/{app_id}/components/{component_id}", status_code=204)
def delete_component(
    app_id: UUID,
    component_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a component."""
    component = db.query(ApplicationComponent).filter(
        ApplicationComponent.id == component_id,
        ApplicationComponent.app_id == app_id
    ).first()
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")

    db.delete(component)
    db.commit()
    return None


# ============== Dependency Endpoints ==============

@router.post("/{app_id}/dependencies", response_model=DependencyResponse, status_code=201)
def create_dependency(
    app_id: UUID,
    dep_data: DependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a dependency between two components."""
    # Verify both components belong to this application
    from_comp = db.query(ApplicationComponent).filter(
        ApplicationComponent.id == dep_data.from_component_id,
        ApplicationComponent.app_id == app_id
    ).first()
    to_comp = db.query(ApplicationComponent).filter(
        ApplicationComponent.id == dep_data.to_component_id,
        ApplicationComponent.app_id == app_id
    ).first()

    if not from_comp or not to_comp:
        raise HTTPException(status_code=400, detail="Both components must belong to the specified application")

    # Check if dependency already exists
    existing = db.query(ComponentDependency).filter(
        ComponentDependency.from_component_id == dep_data.from_component_id,
        ComponentDependency.to_component_id == dep_data.to_component_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")

    dependency = ComponentDependency(**dep_data.model_dump())
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@router.get("/{app_id}/dependency-graph", response_model=DependencyGraphResponse)
def get_dependency_graph(
    app_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the complete dependency graph for an application."""
    # Verify application exists
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app_service = ApplicationService(db)
    graph = app_service.build_dependency_graph(app_id)
    return graph


@router.put("/{app_id}/dependencies/{dependency_id}", response_model=DependencyResponse)
def update_dependency(
    app_id: UUID,
    dependency_id: UUID,
    dependency_update: DependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing dependency."""
    # Verify dependency exists and belongs to this app
    dependency = db.query(ComponentDependency).join(
        ApplicationComponent,
        ComponentDependency.from_component_id == ApplicationComponent.id
    ).filter(
        ComponentDependency.id == dependency_id,
        ApplicationComponent.app_id == app_id
    ).first()
    
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")
    
    # Update fields
    dependency.from_component_id = dependency_update.from_component_id
    dependency.to_component_id = dependency_update.to_component_id
    dependency.dependency_type = dependency_update.dependency_type
    dependency.failure_impact = dependency_update.failure_impact
    
    db.commit()
    db.refresh(dependency)
    return dependency


@router.delete("/dependencies/{dependency_id}", status_code=204)
def delete_dependency(
    dependency_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a dependency."""
    dependency = db.query(ComponentDependency).filter(
        ComponentDependency.id == dependency_id
    ).first()
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")

    db.delete(dependency)
    db.commit()
    return None


# ============== Alert Integration Endpoints ==============

@router.get("/{app_id}/alerts")
def get_application_alerts(
    app_id: UUID,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get alerts for this application."""
    query = db.query(Alert).filter(Alert.app_id == app_id)

    if status:
        query = query.filter(Alert.status == status)

    query = query.order_by(Alert.timestamp.desc()).limit(limit)
    alerts = query.all()

    return {
        "items": [
            {
                "id": str(alert.id),
                "alert_name": alert.alert_name,
                "severity": alert.severity,
                "status": alert.status,
                "timestamp": alert.timestamp,
                "component_id": str(alert.component_id) if alert.component_id else None
            }
            for alert in alerts
        ],
        "total": len(alerts)
    }
