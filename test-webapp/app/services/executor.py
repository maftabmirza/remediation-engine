"""
Test Executor Service - Executes pytest tests and collects results
"""
import subprocess
import json
import os
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import TestRun, TestCase, TestResult
from app.models.test_run import TestRunStatus
from app.models.test_result import TestResultStatus


class TestExecutor:
    """
    Executes pytest tests and manages test run lifecycle
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_test_run(
        self,
        run_id: int,
        suite_id: Optional[int] = None,
        test_case_ids: Optional[List[int]] = None
    ) -> None:
        """
        Execute a test run by running pytest tests

        Args:
            run_id: The test run ID
            suite_id: Optional test suite ID to run all tests in suite
            test_case_ids: Optional list of specific test case IDs to run
        """
        # Get test run
        run_query = select(TestRun).where(TestRun.id == run_id)
        run_result = await self.db.execute(run_query)
        test_run = run_result.scalar_one_or_none()

        if not test_run:
            raise ValueError(f"Test run {run_id} not found")

        try:
            # Update status to running
            test_run.status = TestRunStatus.RUNNING
            test_run.started_at = datetime.utcnow()
            await self.db.commit()

            # Get test cases to execute
            test_cases = await self._get_test_cases(suite_id, test_case_ids)

            if not test_cases:
                raise ValueError("No test cases found to execute")

            # Execute tests
            results = await self._run_pytest_tests(test_cases)

            # Process results
            await self._process_results(test_run, test_cases, results)

            # Update test run status
            test_run.status = TestRunStatus.COMPLETED
            test_run.completed_at = datetime.utcnow()
            await self.db.commit()

        except Exception as e:
            # Handle execution errors
            test_run.status = TestRunStatus.FAILED
            test_run.error_message = str(e)
            test_run.completed_at = datetime.utcnow()
            await self.db.commit()
            raise

    async def _get_test_cases(
        self,
        suite_id: Optional[int] = None,
        test_case_ids: Optional[List[int]] = None
    ) -> List[TestCase]:
        """
        Get test cases to execute based on suite_id or test_case_ids
        """
        query = select(TestCase).where(TestCase.enabled == True)

        if suite_id:
            query = query.where(TestCase.suite_id == suite_id)
        elif test_case_ids:
            query = query.where(TestCase.id.in_(test_case_ids))
        else:
            raise ValueError("Either suite_id or test_case_ids must be provided")

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _run_pytest_tests(self, test_cases: List[TestCase]) -> dict:
        """
        Execute pytest tests and collect results

        This is a simplified implementation. In production, you would:
        1. Run pytest with the custom reporter plugin
        2. Collect results via webhook or JSON output
        3. Handle timeouts and cancellations
        """
        # Build pytest command
        test_files = set()
        for test_case in test_cases:
            test_files.add(test_case.test_file_path)

        # Get the tests directory
        tests_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "tests")

        # Build full paths
        test_paths = [os.path.join(tests_dir, tf) for tf in test_files]

        # Run pytest with JSON output
        cmd = [
            "pytest",
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=/tmp/pytest_results.json",
        ] + test_paths

        try:
            # Execute pytest
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )

            # Parse JSON output if available
            results = {}
            json_file = "/tmp/pytest_results.json"
            if os.path.exists(json_file):
                with open(json_file, 'r') as f:
                    results = json.load(f)

            return results

        except subprocess.TimeoutExpired:
            raise Exception("Test execution timeout exceeded")
        except Exception as e:
            raise Exception(f"Failed to execute tests: {str(e)}")

    async def _process_results(
        self,
        test_run: TestRun,
        test_cases: List[TestCase],
        results: dict
    ) -> None:
        """
        Process pytest results and create TestResult records
        """
        total_tests = len(test_cases)
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0

        # Create a map of test cases by test_id for quick lookup
        test_case_map = {tc.test_id: tc for tc in test_cases}

        # Process results from pytest JSON report
        if "tests" in results:
            for test_data in results["tests"]:
                # Extract test ID from nodeid or name
                test_id = self._extract_test_id(test_data.get("nodeid", ""))

                if test_id not in test_case_map:
                    continue

                test_case = test_case_map[test_id]

                # Map outcome to status
                outcome = test_data.get("outcome", "failed")
                status_map = {
                    "passed": TestResultStatus.PASSED,
                    "failed": TestResultStatus.FAILED,
                    "skipped": TestResultStatus.SKIPPED,
                    "error": TestResultStatus.ERROR
                }
                status = status_map.get(outcome, TestResultStatus.ERROR)

                # Count results
                if status == TestResultStatus.PASSED:
                    passed_tests += 1
                elif status == TestResultStatus.FAILED:
                    failed_tests += 1
                elif status == TestResultStatus.SKIPPED:
                    skipped_tests += 1

                # Create test result
                test_result = TestResult(
                    run_id=test_run.id,
                    case_id=test_case.id,
                    status=status,
                    duration_seconds=test_data.get("duration", 0),
                    error_message=test_data.get("call", {}).get("longrepr") if outcome == "failed" else None,
                    stdout=test_data.get("call", {}).get("stdout"),
                    stderr=test_data.get("call", {}).get("stderr"),
                    executed_at=datetime.utcnow()
                )
                self.db.add(test_result)

        # Update test run counts
        test_run.total_tests = total_tests
        test_run.passed_tests = passed_tests
        test_run.failed_tests = failed_tests
        test_run.skipped_tests = skipped_tests

        await self.db.commit()

    def _extract_test_id(self, nodeid: str) -> str:
        """
        Extract test ID from pytest nodeid

        Example: tests/e2e/linux/test_linux.py::test_L01 -> L01
        """
        if "::" in nodeid:
            parts = nodeid.split("::")
            func_name = parts[-1]
            # Extract test ID from function name (e.g., test_L01 -> L01)
            if "_" in func_name:
                return func_name.split("_")[-1]
        return ""
