"""Validate Alembic migration integrity.

This script checks for common migration issues:
- Broken revision chains
- Duplicate revision IDs
- Multiple heads
- Missing dependencies

Run before deployment to ensure migration integrity.

Usage:
    python alembic/validate_migrations.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic.config import Config
from alembic.script import ScriptDirectory


def validate_migrations():
    """Validate migration chain and detect issues.
    
    Returns:
        bool: True if all validations pass, False otherwise
    """
    print("=" * 60)
    print("Alembic Migration Validation")
    print("=" * 60)
    
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    
    issues = []
    warnings = []
    
    # Get all revisions
    revisions = list(script.walk_revisions())
    print(f"\n[*] Total migrations: {len(revisions)}")
    
    # Check 1: Broken chains
    print("\n[*] Checking revision chain...")
    for revision in revisions:
        if revision.down_revision:
            try:
                script.get_revision(revision.down_revision)
            except Exception as e:
                issues.append(
                    f"Broken chain: {revision.revision} -> {revision.down_revision}\n"
                    f"  Error: {str(e)}"
                )
    
    if not issues:
        print("   [OK] All revision chains are valid")
    
    # Check 2: Duplicate revisions
    print("\n[*] Checking for duplicate revision IDs...")
    revision_ids = [r.revision for r in revisions]
    duplicates = set([x for x in revision_ids if revision_ids.count(x) > 1])
    if duplicates:
        issues.append(f"Duplicate revision IDs found: {duplicates}")
    else:
        print("   [OK] No duplicate revision IDs")
    
    # Check 3: Multiple heads
    print("\n[*] Checking for multiple heads...")
    heads = script.get_heads()
    if len(heads) > 1:
        issues.append(f"Multiple heads found: {heads}\n  This indicates branching in migration history")
    else:
        print(f"   [OK] Single head: {heads[0]}")
    
    # Check 4: Down revision consistency
    print("\n[*] Checking down_revision consistency...")
    for revision in revisions:
        if revision.down_revision:
            # Check if down_revision is in the list of revisions
            down_rev_exists = any(r.revision == revision.down_revision for r in revisions)
            if not down_rev_exists:
                issues.append(
                    f"Missing down_revision: {revision.revision} references "
                    f"{revision.down_revision} which doesn't exist"
                )
    
    if not any("Missing down_revision" in issue for issue in issues):
        print("   [OK] All down_revision references are valid")
    
    # Check 5: Migration file naming
    print("\n[*] Checking migration file naming...")
    versions_dir = Path("alembic/versions")
    if versions_dir.exists():
        migration_files = list(versions_dir.glob("*.py"))
        migration_files = [f for f in migration_files if f.name != "__pycache__" and f.name != "__init__.py"]
        
        if len(migration_files) != len(revisions):
            warnings.append(
                f"File count mismatch: {len(migration_files)} files vs {len(revisions)} revisions"
            )
        else:
            print(f"   [OK] {len(migration_files)} migration files found")
    
    # Check 6: Check for common issues in migration content
    print("\n[*] Checking migration content...")
    idempotent_count = 0
    non_idempotent_count = 0
    
    for revision in revisions:
        if revision.module:
            source = revision.module.__doc__ or ""
            # Check if migration uses table existence checks
            if "Inspector" in str(revision.module.__dict__.get('upgrade', '').__code__.co_names):
                idempotent_count += 1
            else:
                non_idempotent_count += 1
    
    if non_idempotent_count > 0:
        warnings.append(
            f"{non_idempotent_count} migrations may lack idempotency checks\n"
            f"  {idempotent_count} migrations have existence checks"
        )
    else:
        print(f"   [OK] All migrations appear to have idempotency checks")
    
    # Print results
    print("\n" + "=" * 60)
    print("Validation Results")
    print("=" * 60)
    
    if warnings:
        print("\n[WARNING] Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if issues:
        print("\n[ERROR] Issues Found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n[FAIL] Migration validation FAILED")
        return False
    else:
        if warnings:
            print("\n[PASS] Migration validation PASSED (with warnings)")
        else:
            print("\n[PASS] Migration validation PASSED")
        return True


def print_migration_summary():
    """Print a summary of all migrations."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    
    revisions = list(script.walk_revisions("base", "head"))
    revisions.reverse()  # Show in chronological order
    
    for i, revision in enumerate(revisions, 1):
        print(f"\n{i}. {revision.revision[:12]} - {revision.doc}")
        if revision.down_revision:
            print(f"   From: {revision.down_revision[:12]}")


if __name__ == "__main__":
    try:
        success = validate_migrations()
        
        # Optionally print summary
        if "--summary" in sys.argv:
            print_migration_summary()
        
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Validation script error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

