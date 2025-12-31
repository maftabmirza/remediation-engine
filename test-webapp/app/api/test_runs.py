"""
Test Runs API - Manage and execute test runs
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import os

from app.database import get_db
from app.models import TestRun, TestResult, TestCase, TestSuite
from app.models.test_run import TestRunStatus, TestRunTrigger
from app.services.executor import TestExecutor

router = APIRouter(prefix="/test-runs", tags=["test_runs"])

# Get the templates directory
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


# Pydantic Schemas
class TestRunCreate(BaseModel):
    """Schema for creating a test run"""
    suite_id: Optional[int] = None
    test_case_ids: Optional[List[int]] = None
    trigger: TestRunTrigger = TestRunTrigger.MANUAL
    triggered_by: Optional[str] = None
    environment: Optional[str] = None
    metadata: Optional[dict] = None


class TestRunResponse(BaseModel):
    """Schema for test run response"""
    id: int
    suite_id: Optional[int]
    status: str
    trigger: str
    triggered_by: Optional[str]
    environment: Optional[str]
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# API Endpoints
@router.get("/", response_class=HTMLResponse)
async def test_runs_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Render the test runs HTML page
    """
    return templates.TemplateResponse("test_runs.html", {"request": request})


@router.get("/list")
async def list_test_runs(
    status: Optional[TestRunStatus] = None,
    suite_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List test runs with optional filters
    """
    query = select(TestRun)

    # Apply filters
    if status:
        query = query.where(TestRun.status == status)
    if suite_id:
        query = query.where(TestRun.suite_id == suite_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(TestRun.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    test_runs = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": tr.id,
                "suite_id": tr.suite_id,
                "status": tr.status.value,
                "trigger": tr.trigger.value,
                "triggered_by": tr.triggered_by,
                "environment": tr.environment,
                "total_tests": tr.total_tests,
                "passed_tests": tr.passed_tests,
                "failed_tests": tr.failed_tests,
                "skipped_tests": tr.skipped_tests,
                "started_at": tr.started_at.isoformat() if tr.started_at else None,
                "completed_at": tr.completed_at.isoformat() if tr.completed_at else None,
                "created_at": tr.created_at.isoformat()
            }
            for tr in test_runs
        ]
    }


@router.get("/{run_id}")
async def get_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get detailed information about a specific test run
    """
    # Get test run
    run_query = select(TestRun).where(TestRun.id == run_id)
    run_result = await db.execute(run_query)
    test_run = run_result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Get test results
    results_query = select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.executed_at)
    results_result = await db.execute(results_query)
    test_results = results_result.scalars().all()

    return {
        "id": test_run.id,
        "suite_id": test_run.suite_id,
        "status": test_run.status.value,
        "trigger": test_run.trigger.value,
        "triggered_by": test_run.triggered_by,
        "environment": test_run.environment,
        "total_tests": test_run.total_tests,
        "passed_tests": test_run.passed_tests,
        "failed_tests": test_run.failed_tests,
        "skipped_tests": test_run.skipped_tests,
        "error_message": test_run.error_message,
        "metadata": test_run.metadata,
        "started_at": test_run.started_at.isoformat() if test_run.started_at else None,
        "completed_at": test_run.completed_at.isoformat() if test_run.completed_at else None,
        "created_at": test_run.created_at.isoformat(),
        "results": [
            {
                "id": result.id,
                "case_id": result.case_id,
                "status": result.status.value,
                "duration_seconds": result.duration_seconds,
                "error_message": result.error_message,
                "executed_at": result.executed_at.isoformat()
            }
            for result in test_results
        ]
    }


@router.get("/{run_id}/page", response_class=HTMLResponse)
async def test_run_details_page(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Render the test run details HTML page
    """
    return templates.TemplateResponse(
        "test_run_details.html",
        {"request": request, "run_id": run_id}
    )


@router.post("/")
async def create_test_run(
    test_run_data: TestRunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> TestRunResponse:
    """
    Create and execute a new test run
    """
    # Validate suite or test cases
    if not test_run_data.suite_id and not test_run_data.test_case_ids:
        raise HTTPException(
            status_code=400,
            detail="Either suite_id or test_case_ids must be provided"
        )

    # Create test run record
    test_run = TestRun(
        suite_id=test_run_data.suite_id,
        status=TestRunStatus.PENDING,
        trigger=test_run_data.trigger,
        triggered_by=test_run_data.triggered_by,
        environment=test_run_data.environment,
        metadata=test_run_data.metadata
    )
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    # Execute tests in background
    background_tasks.add_task(
        execute_test_run,
        test_run.id,
        test_run_data.suite_id,
        test_run_data.test_case_ids
    )

    return TestRunResponse.model_validate(test_run)


@router.post("/{run_id}/cancel")
async def cancel_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Cancel a running test run
    """
    query = select(TestRun).where(TestRun.id == run_id)
    result = await db.execute(query)
    test_run = result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")

    if test_run.status not in [TestRunStatus.PENDING, TestRunStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel test run with status: {test_run.status.value}"
        )

    test_run.status = TestRunStatus.CANCELLED
    test_run.completed_at = datetime.utcnow()
    await db.commit()

    return {"message": "Test run cancelled successfully"}


@router.delete("/{run_id}")
async def delete_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Delete a test run
    """
    query = select(TestRun).where(TestRun.id == run_id)
    result = await db.execute(query)
    test_run = result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")

    await db.delete(test_run)
    await db.commit()

    return {"message": "Test run deleted successfully"}


# Background task function
async def execute_test_run(
    run_id: int,
    suite_id: Optional[int] = None,
    test_case_ids: Optional[List[int]] = None
):
    """
    Execute test run in background
    """
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            executor = TestExecutor(db)
            await executor.execute_test_run(run_id, suite_id, test_case_ids)
        except Exception as e:
            # Update test run with error
            query = select(TestRun).where(TestRun.id == run_id)
            result = await db.execute(query)
            test_run = result.scalar_one_or_none()

            if test_run:
                test_run.status = TestRunStatus.FAILED
                test_run.error_message = str(e)
                test_run.completed_at = datetime.utcnow()
                await db.commit()
