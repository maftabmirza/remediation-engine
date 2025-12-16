"""Add Application Registry

Revision ID: 006_add_application_registry
Revises: 005_add_agent_mode
Create Date: 2025-12-13 13:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '006_add_application_registry'
down_revision = '005_add_agent_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # Create applications table
    if 'applications' not in tables:
        op.create_table('applications',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('name', sa.String(100), nullable=False, unique=True, index=True),
            sa.Column('display_name', sa.String(200), nullable=True),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('team_owner', sa.String(100), nullable=True),
            sa.Column('criticality', sa.String(20), nullable=True),
            sa.Column('tech_stack', postgresql.JSON, default={}),
            sa.Column('alert_label_matchers', postgresql.JSON, default={}),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        
        # Add check constraint for criticality
        op.create_check_constraint(
            'ck_applications_criticality',
            'applications',
            "criticality IN ('critical', 'high', 'medium', 'low')"
        )

    # Create application_components table
    if 'application_components' not in tables:
        op.create_table('application_components',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('component_type', sa.String(50), nullable=True),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('endpoints', postgresql.JSON, default={}),
            sa.Column('alert_label_matchers', postgresql.JSON, default={}),
            sa.Column('criticality', sa.String(20), default='high'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        
        # Add check constraint for component_type
        op.create_check_constraint(
            'ck_components_type',
            'application_components',
            "component_type IN ('compute', 'database', 'cache', 'queue', 'storage', 'cdn', 'load_balancer', 'api_gateway', 'external')"
        )
        
        # Add unique constraint for app_id + name
        op.create_unique_constraint('uq_app_component_name', 'application_components', ['app_id', 'name'])

    # Create component_dependencies table
    if 'component_dependencies' not in tables:
        op.create_table('component_dependencies',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('from_component_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('application_components.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('to_component_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('application_components.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('dependency_type', sa.String(20), nullable=True),
            sa.Column('failure_impact', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        
        # Add check constraint for dependency_type
        op.create_check_constraint(
            'ck_dependencies_type',
            'component_dependencies',
            "dependency_type IN ('sync', 'async', 'optional')"
        )
        
        # Add unique constraint to prevent duplicate dependencies
        op.create_unique_constraint('uq_component_dependency', 'component_dependencies', ['from_component_id', 'to_component_id'])

    # Add app_id to alerts table to link alerts to applications
    if 'alerts' in tables:
        columns = [col['name'] for col in inspector.get_columns('alerts')]
        if 'app_id' not in columns:
            op.add_column('alerts', sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True, index=True))
        if 'component_id' not in columns:
            op.add_column('alerts', sa.Column('component_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('application_components.id', ondelete='SET NULL'), nullable=True, index=True))


def downgrade() -> None:
    # Remove columns from alerts
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    if 'alerts' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('alerts')]
        if 'component_id' in columns:
            op.drop_column('alerts', 'component_id')
        if 'app_id' in columns:
            op.drop_column('alerts', 'app_id')
    
    # Drop tables in reverse order
    op.drop_table('component_dependencies')
    op.drop_table('application_components')
    op.drop_table('applications')
