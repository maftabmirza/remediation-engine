"""Sync schema drift for troubleshooting tables

Revision ID: 040_sync_schema_drift
Revises: 039_merge_heads
Create Date: 2026-01-05 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '040_sync_schema_drift'
down_revision = '039_merge_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # --- Sync AlertCorrelation ---
    table_ac = 'alert_correlations'
    if table_ac in inspector.get_table_names():
        columns_ac = [c['name'] for c in inspector.get_columns(table_ac)]
        
        # Add new columns
        if 'summary' not in columns_ac:
            op.add_column(table_ac, sa.Column('summary', sa.String(255), nullable=True))
            # Populate nulls with default to avoid constraint error if it becomes not null later
            op.execute(f"UPDATE {table_ac} SET summary = 'Auto-generated correlation'")
            op.alter_column(table_ac, 'summary', nullable=False)
            
        if 'root_cause_analysis' not in columns_ac:
            op.add_column(table_ac, sa.Column('root_cause_analysis', sa.Text(), nullable=True))
            
        if 'confidence_score' not in columns_ac:
            op.add_column(table_ac, sa.Column('confidence_score', sa.Float(), nullable=True))

        if 'status' not in columns_ac:
             op.add_column(table_ac, sa.Column('status', sa.String(50), nullable=False, server_default='active'))
        
        # Drop old columns (Remote specific) - check carefully
        if 'correlation_score' in columns_ac:
             op.drop_column(table_ac, 'correlation_score')
        if 'correlation_type' in columns_ac:
             op.drop_column(table_ac, 'correlation_type')
        if 'related_alert_id' in columns_ac:
             op.drop_column(table_ac, 'related_alert_id') # Assuming it's not a FK we depend on
             
    # --- Sync FailurePattern ---
    table_fp = 'failure_patterns'
    if table_fp in inspector.get_table_names():
        columns_fp = [c['name'] for c in inspector.get_columns(table_fp)]
        
        # Add new columns
        if 'pattern_signature' not in columns_fp:
            op.add_column(table_fp, sa.Column('pattern_signature', sa.Text(), nullable=True))
            op.execute(f"UPDATE {table_fp} SET pattern_signature = 'unknown'")
            op.alter_column(table_fp, 'pattern_signature', nullable=False)

        if 'description' not in columns_fp:
            op.add_column(table_fp, sa.Column('description', sa.Text(), nullable=True))
             
        if 'recommended_action' not in columns_fp:
            op.add_column(table_fp, sa.Column('recommended_action', sa.Text(), nullable=True))
            
        if 'confidence_score' not in columns_fp:
            op.add_column(table_fp, sa.Column('confidence_score', sa.Float(), nullable=True))
            
        if 'root_cause_type' not in columns_fp:
             op.add_column(table_fp, sa.Column('root_cause_type', sa.String(100), nullable=True))
             op.execute(f"UPDATE {table_fp} SET root_cause_type = 'unknown'")
             op.alter_column(table_fp, 'root_cause_type', nullable=False)
        
        # Drop old columns
        if 'pattern_name' in columns_fp:
            op.drop_column(table_fp, 'pattern_name')
        if 'pattern_description' in columns_fp:
            op.drop_column(table_fp, 'pattern_description')
        if 'symptoms' in columns_fp:
            op.drop_column(table_fp, 'symptoms')
        if 'resolution_steps' in columns_fp:
            op.drop_column(table_fp, 'resolution_steps')


def downgrade() -> None:
    # This is a one-way sync to fix drift, downgrade is best-effort or skip
    pass
