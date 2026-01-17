"""
Production Security Checks

Validates that test-specific code and configurations are not present in production.
Run this during application startup in production environments.
"""
import os
import sys
from pathlib import Path


class ProductionSecurityError(Exception):
    """Raised when test code is detected in production environment."""
    pass


def check_test_isolation():
    """
    Verify that test code is not present in production.
    
    Raises:
        ProductionSecurityError: If test artifacts are found in production environment
    """
    # Only run in production (when TESTING is not set or false)
    if os.getenv("TESTING", "false").lower() == "true":
        return  # Skip checks in test environment
    
    errors = []
    
    # 1. Check that tests directory doesn't exist
    app_dir = Path(__file__).parent.parent
    tests_dir = app_dir / "tests"
    if tests_dir.exists():
        errors.append(f"❌ CRITICAL: Test directory found in production: {tests_dir}")
    
    # 2. Check that pytest.ini doesn't exist
    pytest_ini = app_dir / "pytest.ini"
    if pytest_ini.exists():
        errors.append(f"❌ CRITICAL: pytest.ini found in production: {pytest_ini}")
    
    # 3. Verify testing mode is disabled
    testing_mode = os.getenv("TESTING", "false")
    if testing_mode.lower() == "true":
        errors.append("❌ CRITICAL: TESTING environment variable is set to 'true' in production")
    
    # 4. Check for test-specific environment variables
    test_env_vars = ["POSTGRES_DB", "POSTGRES_HOST"]
    for var in test_env_vars:
        value = os.getenv(var, "")
        if "test" in value.lower():
            errors.append(f"❌ WARNING: Environment variable {var}='{value}' contains 'test'")
    
    # 5. Verify rate limiter is enabled
    from app.config import get_settings
    settings = get_settings()
    if settings.testing:
        errors.append("❌ CRITICAL: settings.testing is True in production")
    
    if errors:
        error_msg = "\n".join([
            "=" * 80,
            "🚨 PRODUCTION SECURITY CHECK FAILED 🚨",
            "=" * 80,
            "",
            "Test code or configuration detected in production environment:",
            "",
            *errors,
            "",
            "=" * 80,
            "ACTION REQUIRED: Fix deployment configuration immediately!",
            "=" * 80
        ])
        raise ProductionSecurityError(error_msg)
    
    print("✅ Production security checks passed: No test code detected")


def check_unique_constraints():
    """
    Verify that database models have proper unique constraints.
    
    This ensures data integrity constraints weren't accidentally removed.
    """
    if os.getenv("TESTING", "false").lower() == "true":
        return  # Skip in test environment
    
    try:
        from app.models_application import Application, GrafanaDatasource
        
        # Check Application.name has unique constraint
        app_name_col = Application.__table__.columns.get('name')
        if app_name_col is not None and not app_name_col.unique:
            raise ProductionSecurityError(
                "❌ CRITICAL: Application.name missing unique constraint in production"
            )
        
        # Check GrafanaDatasource.name has unique constraint  
        ds_name_col = GrafanaDatasource.__table__.columns.get('name')
        if ds_name_col is not None and not ds_name_col.unique:
            raise ProductionSecurityError(
                "❌ CRITICAL: GrafanaDatasource.name missing unique constraint in production"
            )
        
        print("✅ Database unique constraints verified")
        
    except ImportError:
        # Models might not be loaded yet during startup
        pass


if __name__ == "__main__":
    """Run security checks when executed directly."""
    try:
        check_test_isolation()
        check_unique_constraints()
        print("\n✅ All production security checks passed!\n")
        sys.exit(0)
    except ProductionSecurityError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
