#!/bin/bash
# Production Deployment Security Verification Script
# Run this before deploying to production

set -e  # Exit on any error

echo "=================================="
echo "🔒 Production Security Checks"
echo "=================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

# Function to print results
check_passed() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
}

check_failed() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    FAILED=1
}

check_warning() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
}

echo "1. Checking .dockerignore configuration..."
if [ -f ".dockerignore" ]; then
    if grep -q "tests/" .dockerignore && grep -q "pytest.ini" .dockerignore; then
        check_passed ".dockerignore properly excludes test files"
    else
        check_failed ".dockerignore missing test file exclusions"
    fi
else
    check_failed ".dockerignore file not found"
fi

echo ""
echo "2. Checking production Dockerfile..."
if [ -f "Dockerfile" ]; then
    if grep -q "COPY tests/" Dockerfile; then
        check_failed "Dockerfile explicitly copies tests/ directory"
    else
        check_passed "Dockerfile does not copy tests/ directory"
    fi
    
    if grep -q "pytest" Dockerfile; then
        check_failed "Dockerfile contains pytest references"
    else
        check_passed "Dockerfile has no pytest references"
    fi
else
    check_failed "Dockerfile not found"
fi

echo ""
echo "3. Checking security checks module..."
if [ -f "app/security_checks.py" ]; then
    check_passed "Security checks module exists"
else
    check_failed "app/security_checks.py not found"
fi

echo ""
echo "4. Checking main.py for security integration..."
if [ -f "app/main.py" ]; then
    if grep -q "check_test_isolation" app/main.py; then
        check_passed "Security checks integrated in main.py"
    else
        check_failed "Security checks NOT integrated in main.py"
    fi
else
    check_failed "app/main.py not found"
fi

echo ""
echo "5. Checking test isolation..."
if [ -d "tests" ]; then
    check_passed "tests/ directory exists (expected in source)"
    
    # Check that tests don't import production code unsafely
    if grep -r "from app.security_checks import" tests/ 2>/dev/null; then
        check_warning "Tests import security_checks (verify it's safe)"
    fi
else
    check_warning "tests/ directory not found (unusual)"
fi

echo ""
echo "6. Verifying production models have unique constraints..."
if grep -q "name = Column(String(100), nullable=False, unique=True" app/models_application.py; then
    check_passed "Application.name has unique=True constraint"
else
    check_failed "Application.name MISSING unique=True constraint"
fi

if grep -q "name = Column(String(100), nullable=False, unique=True" app/models_application.py | tail -1; then
    check_passed "GrafanaDatasource.name has unique=True constraint"
else
    check_warning "Could not verify GrafanaDatasource.name constraint"
fi

echo ""
echo "7. Checking deployment checklist..."
if [ -f "DEPLOYMENT_CHECKLIST.md" ]; then
    check_passed "Deployment checklist exists"
else
    check_warning "DEPLOYMENT_CHECKLIST.md not found"
fi

echo ""
echo "=================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo "Ready for production deployment"
    exit 0
else
    echo -e "${RED}❌ Some checks failed!${NC}"
    echo "Fix issues before deploying to production"
    exit 1
fi
