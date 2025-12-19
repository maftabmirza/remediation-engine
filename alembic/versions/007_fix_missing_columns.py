"""fix missing columns from 001

Revision ID: 007_fix_missing_columns
Revises: 006_add_application_registry
Create Date: 2025-12-13 13:42:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '007_fix_missing_columns'
down_revision = '006_add_application_registry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add columns that were missing from 001 migration due to conditional logic."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Fix auto_analyze_rules table
    if 'auto_analyze_rules' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('auto_analyze_rules')]
        if 'condition_json' not in columns:
            op.add_column('auto_analyze_rules', 
                sa.Column('condition_json', postgresql.JSON, nullable=True))
    
    # Fix server_credentials table - add API-related columns
    if 'server_credentials' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('server_credentials')]
        
        if 'domain' not in columns:
            op.add_column('server_credentials',
                sa.Column('domain', sa.String(255), nullable=True))
        
        if 'api_base_url' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_base_url', sa.String(500), nullable=True))
        
        if 'api_auth_type' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_auth_type', sa.String(50), nullable=True))
        
        if 'api_auth_header' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_auth_header', sa.String(100), nullable=True))
        
        if 'api_token_encrypted' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_token_encrypted', sa.LargeBinary, nullable=True))
        
        if 'api_verify_ssl' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_verify_ssl', sa.Boolean, default=True))
        
        if 'api_timeout_seconds' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_timeout_seconds', sa.Integer, default=30))
        
        if 'api_headers_json' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_headers_json', postgresql.JSON, nullable=True))
        
        if 'api_metadata_json' not in columns:
            op.add_column('server_credentials',
                sa.Column('api_metadata_json', postgresql.JSON, nullable=True))


def downgrade() -> None:
    """Remove the columns added in this migration."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Remove from auto_analyze_rules
    if 'auto_analyze_rules' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('auto_analyze_rules')]
        if 'condition_json' in columns:
            op.drop_column('auto_analyze_rules', 'condition_json')
    
    # Remove from server_credentials
    if 'server_credentials' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('server_credentials')]
        
        for col_name in ['domain', 'api_base_url', 'api_auth_type', 'api_auth_header',
                         'api_token_encrypted', 'api_verify_ssl', 'api_timeout_seconds',
                         'api_headers_json', 'api_metadata_json']:
            if col_name in columns:
                op.drop_column('server_credentials', col_name)
