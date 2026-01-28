-- Add tables for PII and secret detection audit/logging
-- Created: 2026-01-27

--
-- Name: pii_detection_config; Type: TABLE; Schema: public
--

CREATE TABLE public.pii_detection_config (
    id uuid NOT NULL,
    config_type character varying(50) NOT NULL,
    entity_type character varying(100) NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    threshold double precision DEFAULT 0.7 NOT NULL,
    redaction_type character varying(50) DEFAULT 'mask'::character varying NOT NULL,
    custom_pattern text,
    settings_json jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT pii_detection_config_pkey PRIMARY KEY (id),
    CONSTRAINT uq_config_type_entity UNIQUE (config_type, entity_type)
);


--
-- Name: pii_detection_logs; Type: TABLE; Schema: public
--

CREATE TABLE public.pii_detection_logs (
    id uuid NOT NULL,
    detected_at timestamp with time zone DEFAULT now() NOT NULL,
    entity_type character varying(100) NOT NULL,
    detection_engine character varying(50) NOT NULL,
    confidence_score double precision NOT NULL,
    source_type character varying(50) NOT NULL,
    source_id uuid,
    context_snippet text,
    position_start integer NOT NULL,
    position_end integer NOT NULL,
    was_redacted boolean DEFAULT true NOT NULL,
    redaction_type character varying(50),
    original_hash character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT pii_detection_logs_pkey PRIMARY KEY (id)
);


--
-- Name: secret_baselines; Type: TABLE; Schema: public
--

CREATE TABLE public.secret_baselines (
    id uuid NOT NULL,
    secret_hash character varying(64) NOT NULL,
    secret_type character varying(100) NOT NULL,
    first_detected timestamp with time zone DEFAULT now() NOT NULL,
    last_detected timestamp with time zone DEFAULT now() NOT NULL,
    detection_count integer DEFAULT 1 NOT NULL,
    is_acknowledged boolean DEFAULT false NOT NULL,
    acknowledged_by character varying(100),
    acknowledged_at timestamp with time zone,
    notes text,
    CONSTRAINT secret_baselines_pkey PRIMARY KEY (id),
    CONSTRAINT secret_baselines_secret_hash_key UNIQUE (secret_hash)
);


-- Indexes (match SQLAlchemy model indexes)

CREATE INDEX ix_pii_detection_config_config_type ON public.pii_detection_config USING btree (config_type);
CREATE INDEX ix_pii_detection_config_entity_type ON public.pii_detection_config USING btree (entity_type);
CREATE INDEX ix_pii_detection_config_enabled ON public.pii_detection_config USING btree (enabled);

CREATE INDEX ix_pii_detection_logs_detected_at ON public.pii_detection_logs USING btree (detected_at);
CREATE INDEX ix_pii_detection_logs_entity_type ON public.pii_detection_logs USING btree (entity_type);
CREATE INDEX ix_pii_detection_logs_detection_engine ON public.pii_detection_logs USING btree (detection_engine);
CREATE INDEX ix_pii_detection_logs_confidence_score ON public.pii_detection_logs USING btree (confidence_score);
CREATE INDEX ix_pii_detection_logs_source_type ON public.pii_detection_logs USING btree (source_type);
CREATE INDEX ix_pii_detection_logs_source_id ON public.pii_detection_logs USING btree (source_id);
CREATE INDEX ix_pii_detection_logs_original_hash ON public.pii_detection_logs USING btree (original_hash);

CREATE INDEX ix_secret_baselines_secret_type ON public.secret_baselines USING btree (secret_type);
CREATE INDEX ix_secret_baselines_is_acknowledged ON public.secret_baselines USING btree (is_acknowledged);
