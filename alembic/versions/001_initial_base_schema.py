"""Initial base schema - baseline marker for existing databases.

This migration represents the baseline state of the database schema as of 2026-01-26.
It is designed to work in two scenarios:

1. EXISTING DATABASE: If tables already exist, this migration does nothing (it's a marker).
   Run: alembic stamp 001_initial_base

2. NEW DATABASE: Creates all tables from the SQL schema dump file.

Revision ID: 001_initial_base
Revises: 
Create Date: 2026-01-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from pathlib import Path
import re

# revision identifiers, used by Alembic.
revision = '001_initial_base'
down_revision = None
branch_labels = None
depends_on = None


def tables_exist(connection) -> bool:
    """Check if the main tables already exist."""
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()
    # Check for some key tables
    key_tables = ['users', 'alerts', 'runbooks', 'server_credentials']
    return any(t in existing_tables for t in key_tables)


def parse_schema_dump(schema_sql: str) -> list:
    """Parse SQL dump and extract executable statements."""
    statements = []
    current_stmt = []
    in_dollar_quote = False
    
    for line in schema_sql.split('\n'):
        stripped = line.strip()
        
        # Skip psql meta-commands
        if stripped.startswith('\\'):
            continue
        # Skip certain SET commands
        if stripped.startswith('SET ') and 'search_path' not in stripped.lower():
            continue
        # Skip SELECT commands
        if stripped.upper().startswith('SELECT '):
            continue
        # Skip OWNER TO statements
        if 'OWNER TO' in line:
            continue
        # Skip COMMENT ON EXTENSION
        if 'COMMENT ON EXTENSION' in line:
            continue
        # Skip GRANT/REVOKE
        if stripped.upper().startswith('GRANT ') or stripped.upper().startswith('REVOKE '):
            continue
        # Skip empty lines at statement start
        if not current_stmt and not stripped:
            continue
            
        current_stmt.append(line)
        
        # Track dollar-quoted strings (for functions)
        if '$$' in line:
            in_dollar_quote = not in_dollar_quote
        
        # Statement ends with semicolon (outside dollar quotes)
        if stripped.endswith(';') and not in_dollar_quote:
            stmt = '\n'.join(current_stmt).strip()
            if stmt and stmt != ';':
                statements.append(stmt)
            current_stmt = []
    
    return statements


def upgrade() -> None:
    """
    Create database schema for new databases, or skip for existing ones.
    """
    # Get connection to check if tables exist
    connection = op.get_bind()
    
    if tables_exist(connection):
        print("INFO: Tables already exist. This is a baseline migration - no changes needed.")
        print("      If this is an existing database, this migration marks the current state.")
        return
    
    print("INFO: Creating fresh database schema...")
    
    # Enable required extensions first
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "vector"'))
    
    # Read and execute schema dump
    schema_file = Path(__file__).parent.parent.parent / 'database_schema_20260126.sql'
    
    if not schema_file.exists():
        raise RuntimeError(
            f"Schema file not found: {schema_file}\n"
            "For new databases, this file is required. Generate it with:\n"
            "  docker exec aiops-postgres pg_dump -U aiops -d aiops --schema-only > database_schema_20260126.sql"
        )
    
    schema_sql = schema_file.read_text(encoding='utf-8')
    statements = parse_schema_dump(schema_sql)
    
    success_count = 0
    skip_count = 0
    
    for stmt in statements:
        try:
            op.execute(sa.text(stmt))
            success_count += 1
        except Exception as e:
            error_msg = str(e).lower()
            # These errors are expected/safe to ignore
            if 'already exists' in error_msg or 'does not exist' in error_msg:
                skip_count += 1
            else:
                print(f"WARNING: Statement failed: {str(e)[:200]}")
                skip_count += 1
    
    print(f"INFO: Schema creation complete. {success_count} statements executed, {skip_count} skipped.")


def downgrade() -> None:
    """
    Drop all tables.
    
    WARNING: This will delete all data! Use with extreme caution.
    """
    op.execute(sa.text("""
        DO $$ 
        DECLARE
            r RECORD;
        BEGIN
            -- Disable triggers
            SET session_replication_role = 'replica';
            
            -- Drop all tables in public schema
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'alembic_version') LOOP
                EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
            
            -- Drop custom enum types
            FOR r IN (SELECT typname FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid 
                      WHERE n.nspname = 'public' AND t.typtype = 'e') LOOP
                EXECUTE 'DROP TYPE IF EXISTS public.' || quote_ident(r.typname) || ' CASCADE';
            END LOOP;
            
            -- Re-enable triggers
            SET session_replication_role = 'origin';
        END $$;
    """))
