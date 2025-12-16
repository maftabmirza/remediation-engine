"""seed default roles

Revision ID: 012_seed_default_roles
Revises: 011_update_constraints
Create Date: 2025-12-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Boolean, JSON
import uuid

# revision identifiers, used by Alembic.
revision = '012_seed_default_roles'
down_revision = '011_update_constraints'
branch_labels = None
depends_on = None

def upgrade():
    # Define the roles table for bulk insert
    roles_table = table('roles',
        column('id', sa.dialects.postgresql.UUID),
        column('name', String),
        column('description', String),
        column('permissions', JSON),
        column('is_custom', Boolean),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime)
    )
    
    # Check if roles already exist
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT COUNT(*) FROM roles")).scalar()
    
    # Only seed if table is empty
    if result == 0:
        from datetime import datetime
        now = datetime.utcnow()
        
        # Seed default roles with knowledge base permissions
        op.bulk_insert(roles_table, [
            {
                'id': uuid.uuid4(),
                'name': 'owner',
                'description': 'Built-in owner role',
                'permissions': ["manage_users", "manage_servers", "manage_server_groups", "manage_providers", 
                               "execute", "update", "read", "view_audit", 
                               "view_knowledge", "upload_documents", "manage_knowledge"],
                'is_custom': False,
                'created_at': now,
                'updated_at': now
            },
            {
                'id': uuid.uuid4(),
                'name': 'admin',
                'description': 'Built-in admin role',
                'permissions': ["manage_users", "manage_servers", "manage_server_groups", "manage_providers",
                               "execute", "update", "read", "view_audit",
                               "view_knowledge", "upload_documents", "manage_knowledge"],
                'is_custom': False,
                'created_at': now,
                'updated_at': now
            },
            {
                'id': uuid.uuid4(),
                'name': 'maintainer',
                'description': 'Built-in maintainer role',
                'permissions': ["manage_servers", "manage_server_groups", "manage_providers",
                               "update", "execute", "read",
                               "view_knowledge", "upload_documents", "manage_knowledge"],
                'is_custom': False,
                'created_at': now,
                'updated_at': now
            },
            {
                'id': uuid.uuid4(),
                'name': 'operator',
                'description': 'Built-in operator role',
                'permissions': ["execute", "read", "view_knowledge", "upload_documents"],
                'is_custom': False,
                'created_at': now,
                'updated_at': now
            },
            {
                'id': uuid.uuid4(),
                'name': 'viewer',
                'description': 'Built-in viewer role',
                'permissions': ["read", "view_knowledge"],
                'is_custom': False,
                'created_at': now,
                'updated_at': now
            },
            {
                'id': uuid.uuid4(),
                'name': 'auditor',
                'description': 'Built-in auditor role',
                'permissions': ["read", "view_audit", "view_knowledge"],
                'is_custom': False,
                'created_at': now,
                'updated_at': now
            }
        ])


def downgrade():
    # Remove default roles
    op.execute("DELETE FROM roles WHERE is_custom = false")
