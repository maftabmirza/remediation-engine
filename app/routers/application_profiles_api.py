"""
Application Profiles API Router

REST API endpoints for managing application monitoring profiles.
Enables AI-powered observability by storing SLOs, metrics mappings, and datasource configurations.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models_application import ApplicationProfile, Application
from app.models import User
from app.schemas_application_profile import (
    ApplicationProfileCreate,
    ApplicationProfileUpdate,
    ApplicationProfileResponse,
    ApplicationProfileWithApplication,
    ApplicationProfileListResponse,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/application-profiles", tags=["application-profiles"])


@router.post("", response_model=ApplicationProfileResponse, status_code=201)
def create_application_profile(
    profile_data: ApplicationProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new application monitoring profile.

    Args:
        profile_data: Application profile data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created application profile

    Raises:
        HTTPException: 400 if application doesn't exist or profile already exists for this app
    """
    # Check if application exists
    app = db.query(Application).filter(Application.id == profile_data.app_id).first()
    if not app:
        raise HTTPException(status_code=400, detail=f"Application with id {profile_data.app_id} not found")

    # Check if profile already exists for this application
    existing = db.query(ApplicationProfile).filter(ApplicationProfile.app_id == profile_data.app_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Profile already exists for application {app.name}")

    try:
        profile = ApplicationProfile(**profile_data.model_dump())
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database integrity error: {str(e)}")


@router.get("", response_model=ApplicationProfileListResponse)
def list_application_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    architecture_type: Optional[str] = None,
    language: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all application profiles with optional filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        architecture_type: Filter by architecture type
        language: Filter by programming language
        db: Database session
        current_user: Authenticated user

    Returns:
        Paginated list of application profiles
    """
    query = db.query(ApplicationProfile)

    # Apply filters
    if architecture_type:
        query = query.filter(ApplicationProfile.architecture_type == architecture_type)

    if language:
        query = query.filter(ApplicationProfile.language.ilike(f"%{language}%"))

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


@router.get("/by-app/{app_id}", response_model=ApplicationProfileResponse)
def get_profile_by_application(
    app_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get application profile by application ID.

    Args:
        app_id: Application UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Application profile

    Raises:
        HTTPException: 404 if profile not found
    """
    profile = db.query(ApplicationProfile).filter(ApplicationProfile.app_id == app_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found for application {app_id}")

    return profile


@router.get("/{profile_id}", response_model=ApplicationProfileWithApplication)
def get_application_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single application profile by ID with application details.

    Args:
        profile_id: Profile UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Application profile with application details

    Raises:
        HTTPException: 404 if profile not found
    """
    profile = db.query(ApplicationProfile).filter(ApplicationProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Application profile not found")

    return profile


@router.put("/{profile_id}", response_model=ApplicationProfileResponse)
def update_application_profile(
    profile_id: UUID,
    profile_data: ApplicationProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an application profile.

    Args:
        profile_id: Profile UUID
        profile_data: Updated profile data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated application profile

    Raises:
        HTTPException: 404 if profile not found
    """
    profile = db.query(ApplicationProfile).filter(ApplicationProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Application profile not found")

    # Update only provided fields
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete_application_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an application profile.

    Args:
        profile_id: Profile UUID
        db: Database session
        current_user: Authenticated user

    Raises:
        HTTPException: 404 if profile not found
    """
    profile = db.query(ApplicationProfile).filter(ApplicationProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Application profile not found")

    db.delete(profile)
    db.commit()
    return None


@router.get("/{profile_id}/health-check", response_model=dict)
def check_profile_configuration(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if application profile is properly configured for AI queries.

    Args:
        profile_id: Profile UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Configuration status and recommendations

    Example response:
        {
            "is_complete": true,
            "has_slos": true,
            "has_metrics": true,
            "has_service_mappings": true,
            "recommendations": []
        }
    """
    profile = db.query(ApplicationProfile).filter(ApplicationProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Application profile not found")

    recommendations = []

    # Check SLOs
    has_slos = bool(profile.slos and len(profile.slos) > 0)
    if not has_slos:
        recommendations.append("Add SLOs (Service Level Objectives) for health monitoring")

    # Check default metrics
    has_metrics = bool(profile.default_metrics and len(profile.default_metrics) > 0)
    if not has_metrics:
        recommendations.append("Add default metrics to track (e.g., http_requests_total, error_rate)")

    # Check service mappings
    has_service_mappings = bool(profile.service_mappings and len(profile.service_mappings) > 0)
    if not has_service_mappings:
        recommendations.append("Add service mappings for metrics and logs correlation")

    # Check architecture info
    has_architecture = bool(profile.architecture_type)
    if not has_architecture:
        recommendations.append("Set architecture type for better AI context")

    is_complete = has_slos and has_metrics and has_service_mappings and has_architecture

    return {
        "is_complete": is_complete,
        "has_slos": has_slos,
        "has_metrics": has_metrics,
        "has_service_mappings": has_service_mappings,
        "has_architecture": has_architecture,
        "recommendations": recommendations,
        "profile_id": str(profile_id),
        "app_name": profile.application.name if profile.application else None
    }
