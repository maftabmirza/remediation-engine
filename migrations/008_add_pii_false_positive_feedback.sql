-- =============================================================================
-- PII False Positive Feedback Migration
-- Version: 1.0.0
-- Date: 2026-02-01
-- Description: Creates table for PII false positive user feedback and whitelist
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. PII FALSE POSITIVE FEEDBACK TABLE
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pii_false_positive_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What was flagged
    detected_text VARCHAR(500) NOT NULL,
    detected_entity_type VARCHAR(100) NOT NULL,
    detection_engine VARCHAR(50) NOT NULL,
    original_confidence FLOAT,
    
    -- Context
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255),
    agent_mode VARCHAR(50),
    detection_log_id UUID REFERENCES pii_detection_logs(id) ON DELETE SET NULL,
    
    -- Feedback details
    reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_comment TEXT,
    
    -- Whitelist status
    whitelisted BOOLEAN NOT NULL DEFAULT TRUE,
    whitelisted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    whitelist_scope VARCHAR(50) NOT NULL DEFAULT 'organization',
    
    -- Admin review workflow (optional)
    review_status VARCHAR(50) NOT NULL DEFAULT 'auto_approved',
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_whitelist_scope CHECK (whitelist_scope IN ('organization', 'user', 'global')),
    CONSTRAINT chk_review_status CHECK (review_status IN ('auto_approved', 'approved', 'rejected', 'pending'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pii_feedback_text ON pii_false_positive_feedback(detected_text);
CREATE INDEX IF NOT EXISTS idx_pii_feedback_entity_type ON pii_false_positive_feedback(detected_entity_type);
CREATE INDEX IF NOT EXISTS idx_pii_feedback_user_id ON pii_false_positive_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_pii_feedback_whitelisted ON pii_false_positive_feedback(whitelisted) WHERE whitelisted = TRUE;
CREATE INDEX IF NOT EXISTS idx_pii_feedback_reported_at ON pii_false_positive_feedback(reported_at);
CREATE INDEX IF NOT EXISTS idx_pii_feedback_session ON pii_false_positive_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_pii_feedback_review_status ON pii_false_positive_feedback(review_status);

-- Composite index for whitelist lookups (most common query)
CREATE INDEX IF NOT EXISTS idx_pii_feedback_whitelist_lookup 
    ON pii_false_positive_feedback(detected_text, whitelisted, whitelist_scope) 
    WHERE whitelisted = TRUE;

-- -----------------------------------------------------------------------------
-- 2. UPDATE TRIGGER FOR updated_at
-- -----------------------------------------------------------------------------

DROP TRIGGER IF EXISTS update_pii_feedback_updated_at ON pii_false_positive_feedback;
CREATE TRIGGER update_pii_feedback_updated_at
    BEFORE UPDATE ON pii_false_positive_feedback
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 3. COMMENTS FOR DOCUMENTATION
-- -----------------------------------------------------------------------------

COMMENT ON TABLE pii_false_positive_feedback IS 'User feedback for false positive PII/secret detections. Used to build whitelist and improve detection accuracy.';
COMMENT ON COLUMN pii_false_positive_feedback.detected_text IS 'The text that was incorrectly flagged as PII/secret';
COMMENT ON COLUMN pii_false_positive_feedback.detected_entity_type IS 'Type of PII that was detected (EMAIL_ADDRESS, PHONE_NUMBER, etc.)';
COMMENT ON COLUMN pii_false_positive_feedback.detection_engine IS 'Which engine made the detection (presidio or detect_secrets)';
COMMENT ON COLUMN pii_false_positive_feedback.session_id IS 'Agent session ID for context tracking';
COMMENT ON COLUMN pii_false_positive_feedback.agent_mode IS 'Which agent mode: alert, revive, or troubleshoot';
COMMENT ON COLUMN pii_false_positive_feedback.whitelisted IS 'Whether this text is actively whitelisted (can be disabled by admin)';
COMMENT ON COLUMN pii_false_positive_feedback.whitelist_scope IS 'Scope of whitelist: organization, user, or global';
COMMENT ON COLUMN pii_false_positive_feedback.review_status IS 'Admin review status: auto_approved, approved, rejected, or pending';

-- -----------------------------------------------------------------------------
-- Done!
-- -----------------------------------------------------------------------------
