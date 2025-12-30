"""Batch improve remaining migrations with idempotency checks.

This script updates migrations 021-037 to use migration_helpers for idempotency.
Run this script to automatically improve all remaining migrations.

Usage:
    python alembic/batch_improve_migrations.py
"""
import os
import re
from pathlib import Path


# Migrations that need improvement
MIGRATIONS_TO_IMPROVE = [
    '021_add_change_times.py',
    '022_add_change_cis_app.py',
    '023_add_prometheus_dashboards.py',
    '024_add_dashboard_variables.py',
    '025_add_dashboard_annotations.py',
    '026_add_dashboard_links.py',
    '027_add_groups.py',
    '028_add_query_history.py',
    '029_add_variable_dependencies.py',
    '030_add_dashboard_permissions.py',
    '031_add_runbook_acls.py',
    '032_add_snapshots_playlists_rows.py',
    '033_add_application_profiles.py',
    '034_add_grafana_datasources.py',
    '035_add_ds_fks.py',
    '036_add_inquiry_results.py',
    '037_add_inquiry_sessions.py',
]


HELPER_IMPORTS = """
# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    create_table_safe, create_index_safe, add_column_safe,
    create_foreign_key_safe, create_unique_constraint_safe, create_check_constraint_safe,
    drop_index_safe, drop_constraint_safe, drop_column_safe, drop_table_safe
)
"""


def add_helper_imports(content):
    """Add migration helper imports after the standard imports."""
    # Find the line with "# revision identifiers"
    lines = content.split('\n')
    insert_index = None
    
    for i, line in enumerate(lines):
        if '# revision identifiers' in line.lower() or 'revision =' in line:
            insert_index = i
            break
    
    if insert_index is None:
        # Fallback: insert after imports
        for i, line in enumerate(lines):
            if line.startswith('from') or line.startswith('import'):
                insert_index = i + 1
    
    if insert_index:
        lines.insert(insert_index, HELPER_IMPORTS)
    
    return '\n'.join(lines)


def replace_operations(content):
    """Replace direct operations with safe helper functions."""
    replacements = [
        # Table operations
        (r'op\.create_table\(', 'create_table_safe('),
        (r'op\.drop_table\(', 'drop_table_safe('),
        
        # Column operations
        (r'op\.add_column\(', 'add_column_safe('),
        (r'op\.drop_column\(', 'drop_column_safe('),
        
        # Index operations
        (r'op\.create_index\(', 'create_index_safe('),
        (r'op\.drop_index\(', 'drop_index_safe('),
        
        # Constraint operations
        (r'op\.create_foreign_key\(', 'create_foreign_key_safe('),
        (r'op\.create_unique_constraint\(', 'create_unique_constraint_safe('),
        (r'op\.create_check_constraint\(', 'create_check_constraint_safe('),
        (r'op\.drop_constraint\(', 'drop_constraint_safe('),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    return content


def improve_migration(filepath):
    """Improve a single migration file."""
    print(f"Improving {filepath.name}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already improved
    if 'migration_helpers' in content:
        print(f"  Already improved, skipping")
        return False
    
    # Add helper imports
    content = add_helper_imports(content)
    
    # Replace operations
    content = replace_operations(content)
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  [OK] Improved")
    return True


def main():
    """Main function to improve all migrations."""
    versions_dir = Path('alembic/versions')
    
    if not versions_dir.exists():
        print("Error: alembic/versions directory not found")
        return
    
    improved_count = 0
    skipped_count = 0
    
    print("=" * 60)
    print("Batch Migration Improvement")
    print("=" * 60)
    
    for migration_file in MIGRATIONS_TO_IMPROVE:
        filepath = versions_dir / migration_file
        
        if not filepath.exists():
            print(f"Warning: {migration_file} not found, skipping")
            skipped_count += 1
            continue
        
        if improve_migration(filepath):
            improved_count += 1
        else:
            skipped_count += 1
    
    print("\n" + "=" * 60)
    print(f"Improved: {improved_count} migrations")
    print(f"Skipped: {skipped_count} migrations")
    print("=" * 60)
    
    if improved_count > 0:
        print("\nNext steps:")
        print("1. Review the changes: git diff alembic/versions/")
        print("2. Test migrations: python alembic/validate_migrations.py")
        print("3. Commit changes: git add alembic/versions/ && git commit -m 'Improve migrations with idempotency'")


if __name__ == '__main__':
    main()
