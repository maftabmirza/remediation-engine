"""Update format and doc_type constraints

Revision ID: 011_update_constraints
Revises: 010_rename_metadata_column
Create Date: 2025-12-13 19:58:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011_update_constraints'
down_revision = '010_rename_metadata_column'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update format and doc_type check constraints to support new formats."""
    
    # Drop old format constraint
    op.drop_constraint('ck_design_documents_format', 'design_documents', type_='check')
    
    # Add new format constraint with pdf, text, and image
    op.create_check_constraint(
        'ck_design_documents_format',
        'design_documents',
        "format IN ('markdown', 'pdf', 'html', 'yaml', 'text', 'image')"
    )
    
    # Drop old doc_type constraint  
    op.drop_constraint('ck_design_documents_doc_type', 'design_documents', type_='check')
    
    # Add new doc_type constraint with deployment and config
    op.create_check_constraint(
        'ck_design_documents_doc_type',
        'design_documents',
        "doc_type IN ('architecture', 'api_spec', 'runbook', 'sop', 'troubleshooting', 'design_doc', 'postmortem', 'onboarding', 'deployment', 'config')"
    )


def downgrade() -> None:
    """Revert to original constraints."""
    
    # Drop new constraints
    op.drop_constraint('ck_design_documents_format', 'design_documents', type_='check')
    op.drop_constraint('ck_design_documents_doc_type', 'design_documents', type_='check')
    
    # Restore old format constraint
    op.create_check_constraint(
        'ck_design_documents_format',
        'design_documents',
        "format IN ('markdown', 'pdf', 'html', 'yaml')"
    )
    
    # Restore old doc_type constraint
    op.create_check_constraint(
        'ck_design_documents_doc_type',
        'design_documents',
        "doc_type IN ('architecture', 'api_spec', 'runbook', 'sop', 'troubleshooting', 'design_doc', 'postmortem', 'onboarding')"
    )
