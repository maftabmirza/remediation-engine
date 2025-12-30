#!/usr/bin/env python3
"""
Test runner script for the Remediation Engine pytest test suite.

This script provides convenient shortcuts for running different test categories
and configurations.

Usage Examples:
    # Run all tests
    python run_tests.py

    # Run only unit tests
    python run_tests.py --unit

    # Run integration tests
    python run_tests.py --integration

    # Run with coverage report
    python run_tests.py --coverage

    # Run specific test file
    python run_tests.py tests/unit/test_models/test_alert_model.py

    # Run fast tests only (exclude slow tests)
    python run_tests.py --fast

    # Run in parallel
    python run_tests.py --parallel
"""
import argparse
import subprocess
import sys
import os


def run_pytest(args_list):
    """Run pytest with the given arguments."""
    cmd = ["pytest"] + args_list
    print(f"Running: {' '.join(cmd)}")
    print("=" * 70)
    
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Test runner for Remediation Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Test category selection
    category_group = parser.add_mutually_exclusive_group()
    category_group.add_argument(
        "--unit", "-u",
        action="store_true",
        help="Run only unit tests"
    )
    category_group.add_argument(
        "--integration", "-i",
        action="store_true",
        help="Run only integration tests"
    )
    category_group.add_argument(
        "--e2e",
        action="store_true",
        help="Run only end-to-end tests"
    )
    category_group.add_argument(
        "--api",
        action="store_true",
        help="Run only API tests"
    )
    category_group.add_argument(
        "--security",
        action="store_true",
        help="Run only security tests"
    )
    category_group.add_argument(
        "--performance",
        action="store_true",
        help="Run only performance tests"
    )
    
    # Test execution options
    parser.add_argument(
        "--fast", "-f",
        action="store_true",
        help="Run fast tests only (exclude slow tests)"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run with coverage reporting"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel (auto-detect CPU count)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--failfast", "-x",
        action="store_true",
        help="Stop on first failure"
    )
    parser.add_argument(
        "--pdb",
        action="store_true",
        help="Drop into debugger on failure"
    )
    parser.add_argument(
        "--lf",
        action="store_true",
        help="Run last failed tests only"
    )
    parser.add_argument(
        "--markers",
        action="store_true",
        help="Show available test markers"
    )
    
    # Positional argument for specific test path
    parser.add_argument(
        "testpath",
        nargs="?",
        help="Specific test file or directory to run"
    )
    
    args = parser.parse_args()
    
    # Build pytest arguments
    pytest_args = []
    
    # Add test category markers
    if args.unit:
        pytest_args.extend(["-m", "unit"])
    elif args.integration:
        pytest_args.extend(["-m", "integration"])
    elif args.e2e:
        pytest_args.extend(["-m", "e2e"])
    elif args.api:
        pytest_args.extend(["-m", "api"])
    elif args.security:
        pytest_args.extend(["-m", "security"])
    elif args.performance:
        pytest_args.extend(["-m", "performance"])
    
    # Add fast filter
    if args.fast:
        pytest_args.extend(["-m", "not slow"])
    
    # Add parallel execution
    if args.parallel:
        pytest_args.extend(["-n", "auto"])
    
    # Add verbose
    if args.verbose:
        pytest_args.append("-vv")
    
    # Add failfast
    if args.failfast:
        pytest_args.append("-x")
    
    # Add pdb
    if args.pdb:
        pytest_args.append("--pdb")
    
    # Add last failed
    if args.lf:
        pytest_args.append("--lf")
    
    # Add coverage
    if args.coverage:
        pytest_args.extend([
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html"
        ])
    
    # Show markers
    if args.markers:
        pytest_args.append("--markers")
    
    # Add specific test path if provided
    if args.testpath:
        pytest_args.append(args.testpath)
    
    # Run pytest
    return_code = run_pytest(pytest_args)
    
    # Print coverage report location if coverage was run
    if args.coverage and return_code == 0:
        print("\n" + "=" * 70)
        print("Coverage report generated:")
        print("  HTML: file:///" + os.path.abspath("htmlcov/index.html"))
        print("=" * 70)
    
    return return_code


if __name__ == "__main__":
    sys.exit(main())
