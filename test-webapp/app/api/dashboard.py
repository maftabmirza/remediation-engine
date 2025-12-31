"""
Dashboard API - Statistics and overview data
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from typing import Dict, List, Any
import os

from app.database import get_db
from app.models import TestRun, TestResult, TestCase, TestSuite
from app.models.test_run import TestRunStatus
from app.models.test_result import TestResultStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Get the templates directory
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Render the dashboard HTML page
    """
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get dashboard statistics
    """
    # Total test cases
    total_tests_query = select(func.count(TestCase.id))
    total_tests_result = await db.execute(total_tests_query)
    total_tests = total_tests_result.scalar() or 0

    # Total test runs
    total_runs_query = select(func.count(TestRun.id))
    total_runs_result = await db.execute(total_runs_query)
    total_runs = total_runs_result.scalar() or 0

    # Recent test runs (last 24 hours)
    last_24h = datetime.utcnow() - timedelta(hours=24)
    recent_runs_query = select(func.count(TestRun.id)).where(
        TestRun.created_at >= last_24h
    )
    recent_runs_result = await db.execute(recent_runs_query)
    recent_runs = recent_runs_result.scalar() or 0

    # Success rate (last 30 days)
    last_30d = datetime.utcnow() - timedelta(days=30)

    total_results_query = select(func.count(TestResult.id)).where(
        TestResult.executed_at >= last_30d
    )
    total_results_result = await db.execute(total_results_query)
    total_results = total_results_result.scalar() or 0

    passed_results_query = select(func.count(TestResult.id)).where(
        and_(
            TestResult.executed_at >= last_30d,
            TestResult.status == TestResultStatus.PASSED
        )
    )
    passed_results_result = await db.execute(passed_results_query)
    passed_results = passed_results_result.scalar() or 0

    success_rate = (passed_results / total_results * 100) if total_results > 0 else 0

    # Active test runs
    active_runs_query = select(func.count(TestRun.id)).where(
        TestRun.status.in_([TestRunStatus.PENDING, TestRunStatus.RUNNING])
    )
    active_runs_result = await db.execute(active_runs_query)
    active_runs = active_runs_result.scalar() or 0

    return {
        "total_tests": total_tests,
        "total_runs": total_runs,
        "recent_runs": recent_runs,
        "success_rate": round(success_rate, 2),
        "active_runs": active_runs
    }


@router.get("/trends")
async def get_test_trends(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get test execution trends over time
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get test runs by day
    query = select(
        func.date(TestRun.created_at).label("date"),
        func.count(TestRun.id).label("total"),
        func.sum(TestRun.passed_tests).label("passed"),
        func.sum(TestRun.failed_tests).label("failed"),
        func.sum(TestRun.skipped_tests).label("skipped")
    ).where(
        TestRun.created_at >= start_date
    ).group_by(
        func.date(TestRun.created_at)
    ).order_by(
        func.date(TestRun.created_at)
    )

    result = await db.execute(query)
    rows = result.all()

    dates = []
    totals = []
    passed = []
    failed = []
    skipped = []

    for row in rows:
        dates.append(row.date.isoformat())
        totals.append(row.total)
        passed.append(row.passed or 0)
        failed.append(row.failed or 0)
        skipped.append(row.skipped or 0)

    return {
        "dates": dates,
        "totals": totals,
        "passed": passed,
        "failed": failed,
        "skipped": skipped
    }


@router.get("/category-breakdown")
async def get_category_breakdown(
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get test breakdown by category
    """
    query = select(
        TestSuite.category,
        func.count(TestCase.id).label("count")
    ).join(
        TestCase, TestSuite.id == TestCase.suite_id
    ).group_by(
        TestSuite.category
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        {"category": row.category, "count": row.count}
        for row in rows
    ]


@router.get("/recent-runs")
async def get_recent_runs(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get recent test runs
    """
    query = select(TestRun).order_by(TestRun.created_at.desc()).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return [
        {
            "id": run.id,
            "status": run.status.value,
            "trigger": run.trigger.value,
            "total_tests": run.total_tests,
            "passed_tests": run.passed_tests,
            "failed_tests": run.failed_tests,
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None
        }
        for run in runs
    ]
