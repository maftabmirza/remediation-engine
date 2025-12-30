"""Reusable helper functions for Alembic migrations.

This module provides safe, idempotent operations for database migrations.
All functions check for existence before creating/dropping objects.

Usage:
    from migration_helpers import create_table_safe, add_column_safe, create_index_safe
    
    def upgrade():
        if create_table_safe('my_table',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(100))
        ):
            create_index_safe('idx_my_table_name', 'my_table', ['name'])
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from typing import List, Optional, Any


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database.
    
    Args:
        table_name: Name of the table to check
        
    Returns:
        True if table exists, False otherwise
    """
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table.
    
    Args:
        table_name: Name of the table
        column_name: Name of the column to check
        
    Returns:
        True if column exists, False otherwise
    """
    if not table_exists(table_name):
        return False
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(index_name: str) -> bool:
    """Check if an index exists in the database.
    
    Args:
        index_name: Name of the index to check
        
    Returns:
        True if index exists, False otherwise
    """
    conn = op.get_bind()
    result = conn.execute(sa.text(
        f"SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}'"
    ))
    return result.scalar() is not None


def constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Check if a constraint exists on a table.
    
    Args:
        table_name: Name of the table
        constraint_name: Name of the constraint to check
        
    Returns:
        True if constraint exists, False otherwise
    """
    conn = op.get_bind()
    result = conn.execute(sa.text(
        f"SELECT 1 FROM pg_constraint WHERE conname = '{constraint_name}'"
    ))
    return result.scalar() is not None


def extension_exists(extension_name: str) -> bool:
    """Check if a PostgreSQL extension is installed.
    
    Args:
        extension_name: Name of the extension to check
        
    Returns:
        True if extension is installed, False otherwise
    """
    conn = op.get_bind()
    result = conn.execute(sa.text(
        f"SELECT 1 FROM pg_extension WHERE extname = '{extension_name}'"
    ))
    return result.scalar() is not None


def extension_available(extension_name: str) -> bool:
    """Check if a PostgreSQL extension is available for installation.
    
    Args:
        extension_name: Name of the extension to check
        
    Returns:
        True if extension is available, False otherwise
    """
    conn = op.get_bind()
    result = conn.execute(sa.text(
        f"SELECT 1 FROM pg_available_extensions WHERE name = '{extension_name}'"
    ))
    return result.scalar() is not None


def create_table_safe(table_name: str, *args, **kwargs) -> bool:
    """Create a table only if it doesn't exist.
    
    Args:
        table_name: Name of the table to create
        *args: Column definitions and other table arguments
        **kwargs: Additional table options
        
    Returns:
        True if table was created, False if it already existed
    """
    if not table_exists(table_name):
        op.create_table(table_name, *args, **kwargs)
        return True
    return False


def add_column_safe(table_name: str, column: sa.Column) -> bool:
    """Add a column only if it doesn't exist.
    
    Args:
        table_name: Name of the table
        column: Column definition to add
        
    Returns:
        True if column was added, False if it already existed
    """
    if not column_exists(table_name, column.name):
        op.add_column(table_name, column)
        return True
    return False


def create_index_safe(index_name: str, table_name: str, columns: List[str], **kwargs) -> bool:
    """Create an index only if it doesn't exist.
    
    Args:
        index_name: Name of the index to create
        table_name: Name of the table
        columns: List of column names to index
        **kwargs: Additional index options (unique, postgresql_where, etc.)
        
    Returns:
        True if index was created, False if it already existed
    """
    if not index_exists(index_name):
        op.create_index(index_name, table_name, columns, **kwargs)
        return True
    return False


def drop_index_safe(index_name: str, table_name: Optional[str] = None, **kwargs) -> bool:
    """Drop an index only if it exists.
    
    Args:
        index_name: Name of the index to drop
        table_name: Optional table name
        **kwargs: Additional options
        
    Returns:
        True if index was dropped, False if it didn't exist
    """
    if index_exists(index_name):
        op.drop_index(index_name, table_name=table_name, **kwargs)
        return True
    return False


