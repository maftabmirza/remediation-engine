"""add application profiles table

Revision ID: 030_add_application_profiles
Revises: c3031e42d864_add_runbook_step_outputs
Create Date: 2025-12-26 03:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision = '030_add_application_profiles'
down_revision = 'c3031e42d864_add_runbook_step_outputs'
branch_labels = None
depends_on = None


def upgrade():
    # Create application_profiles table
    op.create_table(
        'application_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('app_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True, unique=True),

        # Architecture information
        sa.Column('architecture_type', sa.String(length=50), nullable=True),
        sa.Column('framework', sa.String(length=100), nullable=True),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('architecture_info', JSON, nullable=False, server_default='{}'),

        # Service mappings and metrics
        sa.Column('service_mappings', JSON, nullable=False, server_default='{}'),
        sa.Column('default_metrics', JSON, nullable=False, server_default='[]'),
        sa.Column('slos', JSON, nullable=False, server_default='{}'),

        # Datasource configurations (for future use)
        sa.Column('prometheus_datasource_id', UUID(as_uuid=True), nullable=True),
        sa.Column('loki_datasource_id', UUID(as_uuid=True), nullable=True),
        sa.Column('tempo_datasource_id', UUID(as_uuid=True), nullable=True),

        # AI context preferences
        sa.Column('default_time_range', sa.String(length=20), nullable=False, server_default='1h'),
        sa.Column('log_patterns', JSON, nullable=False, server_default='{}'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),

        # Constraints
        sa.CheckConstraint(
            "architecture_type IN ('monolith', 'microservices', 'serverless', 'hybrid', 'other')",
            name='ck_app_profiles_architecture'
        ),
    )


def downgrade():
    # Drop application_profiles table
    op.drop_table('application_profiles')
