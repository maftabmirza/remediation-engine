#!/bin/bash
#
# Test Execution Script
#
# This script runs pytest tests and reports results to the test-webapp API
#
# Usage:
#   ./scripts/run_tests.sh [options]
#
# Options:
#   --run-id <id>       Test run ID (required for webhook reporting)
#   --suite <name>      Run specific test suite (linux, safety, approval, windows)
#   --test-id <id>      Run specific test by ID (e.g., L01, S01)
#   --no-report         Don't send results to webhook
#   --verbose           Verbose output
#

set -e  # Exit on error

# Default values
RUN_ID=""
SUITE=""
TEST_ID=""
WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:8001/webhook/pytest-results}"
REPORT=true
VERBOSE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --run-id)
            RUN_ID="$2"
            shift 2
            ;;
        --suite)
            SUITE="$2"
            shift 2
            ;;
        --test-id)
            TEST_ID="$2"
            shift 2
            ;;
        --webhook-url)
            WEBHOOK_URL="$2"
            shift 2
            ;;
        --no-report)
            REPORT=false
            shift
            ;;
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --run-id <id>       Test run ID (required for webhook reporting)"
            echo "  --suite <name>      Run specific test suite (linux, safety, approval, windows)"
            echo "  --test-id <id>      Run specific test by ID (e.g., L01, S01)"
            echo "  --webhook-url <url> Webhook URL for reporting"
            echo "  --no-report         Don't send results to webhook"
            echo "  --verbose, -v       Verbose output"
            echo "  --help, -h          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

echo "=========================================="
echo "Test Execution"
echo "=========================================="
echo "Project: $PROJECT_DIR"
echo "Run ID: ${RUN_ID:-<not set>}"
echo "Suite: ${SUITE:-<all>}"
echo "Test ID: ${TEST_ID:-<all>}"
echo "Webhook: $WEBHOOK_URL"
echo "Report: $REPORT"
echo "=========================================="
echo ""

# Build pytest command
PYTEST_CMD="pytest"

# Add verbosity
if [[ -n "$VERBOSE" ]]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add test selection
if [[ -n "$TEST_ID" ]]; then
    # Run specific test by marker
    PYTEST_CMD="$PYTEST_CMD -m $TEST_ID"
elif [[ -n "$SUITE" ]]; then
    # Run specific suite
    PYTEST_CMD="$PYTEST_CMD tests/e2e/${SUITE}/"
else
    # Run all tests
    PYTEST_CMD="$PYTEST_CMD tests/e2e/"
fi

# Add webhook reporting if run ID is provided and reporting is enabled
if [[ -n "$RUN_ID" ]] && [[ "$REPORT" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD --run-id=$RUN_ID --webhook-url=$WEBHOOK_URL"
fi

# Add output options
PYTEST_CMD="$PYTEST_CMD --tb=short --color=yes"

# Print command
echo "Running: $PYTEST_CMD"
echo ""

# Execute tests
$PYTEST_CMD

EXIT_CODE=$?

echo ""
echo "=========================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "✓ Tests completed successfully"
else
    echo "✗ Tests failed with exit code: $EXIT_CODE"
fi
echo "=========================================="

exit $EXIT_CODE