def create_foreign_key_safe(constraint_name: str, source_table: str, referent_table: str,
                            local_cols: List[str], remote_cols: List[str], **kwargs) -> bool:
    """Create a foreign key constraint only if it doesn't exist.
    
    Args:
        constraint_name: Name of the constraint
        source_table: Table containing the foreign key
        referent_table: Table being referenced
        local_cols: Columns in source table
        remote_cols: Columns in referent table
        **kwargs: Additional options (ondelete, onupdate, etc.)
        
    Returns:
        True if constraint was created, False if it already existed
    """
    if not constraint_exists(source_table, constraint_name):
        op.create_foreign_key(constraint_name, source_table, referent_table,
                             local_cols, remote_cols, **kwargs)
        return True
    return False


def create_unique_constraint_safe(constraint_name: str, table_name: str, columns: List[str], **kwargs) -> bool:
    """Create a unique constraint only if it doesn't exist.
    
    Args:
        constraint_name: Name of the constraint
        table_name: Name of the table
        columns: List of column names
        **kwargs: Additional options
        
    Returns:
        True if constraint was created, False if it already existed
    """
    if not constraint_exists(table_name, constraint_name):
        op.create_unique_constraint(constraint_name, table_name, columns, **kwargs)
        return True
    return False


def create_check_constraint_safe(constraint_name: str, table_name: str, condition: str, **kwargs) -> bool:
    """Create a check constraint only if it doesn't exist.
    
    Args:
        constraint_name: Name of the constraint
        table_name: Name of the table
        condition: SQL condition for the check
        **kwargs: Additional options
        
    Returns:
        True if constraint was created, False if it already existed
    """
    if not constraint_exists(table_name, constraint_name):
        op.create_check_constraint(constraint_name, table_name, condition, **kwargs)
        return True
    return False


def drop_constraint_safe(constraint_name: str, table_name: str, type_: str = 'foreignkey') -> bool:
    """Drop a constraint only if it exists.
    
    Args:
        constraint_name: Name of the constraint to drop
        table_name: Name of the table
        type_: Type of constraint ('foreignkey', 'unique', 'check')
        
    Returns:
        True if constraint was dropped, False if it didn't exist
    """
    if constraint_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_=type_)
        return True
    return False


def drop_table_safe(table_name: str) -> bool:
    """Drop a table only if it exists.
    
    Args:
        table_name: Name of the table to drop
        
    Returns:
        True if table was dropped, False if it didn't exist
    """
    if table_exists(table_name):
        op.drop_table(table_name)
        return True
    return False


def drop_column_safe(table_name: str, column_name: str) -> bool:
    """Drop a column only if it exists.
    
    Args:
        table_name: Name of the table
        column_name: Name of the column to drop
        
    Returns:
        True if column was dropped, False if it didn't exist
    """
    if column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)
        return True
    return False


def create_extension_safe(extension_name: str) -> bool:
    """Create a PostgreSQL extension only if it's available and not already installed.
    
    Args:
        extension_name: Name of the extension to create
        
    Returns:
        True if extension was created, False if already existed or not available
    """
    if extension_exists(extension_name):
        return False
    
    if extension_available(extension_name):
        op.execute(f'CREATE EXTENSION IF NOT EXISTS {extension_name}')
        return True
    else:
        print(f"Warning: Extension '{extension_name}' is not available")
        return False


def drop_extension_safe(extension_name: str, cascade: bool = False) -> bool:
    """Drop a PostgreSQL extension only if it exists.
    
    Args:
        extension_name: Name of the extension to drop
        cascade: Whether to use CASCADE option
        
    Returns:
        True if extension was dropped, False if it didn't exist
    """
    if extension_exists(extension_name):
        cascade_str = ' CASCADE' if cascade else ''
        op.execute(f'DROP EXTENSION IF EXISTS {extension_name}{cascade_str}')
        return True
    return False
