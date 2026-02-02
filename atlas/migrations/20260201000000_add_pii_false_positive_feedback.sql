-- Add table for PII false positive feedback and whitelist management
-- Created: 2026-02-01

--
-- Name: pii_false_positive_feedback; Type: TABLE; Schema: public
--

CREATE TABLE public.pii_false_positive_feedback (
    id uuid NOT NULL,
    detected_text character varying(500) NOT NULL,
    detected_entity_type character varying(100) NOT NULL,
    detection_engine character varying(50) NOT NULL,
    original_confidence double precision,
    user_id uuid NOT NULL,
    session_id character varying(255),
    agent_mode character varying(50),
    detection_log_id uuid,
    reported_at timestamp with time zone DEFAULT now() NOT NULL,
    user_comment text,
    whitelisted boolean DEFAULT true NOT NULL,
    whitelisted_at timestamp with time zone DEFAULT now() NOT NULL,
    whitelist_scope character varying(50) DEFAULT 'organization'::character varying NOT NULL,
    review_status character varying(50) DEFAULT 'auto_approved'::character varying NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    review_notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT pii_false_positive_feedback_pkey PRIMARY KEY (id),
    CONSTRAINT pii_false_positive_feedback_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT pii_false_positive_feedback_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL,
    CONSTRAINT pii_false_positive_feedback_detection_log_id_fkey FOREIGN KEY (detection_log_id) REFERENCES public.pii_detection_logs(id) ON DELETE SET NULL,
    CONSTRAINT chk_whitelist_scope CHECK (whitelist_scope IN ('organization', 'user', 'global')),
    CONSTRAINT chk_review_status CHECK (review_status IN ('auto_approved', 'approved', 'rejected', 'pending'))
);


-- Indexes for performance

CREATE INDEX idx_pii_feedback_text ON public.pii_false_positive_feedback USING btree (detected_text);
CREATE INDEX idx_pii_feedback_entity_type ON public.pii_false_positive_feedback USING btree (detected_entity_type);
CREATE INDEX idx_pii_feedback_user_id ON public.pii_false_positive_feedback USING btree (user_id);
CREATE INDEX idx_pii_feedback_whitelisted ON public.pii_false_positive_feedback USING btree (whitelisted) WHERE whitelisted = true;
CREATE INDEX idx_pii_feedback_reported_at ON public.pii_false_positive_feedback USING btree (reported_at);
CREATE INDEX idx_pii_feedback_session ON public.pii_false_positive_feedback USING btree (session_id);
CREATE INDEX idx_pii_feedback_review_status ON public.pii_false_positive_feedback USING btree (review_status);

-- Composite index for whitelist lookups (most common query)
CREATE INDEX idx_pii_feedback_whitelist_lookup ON public.pii_false_positive_feedback USING btree (detected_text, whitelisted, whitelist_scope) WHERE whitelisted = true;


-- Update trigger for updated_at column (uses existing function)

CREATE TRIGGER update_pii_feedback_updated_at
    BEFORE UPDATE ON public.pii_false_positive_feedback
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- Comments for documentation

COMMENT ON TABLE public.pii_false_positive_feedback IS 'User feedback for false positive PII/secret detections. Used to build whitelist and improve detection accuracy.';
COMMENT ON COLUMN public.pii_false_positive_feedback.detected_text IS 'The text that was incorrectly flagged as PII/secret';
COMMENT ON COLUMN public.pii_false_positive_feedback.detected_entity_type IS 'Type of PII that was detected (EMAIL_ADDRESS, PHONE_NUMBER, etc.)';
COMMENT ON COLUMN public.pii_false_positive_feedback.detection_engine IS 'Which engine made the detection (presidio or detect_secrets)';
COMMENT ON COLUMN public.pii_false_positive_feedback.session_id IS 'Agent session ID for context tracking';
COMMENT ON COLUMN public.pii_false_positive_feedback.agent_mode IS 'Which agent mode: alert, revive, or troubleshoot';
COMMENT ON COLUMN public.pii_false_positive_feedback.whitelisted IS 'Whether this text is actively whitelisted (can be disabled by admin)';
COMMENT ON COLUMN public.pii_false_positive_feedback.whitelist_scope IS 'Scope of whitelist: organization, user, or global';
COMMENT ON COLUMN public.pii_false_positive_feedback.review_status IS 'Admin review status: auto_approved, approved, rejected, or pending';
