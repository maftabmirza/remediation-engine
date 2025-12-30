"""add variable dependencies for chaining

Revision ID: 029_add_variable_dependencies
Revises: 028_add_query_history
Create Date: 2025-01-01 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    create_table_safe, create_index_safe, add_column_safe,
    create_foreign_key_safe, create_unique_constraint_safe, create_check_constraint_safe,
    drop_index_safe, drop_constraint_safe, drop_column_safe, drop_table_safe
)

# revision identifiers, used by Alembic.
revision = '029_add_variable_dependencies'
down_revision = '028_add_query_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add depends_on column to dashboard_variables for variable chaining
    # Stores array of variable names this variable depends on
    add_column_safe('dashboard_variables', sa.Column('depends_on', sa.JSON, nullable=True))


def downgrade() -> None:
    drop_column_safe('dashboard_variables', 'depends_on')
