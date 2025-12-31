#!/usr/bin/env python3
"""
Database Initialization Script

This script:
1. Creates all database tables
2. Seeds initial data (test suites and test cases)
3. Sets up default configuration

Usage:
    python scripts/init_db.py
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal, engine, Base
from app.models import TestSuite, TestCase
from app.models.test_case import TestPriority


async def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables created successfully")


async def seed_test_suites():
    """Create default test suites"""
    print("\nSeeding test suites...")

    async with AsyncSessionLocal() as db:
        # Check if suites already exist
        result = await db.execute(select(TestSuite))
        existing_suites = result.scalars().all()

        if existing_suites:
            print(f"  Found {len(existing_suites)} existing suites, skipping...")
            return

        # Create test suites
        suites = [
            TestSuite(
                name="Linux Remediation Tests",
                description="E2E tests for Linux system remediation scenarios",
                category="linux",
                enabled=True
            ),
            TestSuite(
                name="Safety Mechanism Tests",
                description="Tests for safety limits and circuit breakers",
                category="safety",
                enabled=True
            ),
            TestSuite(
                name="Approval Workflow Tests",
                description="Tests for approval and authorization workflows",
                category="approval",
                enabled=True
            ),
            TestSuite(
                name="Windows Remediation Tests",
                description="E2E tests for Windows system remediation",
                category="windows",
                enabled=False  # Disabled by default
            )
        ]

        for suite in suites:
            db.add(suite)
            print(f"  + {suite.name}")

        await db.commit()
        print(f"✓ Created {len(suites)} test suites")


async def seed_test_cases():
    """Create default test cases"""
    print("\nSeeding test cases...")

    async with AsyncSessionLocal() as db:
        # Check if test cases already exist
        result = await db.execute(select(TestCase))
        existing_cases = result.scalars().all()

        if existing_cases:
            print(f"  Found {len(existing_cases)} existing test cases, skipping...")
            return

        # Get test suites
        result = await db.execute(select(TestSuite))
        suites = {suite.category: suite for suite in result.scalars().all()}

        if not suites:
            print("  ✗ No test suites found. Run seed_test_suites first.")
            return

        # Linux test cases
        if "linux" in suites:
            linux_suite = suites["linux"]
            linux_cases = [
                TestCase(
                    test_id="L01",
                    suite_id=linux_suite.id,
                    name="High CPU Usage Remediation",
                    description="Test automated remediation for high CPU usage",
                    test_file_path="e2e/linux/test_linux_remediation.py",
                    test_function="test_L01_high_cpu_remediation",
                    priority=TestPriority.HIGH,
                    timeout_seconds=300,
                    enabled=True,
                    tags=["linux", "cpu", "performance"]
                ),
                TestCase(
                    test_id="L02",
                    suite_id=linux_suite.id,
                    name="High Memory Usage Remediation",
                    description="Test automated remediation for high memory usage",
                    test_file_path="e2e/linux/test_linux_remediation.py",
                    test_function="test_L02_high_memory_remediation",
                    priority=TestPriority.HIGH,
                    timeout_seconds=300,
                    enabled=True,
                    tags=["linux", "memory", "performance"]
                ),
                TestCase(
                    test_id="L03",
                    suite_id=linux_suite.id,
                    name="Disk Space Cleanup",
                    description="Test automated disk space cleanup",
                    test_file_path="e2e/linux/test_linux_remediation.py",
                    test_function="test_L03_disk_space_cleanup",
                    priority=TestPriority.CRITICAL,
                    timeout_seconds=300,
                    enabled=True,
                    tags=["linux", "disk", "cleanup"]
                )
            ]

            for case in linux_cases:
                db.add(case)
                print(f"  + {case.test_id}: {case.name}")

        # Safety test cases
        if "safety" in suites:
            safety_suite = suites["safety"]
            safety_cases = [
                TestCase(
                    test_id="S01",
                    suite_id=safety_suite.id,
                    name="Execution Rate Limiting",
                    description="Test that rate limiting prevents excessive executions",
                    test_file_path="e2e/safety/test_safety_limits.py",
                    test_function="test_S01_execution_rate_limit",
                    priority=TestPriority.CRITICAL,
                    timeout_seconds=180,
                    enabled=True,
                    tags=["safety", "rate-limit", "circuit-breaker"]
                ),
                TestCase(
                    test_id="S02",
                    suite_id=safety_suite.id,
                    name="Concurrent Execution Limit",
                    description="Test concurrent execution limits",
                    test_file_path="e2e/safety/test_safety_limits.py",
                    test_function="test_S02_concurrent_execution_limit",
                    priority=TestPriority.CRITICAL,
                    timeout_seconds=180,
                    enabled=True,
                    tags=["safety", "concurrency", "queue"]
                ),
                TestCase(
                    test_id="S03",
                    suite_id=safety_suite.id,
                    name="Dangerous Operation Prevention",
                    description="Test that dangerous operations are blocked",
                    test_file_path="e2e/safety/test_safety_limits.py",
                    test_function="test_S03_dangerous_operation_prevention",
                    priority=TestPriority.CRITICAL,
                    timeout_seconds=180,
                    enabled=True,
                    tags=["safety", "validation", "prevention"]
                )
            ]

            for case in safety_cases:
                db.add(case)
                print(f"  + {case.test_id}: {case.name}")

        await db.commit()

        # Count total cases
        result = await db.execute(select(TestCase))
        total = len(result.scalars().all())
        print(f"✓ Created {total} test cases")


async def main():
    """Main initialization function"""
    print("=" * 80)
    print("Test Management Database Initialization")
    print("=" * 80)

    try:
        # Create tables
        await create_tables()

        # Seed data
        await seed_test_suites()
        await seed_test_cases()

        print("\n" + "=" * 80)
        print("✓ Database initialization completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
