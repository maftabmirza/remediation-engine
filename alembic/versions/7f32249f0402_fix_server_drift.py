"""fix_server_drift

Revision ID: 7f32249f0402
Revises: 65c6b0133982
Create Date: 2026-01-08 02:15:58.388779

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f32249f0402'
down_revision = '65c6b0133982'
branch_labels = None
depends_on = None

# Helpers
def drop_index_if_exists(index_name, table_name, **kw):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = inspector.get_indexes(table_name)
    if any(i['name'] == index_name for i in indexes):
        op.drop_index(index_name, table_name=table_name, **kw)
    else:
        print(f"Skipping drop: Index {index_name} on {table_name} not found")

def create_index_if_not_exists(index_name, table_name, columns, **kw):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = inspector.get_indexes(table_name)
    if any(i['name'] == index_name for i in indexes):
        print(f"Skipping create: Index {index_name} on {table_name} already exists")
        return
    op.create_index(index_name, table_name, columns, **kw)

def drop_constraint_if_exists(constraint_name, table_name, type_=None, **kw):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if constraint_name is None:
        return
    exists = False
    if type_ == 'unique' or type_ is None:
        try:
            cons = inspector.get_unique_constraints(table_name)
            if any(c['name'] == constraint_name for c in cons):
                exists = True
        except: pass
    if not exists and (type_ == 'foreignkey' or type_ is None):
        try:
            cons = inspector.get_foreign_keys(table_name)
            if any(c['name'] == constraint_name for c in cons):
                exists = True
        except: pass
    if exists:
        op.drop_constraint(constraint_name, table_name=table_name, type_=type_, **kw)
    else:
        print(f"Skipping drop: Constraint {constraint_name} on {table_name} not found")

def drop_column_if_exists(table_name, column_name, **kw):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns(table_name)
    if any(c['name'] == column_name for c in columns):
        op.drop_column(table_name, column_name, **kw)
    else:
        print(f"Skipping drop: Column {column_name} on {table_name} not found")

def upgrade() -> None:
    # Operations from server check
    drop_index_if_exists('idx_alert_correlations_alert_id', 'alert_correlations')
    drop_constraint_if_exists('alert_correlations_alert_id_fkey', 'alert_correlations', type_='foreignkey')
    drop_column_if_exists('alert_correlations', 'alert_id')
    
    create_index_if_not_exists(op.f('ix_alert_correlations_created_at'), 'alert_correlations', ['created_at'], unique=False)
    create_index_if_not_exists(op.f('ix_alerts_correlation_id'), 'alerts', ['correlation_id'], unique=False)


def downgrade() -> None:
    pass
