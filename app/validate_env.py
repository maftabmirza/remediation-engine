#!/usr/bin/env python3
"""
Environment Variable Validation Script

Validates required environment variables at application startup.
Fails fast with clear error messages if configuration is missing or invalid.

NO AUTO-GENERATION - All values must be explicitly set in .env file.
"""
import os
import sys
from typing import List, Tuple


class ValidationError(Exception):
    """Raised when environment validation fails."""
    pass


def validate_required_variable(name: str, description: str = "") -> str:
    """
    Validate that a required environment variable is set and non-empty.
    
    Args:
        name: Environment variable name
        description: Human-readable description for error messages
    
    Returns:
        The value of the environment variable
        
    Raises:
        ValidationError: If variable is missing or empty
    """
    value = os.getenv(name)
    
    if not value or value.strip() == "":
        desc = f" ({description})" if description else ""
        raise ValidationError(
            f"[!] Required environment variable '{name}' is not set{desc}\n"
            f"   Please set it in your .env file"
        )
    
    return value.strip()


def validate_encryption_key(key: str) -> None:
    """
    Validate that ENCRYPTION_KEY is a valid Fernet key.
    
    Args:
        key: The encryption key to validate
        
    Raises:
        ValidationError: If key is invalid
    """
    try:
        from cryptography.fernet import Fernet
        # This will raise an exception if key is invalid
        Fernet(key.encode())
    except Exception as e:
        raise ValidationError(
            f"[!] ENCRYPTION_KEY is not a valid Fernet key: {str(e)}\n"
            f"   Generate a valid key with:\n"
            f"   python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )


def validate_jwt_secret(secret: str) -> None:
    """
    Validate JWT secret is sufficiently strong.
    
    Args:
        secret: The JWT secret to validate
        
    Raises:
        ValidationError: If secret is too weak
    """
    if len(secret) < 32:
        raise ValidationError(
            f"[!] JWT_SECRET must be at least 32 characters long (current: {len(secret)})\n"
            f"   Generate a strong secret with:\n"
            f"   openssl rand -hex 32"
        )
    
    # Warn about default/weak secrets
    weak_secrets = [
        "your-super-secret-jwt-key-change-in-production",
        "change-me",
        "secret",
        "jwt-secret",
        "12345678901234567890123456789012"  # 32 chars but obviously weak
    ]
    
    if secret.lower() in weak_secrets:
        raise ValidationError(
            f"[!] JWT_SECRET appears to be a default/weak value\n"
            f"   Generate a strong secret with:\n"
            f"   openssl rand -hex 32"
        )


def validate_database_config() -> None:
    """
    Validate database configuration variables.
    
    Raises:
        ValidationError: If database configuration is invalid
    """
    required_db_vars = [
        ("POSTGRES_HOST", "Database hostname"),
        ("POSTGRES_PORT", "Database port"),
        ("POSTGRES_DB", "Database name"),
        ("POSTGRES_USER", "Database username"),
        ("POSTGRES_PASSWORD", "Database password"),
    ]
    
    for var_name, description in required_db_vars:
        validate_required_variable(var_name, description)
    
    # Validate port is numeric
    port = os.getenv("POSTGRES_PORT", "")
    try:
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            raise ValueError("Port out of range")
    except ValueError:
        raise ValidationError(
            f"[!] POSTGRES_PORT must be a valid port number (1-65535), got: '{port}'"
        )


def run_validation() -> None:
    """
    Run all environment variable validations.
    
    Exits with code 1 if any validation fails.
    """
    errors: List[str] = []
    
    print("=" * 60)
    print("[*] Validating Environment Configuration")
    print("=" * 60)
    print()
    
    # Track validation steps
    validations: List[Tuple[str, callable]] = [
        ("Database Configuration", validate_database_config),
        ("Encryption Key", lambda: validate_encryption_key(
            validate_required_variable("ENCRYPTION_KEY", "Used to encrypt credentials")
        )),
        ("JWT Secret", lambda: validate_jwt_secret(
            validate_required_variable("JWT_SECRET", "Used to sign authentication tokens")
        )),
    ]
    
    # Run each validation
    for name, validator in validations:
        try:
            print(f"Checking {name}...", end=" ")
            validator()
            print("[OK]")
        except ValidationError as e:
            print("[FAIL]")
            errors.append(str(e))
        except Exception as e:
            print("[FAIL]")
            errors.append(f"[!] Unexpected error validating {name}: {str(e)}")
    
    print()
    
    # Report results
    if errors:
        print("=" * 60)
        print("[!] VALIDATION FAILED")
        print("=" * 60)
        print()
        for error in errors:
            print(error)
            print()
        
        print("=" * 60)
        print("[*] Quick Fix:")
        print("=" * 60)
        print("1. Copy the example environment file:")
        print("   cp .env.example .env")
        print()
        print("2. Generate required secrets:")
        print("   # Encryption Key")
        print("   python3 -c \"from cryptography.fernet import Fernet; print(f'ENCRYPTION_KEY={Fernet.generate_key().decode()}')\"")
        print()
        print("   # JWT Secret")
        print("   openssl rand -hex 32")
        print()
        print("3. Edit .env and fill in all required values")
        print("4. Restart the application")
        print("=" * 60)
        print()
        
        sys.exit(1)
    else:
        print("=" * 60)
        print("[OK] All validations passed!")
        print("=" * 60)
        print()
        sys.exit(0)


if __name__ == "__main__":
    try:
        run_validation()
    except KeyboardInterrupt:
        print("\n[!] Validation interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Fatal error during validation: {e}")
        sys.exit(1)
