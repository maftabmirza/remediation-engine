"""
Test Cases API - CRUD operations for test cases
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import os

from app.database import get_db
from app.models import TestCase, TestSuite
from app.models.test_case import TestPriority

router = APIRouter(prefix="/test-cases", tags=["test_cases"])

# Get the templates directory
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


# Pydantic Schemas
class TestCaseCreate(BaseModel):
    """Schema for creating a test case"""
    test_id: str = Field(..., min_length=1, max_length=50)
    suite_id: int
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    test_file_path: str
    test_function: str
    priority: TestPriority = TestPriority.MEDIUM
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    enabled: bool = True
    tags: Optional[List[str]] = None
    requirements: Optional[dict] = None


class TestCaseUpdate(BaseModel):
    """Schema for updating a test case"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    test_file_path: Optional[str] = None
    test_function: Optional[str] = None
    priority: Optional[TestPriority] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600)
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None
    requirements: Optional[dict] = None


class TestCaseResponse(BaseModel):
    """Schema for test case response"""
    id: int
    test_id: str
    suite_id: int
    name: str
    description: Optional[str]
    test_file_path: str
    test_function: str
    priority: str
    timeout_seconds: int
    enabled: bool
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# API Endpoints
@router.get("/", response_class=HTMLResponse)
async def test_cases_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Render the test cases HTML page
    """
    return templates.TemplateResponse("test_cases.html", {"request": request})


@router.get("/list")
async def list_test_cases(
    suite_id: Optional[int] = None,
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    priority: Optional[TestPriority] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List test cases with optional filters
    """
    query = select(TestCase).join(TestSuite)

    # Apply filters
    if suite_id:
        query = query.where(TestCase.suite_id == suite_id)
    if category:
        query = query.where(TestSuite.category == category)
    if enabled is not None:
        query = query.where(TestCase.enabled == enabled)
    if priority:
        query = query.where(TestCase.priority == priority)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(TestCase.test_id)

    result = await db.execute(query)
    test_cases = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": tc.id,
                "test_id": tc.test_id,
                "suite_id": tc.suite_id,
                "name": tc.name,
                "description": tc.description,
                "test_file_path": tc.test_file_path,
                "test_function": tc.test_function,
                "priority": tc.priority.value,
                "timeout_seconds": tc.timeout_seconds,
                "enabled": tc.enabled,
                "tags": tc.tags,
                "created_at": tc.created_at.isoformat(),
                "updated_at": tc.updated_at.isoformat()
            }
            for tc in test_cases
        ]
    }


@router.get("/{test_case_id}")
async def get_test_case(
    test_case_id: int,
    db: AsyncSession = Depends(get_db)
) -> TestCaseResponse:
    """
    Get a specific test case by ID
    """
    query = select(TestCase).where(TestCase.id == test_case_id)
    result = await db.execute(query)
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    return TestCaseResponse.model_validate(test_case)


@router.post("/")
async def create_test_case(
    test_case_data: TestCaseCreate,
    db: AsyncSession = Depends(get_db)
) -> TestCaseResponse:
    """
    Create a new test case
    """
    # Check if test_id already exists
    existing_query = select(TestCase).where(TestCase.test_id == test_case_data.test_id)
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Test ID already exists")

    # Check if suite exists
    suite_query = select(TestSuite).where(TestSuite.id == test_case_data.suite_id)
    suite_result = await db.execute(suite_query)
    if not suite_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test suite not found")

    # Create test case
    test_case = TestCase(**test_case_data.model_dump())
    db.add(test_case)
    await db.commit()
    await db.refresh(test_case)

    return TestCaseResponse.model_validate(test_case)


@router.put("/{test_case_id}")
async def update_test_case(
    test_case_id: int,
    test_case_data: TestCaseUpdate,
    db: AsyncSession = Depends(get_db)
) -> TestCaseResponse:
    """
    Update an existing test case
    """
    query = select(TestCase).where(TestCase.id == test_case_id)
    result = await db.execute(query)
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    # Update only provided fields
    update_data = test_case_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(test_case, field, value)

    await db.commit()
    await db.refresh(test_case)

    return TestCaseResponse.model_validate(test_case)


@router.delete("/{test_case_id}")
async def delete_test_case(
    test_case_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Delete a test case
    """
    query = select(TestCase).where(TestCase.id == test_case_id)
    result = await db.execute(query)
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    await db.delete(test_case)
    await db.commit()

    return {"message": "Test case deleted successfully"}
