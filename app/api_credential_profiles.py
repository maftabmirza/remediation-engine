"""
API Credential Profiles Management API
Handles CRUD operations for external API service credentials
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from app.database import get_db
from app.models import APICredentialProfile, User
from app.schemas import (
    APICredentialProfileCreate,
    APICredentialProfileUpdate,
    APICredentialProfileResponse
)
from app.utils.crypto import encrypt_value, decrypt_value
from app.services.auth_service import get_current_user

router = APIRouter(
    prefix="/api/credential-profiles",
    tags=["credential-profiles"]
)


@router.get("/", response_model=List[APICredentialProfileResponse])
async def list_credential_profiles(
    skip: int = 0,
    limit: int = 100,
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all API credential profiles.
    """
    query = db.query(APICredentialProfile)

    if enabled_only:
        query = query.filter(APICredentialProfile.enabled == True)

    profiles = query.offset(skip).limit(limit).all()

    # Add computed fields
    for profile in profiles:
        profile.has_token = bool(profile.token_encrypted)
        profile.has_oauth_secret = bool(profile.oauth_client_secret_encrypted)

    return profiles


@router.get("/{profile_id}", response_model=APICredentialProfileResponse)
async def get_credential_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific API credential profile by ID.
    """
    profile = db.query(APICredentialProfile).filter(
        APICredentialProfile.id == profile_id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential profile {profile_id} not found"
        )

    # Add computed fields
    profile.has_token = bool(profile.token_encrypted)
    profile.has_oauth_secret = bool(profile.oauth_client_secret_encrypted)

    return profile


@router.post("/", response_model=APICredentialProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_credential_profile(
    profile_data: APICredentialProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new API credential profile.
    """
    # Encrypt sensitive fields
    token_encrypted = encrypt_value(profile_data.token) if profile_data.token else None
    oauth_secret_encrypted = encrypt_value(profile_data.oauth_client_secret) if profile_data.oauth_client_secret else None

    # Create profile
    profile = APICredentialProfile(
        name=profile_data.name,
        description=profile_data.description,
        credential_type=profile_data.credential_type,
        base_url=profile_data.base_url.rstrip('/'),  # Normalize URL
        auth_type=profile_data.auth_type,
        auth_header=profile_data.auth_header,
        token_encrypted=token_encrypted,
        username=profile_data.username,
        verify_ssl=profile_data.verify_ssl,
        timeout_seconds=profile_data.timeout_seconds,
        default_headers=profile_data.default_headers,
        oauth_token_url=profile_data.oauth_token_url,
        oauth_client_id=profile_data.oauth_client_id,
        oauth_client_secret_encrypted=oauth_secret_encrypted,
        oauth_scope=profile_data.oauth_scope,
        tags=profile_data.tags,
        profile_metadata=profile_data.profile_metadata,
        enabled=profile_data.enabled,
        created_by=current_user.id
    )

    try:
        db.add(profile)
        db.commit()
        db.refresh(profile)
    except IntegrityError as e:
        db.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Credential profile with name '{profile_data.name}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )

    # Add computed fields
    profile.has_token = bool(profile.token_encrypted)
    profile.has_oauth_secret = bool(profile.oauth_client_secret_encrypted)

    return profile


@router.put("/{profile_id}", response_model=APICredentialProfileResponse)
async def update_credential_profile(
    profile_id: UUID,
    profile_data: APICredentialProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing API credential profile.
    """
    profile = db.query(APICredentialProfile).filter(
        APICredentialProfile.id == profile_id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential profile {profile_id} not found"
        )

    # Update fields
    update_data = profile_data.model_dump(exclude_unset=True)

    # Handle encrypted fields
    if 'token' in update_data and update_data['token'] is not None:
        profile.token_encrypted = encrypt_value(update_data.pop('token'))

    if 'oauth_client_secret' in update_data and update_data['oauth_client_secret'] is not None:
        profile.oauth_client_secret_encrypted = encrypt_value(update_data.pop('oauth_client_secret'))

    # Normalize base URL
    if 'base_url' in update_data:
        update_data['base_url'] = update_data['base_url'].rstrip('/')

    # Update remaining fields
    for key, value in update_data.items():
        setattr(profile, key, value)

    try:
        db.commit()
        db.refresh(profile)
    except IntegrityError as e:
        db.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Credential profile with name '{profile_data.name}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )

    # Add computed fields
    profile.has_token = bool(profile.token_encrypted)
    profile.has_oauth_secret = bool(profile.oauth_client_secret_encrypted)

    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an API credential profile.
    """
    profile = db.query(APICredentialProfile).filter(
        APICredentialProfile.id == profile_id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential profile {profile_id} not found"
        )

    # Check if profile is being used by any runbook steps
    # (This will be checked via the database foreign key constraint)

    try:
        db.delete(profile)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete credential profile: it is being used by runbook steps"
        )

    return None


@router.post("/{profile_id}/test", response_model=dict)
async def test_credential_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test an API credential profile by making a simple API call.
    """
    profile = db.query(APICredentialProfile).filter(
        APICredentialProfile.id == profile_id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential profile {profile_id} not found"
        )

    # Import here to avoid circular imports
    import httpx

    # Prepare headers
    headers = dict(profile.default_headers) if profile.default_headers else {}

    # Add authentication
    if profile.auth_type != "none" and profile.token_encrypted:
        token = decrypt_value(profile.token_encrypted)

        if profile.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {token}"
        elif profile.auth_type == "api_key":
            header_name = profile.auth_header or "X-API-Key"
            headers[header_name] = token
        elif profile.auth_type == "basic":
            import base64
            credentials = f"{profile.username}:{token}".encode()
            headers["Authorization"] = f"Basic {base64.b64encode(credentials).decode()}"

    # Make test request
    try:
        async with httpx.AsyncClient(verify=profile.verify_ssl) as client:
            response = await client.get(
                profile.base_url,
                headers=headers,
                timeout=profile.timeout_seconds
            )

            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "message": f"Connection successful" if response.status_code < 400 else f"Connection failed",
                "response_time_ms": int(response.elapsed.total_seconds() * 1000) if hasattr(response, 'elapsed') else None
            }
    except Exception as e:
        return {
            "success": False,
            "status_code": None,
            "message": f"Connection failed: {str(e)}",
            "error": str(e)
        }
