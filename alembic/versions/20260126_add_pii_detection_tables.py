"""add pii detection tables

Revision ID: 20260126_pii_detection
Revises: 
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260126_pii_detection'
down_revision = None  # Update this to the latest revision in your project
branch_labels = None
depends_on = None


def upgrade():
    # Create pii_detection_config table
    op.create_table(
        'pii_detection_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('config_type', sa.String(50), nullable=False, comment='presidio or detect_secrets'),
        sa.Column('entity_type', sa.String(100), nullable=False, comment='Entity/plugin name'),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('threshold', sa.Float(), nullable=False, default=0.7, comment='Confidence threshold (0.0-1.0)'),
        sa.Column('redaction_type', sa.String(50), nullable=False, default='mask', comment='mask, hash, remove, or tag'),
        sa.Column('custom_pattern', sa.Text(), nullable=True, comment='Optional custom regex'),
        sa.Column('settings_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Additional settings'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.UniqueConstraint('config_type', 'entity_type', name='uq_config_type_entity')
    )
    
    # Create indexes for pii_detection_config
    op.create_index('ix_pii_config_type', 'pii_detection_config', ['config_type'])
    op.create_index('ix_pii_config_entity', 'pii_detection_config', ['entity_type'])
    op.create_index('ix_pii_config_enabled', 'pii_detection_config', ['enabled'])
    
    # Create pii_detection_logs table
    op.create_table(
        'pii_detection_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('entity_type', sa.String(100), nullable=False, index=True),
        sa.Column('detection_engine', sa.String(50), nullable=False, index=True, comment='presidio or detect_secrets'),
        sa.Column('confidence_score', sa.Float(), nullable=False, index=True),
        sa.Column('source_type', sa.String(50), nullable=False, index=True, comment='runbook_output, llm_response, alert, etc.'),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True, index=True, comment='FK to source record'),
        sa.Column('context_snippet', sa.Text(), nullable=True, comment='Surrounding text (redacted)'),
        sa.Column('position_start', sa.Integer(), nullable=False),
        sa.Column('position_end', sa.Integer(), nullable=False),
        sa.Column('was_redacted', sa.Boolean(), nullable=False, default=True),
        sa.Column('redaction_type', sa.String(50), nullable=True),
        sa.Column('original_hash', sa.String(64), nullable=False, comment='SHA-256 hash of original value'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )
    
    # Create indexes for pii_detection_logs
    op.create_index('ix_pii_logs_detected_at', 'pii_detection_logs', ['detected_at'])
    op.create_index('ix_pii_logs_entity_type', 'pii_detection_logs', ['entity_type'])
    op.create_index('ix_pii_logs_engine', 'pii_detection_logs', ['detection_engine'])
    op.create_index('ix_pii_logs_source_type', 'pii_detection_logs', ['source_type'])
    op.create_index('ix_pii_logs_source_id', 'pii_detection_logs', ['source_id'])
    op.create_index('ix_pii_logs_confidence', 'pii_detection_logs', ['confidence_score'])
    op.create_index('ix_pii_logs_hash', 'pii_detection_logs', ['original_hash'])
    
    # Create composite indexes for common queries
    op.create_index('ix_pii_logs_date_entity', 'pii_detection_logs', ['detected_at', 'entity_type'])
    op.create_index('ix_pii_logs_source_type_id', 'pii_detection_logs', ['source_type', 'source_id'])
    
    # Create secret_baselines table
    op.create_table(
        'secret_baselines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('secret_hash', sa.String(64), nullable=False, unique=True, index=True, comment='SHA-256 hash of secret'),
        sa.Column('secret_type', sa.String(100), nullable=False, index=True),
        sa.Column('first_detected', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_detected', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('detection_count', sa.Integer(), nullable=False, default=1),
        sa.Column('is_acknowledged', sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column('acknowledged_by', sa.String(100), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True)
    )
    
    # Create indexes for secret_baselines
    op.create_index('ix_secret_baselines_hash', 'secret_baselines', ['secret_hash'])
    op.create_index('ix_secret_baselines_type', 'secret_baselines', ['secret_type'])
    op.create_index('ix_secret_baselines_acknowledged', 'secret_baselines', ['is_acknowledged'])


def downgrade():
    # Drop tables in reverse order
    op.drop_table('secret_baselines')
    op.drop_table('pii_detection_logs')
    op.drop_table('pii_detection_config')
