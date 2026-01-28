--
-- PostgreSQL database dump
--


-- Dumped from database version 16.11 (Debian 16.11-1.pgdg12+1)
-- Dumped by pg_dump version 16.11 (Debian 16.11-1.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

SET check_function_bodies = false;
SET xmloption = content;



--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--




--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--




--
-- Name: paneltype; Type: TYPE; Schema: public; Owner: aiops
--

CREATE TYPE public.paneltype AS ENUM (
    'graph',
    'gauge',
    'stat',
    'table',
    'heatmap',
    'bar',
    'pie'
);




SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: action_proposals; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.action_proposals (
    id uuid NOT NULL,
    task_id uuid NOT NULL,
    action_type character varying(50) NOT NULL,
    description text NOT NULL,
    command text,
    safety_level character varying(20),
    status character varying(20),
    created_at timestamp without time zone,
    approved_at timestamp without time zone,
    approved_by uuid,
    result text,
    rejection_reason text
);




--
-- Name: agent_audit_logs; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.agent_audit_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    session_id uuid,
    step_id uuid,
    user_id uuid,
    action character varying(50) NOT NULL,
    command text,
    details text,
    ip_address character varying(45),
    user_agent character varying(500),
    validation_result character varying(20),
    blocked_reason character varying(500),
    output_preview character varying(1000),
    exit_code integer,
    server_id uuid,
    server_name character varying(255),
    created_at timestamp with time zone DEFAULT now()
);




--
-- Name: agent_pools; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.agent_pools (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    max_concurrent_agents integer,
    created_at timestamp without time zone
);




--
-- Name: agent_rate_limits; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.agent_rate_limits (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    commands_this_minute integer,
    sessions_this_hour integer,
    minute_window_start timestamp with time zone,
    hour_window_start timestamp with time zone,
    max_commands_per_minute integer,
    max_sessions_per_hour integer,
    is_rate_limited boolean,
    rate_limited_until timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now()
);




--
-- Name: agent_rate_limits_id_seq; Type: SEQUENCE; Schema: public; Owner: aiops
--

CREATE SEQUENCE public.agent_rate_limits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;




--
-- Name: agent_rate_limits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: aiops
--

ALTER SEQUENCE public.agent_rate_limits_id_seq OWNED BY public.agent_rate_limits.id;


--
-- Name: agent_sessions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.agent_sessions (
    id uuid NOT NULL,
    chat_session_id uuid,
    user_id uuid NOT NULL,
    server_id uuid,
    goal text NOT NULL,
    status character varying(50),
    auto_approve boolean,
    max_steps integer,
    current_step_number integer,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_message text,
    summary text,
    agent_type character varying(50),
    pool_id uuid,
    worktree_path character varying(1024),
    auto_iterate boolean,
    max_auto_iterations integer,
    last_activity_at timestamp with time zone
);




--
-- Name: agent_steps; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.agent_steps (
    id uuid NOT NULL,
    agent_session_id uuid NOT NULL,
    step_number integer NOT NULL,
    step_type character varying(20) NOT NULL,
    content text NOT NULL,
    reasoning text,
    output text,
    exit_code integer,
    status character varying(20),
    created_at timestamp with time zone,
    executed_at timestamp with time zone,
    iteration_count integer,
    change_set_id uuid,
    validation_result character varying(20),
    blocked_reason character varying(500),
    step_metadata text
);




--
-- Name: agent_tasks; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.agent_tasks (
    id uuid NOT NULL,
    pool_id uuid NOT NULL,
    agent_session_id uuid,
    agent_type character varying(50),
    goal text NOT NULL,
    priority integer,
    status character varying(50),
    worktree_path character varying(1024),
    created_at timestamp without time zone,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    auto_iterate boolean,
    max_iterations integer
);




--
-- Name: ai_action_confirmations; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_action_confirmations (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    user_id uuid NOT NULL,
    action_type character varying(100) NOT NULL,
    action_details json NOT NULL,
    risk_level character varying(20),
    status character varying(20),
    expires_at timestamp with time zone,
    confirmed_at timestamp with time zone,
    created_at timestamp with time zone
);




--
-- Name: ai_feedback; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_feedback (
    id uuid NOT NULL,
    created_at timestamp with time zone,
    message_id uuid,
    runbook_id uuid,
    session_id uuid,
    user_id uuid
);




--
-- Name: ai_helper_audit_logs; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_helper_audit_logs (
    id uuid NOT NULL,
    "timestamp" timestamp with time zone,
    executed boolean DEFAULT false,
    action_blocked boolean DEFAULT false,
    permission_checked boolean DEFAULT true,
    is_error boolean DEFAULT false,
    ai_suggested_action character varying,
    correlation_id character varying,
    execution_result character varying,
    session_id uuid,
    user_action character varying,
    user_id uuid
);




--
-- Name: ai_helper_sessions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_helper_sessions (
    id uuid NOT NULL,
    user_id uuid,
    started_at timestamp with time zone,
    last_activity_at timestamp with time zone,
    status character varying(50) DEFAULT 'active'::character varying,
    session_type character varying(50) DEFAULT 'general'::character varying,
    total_queries integer DEFAULT 0,
    total_tokens_used integer DEFAULT 0,
    total_cost_usd numeric(10,6) DEFAULT '0'::numeric,
    created_at timestamp with time zone
);




--
-- Name: ai_messages; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_messages (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    metadata_json json,
    created_at timestamp with time zone,
    tool_calls json,
    tool_call_id character varying(100),
    tokens_used integer
);




--
-- Name: ai_permissions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_permissions (
    id uuid NOT NULL,
    role_id uuid NOT NULL,
    pillar character varying(20) NOT NULL,
    tool_category character varying(50),
    tool_name character varying(100),
    permission character varying(20) NOT NULL,
    created_at timestamp with time zone
);




--
-- Name: ai_sessions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    title character varying(255),
    context_context_json json,
    created_at timestamp with time zone,
    pillar character varying(20) DEFAULT 'revive'::character varying NOT NULL,
    revive_mode character varying(20),
    context_type character varying(50),
    context_id uuid,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    message_count integer,
    updated_at timestamp with time zone
);




--
-- Name: ai_tool_executions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.ai_tool_executions (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    message_id uuid,
    user_id uuid NOT NULL,
    tool_name character varying(100) NOT NULL,
    tool_category character varying(50) NOT NULL,
    arguments json NOT NULL,
    result text,
    result_status character varying(20),
    permission_required character varying(100),
    permission_granted boolean,
    execution_time_ms integer,
    created_at timestamp with time zone
);




--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);




