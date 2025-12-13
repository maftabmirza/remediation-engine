"""add_runbook_step_outputs

Revision ID: c3031e42d864
Revises: 004_add_scheduler
Create Date: 2025-12-09 23:56:49.492011

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'c3031e42d864'
down_revision = '004_add_scheduler'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('runbook_steps')]
    
    if 'output_variable' not in columns:
        op.add_column('runbook_steps', sa.Column('output_variable', sa.String(length=100), nullable=True))
    
    if 'output_extract_pattern' not in columns:
        op.add_column('runbook_steps', sa.Column('output_extract_pattern', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('runbook_steps', 'output_extract_pattern')
    op.drop_column('runbook_steps', 'output_variable')
