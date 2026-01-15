"""fix_final_drift

Revision ID: 4182a90197d3
Revises: 7f32249f0402
Create Date: 2026-01-08 02:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4182a90197d3'
down_revision = '7f32249f0402'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix defaults for incident_metrics
    op.alter_column('incident_metrics', 'id',
               existing_type=sa.UUID(),
               server_default=sa.text('gen_random_uuid()'),
               existing_nullable=False)
    op.alter_column('incident_metrics', 'incident_detected',
               existing_type=sa.TIMESTAMP(timezone=True),
               server_default=sa.text('now()'),
               existing_nullable=False)
               
    # Add unique constraint for alert_id
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cons = inspector.get_unique_constraints('incident_metrics')
    if not any(c['name'] == 'uq_incident_metrics_alert_id' for c in cons):
        op.create_unique_constraint('uq_incident_metrics_alert_id', 'incident_metrics', ['alert_id'])
    else:
        print("Skipping create unique constraint on incident_metrics.alert_id - already exists")


def downgrade() -> None:
    pass
