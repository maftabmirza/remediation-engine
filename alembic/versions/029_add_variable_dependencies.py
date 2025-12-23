"""add variable dependencies for chaining

Revision ID: 029_add_variable_dependencies
Revises: 028_add_query_history
Create Date: 2025-01-01 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '029_add_variable_dependencies'
down_revision = '028_add_query_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add depends_on column to dashboard_variables for variable chaining
    # Stores array of variable names this variable depends on
    op.add_column('dashboard_variables', sa.Column('depends_on', sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('dashboard_variables', 'depends_on')
