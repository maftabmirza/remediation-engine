"""Add grafana_datasources table

Revision ID: 034_add_grafana_datasources
Revises: 033_add_application_profiles
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '034_add_grafana_datasources'
down_revision = '033_add_application_profiles'
branch_labels = None
depends_on = None


def upgrade():
    """Create grafana_datasources table for Loki, Tempo, and other observability backends."""
    op.create_table(
        'grafana_datasources',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True, index=True),
        sa.Column('datasource_type', sa.String(length=50), nullable=False, index=True),
        sa.Column('url', sa.String(length=512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Authentication
        sa.Column('auth_type', sa.String(length=50), nullable=False, server_default='none'),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password', sa.String(length=512), nullable=True),
        sa.Column('bearer_token', sa.String(length=512), nullable=True),

        # Configuration
        sa.Column('timeout', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('config_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('custom_headers', sa.JSON(), nullable=False, server_default='{}'),

        # Health status
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_healthy', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('health_message', sa.Text(), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(length=255), nullable=True),

        # Constraints
        sa.CheckConstraint(
            "datasource_type IN ('loki', 'tempo', 'prometheus', 'mimir', 'alertmanager', 'jaeger', 'zipkin', 'elasticsearch')",
            name='ck_datasources_type'
        ),
        sa.CheckConstraint(
            "auth_type IN ('none', 'basic', 'bearer', 'oauth2', 'api_key')",
            name='ck_datasources_auth_type'
        ),
    )


def downgrade():
    """Drop grafana_datasources table."""
    op.drop_table('grafana_datasources')