--
-- Name: alert_clusters; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.alert_clusters (
    id uuid NOT NULL,
    cluster_key character varying(255) NOT NULL,
    alert_count integer NOT NULL,
    first_seen timestamp with time zone NOT NULL,
    last_seen timestamp with time zone NOT NULL,
    severity character varying(20) NOT NULL,
    cluster_type character varying(50) NOT NULL,
    summary text,
    is_active boolean NOT NULL,
    closed_at timestamp with time zone,
    closed_reason character varying(100),
    cluster_metadata json,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: alert_correlations; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.alert_correlations (
    id uuid NOT NULL,
    related_alert_id uuid NOT NULL,
    correlation_type character varying(50) NOT NULL,
    correlation_score double precision NOT NULL,
    status character varying(50) NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    summary character varying(255) DEFAULT 'Auto Correlation'::character varying NOT NULL
);




--
-- Name: alerts; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.alerts (
    id uuid NOT NULL,
    fingerprint character varying(100),
    "timestamp" timestamp with time zone NOT NULL,
    alert_name character varying(255) NOT NULL,
    severity character varying(50),
    instance character varying(255),
    job character varying(100),
    status character varying(20),
    labels_json json,
    annotations_json json,
    raw_alert_json json,
    matched_rule_id uuid,
    action_taken character varying(20),
    analyzed boolean,
    analyzed_at timestamp with time zone,
    analyzed_by uuid,
    llm_provider_id uuid,
    ai_analysis text,
    recommendations_json json,
    analysis_count integer,
    created_at timestamp with time zone,
    app_id uuid,
    component_id uuid,
    embedding_text text,
    embedding public.vector(1536),
    cluster_id uuid,
    clustered_at timestamp with time zone,
    correlation_id uuid
);




--
-- Name: analysis_feedback; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.analysis_feedback (
    id uuid NOT NULL,
    alert_id uuid NOT NULL,
    user_id uuid,
    helpful boolean,
    rating integer,
    accuracy character varying(30),
    what_was_missing text,
    what_actually_worked text,
    created_at timestamp with time zone,
    CONSTRAINT ck_analysis_feedback_accuracy CHECK (((accuracy IS NULL) OR ((accuracy)::text = ANY ((ARRAY['accurate'::character varying, 'partially_accurate'::character varying, 'inaccurate'::character varying])::text[])))),
    CONSTRAINT ck_analysis_feedback_rating CHECK (((rating IS NULL) OR ((rating >= 1) AND (rating <= 5))))
);




--
-- Name: api_credential_profiles; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.api_credential_profiles (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    credential_type character varying(50),
    base_url character varying(500) NOT NULL,
    auth_type character varying(30),
    auth_header character varying(100),
    token_encrypted text,
    username character varying(255),
    verify_ssl boolean,
    timeout_seconds integer,
    default_headers json,
    oauth_token_url character varying(500),
    oauth_client_id character varying(255),
    oauth_client_secret_encrypted text,
    oauth_scope text,
    tags json,
    profile_metadata json,
    enabled boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    created_by uuid,
    last_used_at timestamp with time zone
);




--
-- Name: application_components; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.application_components (
    id uuid NOT NULL,
    app_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    component_type character varying(50),
    description text,
    endpoints json,
    alert_label_matchers json,
    criticality character varying(20),
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    hostname character varying(255),
    ip_address character varying(45),
    subtype character varying(50),
    CONSTRAINT ck_components_type CHECK (((component_type)::text = ANY ((ARRAY['compute'::character varying, 'container'::character varying, 'vm'::character varying, 'database'::character varying, 'cache'::character varying, 'queue'::character varying, 'storage'::character varying, 'load_balancer'::character varying, 'firewall'::character varying, 'switch'::character varying, 'router'::character varying, 'cloud_function'::character varying, 'cloud_storage'::character varying, 'cloud_db'::character varying, 'external'::character varying, 'monitoring'::character varying, 'cdn'::character varying, 'api_gateway'::character varying])::text[])))
);




--
-- Name: application_knowledge_configs; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.application_knowledge_configs (
    id uuid NOT NULL,
    app_id uuid NOT NULL,
    git_repo_url character varying,
    git_branch character varying,
    git_auth_type character varying,
    git_token character varying,
    sync_docs boolean,
    sync_code boolean,
    doc_patterns json,
    exclude_patterns json,
    auto_sync_enabled boolean,
    sync_interval_hours integer,
    last_sync_at timestamp with time zone,
    last_sync_status character varying,
    last_sync_stats json,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: application_profiles; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.application_profiles (
    id uuid NOT NULL,
    app_id uuid NOT NULL,
    architecture_type character varying(50),
    framework character varying(100),
    language character varying(50),
    architecture_info json,
    service_mappings json,
    default_metrics json,
    slos json,
    prometheus_datasource_id uuid,
    loki_datasource_id uuid,
    tempo_datasource_id uuid,
    default_time_range character varying(20),
    log_patterns json,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT ck_app_profiles_architecture CHECK (((architecture_type)::text = ANY ((ARRAY['monolith'::character varying, 'microservices'::character varying, 'serverless'::character varying, 'hybrid'::character varying, 'other'::character varying])::text[])))
);




--
-- Name: applications; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.applications (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    display_name character varying(200),
    description text,
    team_owner character varying(100),
    criticality character varying(20),
    tech_stack json,
    alert_label_matchers json,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT ck_applications_criticality CHECK (((criticality)::text = ANY ((ARRAY['critical'::character varying, 'high'::character varying, 'medium'::character varying, 'low'::character varying])::text[])))
);




--
-- Name: apscheduler_jobs; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.apscheduler_jobs (
    id text NOT NULL,
    next_run_time double precision,
    job_state bytea
);




--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.audit_log (
    id uuid NOT NULL,
    user_id uuid,
    action character varying(50) NOT NULL,
    resource_type character varying(50),
    resource_id uuid,
    details_json json,
    ip_address character varying(45),
    created_at timestamp with time zone
);




--
-- Name: auto_analyze_rules; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.auto_analyze_rules (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    priority integer,
    condition_json json,
    alert_name_pattern character varying(255),
    severity_pattern character varying(50),
    instance_pattern character varying(255),
    job_pattern character varying(255),
    action character varying(20),
    enabled boolean,
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: blackout_windows; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.blackout_windows (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    recurrence character varying(20),
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    daily_start_time character varying(5),
    daily_end_time character varying(5),
    days_of_week integer[],
    days_of_month integer[],
    timezone character varying(50),
    applies_to character varying(20),
    applies_to_runbook_ids uuid[],
    enabled boolean,
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: change_events; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.change_events (
    id uuid NOT NULL,
    change_id character varying(255) NOT NULL,
    change_type character varying(50) NOT NULL,
    service_name character varying(255),
    description text,
    "timestamp" timestamp with time zone NOT NULL,
    source character varying(100),
    change_metadata jsonb,
    correlation_score double precision,
    impact_level character varying(20),
    created_at timestamp with time zone,
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    associated_cis jsonb,
    application character varying(255)
);




--
-- Name: change_impact_analysis; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.change_impact_analysis (
    id uuid NOT NULL,
    change_event_id uuid NOT NULL,
    incidents_after integer,
    critical_incidents integer,
    correlation_score double precision NOT NULL,
    impact_level character varying(20) NOT NULL,
    recommendation text,
    analyzed_at timestamp with time zone
);




--
-- Name: change_items; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.change_items (
    id uuid NOT NULL,
    change_set_id uuid NOT NULL,
    file_path character varying(1024) NOT NULL,
    operation character varying(50),
    old_content text,
    new_content text,
    diff_hunks json,
    status character varying(50),
    order_index integer
);




--
-- Name: change_sets; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.change_sets (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    agent_step_id uuid,
    title character varying(255),
    description text,
    status character varying(50),
    created_at timestamp with time zone,
    applied_at timestamp with time zone,
    rolled_back_at timestamp with time zone
);




--
-- Name: circuit_breakers; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.circuit_breakers (
    id uuid NOT NULL,
    scope character varying(20) NOT NULL,
    scope_id uuid,
    state character varying(20),
    failure_count integer,
    success_count integer,
    last_failure_at timestamp with time zone,
    last_success_at timestamp with time zone,
    opened_at timestamp with time zone,
    closes_at timestamp with time zone,
    failure_threshold integer,
    failure_window_minutes integer,
    open_duration_minutes integer,
    manually_opened boolean,
    manually_opened_by uuid,
    manually_opened_reason text,
    updated_at timestamp with time zone
);




--
-- Name: command_allowlist; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.command_allowlist (
    id uuid NOT NULL,
    pattern character varying(500) NOT NULL,
    pattern_type character varying(20),
    os_type character varying(10),
    description text,
    category character varying(50),
    enabled boolean,
    created_at timestamp with time zone
);




--
-- Name: command_blocklist; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.command_blocklist (
    id uuid NOT NULL,
    pattern character varying(500) NOT NULL,
    pattern_type character varying(20),
    os_type character varying(10),
    description text,
    severity character varying(20),
    enabled boolean,
    created_at timestamp with time zone
);




--
-- Name: component_dependencies; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.component_dependencies (
    id uuid NOT NULL,
    from_component_id uuid NOT NULL,
    to_component_id uuid NOT NULL,
    dependency_type character varying(20),
    failure_impact text,
    created_at timestamp with time zone,
    CONSTRAINT ck_dependencies_type CHECK (((dependency_type)::text = ANY ((ARRAY['sync'::character varying, 'async'::character varying, 'optional'::character varying])::text[])))
);




--
-- Name: credential_profiles; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.credential_profiles (
    id uuid NOT NULL,
    name character varying(120) NOT NULL,
    description text,
    username character varying(100),
    credential_type character varying(30),
    backend character varying(30),
    secret_encrypted text,
    metadata_json json,
    last_rotated timestamp with time zone,
    group_id uuid,
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: dashboard_annotations; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.dashboard_annotations (
    id character varying(36) NOT NULL,
    dashboard_id character varying(36),
    panel_id character varying(36),
    "time" timestamp without time zone NOT NULL,
    time_end timestamp without time zone,
    text text NOT NULL,
    title character varying(255),
    tags json,
    color character varying(50),
    icon character varying(50),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by character varying(255)
);




--
-- Name: dashboard_links; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.dashboard_links (
    id character varying(36) NOT NULL,
    dashboard_id character varying(36) NOT NULL,
    title character varying(255) NOT NULL,
    url character varying(512) NOT NULL,
    icon character varying(50),
    type character varying(50),
    sort_order integer,
    open_in_new_tab boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);




--
-- Name: dashboard_panels; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.dashboard_panels (
    id character varying(36) NOT NULL,
    dashboard_id character varying(36) NOT NULL,
    panel_id character varying(36) NOT NULL,
    grid_x integer,
    grid_y integer,
    grid_width integer,
    grid_height integer,
    override_time_range character varying(50),
    override_refresh_interval integer,
    display_order integer,
    row_id character varying(36)
);




--
-- Name: dashboard_permissions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.dashboard_permissions (
    id character varying(36) NOT NULL,
    dashboard_id character varying(36) NOT NULL,
    user_id character varying(36),
    role character varying(50),
    permission character varying(20) NOT NULL,
    created_at timestamp without time zone,
    created_by character varying(255)
);




--
-- Name: dashboard_snapshots; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.dashboard_snapshots (
    id character varying(36) NOT NULL,
    dashboard_id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    key character varying(64) NOT NULL,
    snapshot_data json NOT NULL,
    is_public boolean,
    expires_at timestamp without time zone,
    created_at timestamp without time zone,
    created_by character varying(255)
);




--
-- Name: dashboard_variables; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.dashboard_variables (
    id character varying(36) NOT NULL,
    dashboard_id character varying(36) NOT NULL,
    name character varying(100) NOT NULL,
    label character varying(255),
    type character varying(50) NOT NULL,
    query text,
    datasource_id character varying(36),
    regex character varying(255),
    custom_values json,
    default_value text,
    current_value text,
    multi_select boolean,
    include_all boolean,
    all_value character varying(255),
    hide integer,
    sort integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    depends_on json
);




--
-- Name: dashboards; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.dashboards (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    layout json,
    time_range character varying(50),
    refresh_interval integer,
    auto_refresh boolean,
    tags json,
    folder character varying(255),
    is_public boolean,
    is_favorite boolean,
    is_home boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by character varying(255)
);




--
-- Name: design_chunks; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.design_chunks (
    id uuid NOT NULL,
    app_id uuid,
    source_type character varying(50) NOT NULL,
    source_id uuid NOT NULL,
    chunk_index integer,
    content text NOT NULL,
    content_type character varying(50) NOT NULL,
    embedding public.vector(1536),
    chunk_metadata jsonb,
    created_at timestamp with time zone,
    CONSTRAINT ck_design_chunks_content_type CHECK (((content_type)::text = ANY ((ARRAY['text'::character varying, 'image_description'::character varying, 'ocr'::character varying, 'component_info'::character varying, 'failure_mode'::character varying, 'troubleshooting'::character varying, 'dependency_info'::character varying])::text[]))),
    CONSTRAINT ck_design_chunks_source_type CHECK (((source_type)::text = ANY ((ARRAY['document'::character varying, 'image'::character varying, 'component'::character varying, 'alert_history'::character varying])::text[])))
);




--
-- Name: design_documents; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.design_documents (
    id uuid NOT NULL,
    app_id uuid,
    title character varying(500) NOT NULL,
    slug character varying(500),
    doc_type character varying(50) NOT NULL,
    format character varying(20) NOT NULL,
    raw_content text,
    source_url character varying(1000),
    source_type character varying(50),
    version integer,
    status character varying(20),
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT ck_design_documents_doc_type CHECK (((doc_type)::text = ANY ((ARRAY['architecture'::character varying, 'api_spec'::character varying, 'runbook'::character varying, 'sop'::character varying, 'troubleshooting'::character varying, 'design_doc'::character varying, 'postmortem'::character varying, 'onboarding'::character varying, 'deployment'::character varying, 'config'::character varying])::text[]))),
    CONSTRAINT ck_design_documents_format CHECK (((format)::text = ANY ((ARRAY['markdown'::character varying, 'pdf'::character varying, 'html'::character varying, 'yaml'::character varying, 'text'::character varying, 'image'::character varying])::text[])))
);




--
-- Name: design_images; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.design_images (
    id uuid NOT NULL,
    app_id uuid,
    document_id uuid,
    title character varying(500) NOT NULL,
    image_type character varying(50) NOT NULL,
    storage_path character varying(1000) NOT NULL,
    thumbnail_path character varying(1000),
    file_size_bytes integer,
    mime_type character varying(100),
    ai_description text,
    extracted_text text,
    identified_components jsonb,
    identified_connections jsonb,
    failure_scenarios jsonb,
    processing_status character varying(20),
    processed_at timestamp with time zone,
    created_by uuid,
    created_at timestamp with time zone,
    CONSTRAINT ck_design_images_image_type CHECK (((image_type)::text = ANY ((ARRAY['architecture'::character varying, 'flowchart'::character varying, 'sequence'::character varying, 'erd'::character varying, 'network'::character varying, 'deployment'::character varying, 'component'::character varying, 'other'::character varying])::text[])))
);




--
-- Name: execution_outcomes; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.execution_outcomes (
    id uuid NOT NULL,
    execution_id uuid NOT NULL,
    alert_id uuid,
    user_id uuid,
    resolved_issue boolean,
    resolution_type character varying(30),
    time_to_resolution_minutes integer,
    recommendation_followed boolean,
    manual_steps_taken text,
    improvement_suggestion text,
    created_at timestamp with time zone,
    CONSTRAINT ck_execution_outcomes_resolution_type CHECK (((resolution_type IS NULL) OR ((resolution_type)::text = ANY ((ARRAY['full'::character varying, 'partial'::character varying, 'no_effect'::character varying, 'made_worse'::character varying])::text[])))),
    CONSTRAINT ck_execution_outcomes_time_positive CHECK (((time_to_resolution_minutes IS NULL) OR (time_to_resolution_minutes >= 0)))
);




--
-- Name: execution_rate_limits; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.execution_rate_limits (
    id uuid NOT NULL,
    scope character varying(20) NOT NULL,
    scope_id uuid,
    window_start timestamp with time zone NOT NULL,
    window_end timestamp with time zone NOT NULL,
    execution_count integer,
    last_execution_at timestamp with time zone
);




--
-- Name: failure_patterns; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.failure_patterns (
    id uuid NOT NULL,
    pattern_name character varying(255) NOT NULL,
    pattern_description text,
    root_cause_type character varying(100) NOT NULL,
    symptoms jsonb,
    resolution_steps jsonb,
    occurrence_count integer,
    last_seen_at timestamp with time zone,
    created_at timestamp with time zone
);




--
-- Name: file_backups; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.file_backups (
    id uuid NOT NULL,
    file_version_id uuid NOT NULL,
    backup_path character varying(1024) NOT NULL,
    created_at timestamp with time zone,
    expires_at timestamp with time zone
);




--
-- Name: file_versions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.file_versions (
    id uuid NOT NULL,
    session_id uuid,
    server_id uuid,
    file_path character varying(1024) NOT NULL,
    content text,
    content_hash character varying(64),
    version_number integer,
    created_by character varying(50),
    created_at timestamp with time zone
);




--
-- Name: grafana_datasources; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.grafana_datasources (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    datasource_type character varying(50) NOT NULL,
    url character varying(512) NOT NULL,
    description text,
    auth_type character varying(50),
    username character varying(255),
    password character varying(512),
    bearer_token character varying(512),
    timeout integer,
    is_default boolean,
    is_enabled boolean,
    config_json json,
    custom_headers json,
    last_health_check timestamp with time zone,
    is_healthy boolean,
    health_message text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    created_by character varying(255),
    CONSTRAINT ck_datasources_auth_type CHECK (((auth_type)::text = ANY ((ARRAY['none'::character varying, 'basic'::character varying, 'bearer'::character varying, 'oauth2'::character varying, 'api_key'::character varying])::text[]))),
    CONSTRAINT ck_datasources_type CHECK (((datasource_type)::text = ANY ((ARRAY['loki'::character varying, 'tempo'::character varying, 'prometheus'::character varying, 'mimir'::character varying, 'alertmanager'::character varying, 'jaeger'::character varying, 'zipkin'::character varying, 'elasticsearch'::character varying])::text[])))
);




--
-- Name: group_members; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.group_members (
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    user_id uuid NOT NULL,
    source character varying(20),
    joined_at timestamp with time zone
);




--
-- Name: groups; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.groups (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    role_id uuid,
    ad_group_dn character varying(500),
    sync_enabled boolean,
    last_synced timestamp with time zone,
    is_active boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    created_by uuid
);




--
-- Name: incident_metrics; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.incident_metrics (
    id uuid NOT NULL,
    alert_id uuid NOT NULL,
    service_name character varying(255),
    severity character varying(20),
    incident_started timestamp with time zone NOT NULL,
    resolution_type character varying(50),
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    incident_detected timestamp with time zone NOT NULL,
    incident_acknowledged timestamp with time zone,
    incident_engaged timestamp with time zone,
    incident_resolved timestamp with time zone,
    time_to_detect integer,
    time_to_acknowledge integer,
    time_to_engage integer,
    time_to_resolve integer,
    assigned_to uuid
);




--
-- Name: iteration_loops; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.iteration_loops (
    id uuid NOT NULL,
    agent_task_id uuid NOT NULL,
    iteration_number integer NOT NULL,
    command text,
    output text,
    exit_code integer,
    error_detected boolean,
    error_type character varying(255),
    error_analysis text,
    fix_proposed text,
    created_at timestamp without time zone
);




--
-- Name: itsm_integrations; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.itsm_integrations (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    connector_type character varying(50) NOT NULL,
    config_encrypted text NOT NULL,
    is_enabled boolean NOT NULL,
    last_sync timestamp with time zone,
    last_sync_status character varying(50),
    last_error text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: knowledge_sync_history; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.knowledge_sync_history (
    id uuid NOT NULL,
    started_at timestamp with time zone,
    status character varying(50) DEFAULT 'running'::character varying,
    documents_added integer DEFAULT 0,
    documents_updated integer DEFAULT 0,
    documents_deleted integer DEFAULT 0,
    chunks_created integer DEFAULT 0,
    created_at timestamp with time zone,
    source_id uuid
);




--
-- Name: llm_providers; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.llm_providers (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    provider_type character varying(50) NOT NULL,
    model_id character varying(100) NOT NULL,
    api_key_encrypted text,
    api_base_url character varying(255),
    is_default boolean,
    is_enabled boolean,
    config_json json,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: panel_rows; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.panel_rows (
    id character varying(36) NOT NULL,
    dashboard_id character varying(36) NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    "order" integer,
    is_collapsed boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);




--
-- Name: playlist_items; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.playlist_items (
    id character varying(36) NOT NULL,
    playlist_id character varying(36) NOT NULL,
    dashboard_id character varying(36) NOT NULL,
    "order" integer,
    custom_interval integer
);




--
-- Name: playlists; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.playlists (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    "interval" integer,
    loop boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by character varying(255)
);




--
-- Name: prometheus_datasources; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.prometheus_datasources (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    url character varying(512) NOT NULL,
    description text,
    auth_type character varying(50),
    username character varying(255),
    password character varying(512),
    bearer_token character varying(512),
    timeout integer,
    is_default boolean,
    is_enabled boolean,
    custom_headers json,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by character varying(255)
);




--
-- Name: prometheus_panels; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.prometheus_panels (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    datasource_id character varying(36) NOT NULL,
    promql_query text NOT NULL,
    legend_format character varying(255),
    time_range character varying(50),
    refresh_interval integer,
    step character varying(20),
    panel_type character varying(50),
    visualization_config json,
    thresholds json,
    tags json,
    is_public boolean,
    is_template boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by character varying(255)
);




--
-- Name: query_history; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.query_history (
    id character varying(36) NOT NULL,
    query text NOT NULL,
    datasource_id character varying(36),
    dashboard_id character varying(36),
    panel_id character varying(36),
    time_range character varying(50),
    execution_time_ms integer,
    series_count integer,
    status character varying(20),
    error_message text,
    executed_by character varying(255),
    is_favorite boolean,
    executed_at timestamp without time zone
);




--
-- Name: roles; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.roles (
    id uuid NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    permissions json NOT NULL,
    is_custom boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: runbook_acls; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.runbook_acls (
    id uuid NOT NULL,
    runbook_id uuid NOT NULL,
    group_id uuid NOT NULL,
    can_view boolean,
    can_edit boolean,
    can_execute boolean,
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: runbook_clicks; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.runbook_clicks (
    id uuid NOT NULL,
    source character varying(50) NOT NULL,
    clicked_at timestamp with time zone,
    runbook_id uuid,
    session_id uuid,
    user_id uuid
);




--
-- Name: runbook_executions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.runbook_executions (
    id uuid NOT NULL,
    runbook_id uuid NOT NULL,
    runbook_version integer NOT NULL,
    runbook_snapshot_json json,
    alert_id uuid,
    server_id uuid,
    trigger_id uuid,
    execution_mode character varying(20),
    status character varying(20),
    dry_run boolean,
    triggered_by uuid,
    triggered_by_system boolean,
    approval_required boolean,
    approval_token character varying(64),
    approval_requested_at timestamp with time zone,
    approval_expires_at timestamp with time zone,
    approved_by uuid,
    approved_at timestamp with time zone,
    rejection_reason text,
    queued_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    result_summary text,
    error_message text,
    steps_total integer,
    steps_completed integer,
    steps_failed integer,
    rollback_executed boolean,
    rollback_execution_id uuid,
    variables_json json
);




--
-- Name: runbook_steps; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.runbook_steps (
    id uuid NOT NULL,
    runbook_id uuid NOT NULL,
    step_order integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    step_type character varying(20),
    command_linux text,
    command_windows text,
    target_os character varying(10),
    api_credential_profile_id uuid,
    api_method character varying(10),
    api_endpoint text,
    api_headers_json json,
    api_body text,
    api_body_type character varying(30),
    api_query_params_json json,
    api_expected_status_codes integer[],
    api_response_extract_json json,
    api_follow_redirects boolean,
    api_retry_on_status_codes integer[],
    timeout_seconds integer,
    requires_elevation boolean,
    working_directory character varying(255),
    environment_json json,
    continue_on_fail boolean,
    retry_count integer,
    retry_delay_seconds integer,
    expected_exit_code integer,
    expected_output_pattern character varying(500),
    rollback_command_linux text,
    rollback_command_windows text,
    output_variable character varying(100),
    output_extract_pattern character varying(500),
    run_if_variable character varying(100),
    run_if_value character varying(500)
);




--
-- Name: runbook_triggers; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.runbook_triggers (
    id uuid NOT NULL,
    runbook_id uuid NOT NULL,
    alert_name_pattern character varying(255),
    severity_pattern character varying(50),
    instance_pattern character varying(255),
    job_pattern character varying(255),
    label_matchers_json json,
    annotation_matchers_json json,
    min_duration_seconds integer,
    min_occurrences integer,
    priority integer,
    enabled boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: runbooks; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.runbooks (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    category character varying(50),
    tags character varying[],
    enabled boolean,
    auto_execute boolean,
    approval_required boolean,
    approval_roles character varying[],
    approval_timeout_minutes integer,
    max_executions_per_hour integer,
    cooldown_minutes integer,
    default_server_id uuid,
    target_os_filter character varying[],
    target_from_alert boolean,
    target_alert_label character varying(50),
    version integer,
    source character varying(20),
    source_path character varying(255),
    checksum character varying(64),
    notifications_json json,
    documentation_url character varying(500),
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: schedule_execution_history; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.schedule_execution_history (
    id uuid NOT NULL,
    scheduled_job_id uuid NOT NULL,
    runbook_execution_id uuid,
    scheduled_at timestamp with time zone NOT NULL,
    executed_at timestamp with time zone,
    completed_at timestamp with time zone,
    status character varying(50) NOT NULL,
    error_message text,
    duration_ms integer,
    created_at timestamp with time zone
);




--
-- Name: scheduled_jobs; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.scheduled_jobs (
    id uuid NOT NULL,
    runbook_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    schedule_type character varying(50) NOT NULL,
    cron_expression character varying(100),
    interval_seconds integer,
    start_date timestamp with time zone,
    end_date timestamp with time zone,
    timezone character varying(50),
    target_server_id uuid,
    execution_params json,
    max_instances integer,
    misfire_grace_time integer,
    enabled boolean,
    last_run_at timestamp with time zone,
    last_run_status character varying(50),
    next_run_at timestamp with time zone,
    run_count integer,
    failure_count integer,
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT valid_schedule_type CHECK (((schedule_type)::text = ANY ((ARRAY['cron'::character varying, 'interval'::character varying, 'date'::character varying])::text[])))
);




--
-- Name: server_credentials; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.server_credentials (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    hostname character varying(255) NOT NULL,
    port integer,
    username character varying(100) NOT NULL,
    os_type character varying(20),
    protocol character varying(20),
    auth_type character varying(20),
    ssh_key_encrypted text,
    password_encrypted text,
    credential_source character varying(30),
    credential_profile_id uuid,
    credential_metadata json,
    winrm_transport character varying(20),
    winrm_use_ssl boolean,
    winrm_cert_validation boolean,
    domain character varying(100),
    api_base_url character varying(500),
    api_auth_type character varying(30),
    api_auth_header character varying(100),
    api_token_encrypted text,
    api_verify_ssl boolean,
    api_timeout_seconds integer,
    api_headers_json json,
    api_metadata_json json,
    environment character varying(50),
    tags json,
    group_id uuid,
    last_connection_test timestamp with time zone,
    last_connection_status character varying(20),
    last_connection_error text,
    created_by uuid,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);




--
-- Name: server_groups; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.server_groups (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    parent_id uuid,
    path character varying(255),
    created_at timestamp with time zone
);




--
-- Name: solution_outcomes; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.solution_outcomes (
    id uuid NOT NULL,
    session_id uuid,
    problem_description text NOT NULL,
    problem_embedding public.vector(1536),
    alert_id uuid,
    server_id uuid,
    solution_type character varying(50) NOT NULL,
    solution_reference text,
    solution_summary text,
    success boolean,
    auto_detected boolean,
    user_feedback text,
    feedback_timestamp timestamp with time zone,
    created_at timestamp with time zone,
    CONSTRAINT ck_solution_outcomes_solution_type CHECK (((solution_type)::text = ANY ((ARRAY['runbook'::character varying, 'command'::character varying, 'knowledge'::character varying, 'agent_suggestion'::character varying, 'session'::character varying])::text[])))
);




--
-- Name: step_executions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.step_executions (
    id uuid NOT NULL,
    execution_id uuid NOT NULL,
    step_id uuid,
    step_order integer NOT NULL,
    step_name character varying(100) NOT NULL,
    status character varying(20),
    command_executed text,
    stdout text,
    stderr text,
    exit_code integer,
    http_status_code integer,
    http_response_headers_json json,
    http_response_body text,
    http_request_url text,
    http_request_method character varying(10),
    extracted_values_json json,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    duration_ms integer,
    retry_attempt integer,
    error_type character varying(50),
    error_message text
);




--
-- Name: system_config; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.system_config (
    key character varying(50) NOT NULL,
    value_json json NOT NULL,
    updated_at timestamp with time zone,
    updated_by uuid
);




--
-- Name: terminal_sessions; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.terminal_sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    server_credential_id uuid NOT NULL,
    alert_id uuid,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    recording_path character varying(255)
);




--
-- Name: users; Type: TABLE; Schema: public; Owner: aiops
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(255),
    full_name character varying(100),
    password_hash character varying(255) NOT NULL,
    role character varying(20),
    default_llm_provider_id uuid,
    is_active boolean,
    created_at timestamp with time zone,
    last_login timestamp with time zone,
    ai_preferences json
);




--
-- Name: agent_rate_limits id; Type: DEFAULT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_rate_limits ALTER COLUMN id SET DEFAULT nextval('public.agent_rate_limits_id_seq'::regclass);


--
-- Name: action_proposals action_proposals_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.action_proposals
    ADD CONSTRAINT action_proposals_pkey PRIMARY KEY (id);


--
-- Name: agent_audit_logs agent_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_audit_logs
    ADD CONSTRAINT agent_audit_logs_pkey PRIMARY KEY (id);


--
-- Name: agent_pools agent_pools_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_pools
    ADD CONSTRAINT agent_pools_pkey PRIMARY KEY (id);


--
-- Name: agent_rate_limits agent_rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_rate_limits
    ADD CONSTRAINT agent_rate_limits_pkey PRIMARY KEY (id);


--
-- Name: agent_rate_limits agent_rate_limits_user_id_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_rate_limits
    ADD CONSTRAINT agent_rate_limits_user_id_key UNIQUE (user_id);


--
-- Name: agent_sessions agent_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_sessions
    ADD CONSTRAINT agent_sessions_pkey PRIMARY KEY (id);


--
-- Name: agent_steps agent_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_steps
    ADD CONSTRAINT agent_steps_pkey PRIMARY KEY (id);


--
-- Name: agent_tasks agent_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_tasks
    ADD CONSTRAINT agent_tasks_pkey PRIMARY KEY (id);


--
-- Name: ai_action_confirmations ai_action_confirmations_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_action_confirmations
    ADD CONSTRAINT ai_action_confirmations_pkey PRIMARY KEY (id);


--
-- Name: ai_feedback ai_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_feedback
    ADD CONSTRAINT ai_feedback_pkey PRIMARY KEY (id);


--
-- Name: ai_helper_audit_logs ai_helper_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_helper_audit_logs
    ADD CONSTRAINT ai_helper_audit_logs_pkey PRIMARY KEY (id);


--
-- Name: ai_helper_sessions ai_helper_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_helper_sessions
    ADD CONSTRAINT ai_helper_sessions_pkey PRIMARY KEY (id);


--
-- Name: ai_messages ai_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_messages
    ADD CONSTRAINT ai_messages_pkey PRIMARY KEY (id);


--
-- Name: ai_permissions ai_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_permissions
    ADD CONSTRAINT ai_permissions_pkey PRIMARY KEY (id);


--
-- Name: ai_sessions ai_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_sessions
    ADD CONSTRAINT ai_sessions_pkey PRIMARY KEY (id);


--
-- Name: ai_tool_executions ai_tool_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_tool_executions
    ADD CONSTRAINT ai_tool_executions_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: alert_clusters alert_clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alert_clusters
    ADD CONSTRAINT alert_clusters_pkey PRIMARY KEY (id);


--
-- Name: alert_correlations alert_correlations_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alert_correlations
    ADD CONSTRAINT alert_correlations_pkey PRIMARY KEY (id);


--
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (id);


--
-- Name: analysis_feedback analysis_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.analysis_feedback
    ADD CONSTRAINT analysis_feedback_pkey PRIMARY KEY (id);


--
-- Name: api_credential_profiles api_credential_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.api_credential_profiles
    ADD CONSTRAINT api_credential_profiles_pkey PRIMARY KEY (id);


--
-- Name: application_components application_components_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_components
    ADD CONSTRAINT application_components_pkey PRIMARY KEY (id);


--
-- Name: application_knowledge_configs application_knowledge_configs_app_id_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_knowledge_configs
    ADD CONSTRAINT application_knowledge_configs_app_id_key UNIQUE (app_id);


--
-- Name: application_knowledge_configs application_knowledge_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_knowledge_configs
    ADD CONSTRAINT application_knowledge_configs_pkey PRIMARY KEY (id);


--
-- Name: application_profiles application_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_profiles
    ADD CONSTRAINT application_profiles_pkey PRIMARY KEY (id);


--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);


--
-- Name: apscheduler_jobs apscheduler_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.apscheduler_jobs
    ADD CONSTRAINT apscheduler_jobs_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: auto_analyze_rules auto_analyze_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.auto_analyze_rules
    ADD CONSTRAINT auto_analyze_rules_pkey PRIMARY KEY (id);


--
-- Name: blackout_windows blackout_windows_name_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.blackout_windows
    ADD CONSTRAINT blackout_windows_name_key UNIQUE (name);


--
-- Name: blackout_windows blackout_windows_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.blackout_windows
    ADD CONSTRAINT blackout_windows_pkey PRIMARY KEY (id);


--
-- Name: change_events change_events_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_events
    ADD CONSTRAINT change_events_pkey PRIMARY KEY (id);


--
-- Name: change_impact_analysis change_impact_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_impact_analysis
    ADD CONSTRAINT change_impact_analysis_pkey PRIMARY KEY (id);


--
-- Name: change_items change_items_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_items
    ADD CONSTRAINT change_items_pkey PRIMARY KEY (id);


--
-- Name: change_sets change_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_sets
    ADD CONSTRAINT change_sets_pkey PRIMARY KEY (id);


--
-- Name: circuit_breakers circuit_breakers_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.circuit_breakers
    ADD CONSTRAINT circuit_breakers_pkey PRIMARY KEY (id);


--
-- Name: command_allowlist command_allowlist_pattern_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.command_allowlist
    ADD CONSTRAINT command_allowlist_pattern_key UNIQUE (pattern);


--
-- Name: command_allowlist command_allowlist_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.command_allowlist
    ADD CONSTRAINT command_allowlist_pkey PRIMARY KEY (id);


--
-- Name: command_blocklist command_blocklist_pattern_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.command_blocklist
    ADD CONSTRAINT command_blocklist_pattern_key UNIQUE (pattern);


--
-- Name: command_blocklist command_blocklist_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.command_blocklist
    ADD CONSTRAINT command_blocklist_pkey PRIMARY KEY (id);


--
-- Name: component_dependencies component_dependencies_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.component_dependencies
    ADD CONSTRAINT component_dependencies_pkey PRIMARY KEY (id);


--
-- Name: credential_profiles credential_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.credential_profiles
    ADD CONSTRAINT credential_profiles_pkey PRIMARY KEY (id);


--
-- Name: dashboard_annotations dashboard_annotations_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_annotations
    ADD CONSTRAINT dashboard_annotations_pkey PRIMARY KEY (id);


--
-- Name: dashboard_links dashboard_links_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_links
    ADD CONSTRAINT dashboard_links_pkey PRIMARY KEY (id);


--
-- Name: dashboard_panels dashboard_panels_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_panels
    ADD CONSTRAINT dashboard_panels_pkey PRIMARY KEY (id);


--
-- Name: dashboard_permissions dashboard_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_permissions
    ADD CONSTRAINT dashboard_permissions_pkey PRIMARY KEY (id);


--
-- Name: dashboard_snapshots dashboard_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_snapshots
    ADD CONSTRAINT dashboard_snapshots_pkey PRIMARY KEY (id);


--
-- Name: dashboard_variables dashboard_variables_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_variables
    ADD CONSTRAINT dashboard_variables_pkey PRIMARY KEY (id);


--
-- Name: dashboards dashboards_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboards
    ADD CONSTRAINT dashboards_pkey PRIMARY KEY (id);


--
-- Name: design_chunks design_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_chunks
    ADD CONSTRAINT design_chunks_pkey PRIMARY KEY (id);


--
-- Name: design_documents design_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_documents
    ADD CONSTRAINT design_documents_pkey PRIMARY KEY (id);


--
-- Name: design_images design_images_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_images
    ADD CONSTRAINT design_images_pkey PRIMARY KEY (id);


--
-- Name: execution_outcomes execution_outcomes_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.execution_outcomes
    ADD CONSTRAINT execution_outcomes_pkey PRIMARY KEY (id);


--
-- Name: execution_rate_limits execution_rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.execution_rate_limits
    ADD CONSTRAINT execution_rate_limits_pkey PRIMARY KEY (id);


--
-- Name: failure_patterns failure_patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.failure_patterns
    ADD CONSTRAINT failure_patterns_pkey PRIMARY KEY (id);


--
-- Name: file_backups file_backups_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.file_backups
    ADD CONSTRAINT file_backups_pkey PRIMARY KEY (id);


--
-- Name: file_versions file_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.file_versions
    ADD CONSTRAINT file_versions_pkey PRIMARY KEY (id);


--
-- Name: grafana_datasources grafana_datasources_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.grafana_datasources
    ADD CONSTRAINT grafana_datasources_pkey PRIMARY KEY (id);


--
-- Name: group_members group_members_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.group_members
    ADD CONSTRAINT group_members_pkey PRIMARY KEY (id);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: incident_metrics incident_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.incident_metrics
    ADD CONSTRAINT incident_metrics_pkey PRIMARY KEY (id);


--
-- Name: iteration_loops iteration_loops_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.iteration_loops
    ADD CONSTRAINT iteration_loops_pkey PRIMARY KEY (id);


--
-- Name: itsm_integrations itsm_integrations_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.itsm_integrations
    ADD CONSTRAINT itsm_integrations_pkey PRIMARY KEY (id);


--
-- Name: knowledge_sync_history knowledge_sync_history_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.knowledge_sync_history
    ADD CONSTRAINT knowledge_sync_history_pkey PRIMARY KEY (id);


--
-- Name: llm_providers llm_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.llm_providers
    ADD CONSTRAINT llm_providers_pkey PRIMARY KEY (id);


--
-- Name: panel_rows panel_rows_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.panel_rows
    ADD CONSTRAINT panel_rows_pkey PRIMARY KEY (id);


--
-- Name: playlist_items playlist_items_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.playlist_items
    ADD CONSTRAINT playlist_items_pkey PRIMARY KEY (id);


--
-- Name: playlists playlists_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.playlists
    ADD CONSTRAINT playlists_pkey PRIMARY KEY (id);


--
-- Name: prometheus_datasources prometheus_datasources_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.prometheus_datasources
    ADD CONSTRAINT prometheus_datasources_pkey PRIMARY KEY (id);


--
-- Name: prometheus_panels prometheus_panels_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.prometheus_panels
    ADD CONSTRAINT prometheus_panels_pkey PRIMARY KEY (id);


--
-- Name: query_history query_history_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.query_history
    ADD CONSTRAINT query_history_pkey PRIMARY KEY (id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: runbook_acls runbook_acls_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_acls
    ADD CONSTRAINT runbook_acls_pkey PRIMARY KEY (id);


--
-- Name: runbook_clicks runbook_clicks_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_clicks
    ADD CONSTRAINT runbook_clicks_pkey PRIMARY KEY (id);


--
-- Name: runbook_executions runbook_executions_approval_token_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_approval_token_key UNIQUE (approval_token);


--
-- Name: runbook_executions runbook_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_pkey PRIMARY KEY (id);


--
-- Name: runbook_steps runbook_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_steps
    ADD CONSTRAINT runbook_steps_pkey PRIMARY KEY (id);


--
-- Name: runbook_triggers runbook_triggers_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_triggers
    ADD CONSTRAINT runbook_triggers_pkey PRIMARY KEY (id);


--
-- Name: runbooks runbooks_name_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbooks
    ADD CONSTRAINT runbooks_name_key UNIQUE (name);


--
-- Name: runbooks runbooks_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbooks
    ADD CONSTRAINT runbooks_pkey PRIMARY KEY (id);


--
-- Name: schedule_execution_history schedule_execution_history_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.schedule_execution_history
    ADD CONSTRAINT schedule_execution_history_pkey PRIMARY KEY (id);


--
-- Name: scheduled_jobs scheduled_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.scheduled_jobs
    ADD CONSTRAINT scheduled_jobs_pkey PRIMARY KEY (id);


--
-- Name: server_credentials server_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.server_credentials
    ADD CONSTRAINT server_credentials_pkey PRIMARY KEY (id);


--
-- Name: server_groups server_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.server_groups
    ADD CONSTRAINT server_groups_pkey PRIMARY KEY (id);


--
-- Name: solution_outcomes solution_outcomes_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.solution_outcomes
    ADD CONSTRAINT solution_outcomes_pkey PRIMARY KEY (id);


--
-- Name: step_executions step_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.step_executions
    ADD CONSTRAINT step_executions_pkey PRIMARY KEY (id);


--
-- Name: system_config system_config_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_pkey PRIMARY KEY (key);


--
-- Name: terminal_sessions terminal_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.terminal_sessions
    ADD CONSTRAINT terminal_sessions_pkey PRIMARY KEY (id);


--
-- Name: ai_permissions uq_ai_permission_role_tool; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_permissions
    ADD CONSTRAINT uq_ai_permission_role_tool UNIQUE (role_id, pillar, tool_category, tool_name);


--
-- Name: circuit_breakers uq_circuit_breaker_scope; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.circuit_breakers
    ADD CONSTRAINT uq_circuit_breaker_scope UNIQUE (scope, scope_id);


--
-- Name: group_members uq_group_member; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.group_members
    ADD CONSTRAINT uq_group_member UNIQUE (group_id, user_id);


--
-- Name: incident_metrics uq_incident_metrics_alert_id; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.incident_metrics
    ADD CONSTRAINT uq_incident_metrics_alert_id UNIQUE (alert_id);


--
-- Name: execution_rate_limits uq_rate_limit_window; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.execution_rate_limits
    ADD CONSTRAINT uq_rate_limit_window UNIQUE (scope, scope_id, window_start);


--
-- Name: runbook_acls uq_runbook_group_acl; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_acls
    ADD CONSTRAINT uq_runbook_group_acl UNIQUE (runbook_id, group_id);


--
-- Name: runbook_steps uq_runbook_step_order; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_steps
    ADD CONSTRAINT uq_runbook_step_order UNIQUE (runbook_id, step_order);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: design_chunks_metadata_idx; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX design_chunks_metadata_idx ON public.design_chunks USING gin (chunk_metadata);


--
-- Name: design_chunks_source_idx; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX design_chunks_source_idx ON public.design_chunks USING btree (source_type, source_id);


--
-- Name: idx_alert_correlations_correlation_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_alert_correlations_correlation_type ON public.alert_correlations USING btree (correlation_type);


--
-- Name: idx_alert_correlations_related_alert_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_alert_correlations_related_alert_id ON public.alert_correlations USING btree (related_alert_id);


--
-- Name: idx_allowlist_enabled_os; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_allowlist_enabled_os ON public.command_allowlist USING btree (enabled, os_type);


--
-- Name: idx_analysis_feedback_alert_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_analysis_feedback_alert_id ON public.analysis_feedback USING btree (alert_id);


--
-- Name: idx_analysis_feedback_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_analysis_feedback_created_at ON public.analysis_feedback USING btree (created_at);


--
-- Name: idx_analysis_feedback_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_analysis_feedback_user_id ON public.analysis_feedback USING btree (user_id);


--
-- Name: idx_audit_action; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_audit_action ON public.agent_audit_logs USING btree (action);


--
-- Name: idx_audit_session; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_audit_session ON public.agent_audit_logs USING btree (session_id);


--
-- Name: idx_audit_user_created; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_audit_user_created ON public.agent_audit_logs USING btree (user_id, created_at);


--
-- Name: idx_blackout_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_blackout_enabled ON public.blackout_windows USING btree (enabled);


--
-- Name: idx_blocklist_enabled_os; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_blocklist_enabled_os ON public.command_blocklist USING btree (enabled, os_type);


--
-- Name: idx_circuit_breaker_state; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_circuit_breaker_state ON public.circuit_breakers USING btree (state);


--
-- Name: idx_execution_outcomes_alert_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_execution_outcomes_alert_id ON public.execution_outcomes USING btree (alert_id);


--
-- Name: idx_execution_outcomes_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_execution_outcomes_created_at ON public.execution_outcomes USING btree (created_at);


--
-- Name: idx_execution_outcomes_execution_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_execution_outcomes_execution_id ON public.execution_outcomes USING btree (execution_id);


--
-- Name: idx_execution_outcomes_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_execution_outcomes_user_id ON public.execution_outcomes USING btree (user_id);


--
-- Name: idx_executions_alert; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_executions_alert ON public.runbook_executions USING btree (alert_id);


--
-- Name: idx_executions_approval_token; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_executions_approval_token ON public.runbook_executions USING btree (approval_token);


--
-- Name: idx_executions_queued_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_executions_queued_at ON public.runbook_executions USING btree (queued_at);


--
-- Name: idx_executions_runbook_status; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_executions_runbook_status ON public.runbook_executions USING btree (runbook_id, status);


--
-- Name: idx_executions_status; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_executions_status ON public.runbook_executions USING btree (status);


--
-- Name: idx_rate_limit_scope_window; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_rate_limit_scope_window ON public.execution_rate_limits USING btree (scope, scope_id, window_start);


--
-- Name: idx_runbook_acl_group; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_runbook_acl_group ON public.runbook_acls USING btree (group_id);


--
-- Name: idx_runbook_acl_runbook; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_runbook_acl_runbook ON public.runbook_acls USING btree (runbook_id);


--
-- Name: idx_runbook_steps_runbook_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_runbook_steps_runbook_id ON public.runbook_steps USING btree (runbook_id);


--
-- Name: idx_runbook_steps_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_runbook_steps_type ON public.runbook_steps USING btree (step_type);


--
-- Name: idx_runbooks_category; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_runbooks_category ON public.runbooks USING btree (category);


--
-- Name: idx_runbooks_enabled_auto; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_runbooks_enabled_auto ON public.runbooks USING btree (enabled, auto_execute);


--
-- Name: idx_step_executions_execution_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_step_executions_execution_id ON public.step_executions USING btree (execution_id);


--
-- Name: idx_step_executions_status; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_step_executions_status ON public.step_executions USING btree (status);


--
-- Name: idx_triggers_alert_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_triggers_alert_name ON public.runbook_triggers USING btree (alert_name_pattern);


--
-- Name: idx_triggers_enabled_priority; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX idx_triggers_enabled_priority ON public.runbook_triggers USING btree (enabled, priority);


--
-- Name: ix_agent_audit_logs_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_agent_audit_logs_created_at ON public.agent_audit_logs USING btree (created_at);


--
-- Name: ix_agent_rate_limits_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_agent_rate_limits_user_id ON public.agent_rate_limits USING btree (user_id);


--
-- Name: ix_alert_clusters_cluster_key; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_alert_clusters_cluster_key ON public.alert_clusters USING btree (cluster_key);


--
-- Name: ix_alert_clusters_first_seen; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alert_clusters_first_seen ON public.alert_clusters USING btree (first_seen);


--
-- Name: ix_alert_clusters_is_active; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alert_clusters_is_active ON public.alert_clusters USING btree (is_active);


--
-- Name: ix_alert_clusters_last_seen; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alert_clusters_last_seen ON public.alert_clusters USING btree (last_seen);


--
-- Name: ix_alert_clusters_severity; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alert_clusters_severity ON public.alert_clusters USING btree (severity);


--
-- Name: ix_alert_correlations_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alert_correlations_created_at ON public.alert_correlations USING btree (created_at);


--
-- Name: ix_alerts_action_taken; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_action_taken ON public.alerts USING btree (action_taken);


--
-- Name: ix_alerts_alert_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_alert_name ON public.alerts USING btree (alert_name);


--
-- Name: ix_alerts_analyzed; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_analyzed ON public.alerts USING btree (analyzed);


--
-- Name: ix_alerts_app_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_app_id ON public.alerts USING btree (app_id);


--
-- Name: ix_alerts_cluster_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_cluster_id ON public.alerts USING btree (cluster_id);


--
-- Name: ix_alerts_component_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_component_id ON public.alerts USING btree (component_id);


--
-- Name: ix_alerts_correlation_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_correlation_id ON public.alerts USING btree (correlation_id);


--
-- Name: ix_alerts_fingerprint; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_fingerprint ON public.alerts USING btree (fingerprint);


--
-- Name: ix_alerts_severity; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_severity ON public.alerts USING btree (severity);


--
-- Name: ix_alerts_status; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_alerts_status ON public.alerts USING btree (status);


--
-- Name: ix_analysis_feedback_alert_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_analysis_feedback_alert_id ON public.analysis_feedback USING btree (alert_id);


--
-- Name: ix_analysis_feedback_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_analysis_feedback_created_at ON public.analysis_feedback USING btree (created_at);


--
-- Name: ix_analysis_feedback_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_analysis_feedback_user_id ON public.analysis_feedback USING btree (user_id);


--
-- Name: ix_api_credential_profiles_auth_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_api_credential_profiles_auth_type ON public.api_credential_profiles USING btree (auth_type);


--
-- Name: ix_api_credential_profiles_credential_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_api_credential_profiles_credential_type ON public.api_credential_profiles USING btree (credential_type);


--
-- Name: ix_api_credential_profiles_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_api_credential_profiles_enabled ON public.api_credential_profiles USING btree (enabled);


--
-- Name: ix_api_credential_profiles_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_api_credential_profiles_name ON public.api_credential_profiles USING btree (name);


--
-- Name: ix_application_components_app_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_application_components_app_id ON public.application_components USING btree (app_id);


--
-- Name: ix_application_profiles_app_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_application_profiles_app_id ON public.application_profiles USING btree (app_id);


--
-- Name: ix_applications_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_applications_name ON public.applications USING btree (name);


--
-- Name: ix_apscheduler_jobs_next_run_time; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_apscheduler_jobs_next_run_time ON public.apscheduler_jobs USING btree (next_run_time);


--
-- Name: ix_audit_log_action; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_audit_log_action ON public.audit_log USING btree (action);


--
-- Name: ix_audit_log_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_audit_log_created_at ON public.audit_log USING btree (created_at);


--
-- Name: ix_audit_log_resource_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_audit_log_resource_type ON public.audit_log USING btree (resource_type);


--
-- Name: ix_audit_log_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_audit_log_user_id ON public.audit_log USING btree (user_id);


--
-- Name: ix_auto_analyze_rules_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_auto_analyze_rules_enabled ON public.auto_analyze_rules USING btree (enabled);


--
-- Name: ix_auto_analyze_rules_priority; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_auto_analyze_rules_priority ON public.auto_analyze_rules USING btree (priority);


--
-- Name: ix_blackout_windows_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_blackout_windows_enabled ON public.blackout_windows USING btree (enabled);


--
-- Name: ix_change_events_application; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_change_events_application ON public.change_events USING btree (application);


--
-- Name: ix_change_events_change_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_change_events_change_id ON public.change_events USING btree (change_id);


--
-- Name: ix_change_events_correlation_score; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_change_events_correlation_score ON public.change_events USING btree (correlation_score);


--
-- Name: ix_change_events_service_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_change_events_service_name ON public.change_events USING btree (service_name);


--
-- Name: ix_change_events_source; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_change_events_source ON public.change_events USING btree (source);


--
-- Name: ix_change_events_timestamp; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_change_events_timestamp ON public.change_events USING btree ("timestamp");


--
-- Name: ix_change_impact_analysis_correlation_score; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_change_impact_analysis_correlation_score ON public.change_impact_analysis USING btree (correlation_score);


--
-- Name: ix_component_dependencies_from_component_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_component_dependencies_from_component_id ON public.component_dependencies USING btree (from_component_id);


--
-- Name: ix_component_dependencies_to_component_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_component_dependencies_to_component_id ON public.component_dependencies USING btree (to_component_id);


--
-- Name: ix_credential_profiles_backend; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_credential_profiles_backend ON public.credential_profiles USING btree (backend);


--
-- Name: ix_credential_profiles_credential_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_credential_profiles_credential_type ON public.credential_profiles USING btree (credential_type);


--
-- Name: ix_credential_profiles_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_credential_profiles_name ON public.credential_profiles USING btree (name);


--
-- Name: ix_credential_profiles_username; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_credential_profiles_username ON public.credential_profiles USING btree (username);


--
-- Name: ix_dashboard_annotations_time; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_dashboard_annotations_time ON public.dashboard_annotations USING btree ("time");


--
-- Name: ix_dashboard_snapshots_key; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_dashboard_snapshots_key ON public.dashboard_snapshots USING btree (key);


--
-- Name: ix_dashboards_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_dashboards_name ON public.dashboards USING btree (name);


--
-- Name: ix_design_chunks_app_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_chunks_app_id ON public.design_chunks USING btree (app_id);


--
-- Name: ix_design_documents_app_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_documents_app_id ON public.design_documents USING btree (app_id);


--
-- Name: ix_design_documents_doc_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_documents_doc_type ON public.design_documents USING btree (doc_type);


--
-- Name: ix_design_documents_slug; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_design_documents_slug ON public.design_documents USING btree (slug);


--
-- Name: ix_design_documents_status; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_documents_status ON public.design_documents USING btree (status);


--
-- Name: ix_design_images_app_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_images_app_id ON public.design_images USING btree (app_id);


--
-- Name: ix_design_images_document_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_images_document_id ON public.design_images USING btree (document_id);


--
-- Name: ix_design_images_image_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_images_image_type ON public.design_images USING btree (image_type);


--
-- Name: ix_design_images_processing_status; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_design_images_processing_status ON public.design_images USING btree (processing_status);


--
-- Name: ix_execution_outcomes_alert_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_execution_outcomes_alert_id ON public.execution_outcomes USING btree (alert_id);


--
-- Name: ix_execution_outcomes_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_execution_outcomes_created_at ON public.execution_outcomes USING btree (created_at);


--
-- Name: ix_execution_outcomes_execution_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_execution_outcomes_execution_id ON public.execution_outcomes USING btree (execution_id);


--
-- Name: ix_execution_outcomes_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_execution_outcomes_user_id ON public.execution_outcomes USING btree (user_id);


--
-- Name: ix_failure_patterns_root_cause_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_failure_patterns_root_cause_type ON public.failure_patterns USING btree (root_cause_type);


--
-- Name: ix_grafana_datasources_datasource_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_grafana_datasources_datasource_type ON public.grafana_datasources USING btree (datasource_type);


--
-- Name: ix_grafana_datasources_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_grafana_datasources_name ON public.grafana_datasources USING btree (name);


--
-- Name: ix_group_members_group_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_group_members_group_id ON public.group_members USING btree (group_id);


--
-- Name: ix_group_members_source; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_group_members_source ON public.group_members USING btree (source);


--
-- Name: ix_group_members_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_group_members_user_id ON public.group_members USING btree (user_id);


--
-- Name: ix_groups_is_active; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_groups_is_active ON public.groups USING btree (is_active);


--
-- Name: ix_groups_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_groups_name ON public.groups USING btree (name);


--
-- Name: ix_groups_sync_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_groups_sync_enabled ON public.groups USING btree (sync_enabled);


--
-- Name: ix_incident_metrics_resolution_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_incident_metrics_resolution_type ON public.incident_metrics USING btree (resolution_type);


--
-- Name: ix_incident_metrics_service_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_incident_metrics_service_name ON public.incident_metrics USING btree (service_name);


--
-- Name: ix_incident_metrics_severity; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_incident_metrics_severity ON public.incident_metrics USING btree (severity);


--
-- Name: ix_itsm_integrations_is_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_itsm_integrations_is_enabled ON public.itsm_integrations USING btree (is_enabled);


--
-- Name: ix_itsm_integrations_last_sync; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_itsm_integrations_last_sync ON public.itsm_integrations USING btree (last_sync);


--
-- Name: ix_llm_providers_is_default; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_llm_providers_is_default ON public.llm_providers USING btree (is_default);


--
-- Name: ix_llm_providers_is_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_llm_providers_is_enabled ON public.llm_providers USING btree (is_enabled);


--
-- Name: ix_llm_providers_provider_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_llm_providers_provider_type ON public.llm_providers USING btree (provider_type);


--
-- Name: ix_prometheus_datasources_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_prometheus_datasources_name ON public.prometheus_datasources USING btree (name);


--
-- Name: ix_prometheus_panels_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_prometheus_panels_name ON public.prometheus_panels USING btree (name);


--
-- Name: ix_query_history_executed_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_query_history_executed_at ON public.query_history USING btree (executed_at);


--
-- Name: ix_roles_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_roles_name ON public.roles USING btree (name);


--
-- Name: ix_runbook_executions_status; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_runbook_executions_status ON public.runbook_executions USING btree (status);


--
-- Name: ix_runbook_triggers_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_runbook_triggers_enabled ON public.runbook_triggers USING btree (enabled);


--
-- Name: ix_runbook_triggers_priority; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_runbook_triggers_priority ON public.runbook_triggers USING btree (priority);


--
-- Name: ix_runbooks_auto_execute; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_runbooks_auto_execute ON public.runbooks USING btree (auto_execute);


--
-- Name: ix_runbooks_category; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_runbooks_category ON public.runbooks USING btree (category);


--
-- Name: ix_runbooks_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_runbooks_enabled ON public.runbooks USING btree (enabled);


--
-- Name: ix_server_credentials_credential_profile_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_credentials_credential_profile_id ON public.server_credentials USING btree (credential_profile_id);


--
-- Name: ix_server_credentials_credential_source; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_credentials_credential_source ON public.server_credentials USING btree (credential_source);


--
-- Name: ix_server_credentials_environment; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_credentials_environment ON public.server_credentials USING btree (environment);


--
-- Name: ix_server_credentials_group_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_credentials_group_id ON public.server_credentials USING btree (group_id);


--
-- Name: ix_server_credentials_hostname; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_credentials_hostname ON public.server_credentials USING btree (hostname);


--
-- Name: ix_server_credentials_os_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_credentials_os_type ON public.server_credentials USING btree (os_type);


--
-- Name: ix_server_credentials_protocol; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_credentials_protocol ON public.server_credentials USING btree (protocol);


--
-- Name: ix_server_groups_name; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_groups_name ON public.server_groups USING btree (name);


--
-- Name: ix_server_groups_parent_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_groups_parent_id ON public.server_groups USING btree (parent_id);


--
-- Name: ix_server_groups_path; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_server_groups_path ON public.server_groups USING btree (path);


--
-- Name: ix_solution_outcomes_alert_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_solution_outcomes_alert_id ON public.solution_outcomes USING btree (alert_id);


--
-- Name: ix_solution_outcomes_created_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_solution_outcomes_created_at ON public.solution_outcomes USING btree (created_at);


--
-- Name: ix_solution_outcomes_server_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_solution_outcomes_server_id ON public.solution_outcomes USING btree (server_id);


--
-- Name: ix_solution_outcomes_session_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_solution_outcomes_session_id ON public.solution_outcomes USING btree (session_id);


--
-- Name: ix_terminal_sessions_started_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_terminal_sessions_started_at ON public.terminal_sessions USING btree (started_at);


--
-- Name: ix_terminal_sessions_user_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_terminal_sessions_user_id ON public.terminal_sessions USING btree (user_id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: aiops
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: action_proposals action_proposals_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.action_proposals
    ADD CONSTRAINT action_proposals_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: action_proposals action_proposals_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.action_proposals
    ADD CONSTRAINT action_proposals_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.agent_tasks(id);


--
-- Name: agent_audit_logs agent_audit_logs_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_audit_logs
    ADD CONSTRAINT agent_audit_logs_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.agent_sessions(id) ON DELETE CASCADE;


--
-- Name: agent_audit_logs agent_audit_logs_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_audit_logs
    ADD CONSTRAINT agent_audit_logs_step_id_fkey FOREIGN KEY (step_id) REFERENCES public.agent_steps(id) ON DELETE SET NULL;


--
-- Name: agent_audit_logs agent_audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_audit_logs
    ADD CONSTRAINT agent_audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: agent_pools agent_pools_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_pools
    ADD CONSTRAINT agent_pools_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.ai_sessions(id);


--
-- Name: agent_rate_limits agent_rate_limits_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_rate_limits
    ADD CONSTRAINT agent_rate_limits_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: agent_sessions agent_sessions_chat_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_sessions
    ADD CONSTRAINT agent_sessions_chat_session_id_fkey FOREIGN KEY (chat_session_id) REFERENCES public.ai_sessions(id);


--
-- Name: agent_sessions agent_sessions_pool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_sessions
    ADD CONSTRAINT agent_sessions_pool_id_fkey FOREIGN KEY (pool_id) REFERENCES public.agent_pools(id);


--
-- Name: agent_sessions agent_sessions_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_sessions
    ADD CONSTRAINT agent_sessions_server_id_fkey FOREIGN KEY (server_id) REFERENCES public.server_credentials(id);


--
-- Name: agent_sessions agent_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_sessions
    ADD CONSTRAINT agent_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: agent_steps agent_steps_agent_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_steps
    ADD CONSTRAINT agent_steps_agent_session_id_fkey FOREIGN KEY (agent_session_id) REFERENCES public.agent_sessions(id) ON DELETE CASCADE;


--
-- Name: agent_steps agent_steps_change_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_steps
    ADD CONSTRAINT agent_steps_change_set_id_fkey FOREIGN KEY (change_set_id) REFERENCES public.change_sets(id);


--
-- Name: agent_tasks agent_tasks_agent_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_tasks
    ADD CONSTRAINT agent_tasks_agent_session_id_fkey FOREIGN KEY (agent_session_id) REFERENCES public.agent_sessions(id);


--
-- Name: agent_tasks agent_tasks_pool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.agent_tasks
    ADD CONSTRAINT agent_tasks_pool_id_fkey FOREIGN KEY (pool_id) REFERENCES public.agent_pools(id);


--
-- Name: ai_action_confirmations ai_action_confirmations_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_action_confirmations
    ADD CONSTRAINT ai_action_confirmations_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.ai_sessions(id);


--
-- Name: ai_action_confirmations ai_action_confirmations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_action_confirmations
    ADD CONSTRAINT ai_action_confirmations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_helper_audit_logs ai_helper_audit_logs_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_helper_audit_logs
    ADD CONSTRAINT ai_helper_audit_logs_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.ai_helper_sessions(id);


--
-- Name: ai_messages ai_messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_messages
    ADD CONSTRAINT ai_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.ai_sessions(id) ON DELETE CASCADE;


--
-- Name: ai_permissions ai_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_permissions
    ADD CONSTRAINT ai_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: ai_sessions ai_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_sessions
    ADD CONSTRAINT ai_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_tool_executions ai_tool_executions_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_tool_executions
    ADD CONSTRAINT ai_tool_executions_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.ai_messages(id);


--
-- Name: ai_tool_executions ai_tool_executions_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_tool_executions
    ADD CONSTRAINT ai_tool_executions_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.ai_sessions(id);


--
-- Name: ai_tool_executions ai_tool_executions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.ai_tool_executions
    ADD CONSTRAINT ai_tool_executions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: alert_correlations alert_correlations_related_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alert_correlations
    ADD CONSTRAINT alert_correlations_related_alert_id_fkey FOREIGN KEY (related_alert_id) REFERENCES public.alerts(id) ON DELETE CASCADE;


--
-- Name: alerts alerts_analyzed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_analyzed_by_fkey FOREIGN KEY (analyzed_by) REFERENCES public.users(id);


--
-- Name: alerts alerts_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE SET NULL;


--
-- Name: alerts alerts_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_component_id_fkey FOREIGN KEY (component_id) REFERENCES public.application_components(id) ON DELETE SET NULL;


--
-- Name: alerts alerts_correlation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_correlation_id_fkey FOREIGN KEY (correlation_id) REFERENCES public.alert_correlations(id) ON DELETE SET NULL;


--
-- Name: alerts alerts_llm_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_llm_provider_id_fkey FOREIGN KEY (llm_provider_id) REFERENCES public.llm_providers(id);


--
-- Name: alerts alerts_matched_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_matched_rule_id_fkey FOREIGN KEY (matched_rule_id) REFERENCES public.auto_analyze_rules(id);


--
-- Name: analysis_feedback analysis_feedback_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.analysis_feedback
    ADD CONSTRAINT analysis_feedback_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE CASCADE;


--
-- Name: analysis_feedback analysis_feedback_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.analysis_feedback
    ADD CONSTRAINT analysis_feedback_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: api_credential_profiles api_credential_profiles_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.api_credential_profiles
    ADD CONSTRAINT api_credential_profiles_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: application_components application_components_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_components
    ADD CONSTRAINT application_components_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: application_knowledge_configs application_knowledge_configs_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_knowledge_configs
    ADD CONSTRAINT application_knowledge_configs_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: application_profiles application_profiles_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_profiles
    ADD CONSTRAINT application_profiles_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: auto_analyze_rules auto_analyze_rules_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.auto_analyze_rules
    ADD CONSTRAINT auto_analyze_rules_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: blackout_windows blackout_windows_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.blackout_windows
    ADD CONSTRAINT blackout_windows_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: change_items change_items_change_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_items
    ADD CONSTRAINT change_items_change_set_id_fkey FOREIGN KEY (change_set_id) REFERENCES public.change_sets(id);


--
-- Name: change_sets change_sets_agent_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_sets
    ADD CONSTRAINT change_sets_agent_step_id_fkey FOREIGN KEY (agent_step_id) REFERENCES public.agent_steps(id);


--
-- Name: change_sets change_sets_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_sets
    ADD CONSTRAINT change_sets_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.ai_sessions(id);


--
-- Name: circuit_breakers circuit_breakers_manually_opened_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.circuit_breakers
    ADD CONSTRAINT circuit_breakers_manually_opened_by_fkey FOREIGN KEY (manually_opened_by) REFERENCES public.users(id);


--
-- Name: component_dependencies component_dependencies_from_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.component_dependencies
    ADD CONSTRAINT component_dependencies_from_component_id_fkey FOREIGN KEY (from_component_id) REFERENCES public.application_components(id) ON DELETE CASCADE;


--
-- Name: component_dependencies component_dependencies_to_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.component_dependencies
    ADD CONSTRAINT component_dependencies_to_component_id_fkey FOREIGN KEY (to_component_id) REFERENCES public.application_components(id) ON DELETE CASCADE;


--
-- Name: credential_profiles credential_profiles_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.credential_profiles
    ADD CONSTRAINT credential_profiles_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: credential_profiles credential_profiles_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.credential_profiles
    ADD CONSTRAINT credential_profiles_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.server_groups(id);


--
-- Name: dashboard_annotations dashboard_annotations_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_annotations
    ADD CONSTRAINT dashboard_annotations_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: dashboard_annotations dashboard_annotations_panel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_annotations
    ADD CONSTRAINT dashboard_annotations_panel_id_fkey FOREIGN KEY (panel_id) REFERENCES public.prometheus_panels(id);


--
-- Name: dashboard_links dashboard_links_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_links
    ADD CONSTRAINT dashboard_links_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: dashboard_panels dashboard_panels_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_panels
    ADD CONSTRAINT dashboard_panels_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: dashboard_panels dashboard_panels_panel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_panels
    ADD CONSTRAINT dashboard_panels_panel_id_fkey FOREIGN KEY (panel_id) REFERENCES public.prometheus_panels(id);


--
-- Name: dashboard_panels dashboard_panels_row_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_panels
    ADD CONSTRAINT dashboard_panels_row_id_fkey FOREIGN KEY (row_id) REFERENCES public.panel_rows(id);


--
-- Name: dashboard_permissions dashboard_permissions_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_permissions
    ADD CONSTRAINT dashboard_permissions_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: dashboard_snapshots dashboard_snapshots_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_snapshots
    ADD CONSTRAINT dashboard_snapshots_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: dashboard_variables dashboard_variables_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_variables
    ADD CONSTRAINT dashboard_variables_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: dashboard_variables dashboard_variables_datasource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.dashboard_variables
    ADD CONSTRAINT dashboard_variables_datasource_id_fkey FOREIGN KEY (datasource_id) REFERENCES public.prometheus_datasources(id);


--
-- Name: design_chunks design_chunks_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_chunks
    ADD CONSTRAINT design_chunks_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: design_documents design_documents_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_documents
    ADD CONSTRAINT design_documents_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: design_documents design_documents_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_documents
    ADD CONSTRAINT design_documents_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: design_images design_images_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_images
    ADD CONSTRAINT design_images_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: design_images design_images_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_images
    ADD CONSTRAINT design_images_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: design_images design_images_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.design_images
    ADD CONSTRAINT design_images_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.design_documents(id) ON DELETE SET NULL;


--
-- Name: execution_outcomes execution_outcomes_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.execution_outcomes
    ADD CONSTRAINT execution_outcomes_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE SET NULL;


--
-- Name: execution_outcomes execution_outcomes_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.execution_outcomes
    ADD CONSTRAINT execution_outcomes_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.runbook_executions(id) ON DELETE CASCADE;


--
-- Name: execution_outcomes execution_outcomes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.execution_outcomes
    ADD CONSTRAINT execution_outcomes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: file_backups file_backups_file_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.file_backups
    ADD CONSTRAINT file_backups_file_version_id_fkey FOREIGN KEY (file_version_id) REFERENCES public.file_versions(id);


--
-- Name: file_versions file_versions_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.file_versions
    ADD CONSTRAINT file_versions_server_id_fkey FOREIGN KEY (server_id) REFERENCES public.server_credentials(id);


--
-- Name: file_versions file_versions_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.file_versions
    ADD CONSTRAINT file_versions_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.ai_sessions(id);


--
-- Name: alerts fk_alert_cluster; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT fk_alert_cluster FOREIGN KEY (cluster_id) REFERENCES public.alert_clusters(id) ON DELETE SET NULL;


--
-- Name: application_profiles fk_app_profiles_loki_datasource; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_profiles
    ADD CONSTRAINT fk_app_profiles_loki_datasource FOREIGN KEY (loki_datasource_id) REFERENCES public.grafana_datasources(id) ON DELETE SET NULL;


--
-- Name: application_profiles fk_app_profiles_prometheus_datasource; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_profiles
    ADD CONSTRAINT fk_app_profiles_prometheus_datasource FOREIGN KEY (prometheus_datasource_id) REFERENCES public.grafana_datasources(id) ON DELETE SET NULL;


--
-- Name: application_profiles fk_app_profiles_tempo_datasource; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.application_profiles
    ADD CONSTRAINT fk_app_profiles_tempo_datasource FOREIGN KEY (tempo_datasource_id) REFERENCES public.grafana_datasources(id) ON DELETE SET NULL;


--
-- Name: change_impact_analysis fk_impact_change; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.change_impact_analysis
    ADD CONSTRAINT fk_impact_change FOREIGN KEY (change_event_id) REFERENCES public.change_events(id) ON DELETE CASCADE;


--
-- Name: group_members group_members_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.group_members
    ADD CONSTRAINT group_members_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_members group_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.group_members
    ADD CONSTRAINT group_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: groups groups_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: groups groups_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: incident_metrics incident_metrics_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.incident_metrics
    ADD CONSTRAINT incident_metrics_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE CASCADE;


--
-- Name: incident_metrics incident_metrics_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.incident_metrics
    ADD CONSTRAINT incident_metrics_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: iteration_loops iteration_loops_agent_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.iteration_loops
    ADD CONSTRAINT iteration_loops_agent_task_id_fkey FOREIGN KEY (agent_task_id) REFERENCES public.agent_tasks(id);


--
-- Name: panel_rows panel_rows_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.panel_rows
    ADD CONSTRAINT panel_rows_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: playlist_items playlist_items_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.playlist_items
    ADD CONSTRAINT playlist_items_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: playlist_items playlist_items_playlist_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.playlist_items
    ADD CONSTRAINT playlist_items_playlist_id_fkey FOREIGN KEY (playlist_id) REFERENCES public.playlists(id);


--
-- Name: prometheus_panels prometheus_panels_datasource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.prometheus_panels
    ADD CONSTRAINT prometheus_panels_datasource_id_fkey FOREIGN KEY (datasource_id) REFERENCES public.prometheus_datasources(id);


--
-- Name: query_history query_history_dashboard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.query_history
    ADD CONSTRAINT query_history_dashboard_id_fkey FOREIGN KEY (dashboard_id) REFERENCES public.dashboards(id);


--
-- Name: query_history query_history_datasource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.query_history
    ADD CONSTRAINT query_history_datasource_id_fkey FOREIGN KEY (datasource_id) REFERENCES public.prometheus_datasources(id);


--
-- Name: query_history query_history_panel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.query_history
    ADD CONSTRAINT query_history_panel_id_fkey FOREIGN KEY (panel_id) REFERENCES public.prometheus_panels(id);


--
-- Name: runbook_acls runbook_acls_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_acls
    ADD CONSTRAINT runbook_acls_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: runbook_acls runbook_acls_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_acls
    ADD CONSTRAINT runbook_acls_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: runbook_acls runbook_acls_runbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_acls
    ADD CONSTRAINT runbook_acls_runbook_id_fkey FOREIGN KEY (runbook_id) REFERENCES public.runbooks(id) ON DELETE CASCADE;


--
-- Name: runbook_executions runbook_executions_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id);


--
-- Name: runbook_executions runbook_executions_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: runbook_executions runbook_executions_runbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_runbook_id_fkey FOREIGN KEY (runbook_id) REFERENCES public.runbooks(id);


--
-- Name: runbook_executions runbook_executions_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_server_id_fkey FOREIGN KEY (server_id) REFERENCES public.server_credentials(id);


--
-- Name: runbook_executions runbook_executions_trigger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_trigger_id_fkey FOREIGN KEY (trigger_id) REFERENCES public.runbook_triggers(id);


--
-- Name: runbook_executions runbook_executions_triggered_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_executions
    ADD CONSTRAINT runbook_executions_triggered_by_fkey FOREIGN KEY (triggered_by) REFERENCES public.users(id);


--
-- Name: runbook_steps runbook_steps_api_credential_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_steps
    ADD CONSTRAINT runbook_steps_api_credential_profile_id_fkey FOREIGN KEY (api_credential_profile_id) REFERENCES public.api_credential_profiles(id) ON DELETE SET NULL;


--
-- Name: runbook_steps runbook_steps_runbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_steps
    ADD CONSTRAINT runbook_steps_runbook_id_fkey FOREIGN KEY (runbook_id) REFERENCES public.runbooks(id) ON DELETE CASCADE;


--
-- Name: runbook_triggers runbook_triggers_runbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbook_triggers
    ADD CONSTRAINT runbook_triggers_runbook_id_fkey FOREIGN KEY (runbook_id) REFERENCES public.runbooks(id) ON DELETE CASCADE;


--
-- Name: runbooks runbooks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbooks
    ADD CONSTRAINT runbooks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: runbooks runbooks_default_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.runbooks
    ADD CONSTRAINT runbooks_default_server_id_fkey FOREIGN KEY (default_server_id) REFERENCES public.server_credentials(id);


--
-- Name: schedule_execution_history schedule_execution_history_runbook_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.schedule_execution_history
    ADD CONSTRAINT schedule_execution_history_runbook_execution_id_fkey FOREIGN KEY (runbook_execution_id) REFERENCES public.runbook_executions(id);


--
-- Name: schedule_execution_history schedule_execution_history_scheduled_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.schedule_execution_history
    ADD CONSTRAINT schedule_execution_history_scheduled_job_id_fkey FOREIGN KEY (scheduled_job_id) REFERENCES public.scheduled_jobs(id) ON DELETE CASCADE;


--
-- Name: scheduled_jobs scheduled_jobs_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.scheduled_jobs
    ADD CONSTRAINT scheduled_jobs_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: scheduled_jobs scheduled_jobs_runbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.scheduled_jobs
    ADD CONSTRAINT scheduled_jobs_runbook_id_fkey FOREIGN KEY (runbook_id) REFERENCES public.runbooks(id) ON DELETE CASCADE;


--
-- Name: scheduled_jobs scheduled_jobs_target_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.scheduled_jobs
    ADD CONSTRAINT scheduled_jobs_target_server_id_fkey FOREIGN KEY (target_server_id) REFERENCES public.server_credentials(id);


--
-- Name: server_credentials server_credentials_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.server_credentials
    ADD CONSTRAINT server_credentials_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: server_credentials server_credentials_credential_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.server_credentials
    ADD CONSTRAINT server_credentials_credential_profile_id_fkey FOREIGN KEY (credential_profile_id) REFERENCES public.credential_profiles(id);


--
-- Name: server_credentials server_credentials_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.server_credentials
    ADD CONSTRAINT server_credentials_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.server_groups(id);


--
-- Name: server_groups server_groups_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.server_groups
    ADD CONSTRAINT server_groups_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.server_groups(id);


--
-- Name: solution_outcomes solution_outcomes_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.solution_outcomes
    ADD CONSTRAINT solution_outcomes_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE SET NULL;


--
-- Name: solution_outcomes solution_outcomes_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.solution_outcomes
    ADD CONSTRAINT solution_outcomes_server_id_fkey FOREIGN KEY (server_id) REFERENCES public.server_credentials(id) ON DELETE SET NULL;


--
-- Name: step_executions step_executions_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.step_executions
    ADD CONSTRAINT step_executions_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.runbook_executions(id) ON DELETE CASCADE;


--
-- Name: step_executions step_executions_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.step_executions
    ADD CONSTRAINT step_executions_step_id_fkey FOREIGN KEY (step_id) REFERENCES public.runbook_steps(id);


--
-- Name: system_config system_config_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: terminal_sessions terminal_sessions_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.terminal_sessions
    ADD CONSTRAINT terminal_sessions_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id);


--
-- Name: terminal_sessions terminal_sessions_server_credential_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.terminal_sessions
    ADD CONSTRAINT terminal_sessions_server_credential_id_fkey FOREIGN KEY (server_credential_id) REFERENCES public.server_credentials(id);


--
-- Name: terminal_sessions terminal_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.terminal_sessions
    ADD CONSTRAINT terminal_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: users users_default_llm_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: aiops
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_default_llm_provider_id_fkey FOREIGN KEY (default_llm_provider_id) REFERENCES public.llm_providers(id);


--
-- Name: pii_detection_config; Type: TABLE; Schema: public; Owner: aiops
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
-- Name: pii_detection_logs; Type: TABLE; Schema: public; Owner: aiops
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
-- Name: secret_baselines; Type: TABLE; Schema: public; Owner: aiops
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


--
-- Name: ix_pii_detection_config_config_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_config_config_type ON public.pii_detection_config USING btree (config_type);


--
-- Name: ix_pii_detection_config_entity_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_config_entity_type ON public.pii_detection_config USING btree (entity_type);


--
-- Name: ix_pii_detection_config_enabled; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_config_enabled ON public.pii_detection_config USING btree (enabled);


--
-- Name: ix_pii_detection_logs_detected_at; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_logs_detected_at ON public.pii_detection_logs USING btree (detected_at);


--
-- Name: ix_pii_detection_logs_entity_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_logs_entity_type ON public.pii_detection_logs USING btree (entity_type);


--
-- Name: ix_pii_detection_logs_detection_engine; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_logs_detection_engine ON public.pii_detection_logs USING btree (detection_engine);


--
-- Name: ix_pii_detection_logs_confidence_score; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_logs_confidence_score ON public.pii_detection_logs USING btree (confidence_score);


--
-- Name: ix_pii_detection_logs_source_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_logs_source_type ON public.pii_detection_logs USING btree (source_type);


--
-- Name: ix_pii_detection_logs_source_id; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_logs_source_id ON public.pii_detection_logs USING btree (source_id);


--
-- Name: ix_pii_detection_logs_original_hash; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_pii_detection_logs_original_hash ON public.pii_detection_logs USING btree (original_hash);


--
-- Name: ix_secret_baselines_secret_type; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_secret_baselines_secret_type ON public.secret_baselines USING btree (secret_type);


--
-- Name: ix_secret_baselines_is_acknowledged; Type: INDEX; Schema: public; Owner: aiops
--

CREATE INDEX ix_secret_baselines_is_acknowledged ON public.secret_baselines USING btree (is_acknowledged);


--
-- PostgreSQL database dump complete
--



