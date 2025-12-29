"""update_incident_metrics_schema_to_match_model

Revision ID: 4e706f82cee5
Revises: 30efa51c24a2
Create Date: 2025-12-29

This migration updates the incident_metrics table to match the current model definition.
The old schema had simple start/end timestamps and a boolean resolved flag.
The new schema has detailed lifecycle tracking with multiple timestamps and calculated metrics.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Import migration helpers
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from migration_helpers import (
    add_column_safe, drop_column_safe, column_exists
)

# revision identifiers, used by Alembic.
revision = '4e706f82cee5'
down_revision = '30efa51c24a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Transform incident_metrics from old schema to new schema.
    
    Old schema (11 columns):
    - incident_start, incident_end, incident_resolved (boolean), mttr_minutes
    
    New schema (17 columns):
    - incident_started, incident_detected, incident_acknowledged, 
      incident_engaged, incident_resolved (timestamp)
    - time_to_detect, time_to_acknowledge, time_to_engage, time_to_resolve
    - assigned_to
    """
    
    # Step 1: Rename incident_start to incident_started (if old column exists)
    if column_exists('incident_metrics', 'incident_start'):
        op.alter_column('incident_metrics', 'incident_start', 
                       new_column_name='incident_started')
    
    # Step 2: Add new timestamp columns
    add_column_safe('incident_metrics', 
                   sa.Column('incident_detected', sa.DateTime(timezone=True), nullable=False,
                            server_default=sa.text('NOW()')))
    
    add_column_safe('incident_metrics', 
                   sa.Column('incident_acknowledged', sa.DateTime(timezone=True), nullable=True))
    
    add_column_safe('incident_metrics', 
                   sa.Column('incident_engaged', sa.DateTime(timezone=True), nullable=True))
    
    # Step 3: Handle incident_resolved column transformation
    # Old: boolean, New: timestamp
    # If old boolean column exists, we need to:
    # 1. Rename it temporarily
    # 2. Create new timestamp column
    # 3. Migrate data (if resolved=true, use incident_end as resolved timestamp)
    # 4. Drop old column
    
    if column_exists('incident_metrics', 'incident_resolved'):
        # Check if it's a boolean (old schema)
        conn = op.get_bind()
        result = conn.execute(sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'incident_metrics' AND column_name = 'incident_resolved'"
        ))
        data_type = result.scalar()
        
        if data_type == 'boolean':
            # Rename old boolean column
            op.alter_column('incident_metrics', 'incident_resolved',
                          new_column_name='incident_resolved_old')
            
            # Add new timestamp column
            op.add_column('incident_metrics',
                         sa.Column('incident_resolved', sa.DateTime(timezone=True), nullable=True))
            
            # Migrate data: if incident_resolved_old=true, use incident_end as timestamp
            if column_exists('incident_metrics', 'incident_end'):
                conn.execute(sa.text(
                    "UPDATE incident_metrics "
                    "SET incident_resolved = incident_end "
                    "WHERE incident_resolved_old = true"
                ))
            
            # Drop old boolean column
            op.drop_column('incident_metrics', 'incident_resolved_old')
    else:
        # Column doesn't exist, add it
        add_column_safe('incident_metrics',
                       sa.Column('incident_resolved', sa.DateTime(timezone=True), nullable=True))
    
    # Step 4: Add calculated duration columns
    add_column_safe('incident_metrics',
                   sa.Column('time_to_detect', sa.Integer(), nullable=True))
    
    add_column_safe('incident_metrics',
                   sa.Column('time_to_acknowledge', sa.Integer(), nullable=True))
    
    add_column_safe('incident_metrics',
                   sa.Column('time_to_engage', sa.Integer(), nullable=True))
    
    # time_to_resolve replaces mttr_minutes
    add_column_safe('incident_metrics',
                   sa.Column('time_to_resolve', sa.Integer(), nullable=True))
    
    # Migrate mttr_minutes to time_to_resolve if it exists
    if column_exists('incident_metrics', 'mttr_minutes'):
        conn = op.get_bind()
        # Convert minutes to seconds
        conn.execute(sa.text(
            "UPDATE incident_metrics "
            "SET time_to_resolve = mttr_minutes * 60 "
            "WHERE mttr_minutes IS NOT NULL AND time_to_resolve IS NULL"
        ))
    
    # Step 5: Add assigned_to column
    add_column_safe('incident_metrics',
                   sa.Column('assigned_to', postgresql.UUID(as_uuid=True),
                            sa.ForeignKey('users.id', ondelete='SET NULL'),
                            nullable=True))
    
    # Step 6: Remove old columns that are no longer needed
    drop_column_safe('incident_metrics', 'incident_end')
    drop_column_safe('incident_metrics', 'mttr_minutes')
    
    # Step 7: Create indexes for new columns
    op.create_index('idx_incident_metrics_assigned_to', 'incident_metrics', ['assigned_to'], 
                   unique=False, if_not_exists=True)


def downgrade() -> None:
    """
    Revert to old schema (not recommended - data loss will occur)
    """
    # Drop new indexes
    op.drop_index('idx_incident_metrics_assigned_to', table_name='incident_metrics', 
                 if_exists=True)
    
    # Remove new columns
    drop_column_safe('incident_metrics', 'assigned_to')
    drop_column_safe('incident_metrics', 'time_to_resolve')
    drop_column_safe('incident_metrics', 'time_to_engage')
    drop_column_safe('incident_metrics', 'time_to_acknowledge')
    drop_column_safe('incident_metrics', 'time_to_detect')
    
    # Add back old columns
    add_column_safe('incident_metrics',
                   sa.Column('incident_end', sa.DateTime(timezone=True), nullable=True))
    add_column_safe('incident_metrics',
                   sa.Column('mttr_minutes', sa.Integer(), nullable=True))
    
    # Convert incident_resolved timestamp back to boolean
    if column_exists('incident_metrics', 'incident_resolved'):
        op.alter_column('incident_metrics', 'incident_resolved',
                       new_column_name='incident_resolved_ts')
        op.add_column('incident_metrics',
                     sa.Column('incident_resolved', sa.Boolean(), 
                              server_default='false', nullable=True))
        
        conn = op.get_bind()
        conn.execute(sa.text(
            "UPDATE incident_metrics "
            "SET incident_resolved = (incident_resolved_ts IS NOT NULL)"
        ))
        
        drop_column_safe('incident_metrics', 'incident_resolved_ts')
    
    # Rename incident_started back to incident_start
    if column_exists('incident_metrics', 'incident_started'):
        op.alter_column('incident_metrics', 'incident_started',
                       new_column_name='incident_start')
    
    # Remove new timestamp columns
    drop_column_safe('incident_metrics', 'incident_engaged')
    drop_column_safe('incident_metrics', 'incident_acknowledged')
    drop_column_safe('incident_metrics', 'incident_detected')
