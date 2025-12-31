"""
Webhook API - Receive pytest results from test execution
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import TestRun, TestResult, TestCase
from app.models.test_run import TestRunStatus
from app.models.test_result import TestResultStatus

router = APIRouter(prefix="/webhook", tags=["webhook"])


# Pydantic Schemas
class TestResultItem(BaseModel):
    """Individual test result from pytest"""
    test_id: str
    status: str  # passed, failed, skipped, error
    duration: Optional[float] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class PytestWebhookPayload(BaseModel):
    """Webhook payload from pytest execution"""
    run_id: int
    status: str  # completed, failed
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    duration: Optional[float] = None
    results: List[TestResultItem] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@router.post("/pytest-results")
async def receive_pytest_results(
    payload: PytestWebhookPayload,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Receive and process pytest test results

    This webhook is called by the pytest plugin after test execution completes.
    It updates the test run and creates test result records.
    """
    # Get the test run
    run_query = select(TestRun).where(TestRun.id == payload.run_id)
    run_result = await db.execute(run_query)
    test_run = run_result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail=f"Test run {payload.run_id} not found")

    # Update test run
    test_run.status = TestRunStatus.COMPLETED if payload.status == "completed" else TestRunStatus.FAILED
    test_run.total_tests = payload.total_tests
    test_run.passed_tests = payload.passed_tests
    test_run.failed_tests = payload.failed_tests
    test_run.skipped_tests = payload.skipped_tests
    test_run.completed_at = datetime.utcnow()

    if payload.error_message:
        test_run.error_message = payload.error_message

    if payload.metadata:
        test_run.metadata = payload.metadata

    # Process individual test results
    for result_item in payload.results:
        # Find the test case by test_id
        case_query = select(TestCase).where(TestCase.test_id == result_item.test_id)
        case_result = await db.execute(case_query)
        test_case = case_result.scalar_one_or_none()

        if not test_case:
            # Log warning but continue processing
            print(f"Warning: Test case with ID {result_item.test_id} not found")
            continue

        # Map status string to enum
        status_map = {
            "passed": TestResultStatus.PASSED,
            "failed": TestResultStatus.FAILED,
            "skipped": TestResultStatus.SKIPPED,
            "error": TestResultStatus.ERROR
        }
        status = status_map.get(result_item.status.lower(), TestResultStatus.ERROR)

        # Create test result record
        test_result = TestResult(
            run_id=test_run.id,
            case_id=test_case.id,
            status=status,
            duration_seconds=result_item.duration,
            error_message=result_item.error_message,
            stack_trace=result_item.stack_trace,
            stdout=result_item.stdout,
            stderr=result_item.stderr,
            executed_at=datetime.utcnow()
        )
        db.add(test_result)

    await db.commit()

    return {
        "message": "Test results processed successfully",
        "run_id": test_run.id,
        "status": test_run.status.value,
        "total_tests": test_run.total_tests,
        "passed_tests": test_run.passed_tests,
        "failed_tests": test_run.failed_tests
    }


@router.post("/alert-triggered")
async def handle_alert_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Handle webhooks from the remediation engine when alerts are triggered

    This endpoint can automatically execute tests linked to specific alerts.
    """
    payload = await request.json()

    alert_name = payload.get("alert_name")
    if not alert_name:
        raise HTTPException(status_code=400, detail="alert_name is required")

    # Here you would implement logic to:
    # 1. Find test cases linked to this alert
    # 2. Create a new test run
    # 3. Execute the tests

    # For now, just return acknowledgment
    return {
        "message": "Alert webhook received",
        "alert_name": alert_name,
        "action": "Tests will be executed if configured"
    }
