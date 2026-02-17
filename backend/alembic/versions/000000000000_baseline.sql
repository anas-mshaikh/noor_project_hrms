--
-- PostgreSQL database dump
--

\restrict uIxhcZ52CCNVIRsrwpZlMNP0kzqa8EKahliI25sr5dgNpNu2RbQJYyOIOQgj0MD

-- Dumped from database version 17.7 (Debian 17.7-3.pgdg12+1)
-- Dumped by pg_dump version 17.7 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: analytics; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA analytics;


--
-- Name: attendance; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA attendance;


--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA audit;


--
-- Name: dms; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA dms;


--
-- Name: face; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA face;


--
-- Name: hr; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA hr;


--
-- Name: hr_core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA hr_core;


--
-- Name: iam; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA iam;


--
-- Name: imports; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA imports;


--
-- Name: leave; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA leave;


--
-- Name: mobile; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA mobile;


--
-- Name: skills; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA skills;


--
-- Name: tenancy; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tenancy;


--
-- Name: vision; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA vision;


--
-- Name: work; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA work;


--
-- Name: workflow; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA workflow;


--
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA vision;


--
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: init_weekly_off_for_branch(); Type: FUNCTION; Schema: leave; Owner: -
--

CREATE FUNCTION leave.init_weekly_off_for_branch() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
              INSERT INTO leave.weekly_off (tenant_id, branch_id, weekday, is_off)
              SELECT
                NEW.tenant_id,
                NEW.id,
                gs.weekday,
                (gs.weekday IN (4,5)) AS is_off
              FROM (SELECT generate_series(0,6) AS weekday) gs
              ON CONFLICT (tenant_id, branch_id, weekday) DO NOTHING;

              RETURN NEW;
            END;
            $$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
              NEW.updated_at = now();
              RETURN NEW;
            END;
            $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: pos_summary; Type: TABLE; Schema: analytics; Owner: -
--

CREATE TABLE analytics.pos_summary (
    dataset_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    qty numeric,
    net_sales numeric,
    bills integer,
    customers integer,
    return_customers integer,
    tenant_id uuid NOT NULL
);


--
-- Name: attendance_daily; Type: TABLE; Schema: attendance; Owner: -
--

CREATE TABLE attendance.attendance_daily (
    id uuid NOT NULL,
    branch_id uuid NOT NULL,
    business_date date NOT NULL,
    employee_id uuid NOT NULL,
    punch_in timestamp with time zone,
    punch_out timestamp with time zone,
    total_minutes integer,
    confidence double precision,
    anomalies_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: attendance_summary; Type: TABLE; Schema: attendance; Owner: -
--

CREATE TABLE attendance.attendance_summary (
    dataset_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    present integer,
    absent integer,
    work_minutes integer,
    stocking_done integer,
    stocking_missed integer,
    tenant_id uuid NOT NULL
);


--
-- Name: day_overrides; Type: TABLE; Schema: attendance; Owner: -
--

CREATE TABLE attendance.day_overrides (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    day date NOT NULL,
    status text NOT NULL,
    source_type text NOT NULL,
    source_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_day_overrides_source_type CHECK ((source_type = 'LEAVE_REQUEST'::text)),
    CONSTRAINT ck_day_overrides_status CHECK ((status = 'ON_LEAVE'::text))
);


--
-- Name: audit_log; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    actor_user_id uuid NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    diff_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    correlation_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: document_links; Type: TABLE; Schema: dms; Owner: -
--

CREATE TABLE dms.document_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    document_id uuid NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid
);


--
-- Name: document_types; Type: TABLE; Schema: dms; Owner: -
--

CREATE TABLE dms.document_types (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code character varying(64) NOT NULL,
    name character varying(200) NOT NULL,
    requires_expiry boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: document_versions; Type: TABLE; Schema: dms; Owner: -
--

CREATE TABLE dms.document_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    document_id uuid NOT NULL,
    file_id uuid NOT NULL,
    version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: documents; Type: TABLE; Schema: dms; Owner: -
--

CREATE TABLE dms.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    document_type_id uuid NOT NULL,
    title text,
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    issued_at date,
    expires_at date,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_dms_documents_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'ARCHIVED'::character varying])::text[])))
);


--
-- Name: expiry_events; Type: TABLE; Schema: dms; Owner: -
--

CREATE TABLE dms.expiry_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    document_id uuid NOT NULL,
    rule_id uuid NOT NULL,
    fired_at timestamp with time zone DEFAULT now() NOT NULL,
    channel character varying(32),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: expiry_rules; Type: TABLE; Schema: dms; Owner: -
--

CREATE TABLE dms.expiry_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    document_type_id uuid,
    days_before integer NOT NULL,
    notify_roles text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: files; Type: TABLE; Schema: dms; Owner: -
--

CREATE TABLE dms.files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    storage_provider character varying(32) NOT NULL,
    bucket text,
    object_key text NOT NULL,
    content_type text,
    size_bytes bigint,
    sha256 character varying(64),
    original_filename text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: employee_faces; Type: TABLE; Schema: face; Owner: -
--

CREATE TABLE face.employee_faces (
    id uuid NOT NULL,
    employee_id uuid NOT NULL,
    embedding public.vector(512) NOT NULL,
    snapshot_path text,
    quality_score double precision,
    model_version character varying(64) DEFAULT 'unknown'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: hr_application_notes; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_application_notes (
    id uuid NOT NULL,
    application_id uuid NOT NULL,
    author_id uuid,
    note text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: hr_applications; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_applications (
    id uuid NOT NULL,
    opening_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    resume_id uuid NOT NULL,
    stage_id uuid,
    status character varying(16) DEFAULT 'ACTIVE'::character varying NOT NULL,
    source_run_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    employee_id uuid,
    hired_at timestamp with time zone,
    start_date date,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL
);


--
-- Name: hr_onboarding_plans; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_onboarding_plans (
    id uuid NOT NULL,
    branch_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    application_id uuid,
    status character varying(16) DEFAULT 'ACTIVE'::character varying NOT NULL,
    start_date date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL
);


--
-- Name: hr_onboarding_tasks; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_onboarding_tasks (
    id uuid NOT NULL,
    plan_id uuid NOT NULL,
    title text NOT NULL,
    task_type character varying(16) DEFAULT 'TASK'::character varying NOT NULL,
    status character varying(16) DEFAULT 'PENDING'::character varying NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    due_date date,
    completed_at timestamp with time zone,
    metadata_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: hr_openings; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_openings (
    id uuid NOT NULL,
    branch_id uuid NOT NULL,
    title text NOT NULL,
    jd_text text NOT NULL,
    requirements_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    status character varying(16) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL
);


--
-- Name: hr_pipeline_stages; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_pipeline_stages (
    id uuid NOT NULL,
    opening_id uuid NOT NULL,
    name text NOT NULL,
    sort_order integer NOT NULL,
    is_terminal boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: hr_resume_batches; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_resume_batches (
    id uuid NOT NULL,
    opening_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    total_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL
);


--
-- Name: hr_resume_views; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_resume_views (
    id uuid NOT NULL,
    resume_id uuid NOT NULL,
    view_type character varying(16) NOT NULL,
    text_hash character varying(64) NOT NULL,
    embedding public.vector(1024),
    tokens integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: hr_resumes; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_resumes (
    id uuid NOT NULL,
    opening_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    batch_id uuid,
    original_filename text NOT NULL,
    file_path text NOT NULL,
    parsed_path text,
    clean_text_path text,
    status character varying(16) DEFAULT 'UPLOADED'::character varying NOT NULL,
    error text,
    rq_job_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    embedding_status character varying(16) DEFAULT 'PENDING'::character varying NOT NULL,
    embedding_error text,
    embedded_at timestamp with time zone,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL
);


--
-- Name: hr_screening_explanations; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_screening_explanations (
    run_id uuid NOT NULL,
    resume_id uuid NOT NULL,
    rank integer,
    model_name text NOT NULL,
    prompt_version text NOT NULL,
    explanation_json jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: hr_screening_results; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_screening_results (
    run_id uuid NOT NULL,
    resume_id uuid NOT NULL,
    rank integer NOT NULL,
    final_score double precision NOT NULL,
    rerank_score double precision,
    retrieval_score double precision,
    best_view_type character varying(16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: hr_screening_runs; Type: TABLE; Schema: hr; Owner: -
--

CREATE TABLE hr.hr_screening_runs (
    id uuid NOT NULL,
    opening_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    status character varying(16) DEFAULT 'QUEUED'::character varying NOT NULL,
    config_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    model_versions_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    rq_job_id text,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    progress_total integer DEFAULT 0 NOT NULL,
    progress_done integer DEFAULT 0 NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL
);


--
-- Name: employee_bank_accounts; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.employee_bank_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    iban character varying(64),
    account_number character varying(64),
    bank_name character varying(200),
    is_primary boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_employee_bank_accounts_one_identifier CHECK (((iban IS NOT NULL) OR (account_number IS NOT NULL)))
);


--
-- Name: employee_contracts; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.employee_contracts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    contract_type character varying(64),
    start_date date,
    end_date date,
    probation_end_date date,
    wage_type character varying(32),
    base_salary numeric,
    currency_code character varying(8),
    terms jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: employee_dependents; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.employee_dependents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    relationship character varying(64),
    dob date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: employee_employment; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.employee_employment (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    org_unit_id uuid,
    job_title_id uuid,
    grade_id uuid,
    manager_employee_id uuid,
    start_date date NOT NULL,
    end_date date,
    is_primary boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_employee_employment_end_gte_start CHECK (((end_date IS NULL) OR (end_date >= start_date)))
);


--
-- Name: employee_government_ids; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.employee_government_ids (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    id_type character varying(64) NOT NULL,
    id_number character varying(128) NOT NULL,
    issued_at date,
    expires_at date,
    issuing_country character varying(64),
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: employee_user_links; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.employee_user_links (
    employee_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: employees; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.employees (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    person_id uuid NOT NULL,
    employee_code character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    join_date date,
    termination_date date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_hr_core_employees_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'INACTIVE'::character varying, 'TERMINATED'::character varying])::text[])))
);


--
-- Name: persons; Type: TABLE; Schema: hr_core; Owner: -
--

CREATE TABLE hr_core.persons (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    first_name character varying(200) NOT NULL,
    last_name character varying(200) NOT NULL,
    dob date,
    nationality character varying(100),
    phone character varying(32),
    address jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    email vision.citext
);


--
-- Name: v_employee_current_employment; Type: VIEW; Schema: hr_core; Owner: -
--

CREATE VIEW hr_core.v_employee_current_employment AS
 SELECT e.id AS employee_id,
    e.tenant_id,
    e.company_id,
    e.person_id,
    e.employee_code,
    e.status,
    e.join_date,
    e.termination_date,
    e.created_at,
    e.updated_at,
    ee.branch_id,
    ee.org_unit_id,
    ee.job_title_id,
    ee.grade_id,
    ee.manager_employee_id,
    ee.start_date,
    ee.end_date,
    ee.is_primary
   FROM (hr_core.employees e
     JOIN LATERAL ( SELECT ee_inner.id,
            ee_inner.tenant_id,
            ee_inner.company_id,
            ee_inner.employee_id,
            ee_inner.branch_id,
            ee_inner.org_unit_id,
            ee_inner.job_title_id,
            ee_inner.grade_id,
            ee_inner.manager_employee_id,
            ee_inner.start_date,
            ee_inner.end_date,
            ee_inner.is_primary,
            ee_inner.created_at,
            ee_inner.updated_at
           FROM hr_core.employee_employment ee_inner
          WHERE ((ee_inner.employee_id = e.id) AND (ee_inner.end_date IS NULL))
          ORDER BY ee_inner.is_primary DESC, ee_inner.start_date DESC
         LIMIT 1) ee ON (true));


--
-- Name: api_tokens; Type: TABLE; Schema: iam; Owner: -
--

CREATE TABLE iam.api_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    token_hash text NOT NULL,
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: permissions; Type: TABLE; Schema: iam; Owner: -
--

CREATE TABLE iam.permissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(64) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: iam; Owner: -
--

CREATE TABLE iam.refresh_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    token_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    ip text,
    user_agent text
);


--
-- Name: role_permissions; Type: TABLE; Schema: iam; Owner: -
--

CREATE TABLE iam.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL
);


--
-- Name: roles; Type: TABLE; Schema: iam; Owner: -
--

CREATE TABLE iam.roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(64) NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_roles; Type: TABLE; Schema: iam; Owner: -
--

CREATE TABLE iam.user_roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid,
    branch_id uuid,
    role_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: iam; Owner: -
--

CREATE TABLE iam.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    phone character varying(32),
    password_hash text,
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_by uuid,
    deleted_at timestamp with time zone,
    email vision.citext NOT NULL,
    CONSTRAINT ck_iam_users_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'DISABLED'::character varying])::text[])))
);


--
-- Name: datasets; Type: TABLE; Schema: imports; Owner: -
--

CREATE TABLE imports.datasets (
    id uuid NOT NULL,
    month_key character varying(16) NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    uploaded_by character varying(200),
    status character varying(16) DEFAULT 'VALIDATING'::character varying NOT NULL,
    sync_status character varying(16) DEFAULT 'DISABLED'::character varying NOT NULL,
    raw_file_path text,
    checksum character varying(64) NOT NULL,
    branch_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    CONSTRAINT ck_datasets_status CHECK (((status)::text = ANY ((ARRAY['VALIDATING'::character varying, 'READY'::character varying, 'FAILED'::character varying])::text[]))),
    CONSTRAINT ck_datasets_sync_status CHECK (((sync_status)::text = ANY ((ARRAY['DISABLED'::character varying, 'PENDING'::character varying, 'SYNCED'::character varying, 'FAILED'::character varying])::text[])))
);


--
-- Name: month_state; Type: TABLE; Schema: imports; Owner: -
--

CREATE TABLE imports.month_state (
    month_key character varying(16) NOT NULL,
    published_dataset_id uuid,
    tenant_id uuid NOT NULL,
    branch_id uuid NOT NULL
);


--
-- Name: employee_leave_policy; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.employee_leave_policy (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    policy_id uuid NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: holidays; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.holidays (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid,
    branch_id uuid,
    day date NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: leave_ledger; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.leave_ledger (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    leave_type_id uuid NOT NULL,
    period_year integer NOT NULL,
    delta_days numeric(6,2) NOT NULL,
    source_type text NOT NULL,
    source_id uuid,
    note text,
    created_by_user_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_leave_ledger_source_type CHECK ((source_type = ANY (ARRAY['ALLOCATION'::text, 'LEAVE_REQUEST'::text, 'ADJUSTMENT'::text, 'CARRYOVER'::text])))
);


--
-- Name: leave_policies; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.leave_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    company_id uuid,
    branch_id uuid,
    effective_from date NOT NULL,
    effective_to date,
    year_start_month smallint DEFAULT 1 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_leave_policies_year_start_month CHECK (((year_start_month >= 1) AND (year_start_month <= 12)))
);


--
-- Name: leave_policy_rules; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.leave_policy_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    policy_id uuid NOT NULL,
    leave_type_id uuid NOT NULL,
    annual_entitlement_days numeric(6,2) DEFAULT 0 NOT NULL,
    allow_half_day boolean DEFAULT false NOT NULL,
    requires_attachment boolean,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: leave_request_days; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.leave_request_days (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    leave_request_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    day date NOT NULL,
    countable boolean NOT NULL,
    day_fraction numeric(3,2) NOT NULL,
    is_weekend boolean NOT NULL,
    is_holiday boolean NOT NULL,
    holiday_name text
);


--
-- Name: leave_requests; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.leave_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    leave_type_id uuid NOT NULL,
    policy_id uuid NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    unit text NOT NULL,
    half_day_part text,
    requested_days numeric(6,2) NOT NULL,
    reason text,
    status text NOT NULL,
    workflow_request_id uuid,
    company_id uuid,
    branch_id uuid,
    idempotency_key text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_leave_requests_half_day_part CHECK (((half_day_part = ANY (ARRAY['AM'::text, 'PM'::text])) OR (half_day_part IS NULL))),
    CONSTRAINT ck_leave_requests_status CHECK ((status = ANY (ARRAY['DRAFT'::text, 'PENDING'::text, 'APPROVED'::text, 'REJECTED'::text, 'CANCELED'::text]))),
    CONSTRAINT ck_leave_requests_unit CHECK ((unit = ANY (ARRAY['DAY'::text, 'HALF_DAY'::text])))
);


--
-- Name: leave_types; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.leave_types (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    is_paid boolean DEFAULT true NOT NULL,
    unit text DEFAULT 'DAY'::text NOT NULL,
    requires_attachment boolean DEFAULT false NOT NULL,
    allow_negative_balance boolean DEFAULT false NOT NULL,
    max_consecutive_days integer,
    min_notice_days integer,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_leave_types_unit CHECK ((unit = ANY (ARRAY['DAY'::text, 'HALF_DAY'::text])))
);


--
-- Name: weekly_off; Type: TABLE; Schema: leave; Owner: -
--

CREATE TABLE leave.weekly_off (
    tenant_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    weekday smallint NOT NULL,
    is_off boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_leave_weekly_off_weekday CHECK (((weekday >= 0) AND (weekday <= 6)))
);


--
-- Name: mobile_accounts; Type: TABLE; Schema: mobile; Owner: -
--

CREATE TABLE mobile.mobile_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    employee_code character varying(64) NOT NULL,
    firebase_uid character varying(128) NOT NULL,
    role character varying(32) DEFAULT 'employee'::character varying NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone
);


--
-- Name: employee_skills; Type: TABLE; Schema: skills; Owner: -
--

CREATE TABLE skills.employee_skills (
    employee_id uuid NOT NULL,
    skill_id uuid NOT NULL,
    proficiency integer NOT NULL,
    confidence double precision DEFAULT 1.0 NOT NULL,
    source character varying(32),
    last_used_at timestamp with time zone,
    tenant_id uuid NOT NULL,
    CONSTRAINT ck_employee_skills_proficiency_1_5 CHECK (((proficiency >= 1) AND (proficiency <= 5)))
);


--
-- Name: skill_taxonomy; Type: TABLE; Schema: skills; Owner: -
--

CREATE TABLE skills.skill_taxonomy (
    id uuid NOT NULL,
    code character varying(64) NOT NULL,
    name character varying(200) NOT NULL,
    category character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: branches; Type: TABLE; Schema: tenancy; Owner: -
--

CREATE TABLE tenancy.branches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    code character varying(64) NOT NULL,
    timezone character varying(64),
    address jsonb DEFAULT '{}'::jsonb NOT NULL,
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: companies; Type: TABLE; Schema: tenancy; Owner: -
--

CREATE TABLE tenancy.companies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    legal_name character varying(200),
    currency_code character varying(8),
    timezone character varying(64),
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: grades; Type: TABLE; Schema: tenancy; Owner: -
--

CREATE TABLE tenancy.grades (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    level integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: job_titles; Type: TABLE; Schema: tenancy; Owner: -
--

CREATE TABLE tenancy.job_titles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: org_units; Type: TABLE; Schema: tenancy; Owner: -
--

CREATE TABLE tenancy.org_units (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    branch_id uuid,
    parent_id uuid,
    name character varying(200) NOT NULL,
    unit_type character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tenants; Type: TABLE; Schema: tenancy; Owner: -
--

CREATE TABLE tenancy.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(200) NOT NULL,
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_tenancy_tenants_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'INACTIVE'::character varying, 'SUSPENDED'::character varying])::text[])))
);


--
-- Name: artifacts; Type: TABLE; Schema: vision; Owner: -
--

CREATE TABLE vision.artifacts (
    id uuid NOT NULL,
    job_id uuid NOT NULL,
    type character varying(16) NOT NULL,
    path text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL,
    CONSTRAINT ck_artifacts_type CHECK (((type)::text = ANY ((ARRAY['csv'::character varying, 'pdf'::character varying, 'json'::character varying])::text[])))
);


--
-- Name: cameras; Type: TABLE; Schema: vision; Owner: -
--

CREATE TABLE vision.cameras (
    id uuid NOT NULL,
    branch_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    placement character varying(200),
    calibration_json jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: events; Type: TABLE; Schema: vision; Owner: -
--

CREATE TABLE vision.events (
    id uuid NOT NULL,
    job_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    event_type character varying(16) NOT NULL,
    entrance_id character varying(64),
    track_key character varying(64) NOT NULL,
    employee_id uuid,
    confidence double precision,
    snapshot_path text,
    is_inferred boolean DEFAULT false NOT NULL,
    meta jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL,
    CONSTRAINT ck_events_event_type CHECK (((event_type)::text = ANY ((ARRAY['entry'::character varying, 'exit'::character varying])::text[])))
);


--
-- Name: jobs; Type: TABLE; Schema: vision; Owner: -
--

CREATE TABLE vision.jobs (
    id uuid NOT NULL,
    video_id uuid NOT NULL,
    status character varying(32) DEFAULT 'PENDING'::character varying NOT NULL,
    progress integer DEFAULT 0 NOT NULL,
    pipeline_version character varying(64) DEFAULT 'v1'::character varying NOT NULL,
    model_versions_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    config_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    tenant_id uuid NOT NULL,
    CONSTRAINT ck_jobs_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'RUNNING'::character varying, 'POSTPROCESSING'::character varying, 'DONE'::character varying, 'FAILED'::character varying, 'CANCELED'::character varying])::text[])))
);


--
-- Name: metrics_hourly; Type: TABLE; Schema: vision; Owner: -
--

CREATE TABLE vision.metrics_hourly (
    id uuid NOT NULL,
    job_id uuid NOT NULL,
    hour_start_ts timestamp with time zone NOT NULL,
    entries integer DEFAULT 0 NOT NULL,
    exits integer DEFAULT 0 NOT NULL,
    unique_visitors integer DEFAULT 0 NOT NULL,
    avg_dwell_sec double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: tracks; Type: TABLE; Schema: vision; Owner: -
--

CREATE TABLE vision.tracks (
    id uuid NOT NULL,
    job_id uuid NOT NULL,
    track_key character varying(64) NOT NULL,
    entrance_id character varying(64),
    first_ts timestamp with time zone NOT NULL,
    last_ts timestamp with time zone NOT NULL,
    best_snapshot_path text,
    assigned_type character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    employee_id uuid,
    identity_confidence double precision,
    first_seen_zone character varying(16),
    last_seen_zone character varying(16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL,
    CONSTRAINT ck_tracks_assigned_type CHECK (((assigned_type)::text = ANY ((ARRAY['employee'::character varying, 'visitor'::character varying, 'unknown'::character varying])::text[])))
);


--
-- Name: videos; Type: TABLE; Schema: vision; Owner: -
--

CREATE TABLE vision.videos (
    id uuid NOT NULL,
    branch_id uuid NOT NULL,
    camera_id uuid NOT NULL,
    business_date date NOT NULL,
    file_path text NOT NULL,
    sha256 character varying(64),
    duration_sec double precision,
    fps double precision,
    width integer,
    height integer,
    uploaded_by character varying(200),
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    recorded_start_ts timestamp with time zone,
    tenant_id uuid NOT NULL
);


--
-- Name: task_assignments; Type: TABLE; Schema: work; Owner: -
--

CREATE TABLE work.task_assignments (
    id uuid NOT NULL,
    task_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    assigned_by character varying(32) DEFAULT 'auto'::character varying NOT NULL,
    score double precision NOT NULL,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    tenant_id uuid NOT NULL
);


--
-- Name: task_required_skills; Type: TABLE; Schema: work; Owner: -
--

CREATE TABLE work.task_required_skills (
    task_id uuid NOT NULL,
    skill_id uuid NOT NULL,
    min_proficiency integer DEFAULT 1 NOT NULL,
    required boolean DEFAULT true NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: tasks; Type: TABLE; Schema: work; Owner: -
--

CREATE TABLE work.tasks (
    id uuid NOT NULL,
    branch_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    task_type character varying(64),
    priority integer DEFAULT 3 NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    window_start timestamp with time zone,
    window_end timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: notification_outbox; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.notification_outbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    channel character varying(32) NOT NULL,
    recipient_user_id uuid NOT NULL,
    template_code character varying(64) NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    status character varying(32) DEFAULT 'PENDING'::character varying NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    next_retry_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    dedupe_key text
);


--
-- Name: notifications; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    recipient_user_id uuid NOT NULL,
    outbox_id uuid NOT NULL,
    type text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    entity_type text,
    entity_id uuid,
    action_url text,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    read_at timestamp with time zone
);


--
-- Name: request_attachments; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.request_attachments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_id uuid NOT NULL,
    file_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    note text
);


--
-- Name: request_comments; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.request_comments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    request_id uuid NOT NULL,
    author_user_id uuid NOT NULL,
    body text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: request_events; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.request_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_id uuid NOT NULL,
    actor_user_id uuid,
    event_type text NOT NULL,
    data jsonb DEFAULT '{}'::jsonb NOT NULL,
    correlation_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: request_step_assignees; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.request_step_assignees (
    tenant_id uuid NOT NULL,
    step_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: request_steps; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.request_steps (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    request_id uuid NOT NULL,
    step_order integer NOT NULL,
    approver_user_id uuid,
    decision character varying(32),
    decided_at timestamp with time zone,
    comment text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    assignee_type text,
    assignee_role_code text,
    assignee_user_id uuid
);


--
-- Name: request_types; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.request_types (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(64) NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: requests; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    branch_id uuid,
    request_type_id uuid NOT NULL,
    workflow_definition_id uuid NOT NULL,
    requester_employee_id uuid NOT NULL,
    subject text,
    status character varying(32) DEFAULT 'draft'::character varying NOT NULL,
    current_step integer DEFAULT 0 NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_user_id uuid,
    subject_employee_id uuid,
    entity_type text,
    entity_id uuid,
    idempotency_key text,
    CONSTRAINT ck_workflow_requests_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'submitted'::character varying, 'approved'::character varying, 'rejected'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: v_pending_approvals; Type: VIEW; Schema: workflow; Owner: -
--

CREATE VIEW workflow.v_pending_approvals AS
 SELECT r.id AS request_id,
    r.tenant_id,
    r.company_id,
    r.branch_id,
    r.request_type_id,
    r.workflow_definition_id,
    r.requester_employee_id,
    r.subject,
    r.status,
    r.current_step,
    r.created_at,
    s.id AS request_step_id,
    s.step_order,
    s.approver_user_id
   FROM (workflow.requests r
     JOIN workflow.request_steps s ON ((s.request_id = r.id)))
  WHERE (s.decision IS NULL);


--
-- Name: workflow_definition_steps; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.workflow_definition_steps (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    workflow_definition_id uuid NOT NULL,
    step_order integer NOT NULL,
    approver_mode character varying(32) NOT NULL,
    role_code character varying(64),
    user_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    scope_mode text DEFAULT 'TENANT'::text NOT NULL,
    fallback_role_code text
);


--
-- Name: workflow_definitions; Type: TABLE; Schema: workflow; Owner: -
--

CREATE TABLE workflow.workflow_definitions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid,
    request_type_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    code text,
    version integer
);


--
-- Name: pos_summary pos_summary_pkey; Type: CONSTRAINT; Schema: analytics; Owner: -
--

ALTER TABLE ONLY analytics.pos_summary
    ADD CONSTRAINT pos_summary_pkey PRIMARY KEY (dataset_id, employee_id);


--
-- Name: attendance_daily attendance_daily_pkey; Type: CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_daily
    ADD CONSTRAINT attendance_daily_pkey PRIMARY KEY (id);


--
-- Name: attendance_summary attendance_summary_pkey; Type: CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_summary
    ADD CONSTRAINT attendance_summary_pkey PRIMARY KEY (dataset_id, employee_id);


--
-- Name: day_overrides day_overrides_pkey; Type: CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.day_overrides
    ADD CONSTRAINT day_overrides_pkey PRIMARY KEY (id);


--
-- Name: attendance_daily uq_attendance_store_date_employee; Type: CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_daily
    ADD CONSTRAINT uq_attendance_store_date_employee UNIQUE (branch_id, business_date, employee_id);


--
-- Name: day_overrides uq_day_overrides_unique; Type: CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.day_overrides
    ADD CONSTRAINT uq_day_overrides_unique UNIQUE (tenant_id, employee_id, day, source_type, source_id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: document_links document_links_pkey; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_links
    ADD CONSTRAINT document_links_pkey PRIMARY KEY (id);


--
-- Name: document_types document_types_pkey; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_types
    ADD CONSTRAINT document_types_pkey PRIMARY KEY (id);


--
-- Name: document_versions document_versions_pkey; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_versions
    ADD CONSTRAINT document_versions_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: expiry_events expiry_events_pkey; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.expiry_events
    ADD CONSTRAINT expiry_events_pkey PRIMARY KEY (id);


--
-- Name: expiry_rules expiry_rules_pkey; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.expiry_rules
    ADD CONSTRAINT expiry_rules_pkey PRIMARY KEY (id);


--
-- Name: files files_pkey; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);


--
-- Name: document_types uq_document_types_tenant_code; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_types
    ADD CONSTRAINT uq_document_types_tenant_code UNIQUE (tenant_id, code);


--
-- Name: document_versions uq_document_versions_doc_v; Type: CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_versions
    ADD CONSTRAINT uq_document_versions_doc_v UNIQUE (document_id, version);


--
-- Name: employee_faces employee_faces_pkey; Type: CONSTRAINT; Schema: face; Owner: -
--

ALTER TABLE ONLY face.employee_faces
    ADD CONSTRAINT employee_faces_pkey PRIMARY KEY (id);


--
-- Name: hr_application_notes hr_application_notes_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_application_notes
    ADD CONSTRAINT hr_application_notes_pkey PRIMARY KEY (id);


--
-- Name: hr_applications hr_applications_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT hr_applications_pkey PRIMARY KEY (id);


--
-- Name: hr_onboarding_plans hr_onboarding_plans_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_plans
    ADD CONSTRAINT hr_onboarding_plans_pkey PRIMARY KEY (id);


--
-- Name: hr_onboarding_tasks hr_onboarding_tasks_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_tasks
    ADD CONSTRAINT hr_onboarding_tasks_pkey PRIMARY KEY (id);


--
-- Name: hr_openings hr_openings_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_openings
    ADD CONSTRAINT hr_openings_pkey PRIMARY KEY (id);


--
-- Name: hr_pipeline_stages hr_pipeline_stages_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_pipeline_stages
    ADD CONSTRAINT hr_pipeline_stages_pkey PRIMARY KEY (id);


--
-- Name: hr_resume_batches hr_resume_batches_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_batches
    ADD CONSTRAINT hr_resume_batches_pkey PRIMARY KEY (id);


--
-- Name: hr_resume_views hr_resume_views_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_views
    ADD CONSTRAINT hr_resume_views_pkey PRIMARY KEY (id);


--
-- Name: hr_resumes hr_resumes_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resumes
    ADD CONSTRAINT hr_resumes_pkey PRIMARY KEY (id);


--
-- Name: hr_screening_explanations hr_screening_explanations_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_explanations
    ADD CONSTRAINT hr_screening_explanations_pkey PRIMARY KEY (run_id, resume_id);


--
-- Name: hr_screening_results hr_screening_results_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_results
    ADD CONSTRAINT hr_screening_results_pkey PRIMARY KEY (run_id, resume_id);


--
-- Name: hr_screening_runs hr_screening_runs_pkey; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_runs
    ADD CONSTRAINT hr_screening_runs_pkey PRIMARY KEY (id);


--
-- Name: hr_applications uq_hr_applications_opening_resume; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT uq_hr_applications_opening_resume UNIQUE (opening_id, resume_id);


--
-- Name: hr_pipeline_stages uq_hr_pipeline_stages_opening_name; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_pipeline_stages
    ADD CONSTRAINT uq_hr_pipeline_stages_opening_name UNIQUE (opening_id, name);


--
-- Name: hr_resume_views uq_hr_resume_views_resume_type; Type: CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_views
    ADD CONSTRAINT uq_hr_resume_views_resume_type UNIQUE (resume_id, view_type);


--
-- Name: employee_bank_accounts employee_bank_accounts_pkey; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_bank_accounts
    ADD CONSTRAINT employee_bank_accounts_pkey PRIMARY KEY (id);


--
-- Name: employee_contracts employee_contracts_pkey; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_contracts
    ADD CONSTRAINT employee_contracts_pkey PRIMARY KEY (id);


--
-- Name: employee_dependents employee_dependents_pkey; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_dependents
    ADD CONSTRAINT employee_dependents_pkey PRIMARY KEY (id);


--
-- Name: employee_employment employee_employment_pkey; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT employee_employment_pkey PRIMARY KEY (id);


--
-- Name: employee_government_ids employee_government_ids_pkey; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_government_ids
    ADD CONSTRAINT employee_government_ids_pkey PRIMARY KEY (id);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (id);


--
-- Name: persons persons_pkey; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.persons
    ADD CONSTRAINT persons_pkey PRIMARY KEY (id);


--
-- Name: employee_user_links pk_employee_user_links; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_user_links
    ADD CONSTRAINT pk_employee_user_links PRIMARY KEY (employee_id);


--
-- Name: employee_user_links uq_employee_user_links_user_id; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_user_links
    ADD CONSTRAINT uq_employee_user_links_user_id UNIQUE (user_id);


--
-- Name: employees uq_hr_employees_company_employee_code; Type: CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employees
    ADD CONSTRAINT uq_hr_employees_company_employee_code UNIQUE (company_id, employee_code);


--
-- Name: api_tokens api_tokens_pkey; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.api_tokens
    ADD CONSTRAINT api_tokens_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: role_permissions pk_role_permissions; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.role_permissions
    ADD CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: api_tokens uq_api_tokens_tenant_name; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.api_tokens
    ADD CONSTRAINT uq_api_tokens_tenant_name UNIQUE (tenant_id, name);


--
-- Name: permissions uq_permissions_code; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.permissions
    ADD CONSTRAINT uq_permissions_code UNIQUE (code);


--
-- Name: roles uq_roles_code; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.roles
    ADD CONSTRAINT uq_roles_code UNIQUE (code);


--
-- Name: user_roles uq_user_roles_scope; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.user_roles
    ADD CONSTRAINT uq_user_roles_scope UNIQUE NULLS NOT DISTINCT (user_id, tenant_id, role_id, company_id, branch_id);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: datasets datasets_pkey; Type: CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.datasets
    ADD CONSTRAINT datasets_pkey PRIMARY KEY (id);


--
-- Name: month_state pk_month_state; Type: CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.month_state
    ADD CONSTRAINT pk_month_state PRIMARY KEY (tenant_id, branch_id, month_key);


--
-- Name: datasets uq_datasets_tenant_branch_month_checksum; Type: CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.datasets
    ADD CONSTRAINT uq_datasets_tenant_branch_month_checksum UNIQUE (tenant_id, branch_id, month_key, checksum);


--
-- Name: employee_leave_policy employee_leave_policy_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.employee_leave_policy
    ADD CONSTRAINT employee_leave_policy_pkey PRIMARY KEY (id);


--
-- Name: holidays holidays_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.holidays
    ADD CONSTRAINT holidays_pkey PRIMARY KEY (id);


--
-- Name: leave_ledger leave_ledger_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_ledger
    ADD CONSTRAINT leave_ledger_pkey PRIMARY KEY (id);


--
-- Name: leave_policies leave_policies_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policies
    ADD CONSTRAINT leave_policies_pkey PRIMARY KEY (id);


--
-- Name: leave_policy_rules leave_policy_rules_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policy_rules
    ADD CONSTRAINT leave_policy_rules_pkey PRIMARY KEY (id);


--
-- Name: leave_request_days leave_request_days_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_request_days
    ADD CONSTRAINT leave_request_days_pkey PRIMARY KEY (id);


--
-- Name: leave_requests leave_requests_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT leave_requests_pkey PRIMARY KEY (id);


--
-- Name: leave_types leave_types_pkey; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_types
    ADD CONSTRAINT leave_types_pkey PRIMARY KEY (id);


--
-- Name: weekly_off pk_leave_weekly_off; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.weekly_off
    ADD CONSTRAINT pk_leave_weekly_off PRIMARY KEY (tenant_id, branch_id, weekday);


--
-- Name: leave_policies uq_leave_policies_tenant_code; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policies
    ADD CONSTRAINT uq_leave_policies_tenant_code UNIQUE (tenant_id, code);


--
-- Name: leave_policy_rules uq_leave_policy_rules_unique; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policy_rules
    ADD CONSTRAINT uq_leave_policy_rules_unique UNIQUE (tenant_id, policy_id, leave_type_id);


--
-- Name: leave_request_days uq_leave_request_days_unique; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_request_days
    ADD CONSTRAINT uq_leave_request_days_unique UNIQUE (tenant_id, leave_request_id, day);


--
-- Name: leave_types uq_leave_types_tenant_code; Type: CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_types
    ADD CONSTRAINT uq_leave_types_tenant_code UNIQUE (tenant_id, code);


--
-- Name: mobile_accounts mobile_accounts_pkey; Type: CONSTRAINT; Schema: mobile; Owner: -
--

ALTER TABLE ONLY mobile.mobile_accounts
    ADD CONSTRAINT mobile_accounts_pkey PRIMARY KEY (id);


--
-- Name: mobile_accounts uq_mobile_accounts_firebase_uid; Type: CONSTRAINT; Schema: mobile; Owner: -
--

ALTER TABLE ONLY mobile.mobile_accounts
    ADD CONSTRAINT uq_mobile_accounts_firebase_uid UNIQUE (firebase_uid);


--
-- Name: mobile_accounts uq_mobile_accounts_store_employee; Type: CONSTRAINT; Schema: mobile; Owner: -
--

ALTER TABLE ONLY mobile.mobile_accounts
    ADD CONSTRAINT uq_mobile_accounts_store_employee UNIQUE (branch_id, employee_id);


--
-- Name: employee_skills pk_employee_skills; Type: CONSTRAINT; Schema: skills; Owner: -
--

ALTER TABLE ONLY skills.employee_skills
    ADD CONSTRAINT pk_employee_skills PRIMARY KEY (employee_id, skill_id);


--
-- Name: skill_taxonomy skill_taxonomy_pkey; Type: CONSTRAINT; Schema: skills; Owner: -
--

ALTER TABLE ONLY skills.skill_taxonomy
    ADD CONSTRAINT skill_taxonomy_pkey PRIMARY KEY (id);


--
-- Name: skill_taxonomy uq_skill_taxonomy_tenant_code; Type: CONSTRAINT; Schema: skills; Owner: -
--

ALTER TABLE ONLY skills.skill_taxonomy
    ADD CONSTRAINT uq_skill_taxonomy_tenant_code UNIQUE (tenant_id, code);


--
-- Name: branches branches_pkey; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.branches
    ADD CONSTRAINT branches_pkey PRIMARY KEY (id);


--
-- Name: companies companies_pkey; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (id);


--
-- Name: grades grades_pkey; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.grades
    ADD CONSTRAINT grades_pkey PRIMARY KEY (id);


--
-- Name: job_titles job_titles_pkey; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.job_titles
    ADD CONSTRAINT job_titles_pkey PRIMARY KEY (id);


--
-- Name: org_units org_units_pkey; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.org_units
    ADD CONSTRAINT org_units_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: branches uq_branches_company_code; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.branches
    ADD CONSTRAINT uq_branches_company_code UNIQUE (company_id, code);


--
-- Name: branches uq_branches_company_name; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.branches
    ADD CONSTRAINT uq_branches_company_name UNIQUE (company_id, name);


--
-- Name: companies uq_companies_tenant_name; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.companies
    ADD CONSTRAINT uq_companies_tenant_name UNIQUE (tenant_id, name);


--
-- Name: grades uq_grades_company_name; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.grades
    ADD CONSTRAINT uq_grades_company_name UNIQUE (company_id, name);


--
-- Name: job_titles uq_job_titles_company_name; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.job_titles
    ADD CONSTRAINT uq_job_titles_company_name UNIQUE (company_id, name);


--
-- Name: org_units uq_org_units_company_parent_name; Type: CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.org_units
    ADD CONSTRAINT uq_org_units_company_parent_name UNIQUE (company_id, parent_id, name);


--
-- Name: artifacts artifacts_pkey; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.artifacts
    ADD CONSTRAINT artifacts_pkey PRIMARY KEY (id);


--
-- Name: cameras cameras_pkey; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.cameras
    ADD CONSTRAINT cameras_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: metrics_hourly metrics_hourly_pkey; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.metrics_hourly
    ADD CONSTRAINT metrics_hourly_pkey PRIMARY KEY (id);


--
-- Name: tracks tracks_pkey; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.tracks
    ADD CONSTRAINT tracks_pkey PRIMARY KEY (id);


--
-- Name: metrics_hourly uq_metrics_job_hour; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.metrics_hourly
    ADD CONSTRAINT uq_metrics_job_hour UNIQUE (job_id, hour_start_ts);


--
-- Name: tracks uq_tracks_job_track_key; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.tracks
    ADD CONSTRAINT uq_tracks_job_track_key UNIQUE (job_id, track_key);


--
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);


--
-- Name: task_required_skills pk_task_required_skills; Type: CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_required_skills
    ADD CONSTRAINT pk_task_required_skills PRIMARY KEY (task_id, skill_id);


--
-- Name: task_assignments task_assignments_pkey; Type: CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_assignments
    ADD CONSTRAINT task_assignments_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: notification_outbox notification_outbox_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notification_outbox
    ADD CONSTRAINT notification_outbox_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: request_step_assignees pk_request_step_assignees; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_step_assignees
    ADD CONSTRAINT pk_request_step_assignees PRIMARY KEY (step_id, user_id);


--
-- Name: request_attachments request_attachments_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_attachments
    ADD CONSTRAINT request_attachments_pkey PRIMARY KEY (id);


--
-- Name: request_comments request_comments_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_comments
    ADD CONSTRAINT request_comments_pkey PRIMARY KEY (id);


--
-- Name: request_events request_events_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_events
    ADD CONSTRAINT request_events_pkey PRIMARY KEY (id);


--
-- Name: request_steps request_steps_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_steps
    ADD CONSTRAINT request_steps_pkey PRIMARY KEY (id);


--
-- Name: request_types request_types_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_types
    ADD CONSTRAINT request_types_pkey PRIMARY KEY (id);


--
-- Name: requests requests_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT requests_pkey PRIMARY KEY (id);


--
-- Name: notifications uq_notifications_outbox_id; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notifications
    ADD CONSTRAINT uq_notifications_outbox_id UNIQUE (outbox_id);


--
-- Name: request_steps uq_request_steps_request_order; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_steps
    ADD CONSTRAINT uq_request_steps_request_order UNIQUE (request_id, step_order);


--
-- Name: request_types uq_request_types_code; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_types
    ADD CONSTRAINT uq_request_types_code UNIQUE (code);


--
-- Name: workflow_definition_steps uq_workflow_definition_steps_order; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definition_steps
    ADD CONSTRAINT uq_workflow_definition_steps_order UNIQUE (workflow_definition_id, step_order);


--
-- Name: workflow_definition_steps workflow_definition_steps_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definition_steps
    ADD CONSTRAINT workflow_definition_steps_pkey PRIMARY KEY (id);


--
-- Name: workflow_definitions workflow_definitions_pkey; Type: CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definitions
    ADD CONSTRAINT workflow_definitions_pkey PRIMARY KEY (id);


--
-- Name: ix_analytics_pos_summary_employee_id; Type: INDEX; Schema: analytics; Owner: -
--

CREATE INDEX ix_analytics_pos_summary_employee_id ON analytics.pos_summary USING btree (employee_id);


--
-- Name: ix_analytics_pos_summary_tenant_id; Type: INDEX; Schema: analytics; Owner: -
--

CREATE INDEX ix_analytics_pos_summary_tenant_id ON analytics.pos_summary USING btree (tenant_id);


--
-- Name: ix_attendance_attendance_daily_tenant_id; Type: INDEX; Schema: attendance; Owner: -
--

CREATE INDEX ix_attendance_attendance_daily_tenant_id ON attendance.attendance_daily USING btree (tenant_id);


--
-- Name: ix_attendance_attendance_summary_employee_id; Type: INDEX; Schema: attendance; Owner: -
--

CREATE INDEX ix_attendance_attendance_summary_employee_id ON attendance.attendance_summary USING btree (employee_id);


--
-- Name: ix_attendance_attendance_summary_tenant_id; Type: INDEX; Schema: attendance; Owner: -
--

CREATE INDEX ix_attendance_attendance_summary_tenant_id ON attendance.attendance_summary USING btree (tenant_id);


--
-- Name: ix_attendance_daily_business_date; Type: INDEX; Schema: attendance; Owner: -
--

CREATE INDEX ix_attendance_daily_business_date ON attendance.attendance_daily USING btree (business_date);


--
-- Name: ix_attendance_daily_employee_id; Type: INDEX; Schema: attendance; Owner: -
--

CREATE INDEX ix_attendance_daily_employee_id ON attendance.attendance_daily USING btree (employee_id);


--
-- Name: ix_attendance_daily_store_id; Type: INDEX; Schema: attendance; Owner: -
--

CREATE INDEX ix_attendance_daily_store_id ON attendance.attendance_daily USING btree (branch_id);


--
-- Name: ix_day_overrides_employee_day; Type: INDEX; Schema: attendance; Owner: -
--

CREATE INDEX ix_day_overrides_employee_day ON attendance.day_overrides USING btree (tenant_id, employee_id, day);


--
-- Name: ix_audit_log_entity; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_audit_log_entity ON audit.audit_log USING btree (tenant_id, entity_type, entity_id);


--
-- Name: ix_audit_log_tenant_created_at; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_audit_log_tenant_created_at ON audit.audit_log USING btree (tenant_id, created_at);


--
-- Name: ix_document_links_tenant_entity; Type: INDEX; Schema: dms; Owner: -
--

CREATE INDEX ix_document_links_tenant_entity ON dms.document_links USING btree (tenant_id, entity_type, entity_id);


--
-- Name: ix_document_versions_document_id; Type: INDEX; Schema: dms; Owner: -
--

CREATE INDEX ix_document_versions_document_id ON dms.document_versions USING btree (document_id);


--
-- Name: ix_documents_tenant_expires_at; Type: INDEX; Schema: dms; Owner: -
--

CREATE INDEX ix_documents_tenant_expires_at ON dms.documents USING btree (tenant_id, expires_at) WHERE (expires_at IS NOT NULL);


--
-- Name: ix_expiry_events_tenant_id_fired_at; Type: INDEX; Schema: dms; Owner: -
--

CREATE INDEX ix_expiry_events_tenant_id_fired_at ON dms.expiry_events USING btree (tenant_id, fired_at);


--
-- Name: ix_expiry_rules_tenant_id; Type: INDEX; Schema: dms; Owner: -
--

CREATE INDEX ix_expiry_rules_tenant_id ON dms.expiry_rules USING btree (tenant_id);


--
-- Name: ix_files_tenant_id; Type: INDEX; Schema: dms; Owner: -
--

CREATE INDEX ix_files_tenant_id ON dms.files USING btree (tenant_id);


--
-- Name: ix_employee_faces_employee_id; Type: INDEX; Schema: face; Owner: -
--

CREATE INDEX ix_employee_faces_employee_id ON face.employee_faces USING btree (employee_id);


--
-- Name: ix_face_employee_faces_tenant_id; Type: INDEX; Schema: face; Owner: -
--

CREATE INDEX ix_face_employee_faces_tenant_id ON face.employee_faces USING btree (tenant_id);


--
-- Name: ix_hr_application_notes_application_created_at; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_application_notes_application_created_at ON hr.hr_application_notes USING btree (application_id, created_at);


--
-- Name: ix_hr_applications_employee_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_applications_employee_id ON hr.hr_applications USING btree (employee_id);


--
-- Name: ix_hr_applications_opening_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_applications_opening_id ON hr.hr_applications USING btree (opening_id);


--
-- Name: ix_hr_applications_stage_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_applications_stage_id ON hr.hr_applications USING btree (stage_id);


--
-- Name: ix_hr_applications_status; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_applications_status ON hr.hr_applications USING btree (status);


--
-- Name: ix_hr_applications_store_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_applications_store_id ON hr.hr_applications USING btree (branch_id);


--
-- Name: ix_hr_hr_application_notes_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_application_notes_tenant_id ON hr.hr_application_notes USING btree (tenant_id);


--
-- Name: ix_hr_hr_applications_company_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_applications_company_id ON hr.hr_applications USING btree (company_id);


--
-- Name: ix_hr_hr_applications_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_applications_tenant_id ON hr.hr_applications USING btree (tenant_id);


--
-- Name: ix_hr_hr_onboarding_plans_company_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_onboarding_plans_company_id ON hr.hr_onboarding_plans USING btree (company_id);


--
-- Name: ix_hr_hr_onboarding_plans_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_onboarding_plans_tenant_id ON hr.hr_onboarding_plans USING btree (tenant_id);


--
-- Name: ix_hr_hr_onboarding_tasks_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_onboarding_tasks_tenant_id ON hr.hr_onboarding_tasks USING btree (tenant_id);


--
-- Name: ix_hr_hr_openings_company_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_openings_company_id ON hr.hr_openings USING btree (company_id);


--
-- Name: ix_hr_hr_openings_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_openings_tenant_id ON hr.hr_openings USING btree (tenant_id);


--
-- Name: ix_hr_hr_pipeline_stages_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_pipeline_stages_tenant_id ON hr.hr_pipeline_stages USING btree (tenant_id);


--
-- Name: ix_hr_hr_resume_batches_company_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_resume_batches_company_id ON hr.hr_resume_batches USING btree (company_id);


--
-- Name: ix_hr_hr_resume_batches_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_resume_batches_tenant_id ON hr.hr_resume_batches USING btree (tenant_id);


--
-- Name: ix_hr_hr_resume_views_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_resume_views_tenant_id ON hr.hr_resume_views USING btree (tenant_id);


--
-- Name: ix_hr_hr_resumes_company_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_resumes_company_id ON hr.hr_resumes USING btree (company_id);


--
-- Name: ix_hr_hr_resumes_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_resumes_tenant_id ON hr.hr_resumes USING btree (tenant_id);


--
-- Name: ix_hr_hr_screening_explanations_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_screening_explanations_tenant_id ON hr.hr_screening_explanations USING btree (tenant_id);


--
-- Name: ix_hr_hr_screening_results_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_screening_results_tenant_id ON hr.hr_screening_results USING btree (tenant_id);


--
-- Name: ix_hr_hr_screening_runs_company_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_screening_runs_company_id ON hr.hr_screening_runs USING btree (company_id);


--
-- Name: ix_hr_hr_screening_runs_tenant_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_hr_screening_runs_tenant_id ON hr.hr_screening_runs USING btree (tenant_id);


--
-- Name: ix_hr_onboarding_plans_employee_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_onboarding_plans_employee_id ON hr.hr_onboarding_plans USING btree (employee_id);


--
-- Name: ix_hr_onboarding_plans_status; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_onboarding_plans_status ON hr.hr_onboarding_plans USING btree (status);


--
-- Name: ix_hr_onboarding_plans_store_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_onboarding_plans_store_id ON hr.hr_onboarding_plans USING btree (branch_id);


--
-- Name: ix_hr_onboarding_tasks_plan_sort; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_onboarding_tasks_plan_sort ON hr.hr_onboarding_tasks USING btree (plan_id, sort_order);


--
-- Name: ix_hr_onboarding_tasks_plan_status; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_onboarding_tasks_plan_status ON hr.hr_onboarding_tasks USING btree (plan_id, status);


--
-- Name: ix_hr_openings_status; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_openings_status ON hr.hr_openings USING btree (status);


--
-- Name: ix_hr_openings_store_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_openings_store_id ON hr.hr_openings USING btree (branch_id);


--
-- Name: ix_hr_pipeline_stages_opening_sort; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_pipeline_stages_opening_sort ON hr.hr_pipeline_stages USING btree (opening_id, sort_order);


--
-- Name: ix_hr_resume_batches_opening_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resume_batches_opening_id ON hr.hr_resume_batches USING btree (opening_id);


--
-- Name: ix_hr_resume_batches_store_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resume_batches_store_id ON hr.hr_resume_batches USING btree (branch_id);


--
-- Name: ix_hr_resume_views_embedding_ivfflat; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resume_views_embedding_ivfflat ON hr.hr_resume_views USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: ix_hr_resume_views_resume_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resume_views_resume_id ON hr.hr_resume_views USING btree (resume_id);


--
-- Name: ix_hr_resume_views_updated_at; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resume_views_updated_at ON hr.hr_resume_views USING btree (updated_at);


--
-- Name: ix_hr_resume_views_view_type; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resume_views_view_type ON hr.hr_resume_views USING btree (view_type);


--
-- Name: ix_hr_resumes_embedding_status; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resumes_embedding_status ON hr.hr_resumes USING btree (embedding_status);


--
-- Name: ix_hr_resumes_opening_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resumes_opening_id ON hr.hr_resumes USING btree (opening_id);


--
-- Name: ix_hr_resumes_status; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resumes_status ON hr.hr_resumes USING btree (status);


--
-- Name: ix_hr_resumes_store_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_resumes_store_id ON hr.hr_resumes USING btree (branch_id);


--
-- Name: ix_hr_screening_explanations_run_created_at; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_explanations_run_created_at ON hr.hr_screening_explanations USING btree (run_id, created_at);


--
-- Name: ix_hr_screening_explanations_run_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_explanations_run_id ON hr.hr_screening_explanations USING btree (run_id);


--
-- Name: ix_hr_screening_results_run_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_results_run_id ON hr.hr_screening_results USING btree (run_id);


--
-- Name: ix_hr_screening_results_run_rank; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_results_run_rank ON hr.hr_screening_results USING btree (run_id, rank);


--
-- Name: ix_hr_screening_runs_created_at; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_runs_created_at ON hr.hr_screening_runs USING btree (created_at);


--
-- Name: ix_hr_screening_runs_opening_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_runs_opening_id ON hr.hr_screening_runs USING btree (opening_id);


--
-- Name: ix_hr_screening_runs_status; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_runs_status ON hr.hr_screening_runs USING btree (status);


--
-- Name: ix_hr_screening_runs_store_id; Type: INDEX; Schema: hr; Owner: -
--

CREATE INDEX ix_hr_screening_runs_store_id ON hr.hr_screening_runs USING btree (branch_id);


--
-- Name: ix_employee_bank_accounts_employee_id; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_employee_bank_accounts_employee_id ON hr_core.employee_bank_accounts USING btree (employee_id);


--
-- Name: ix_employee_contracts_employee_id; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_employee_contracts_employee_id ON hr_core.employee_contracts USING btree (employee_id);


--
-- Name: ix_employee_dependents_employee_id; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_employee_dependents_employee_id ON hr_core.employee_dependents USING btree (employee_id);


--
-- Name: ix_employee_employment_employee_id_start_date; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_employee_employment_employee_id_start_date ON hr_core.employee_employment USING btree (employee_id, start_date);


--
-- Name: ix_employee_employment_manager_current; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_employee_employment_manager_current ON hr_core.employee_employment USING btree (manager_employee_id) WHERE (end_date IS NULL);


--
-- Name: ix_employee_government_ids_employee_id; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_employee_government_ids_employee_id ON hr_core.employee_government_ids USING btree (employee_id);


--
-- Name: ix_employee_government_ids_tenant_expires_at; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_employee_government_ids_tenant_expires_at ON hr_core.employee_government_ids USING btree (tenant_id, expires_at) WHERE (expires_at IS NOT NULL);


--
-- Name: ix_hr_employees_tenant_id_status; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_hr_employees_tenant_id_status ON hr_core.employees USING btree (tenant_id, status);


--
-- Name: ix_persons_tenant_id; Type: INDEX; Schema: hr_core; Owner: -
--

CREATE INDEX ix_persons_tenant_id ON hr_core.persons USING btree (tenant_id);


--
-- Name: ix_api_tokens_tenant_id_status; Type: INDEX; Schema: iam; Owner: -
--

CREATE INDEX ix_api_tokens_tenant_id_status ON iam.api_tokens USING btree (tenant_id, status);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: iam; Owner: -
--

CREATE INDEX ix_refresh_tokens_user_id ON iam.refresh_tokens USING btree (user_id);


--
-- Name: ix_user_roles_tenant_id; Type: INDEX; Schema: iam; Owner: -
--

CREATE INDEX ix_user_roles_tenant_id ON iam.user_roles USING btree (tenant_id);


--
-- Name: ix_user_roles_user_id; Type: INDEX; Schema: iam; Owner: -
--

CREATE INDEX ix_user_roles_user_id ON iam.user_roles USING btree (user_id);


--
-- Name: uq_refresh_tokens_token_hash; Type: INDEX; Schema: iam; Owner: -
--

CREATE UNIQUE INDEX uq_refresh_tokens_token_hash ON iam.refresh_tokens USING btree (token_hash);


--
-- Name: uq_users_email_not_deleted; Type: INDEX; Schema: iam; Owner: -
--

CREATE UNIQUE INDEX uq_users_email_not_deleted ON iam.users USING btree (email) WHERE (deleted_at IS NULL);


--
-- Name: ix_datasets_month_key; Type: INDEX; Schema: imports; Owner: -
--

CREATE INDEX ix_datasets_month_key ON imports.datasets USING btree (month_key);


--
-- Name: ix_datasets_store_id; Type: INDEX; Schema: imports; Owner: -
--

CREATE INDEX ix_datasets_store_id ON imports.datasets USING btree (branch_id);


--
-- Name: ix_imports_datasets_tenant_id; Type: INDEX; Schema: imports; Owner: -
--

CREATE INDEX ix_imports_datasets_tenant_id ON imports.datasets USING btree (tenant_id);


--
-- Name: ix_imports_month_state_tenant_id; Type: INDEX; Schema: imports; Owner: -
--

CREATE INDEX ix_imports_month_state_tenant_id ON imports.month_state USING btree (tenant_id);


--
-- Name: ix_leave_holidays_tenant_branch_day; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_holidays_tenant_branch_day ON leave.holidays USING btree (tenant_id, branch_id, day);


--
-- Name: ix_leave_ledger_employee_type_year; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_ledger_employee_type_year ON leave.leave_ledger USING btree (tenant_id, employee_id, leave_type_id, period_year);


--
-- Name: ix_leave_ledger_source; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_ledger_source ON leave.leave_ledger USING btree (tenant_id, source_type, source_id);


--
-- Name: ix_leave_request_days_day; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_request_days_day ON leave.leave_request_days USING btree (tenant_id, day);


--
-- Name: ix_leave_request_days_employee_day; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_request_days_employee_day ON leave.leave_request_days USING btree (tenant_id, employee_id, day);


--
-- Name: ix_leave_requests_branch_dates; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_requests_branch_dates ON leave.leave_requests USING btree (tenant_id, branch_id, start_date, end_date);


--
-- Name: ix_leave_requests_employee_created_at; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_requests_employee_created_at ON leave.leave_requests USING btree (tenant_id, employee_id, created_at);


--
-- Name: ix_leave_types_tenant_is_active; Type: INDEX; Schema: leave; Owner: -
--

CREATE INDEX ix_leave_types_tenant_is_active ON leave.leave_types USING btree (tenant_id, is_active);


--
-- Name: uq_employee_leave_policy_active; Type: INDEX; Schema: leave; Owner: -
--

CREATE UNIQUE INDEX uq_employee_leave_policy_active ON leave.employee_leave_policy USING btree (tenant_id, employee_id) WHERE (effective_to IS NULL);


--
-- Name: uq_leave_holidays_branch; Type: INDEX; Schema: leave; Owner: -
--

CREATE UNIQUE INDEX uq_leave_holidays_branch ON leave.holidays USING btree (tenant_id, branch_id, day) WHERE (branch_id IS NOT NULL);


--
-- Name: uq_leave_holidays_global; Type: INDEX; Schema: leave; Owner: -
--

CREATE UNIQUE INDEX uq_leave_holidays_global ON leave.holidays USING btree (tenant_id, day) WHERE ((branch_id IS NULL) AND (company_id IS NULL));


--
-- Name: uq_leave_ledger_leave_request_idem; Type: INDEX; Schema: leave; Owner: -
--

CREATE UNIQUE INDEX uq_leave_ledger_leave_request_idem ON leave.leave_ledger USING btree (tenant_id, source_type, source_id, leave_type_id) WHERE ((source_type = 'LEAVE_REQUEST'::text) AND (source_id IS NOT NULL));


--
-- Name: uq_leave_requests_idempotency; Type: INDEX; Schema: leave; Owner: -
--

CREATE UNIQUE INDEX uq_leave_requests_idempotency ON leave.leave_requests USING btree (tenant_id, employee_id, idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: ix_mobile_accounts_employee_id; Type: INDEX; Schema: mobile; Owner: -
--

CREATE INDEX ix_mobile_accounts_employee_id ON mobile.mobile_accounts USING btree (employee_id);


--
-- Name: ix_mobile_accounts_org_id; Type: INDEX; Schema: mobile; Owner: -
--

CREATE INDEX ix_mobile_accounts_org_id ON mobile.mobile_accounts USING btree (tenant_id);


--
-- Name: ix_mobile_accounts_store_active; Type: INDEX; Schema: mobile; Owner: -
--

CREATE INDEX ix_mobile_accounts_store_active ON mobile.mobile_accounts USING btree (branch_id, active);


--
-- Name: ix_mobile_accounts_store_id; Type: INDEX; Schema: mobile; Owner: -
--

CREATE INDEX ix_mobile_accounts_store_id ON mobile.mobile_accounts USING btree (branch_id);


--
-- Name: ix_employee_skills_employee_id; Type: INDEX; Schema: skills; Owner: -
--

CREATE INDEX ix_employee_skills_employee_id ON skills.employee_skills USING btree (employee_id);


--
-- Name: ix_employee_skills_skill_id; Type: INDEX; Schema: skills; Owner: -
--

CREATE INDEX ix_employee_skills_skill_id ON skills.employee_skills USING btree (skill_id);


--
-- Name: ix_skills_employee_skills_tenant_id; Type: INDEX; Schema: skills; Owner: -
--

CREATE INDEX ix_skills_employee_skills_tenant_id ON skills.employee_skills USING btree (tenant_id);


--
-- Name: ix_skills_skill_taxonomy_tenant_id; Type: INDEX; Schema: skills; Owner: -
--

CREATE INDEX ix_skills_skill_taxonomy_tenant_id ON skills.skill_taxonomy USING btree (tenant_id);


--
-- Name: ix_branches_company_id; Type: INDEX; Schema: tenancy; Owner: -
--

CREATE INDEX ix_branches_company_id ON tenancy.branches USING btree (company_id);


--
-- Name: ix_companies_tenant_id; Type: INDEX; Schema: tenancy; Owner: -
--

CREATE INDEX ix_companies_tenant_id ON tenancy.companies USING btree (tenant_id);


--
-- Name: ix_org_units_branch_id; Type: INDEX; Schema: tenancy; Owner: -
--

CREATE INDEX ix_org_units_branch_id ON tenancy.org_units USING btree (branch_id);


--
-- Name: ix_org_units_company_id; Type: INDEX; Schema: tenancy; Owner: -
--

CREATE INDEX ix_org_units_company_id ON tenancy.org_units USING btree (company_id);


--
-- Name: ix_tenants_status; Type: INDEX; Schema: tenancy; Owner: -
--

CREATE INDEX ix_tenants_status ON tenancy.tenants USING btree (status);


--
-- Name: ix_artifacts_job_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_artifacts_job_id ON vision.artifacts USING btree (job_id);


--
-- Name: ix_cameras_store_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_cameras_store_id ON vision.cameras USING btree (branch_id);


--
-- Name: ix_events_employee_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_events_employee_id ON vision.events USING btree (employee_id);


--
-- Name: ix_events_employee_id_ts; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_events_employee_id_ts ON vision.events USING btree (employee_id, ts);


--
-- Name: ix_events_job_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_events_job_id ON vision.events USING btree (job_id);


--
-- Name: ix_events_job_id_ts; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_events_job_id_ts ON vision.events USING btree (job_id, ts);


--
-- Name: ix_jobs_video_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_jobs_video_id ON vision.jobs USING btree (video_id);


--
-- Name: ix_metrics_hourly_job_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_metrics_hourly_job_id ON vision.metrics_hourly USING btree (job_id);


--
-- Name: ix_tracks_employee_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_tracks_employee_id ON vision.tracks USING btree (employee_id);


--
-- Name: ix_tracks_job_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_tracks_job_id ON vision.tracks USING btree (job_id);


--
-- Name: ix_videos_business_date; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_videos_business_date ON vision.videos USING btree (business_date);


--
-- Name: ix_videos_camera_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_videos_camera_id ON vision.videos USING btree (camera_id);


--
-- Name: ix_videos_sha256; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_videos_sha256 ON vision.videos USING btree (sha256);


--
-- Name: ix_videos_store_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_videos_store_id ON vision.videos USING btree (branch_id);


--
-- Name: ix_vision_artifacts_tenant_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_vision_artifacts_tenant_id ON vision.artifacts USING btree (tenant_id);


--
-- Name: ix_vision_cameras_tenant_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_vision_cameras_tenant_id ON vision.cameras USING btree (tenant_id);


--
-- Name: ix_vision_events_tenant_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_vision_events_tenant_id ON vision.events USING btree (tenant_id);


--
-- Name: ix_vision_jobs_tenant_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_vision_jobs_tenant_id ON vision.jobs USING btree (tenant_id);


--
-- Name: ix_vision_metrics_hourly_tenant_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_vision_metrics_hourly_tenant_id ON vision.metrics_hourly USING btree (tenant_id);


--
-- Name: ix_vision_tracks_tenant_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_vision_tracks_tenant_id ON vision.tracks USING btree (tenant_id);


--
-- Name: ix_vision_videos_tenant_id; Type: INDEX; Schema: vision; Owner: -
--

CREATE INDEX ix_vision_videos_tenant_id ON vision.videos USING btree (tenant_id);


--
-- Name: ix_task_assignments_employee_id; Type: INDEX; Schema: work; Owner: -
--

CREATE INDEX ix_task_assignments_employee_id ON work.task_assignments USING btree (employee_id);


--
-- Name: ix_task_assignments_task_id; Type: INDEX; Schema: work; Owner: -
--

CREATE INDEX ix_task_assignments_task_id ON work.task_assignments USING btree (task_id);


--
-- Name: ix_work_task_assignments_tenant_id; Type: INDEX; Schema: work; Owner: -
--

CREATE INDEX ix_work_task_assignments_tenant_id ON work.task_assignments USING btree (tenant_id);


--
-- Name: ix_work_task_required_skills_tenant_id; Type: INDEX; Schema: work; Owner: -
--

CREATE INDEX ix_work_task_required_skills_tenant_id ON work.task_required_skills USING btree (tenant_id);


--
-- Name: ix_work_tasks_store_status; Type: INDEX; Schema: work; Owner: -
--

CREATE INDEX ix_work_tasks_store_status ON work.tasks USING btree (branch_id, status);


--
-- Name: ix_work_tasks_tenant_id; Type: INDEX; Schema: work; Owner: -
--

CREATE INDEX ix_work_tasks_tenant_id ON work.tasks USING btree (tenant_id);


--
-- Name: ix_notification_outbox_tenant_status_retry; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_notification_outbox_tenant_status_retry ON workflow.notification_outbox USING btree (tenant_id, status, next_retry_at);


--
-- Name: ix_notifications_recipient_created_at; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_notifications_recipient_created_at ON workflow.notifications USING btree (tenant_id, recipient_user_id, created_at);


--
-- Name: ix_notifications_recipient_read_at; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_notifications_recipient_read_at ON workflow.notifications USING btree (tenant_id, recipient_user_id, read_at);


--
-- Name: ix_request_attachments_request_id; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_request_attachments_request_id ON workflow.request_attachments USING btree (request_id);


--
-- Name: ix_request_comments_request_id_created_at; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_request_comments_request_id_created_at ON workflow.request_comments USING btree (request_id, created_at);


--
-- Name: ix_request_events_tenant_request_created_at; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_request_events_tenant_request_created_at ON workflow.request_events USING btree (tenant_id, request_id, created_at);


--
-- Name: ix_request_step_assignees_tenant_user_step; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_request_step_assignees_tenant_user_step ON workflow.request_step_assignees USING btree (tenant_id, user_id, step_id);


--
-- Name: ix_request_steps_approver_decided_at; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_request_steps_approver_decided_at ON workflow.request_steps USING btree (approver_user_id, decided_at);


--
-- Name: ix_request_steps_approver_pending; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_request_steps_approver_pending ON workflow.request_steps USING btree (approver_user_id) WHERE (decision IS NULL);


--
-- Name: ix_request_steps_request_id; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_request_steps_request_id ON workflow.request_steps USING btree (request_id);


--
-- Name: ix_requests_requester_created_at; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_requests_requester_created_at ON workflow.requests USING btree (requester_employee_id, created_at);


--
-- Name: ix_requests_tenant_status_type_created_at; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_requests_tenant_status_type_created_at ON workflow.requests USING btree (tenant_id, status, request_type_id, created_at DESC);


--
-- Name: ix_workflow_definitions_tenant_active; Type: INDEX; Schema: workflow; Owner: -
--

CREATE INDEX ix_workflow_definitions_tenant_active ON workflow.workflow_definitions USING btree (tenant_id, is_active);


--
-- Name: uq_notification_outbox_dedupe; Type: INDEX; Schema: workflow; Owner: -
--

CREATE UNIQUE INDEX uq_notification_outbox_dedupe ON workflow.notification_outbox USING btree (tenant_id, channel, dedupe_key) WHERE (dedupe_key IS NOT NULL);


--
-- Name: uq_requests_tenant_creator_idempotency; Type: INDEX; Schema: workflow; Owner: -
--

CREATE UNIQUE INDEX uq_requests_tenant_creator_idempotency ON workflow.requests USING btree (tenant_id, created_by_user_id, idempotency_key) WHERE ((created_by_user_id IS NOT NULL) AND (idempotency_key IS NOT NULL));


--
-- Name: document_types trg_set_updated_at_dms_document_types; Type: TRIGGER; Schema: dms; Owner: -
--

CREATE TRIGGER trg_set_updated_at_dms_document_types BEFORE UPDATE ON dms.document_types FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: documents trg_set_updated_at_dms_documents; Type: TRIGGER; Schema: dms; Owner: -
--

CREATE TRIGGER trg_set_updated_at_dms_documents BEFORE UPDATE ON dms.documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: expiry_rules trg_set_updated_at_dms_expiry_rules; Type: TRIGGER; Schema: dms; Owner: -
--

CREATE TRIGGER trg_set_updated_at_dms_expiry_rules BEFORE UPDATE ON dms.expiry_rules FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: files trg_set_updated_at_dms_files; Type: TRIGGER; Schema: dms; Owner: -
--

CREATE TRIGGER trg_set_updated_at_dms_files BEFORE UPDATE ON dms.files FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: hr_applications trg_set_updated_at_hr_hr_applications; Type: TRIGGER; Schema: hr; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_hr_applications BEFORE UPDATE ON hr.hr_applications FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: hr_onboarding_plans trg_set_updated_at_hr_hr_onboarding_plans; Type: TRIGGER; Schema: hr; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_hr_onboarding_plans BEFORE UPDATE ON hr.hr_onboarding_plans FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: hr_onboarding_tasks trg_set_updated_at_hr_hr_onboarding_tasks; Type: TRIGGER; Schema: hr; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_hr_onboarding_tasks BEFORE UPDATE ON hr.hr_onboarding_tasks FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: hr_openings trg_set_updated_at_hr_hr_openings; Type: TRIGGER; Schema: hr; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_hr_openings BEFORE UPDATE ON hr.hr_openings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: hr_resume_views trg_set_updated_at_hr_hr_resume_views; Type: TRIGGER; Schema: hr; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_hr_resume_views BEFORE UPDATE ON hr.hr_resume_views FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: hr_resumes trg_set_updated_at_hr_hr_resumes; Type: TRIGGER; Schema: hr; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_hr_resumes BEFORE UPDATE ON hr.hr_resumes FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employee_bank_accounts trg_set_updated_at_hr_core_employee_bank_accounts; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_employee_bank_accounts BEFORE UPDATE ON hr_core.employee_bank_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employee_contracts trg_set_updated_at_hr_core_employee_contracts; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_employee_contracts BEFORE UPDATE ON hr_core.employee_contracts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employee_dependents trg_set_updated_at_hr_core_employee_dependents; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_employee_dependents BEFORE UPDATE ON hr_core.employee_dependents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employee_employment trg_set_updated_at_hr_core_employee_employment; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_employee_employment BEFORE UPDATE ON hr_core.employee_employment FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employee_government_ids trg_set_updated_at_hr_core_employee_government_ids; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_employee_government_ids BEFORE UPDATE ON hr_core.employee_government_ids FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employee_user_links trg_set_updated_at_hr_core_employee_user_links; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_employee_user_links BEFORE UPDATE ON hr_core.employee_user_links FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employees trg_set_updated_at_hr_core_employees; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_employees BEFORE UPDATE ON hr_core.employees FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: persons trg_set_updated_at_hr_core_persons; Type: TRIGGER; Schema: hr_core; Owner: -
--

CREATE TRIGGER trg_set_updated_at_hr_core_persons BEFORE UPDATE ON hr_core.persons FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: api_tokens trg_set_updated_at_iam_api_tokens; Type: TRIGGER; Schema: iam; Owner: -
--

CREATE TRIGGER trg_set_updated_at_iam_api_tokens BEFORE UPDATE ON iam.api_tokens FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: permissions trg_set_updated_at_iam_permissions; Type: TRIGGER; Schema: iam; Owner: -
--

CREATE TRIGGER trg_set_updated_at_iam_permissions BEFORE UPDATE ON iam.permissions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: roles trg_set_updated_at_iam_roles; Type: TRIGGER; Schema: iam; Owner: -
--

CREATE TRIGGER trg_set_updated_at_iam_roles BEFORE UPDATE ON iam.roles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: users trg_set_updated_at_iam_users; Type: TRIGGER; Schema: iam; Owner: -
--

CREATE TRIGGER trg_set_updated_at_iam_users BEFORE UPDATE ON iam.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: leave_policies trg_set_updated_at_leave_leave_policies; Type: TRIGGER; Schema: leave; Owner: -
--

CREATE TRIGGER trg_set_updated_at_leave_leave_policies BEFORE UPDATE ON leave.leave_policies FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: leave_requests trg_set_updated_at_leave_leave_requests; Type: TRIGGER; Schema: leave; Owner: -
--

CREATE TRIGGER trg_set_updated_at_leave_leave_requests BEFORE UPDATE ON leave.leave_requests FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: leave_types trg_set_updated_at_leave_leave_types; Type: TRIGGER; Schema: leave; Owner: -
--

CREATE TRIGGER trg_set_updated_at_leave_leave_types BEFORE UPDATE ON leave.leave_types FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: branches trg_leave_weekly_off_default; Type: TRIGGER; Schema: tenancy; Owner: -
--

CREATE TRIGGER trg_leave_weekly_off_default AFTER INSERT ON tenancy.branches FOR EACH ROW EXECUTE FUNCTION leave.init_weekly_off_for_branch();


--
-- Name: branches trg_set_updated_at_tenancy_branches; Type: TRIGGER; Schema: tenancy; Owner: -
--

CREATE TRIGGER trg_set_updated_at_tenancy_branches BEFORE UPDATE ON tenancy.branches FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: companies trg_set_updated_at_tenancy_companies; Type: TRIGGER; Schema: tenancy; Owner: -
--

CREATE TRIGGER trg_set_updated_at_tenancy_companies BEFORE UPDATE ON tenancy.companies FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: grades trg_set_updated_at_tenancy_grades; Type: TRIGGER; Schema: tenancy; Owner: -
--

CREATE TRIGGER trg_set_updated_at_tenancy_grades BEFORE UPDATE ON tenancy.grades FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: job_titles trg_set_updated_at_tenancy_job_titles; Type: TRIGGER; Schema: tenancy; Owner: -
--

CREATE TRIGGER trg_set_updated_at_tenancy_job_titles BEFORE UPDATE ON tenancy.job_titles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: org_units trg_set_updated_at_tenancy_org_units; Type: TRIGGER; Schema: tenancy; Owner: -
--

CREATE TRIGGER trg_set_updated_at_tenancy_org_units BEFORE UPDATE ON tenancy.org_units FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: tenants trg_set_updated_at_tenancy_tenants; Type: TRIGGER; Schema: tenancy; Owner: -
--

CREATE TRIGGER trg_set_updated_at_tenancy_tenants BEFORE UPDATE ON tenancy.tenants FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: notification_outbox trg_set_updated_at_workflow_notification_outbox; Type: TRIGGER; Schema: workflow; Owner: -
--

CREATE TRIGGER trg_set_updated_at_workflow_notification_outbox BEFORE UPDATE ON workflow.notification_outbox FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: requests trg_set_updated_at_workflow_requests; Type: TRIGGER; Schema: workflow; Owner: -
--

CREATE TRIGGER trg_set_updated_at_workflow_requests BEFORE UPDATE ON workflow.requests FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: workflow_definition_steps trg_set_updated_at_workflow_workflow_definition_steps; Type: TRIGGER; Schema: workflow; Owner: -
--

CREATE TRIGGER trg_set_updated_at_workflow_workflow_definition_steps BEFORE UPDATE ON workflow.workflow_definition_steps FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: workflow_definitions trg_set_updated_at_workflow_workflow_definitions; Type: TRIGGER; Schema: workflow; Owner: -
--

CREATE TRIGGER trg_set_updated_at_workflow_workflow_definitions BEFORE UPDATE ON workflow.workflow_definitions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: pos_summary fk_analytics_pos_summary_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: analytics; Owner: -
--

ALTER TABLE ONLY analytics.pos_summary
    ADD CONSTRAINT fk_analytics_pos_summary_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE RESTRICT;


--
-- Name: pos_summary fk_analytics_pos_summary_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: analytics; Owner: -
--

ALTER TABLE ONLY analytics.pos_summary
    ADD CONSTRAINT fk_analytics_pos_summary_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: pos_summary pos_summary_dataset_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: -
--

ALTER TABLE ONLY analytics.pos_summary
    ADD CONSTRAINT pos_summary_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES imports.datasets(id) ON DELETE CASCADE;


--
-- Name: attendance_summary attendance_summary_dataset_id_fkey; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_summary
    ADD CONSTRAINT attendance_summary_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES imports.datasets(id) ON DELETE CASCADE;


--
-- Name: attendance_daily fk_attendance_attendance_daily_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_daily
    ADD CONSTRAINT fk_attendance_attendance_daily_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: attendance_daily fk_attendance_attendance_daily_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_daily
    ADD CONSTRAINT fk_attendance_attendance_daily_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE RESTRICT;


--
-- Name: attendance_daily fk_attendance_attendance_daily_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_daily
    ADD CONSTRAINT fk_attendance_attendance_daily_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: attendance_summary fk_attendance_attendance_summary_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_summary
    ADD CONSTRAINT fk_attendance_attendance_summary_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE RESTRICT;


--
-- Name: attendance_summary fk_attendance_attendance_summary_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.attendance_summary
    ADD CONSTRAINT fk_attendance_attendance_summary_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: day_overrides fk_day_overrides_branch_id; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.day_overrides
    ADD CONSTRAINT fk_day_overrides_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: day_overrides fk_day_overrides_employee_id; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.day_overrides
    ADD CONSTRAINT fk_day_overrides_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: day_overrides fk_day_overrides_tenant_id; Type: FK CONSTRAINT; Schema: attendance; Owner: -
--

ALTER TABLE ONLY attendance.day_overrides
    ADD CONSTRAINT fk_day_overrides_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: audit_log fk_audit_log_actor_user_id; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.audit_log
    ADD CONSTRAINT fk_audit_log_actor_user_id FOREIGN KEY (actor_user_id) REFERENCES iam.users(id) ON DELETE RESTRICT;


--
-- Name: audit_log fk_audit_log_tenant_id; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.audit_log
    ADD CONSTRAINT fk_audit_log_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: document_links fk_document_links_document_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_links
    ADD CONSTRAINT fk_document_links_document_id FOREIGN KEY (document_id) REFERENCES dms.documents(id) ON DELETE CASCADE;


--
-- Name: document_links fk_document_links_tenant_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_links
    ADD CONSTRAINT fk_document_links_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: document_types fk_document_types_tenant_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_types
    ADD CONSTRAINT fk_document_types_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: document_versions fk_document_versions_document_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_versions
    ADD CONSTRAINT fk_document_versions_document_id FOREIGN KEY (document_id) REFERENCES dms.documents(id) ON DELETE CASCADE;


--
-- Name: document_versions fk_document_versions_file_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_versions
    ADD CONSTRAINT fk_document_versions_file_id FOREIGN KEY (file_id) REFERENCES dms.files(id) ON DELETE RESTRICT;


--
-- Name: document_versions fk_document_versions_tenant_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.document_versions
    ADD CONSTRAINT fk_document_versions_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: documents fk_documents_document_type_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.documents
    ADD CONSTRAINT fk_documents_document_type_id FOREIGN KEY (document_type_id) REFERENCES dms.document_types(id) ON DELETE RESTRICT;


--
-- Name: documents fk_documents_tenant_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.documents
    ADD CONSTRAINT fk_documents_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: expiry_events fk_expiry_events_document_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.expiry_events
    ADD CONSTRAINT fk_expiry_events_document_id FOREIGN KEY (document_id) REFERENCES dms.documents(id) ON DELETE CASCADE;


--
-- Name: expiry_events fk_expiry_events_rule_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.expiry_events
    ADD CONSTRAINT fk_expiry_events_rule_id FOREIGN KEY (rule_id) REFERENCES dms.expiry_rules(id) ON DELETE CASCADE;


--
-- Name: expiry_events fk_expiry_events_tenant_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.expiry_events
    ADD CONSTRAINT fk_expiry_events_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: expiry_rules fk_expiry_rules_document_type_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.expiry_rules
    ADD CONSTRAINT fk_expiry_rules_document_type_id FOREIGN KEY (document_type_id) REFERENCES dms.document_types(id) ON DELETE SET NULL;


--
-- Name: expiry_rules fk_expiry_rules_tenant_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.expiry_rules
    ADD CONSTRAINT fk_expiry_rules_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: files fk_files_tenant_id; Type: FK CONSTRAINT; Schema: dms; Owner: -
--

ALTER TABLE ONLY dms.files
    ADD CONSTRAINT fk_files_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: employee_faces fk_face_employee_faces_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: face; Owner: -
--

ALTER TABLE ONLY face.employee_faces
    ADD CONSTRAINT fk_face_employee_faces_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_faces fk_face_employee_faces_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: face; Owner: -
--

ALTER TABLE ONLY face.employee_faces
    ADD CONSTRAINT fk_face_employee_faces_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_application_notes fk_hr_hr_application_notes_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_application_notes
    ADD CONSTRAINT fk_hr_hr_application_notes_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_applications fk_hr_hr_applications_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT fk_hr_hr_applications_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: hr_applications fk_hr_hr_applications_company_id__tenancy_companies; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT fk_hr_hr_applications_company_id__tenancy_companies FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: hr_applications fk_hr_hr_applications_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT fk_hr_hr_applications_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE SET NULL;


--
-- Name: hr_applications fk_hr_hr_applications_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT fk_hr_hr_applications_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_onboarding_plans fk_hr_hr_onboarding_plans_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_plans
    ADD CONSTRAINT fk_hr_hr_onboarding_plans_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: hr_onboarding_plans fk_hr_hr_onboarding_plans_company_id__tenancy_companies; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_plans
    ADD CONSTRAINT fk_hr_hr_onboarding_plans_company_id__tenancy_companies FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: hr_onboarding_plans fk_hr_hr_onboarding_plans_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_plans
    ADD CONSTRAINT fk_hr_hr_onboarding_plans_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: hr_onboarding_plans fk_hr_hr_onboarding_plans_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_plans
    ADD CONSTRAINT fk_hr_hr_onboarding_plans_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_onboarding_tasks fk_hr_hr_onboarding_tasks_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_tasks
    ADD CONSTRAINT fk_hr_hr_onboarding_tasks_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_openings fk_hr_hr_openings_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_openings
    ADD CONSTRAINT fk_hr_hr_openings_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: hr_openings fk_hr_hr_openings_company_id__tenancy_companies; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_openings
    ADD CONSTRAINT fk_hr_hr_openings_company_id__tenancy_companies FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: hr_openings fk_hr_hr_openings_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_openings
    ADD CONSTRAINT fk_hr_hr_openings_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_pipeline_stages fk_hr_hr_pipeline_stages_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_pipeline_stages
    ADD CONSTRAINT fk_hr_hr_pipeline_stages_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_resume_batches fk_hr_hr_resume_batches_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_batches
    ADD CONSTRAINT fk_hr_hr_resume_batches_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: hr_resume_batches fk_hr_hr_resume_batches_company_id__tenancy_companies; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_batches
    ADD CONSTRAINT fk_hr_hr_resume_batches_company_id__tenancy_companies FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: hr_resume_batches fk_hr_hr_resume_batches_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_batches
    ADD CONSTRAINT fk_hr_hr_resume_batches_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_resume_views fk_hr_hr_resume_views_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_views
    ADD CONSTRAINT fk_hr_hr_resume_views_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_resumes fk_hr_hr_resumes_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resumes
    ADD CONSTRAINT fk_hr_hr_resumes_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: hr_resumes fk_hr_hr_resumes_company_id__tenancy_companies; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resumes
    ADD CONSTRAINT fk_hr_hr_resumes_company_id__tenancy_companies FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: hr_resumes fk_hr_hr_resumes_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resumes
    ADD CONSTRAINT fk_hr_hr_resumes_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_screening_explanations fk_hr_hr_screening_explanations_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_explanations
    ADD CONSTRAINT fk_hr_hr_screening_explanations_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_screening_results fk_hr_hr_screening_results_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_results
    ADD CONSTRAINT fk_hr_hr_screening_results_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_screening_runs fk_hr_hr_screening_runs_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_runs
    ADD CONSTRAINT fk_hr_hr_screening_runs_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: hr_screening_runs fk_hr_hr_screening_runs_company_id__tenancy_companies; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_runs
    ADD CONSTRAINT fk_hr_hr_screening_runs_company_id__tenancy_companies FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: hr_screening_runs fk_hr_hr_screening_runs_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_runs
    ADD CONSTRAINT fk_hr_hr_screening_runs_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: hr_application_notes hr_application_notes_application_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_application_notes
    ADD CONSTRAINT hr_application_notes_application_id_fkey FOREIGN KEY (application_id) REFERENCES hr.hr_applications(id) ON DELETE CASCADE;


--
-- Name: hr_applications hr_applications_opening_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT hr_applications_opening_id_fkey FOREIGN KEY (opening_id) REFERENCES hr.hr_openings(id) ON DELETE CASCADE;


--
-- Name: hr_applications hr_applications_resume_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT hr_applications_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES hr.hr_resumes(id) ON DELETE CASCADE;


--
-- Name: hr_applications hr_applications_source_run_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT hr_applications_source_run_id_fkey FOREIGN KEY (source_run_id) REFERENCES hr.hr_screening_runs(id) ON DELETE SET NULL;


--
-- Name: hr_applications hr_applications_stage_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_applications
    ADD CONSTRAINT hr_applications_stage_id_fkey FOREIGN KEY (stage_id) REFERENCES hr.hr_pipeline_stages(id) ON DELETE SET NULL;


--
-- Name: hr_onboarding_plans hr_onboarding_plans_application_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_plans
    ADD CONSTRAINT hr_onboarding_plans_application_id_fkey FOREIGN KEY (application_id) REFERENCES hr.hr_applications(id) ON DELETE SET NULL;


--
-- Name: hr_onboarding_tasks hr_onboarding_tasks_plan_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_onboarding_tasks
    ADD CONSTRAINT hr_onboarding_tasks_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES hr.hr_onboarding_plans(id) ON DELETE CASCADE;


--
-- Name: hr_pipeline_stages hr_pipeline_stages_opening_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_pipeline_stages
    ADD CONSTRAINT hr_pipeline_stages_opening_id_fkey FOREIGN KEY (opening_id) REFERENCES hr.hr_openings(id) ON DELETE CASCADE;


--
-- Name: hr_resume_batches hr_resume_batches_opening_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_batches
    ADD CONSTRAINT hr_resume_batches_opening_id_fkey FOREIGN KEY (opening_id) REFERENCES hr.hr_openings(id) ON DELETE CASCADE;


--
-- Name: hr_resume_views hr_resume_views_resume_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resume_views
    ADD CONSTRAINT hr_resume_views_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES hr.hr_resumes(id) ON DELETE CASCADE;


--
-- Name: hr_resumes hr_resumes_batch_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resumes
    ADD CONSTRAINT hr_resumes_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES hr.hr_resume_batches(id) ON DELETE SET NULL;


--
-- Name: hr_resumes hr_resumes_opening_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_resumes
    ADD CONSTRAINT hr_resumes_opening_id_fkey FOREIGN KEY (opening_id) REFERENCES hr.hr_openings(id) ON DELETE CASCADE;


--
-- Name: hr_screening_explanations hr_screening_explanations_resume_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_explanations
    ADD CONSTRAINT hr_screening_explanations_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES hr.hr_resumes(id) ON DELETE CASCADE;


--
-- Name: hr_screening_explanations hr_screening_explanations_run_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_explanations
    ADD CONSTRAINT hr_screening_explanations_run_id_fkey FOREIGN KEY (run_id) REFERENCES hr.hr_screening_runs(id) ON DELETE CASCADE;


--
-- Name: hr_screening_results hr_screening_results_resume_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_results
    ADD CONSTRAINT hr_screening_results_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES hr.hr_resumes(id) ON DELETE CASCADE;


--
-- Name: hr_screening_results hr_screening_results_run_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_results
    ADD CONSTRAINT hr_screening_results_run_id_fkey FOREIGN KEY (run_id) REFERENCES hr.hr_screening_runs(id) ON DELETE CASCADE;


--
-- Name: hr_screening_runs hr_screening_runs_opening_id_fkey; Type: FK CONSTRAINT; Schema: hr; Owner: -
--

ALTER TABLE ONLY hr.hr_screening_runs
    ADD CONSTRAINT hr_screening_runs_opening_id_fkey FOREIGN KEY (opening_id) REFERENCES hr.hr_openings(id) ON DELETE CASCADE;


--
-- Name: employee_bank_accounts fk_employee_bank_accounts_employee_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_bank_accounts
    ADD CONSTRAINT fk_employee_bank_accounts_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_bank_accounts fk_employee_bank_accounts_tenant_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_bank_accounts
    ADD CONSTRAINT fk_employee_bank_accounts_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: employee_contracts fk_employee_contracts_company_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_contracts
    ADD CONSTRAINT fk_employee_contracts_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: employee_contracts fk_employee_contracts_employee_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_contracts
    ADD CONSTRAINT fk_employee_contracts_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_contracts fk_employee_contracts_tenant_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_contracts
    ADD CONSTRAINT fk_employee_contracts_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: employee_dependents fk_employee_dependents_employee_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_dependents
    ADD CONSTRAINT fk_employee_dependents_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_dependents fk_employee_dependents_tenant_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_dependents
    ADD CONSTRAINT fk_employee_dependents_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: employee_employment fk_employee_employment_branch_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: employee_employment fk_employee_employment_company_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: employee_employment fk_employee_employment_employee_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_employment fk_employee_employment_grade_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_grade_id FOREIGN KEY (grade_id) REFERENCES tenancy.grades(id) ON DELETE SET NULL;


--
-- Name: employee_employment fk_employee_employment_job_title_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_job_title_id FOREIGN KEY (job_title_id) REFERENCES tenancy.job_titles(id) ON DELETE SET NULL;


--
-- Name: employee_employment fk_employee_employment_manager_employee_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_manager_employee_id FOREIGN KEY (manager_employee_id) REFERENCES hr_core.employees(id) ON DELETE SET NULL;


--
-- Name: employee_employment fk_employee_employment_org_unit_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_org_unit_id FOREIGN KEY (org_unit_id) REFERENCES tenancy.org_units(id) ON DELETE SET NULL;


--
-- Name: employee_employment fk_employee_employment_tenant_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_employment
    ADD CONSTRAINT fk_employee_employment_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: employee_government_ids fk_employee_government_ids_employee_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_government_ids
    ADD CONSTRAINT fk_employee_government_ids_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_government_ids fk_employee_government_ids_tenant_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_government_ids
    ADD CONSTRAINT fk_employee_government_ids_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: employee_user_links fk_employee_user_links_employee_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_user_links
    ADD CONSTRAINT fk_employee_user_links_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_user_links fk_employee_user_links_user_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employee_user_links
    ADD CONSTRAINT fk_employee_user_links_user_id FOREIGN KEY (user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: employees fk_hr_employees_company_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employees
    ADD CONSTRAINT fk_hr_employees_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: employees fk_hr_employees_person_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employees
    ADD CONSTRAINT fk_hr_employees_person_id FOREIGN KEY (person_id) REFERENCES hr_core.persons(id) ON DELETE CASCADE;


--
-- Name: employees fk_hr_employees_tenant_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.employees
    ADD CONSTRAINT fk_hr_employees_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: persons fk_persons_tenant_id; Type: FK CONSTRAINT; Schema: hr_core; Owner: -
--

ALTER TABLE ONLY hr_core.persons
    ADD CONSTRAINT fk_persons_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: api_tokens fk_api_tokens_tenant_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.api_tokens
    ADD CONSTRAINT fk_api_tokens_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens fk_refresh_tokens_user_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.refresh_tokens
    ADD CONSTRAINT fk_refresh_tokens_user_id FOREIGN KEY (user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: role_permissions fk_role_permissions_permission_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.role_permissions
    ADD CONSTRAINT fk_role_permissions_permission_id FOREIGN KEY (permission_id) REFERENCES iam.permissions(id) ON DELETE CASCADE;


--
-- Name: role_permissions fk_role_permissions_role_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.role_permissions
    ADD CONSTRAINT fk_role_permissions_role_id FOREIGN KEY (role_id) REFERENCES iam.roles(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_user_roles_branch_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.user_roles
    ADD CONSTRAINT fk_user_roles_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_user_roles_company_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.user_roles
    ADD CONSTRAINT fk_user_roles_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_user_roles_role_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.user_roles
    ADD CONSTRAINT fk_user_roles_role_id FOREIGN KEY (role_id) REFERENCES iam.roles(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_user_roles_tenant_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.user_roles
    ADD CONSTRAINT fk_user_roles_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_user_roles_user_id; Type: FK CONSTRAINT; Schema: iam; Owner: -
--

ALTER TABLE ONLY iam.user_roles
    ADD CONSTRAINT fk_user_roles_user_id FOREIGN KEY (user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: datasets fk_imports_datasets_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.datasets
    ADD CONSTRAINT fk_imports_datasets_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: datasets fk_imports_datasets_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.datasets
    ADD CONSTRAINT fk_imports_datasets_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: month_state fk_imports_month_state_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.month_state
    ADD CONSTRAINT fk_imports_month_state_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: month_state fk_month_state_branch_id; Type: FK CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.month_state
    ADD CONSTRAINT fk_month_state_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: month_state month_state_published_dataset_id_fkey; Type: FK CONSTRAINT; Schema: imports; Owner: -
--

ALTER TABLE ONLY imports.month_state
    ADD CONSTRAINT month_state_published_dataset_id_fkey FOREIGN KEY (published_dataset_id) REFERENCES imports.datasets(id) ON DELETE SET NULL;


--
-- Name: employee_leave_policy fk_employee_leave_policy_employee_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.employee_leave_policy
    ADD CONSTRAINT fk_employee_leave_policy_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_leave_policy fk_employee_leave_policy_policy_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.employee_leave_policy
    ADD CONSTRAINT fk_employee_leave_policy_policy_id FOREIGN KEY (policy_id) REFERENCES leave.leave_policies(id) ON DELETE CASCADE;


--
-- Name: employee_leave_policy fk_employee_leave_policy_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.employee_leave_policy
    ADD CONSTRAINT fk_employee_leave_policy_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: holidays fk_leave_holidays_branch_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.holidays
    ADD CONSTRAINT fk_leave_holidays_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: holidays fk_leave_holidays_company_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.holidays
    ADD CONSTRAINT fk_leave_holidays_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: holidays fk_leave_holidays_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.holidays
    ADD CONSTRAINT fk_leave_holidays_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: leave_ledger fk_leave_ledger_created_by_user_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_ledger
    ADD CONSTRAINT fk_leave_ledger_created_by_user_id FOREIGN KEY (created_by_user_id) REFERENCES iam.users(id) ON DELETE SET NULL;


--
-- Name: leave_ledger fk_leave_ledger_employee_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_ledger
    ADD CONSTRAINT fk_leave_ledger_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: leave_ledger fk_leave_ledger_leave_type_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_ledger
    ADD CONSTRAINT fk_leave_ledger_leave_type_id FOREIGN KEY (leave_type_id) REFERENCES leave.leave_types(id) ON DELETE RESTRICT;


--
-- Name: leave_ledger fk_leave_ledger_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_ledger
    ADD CONSTRAINT fk_leave_ledger_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: leave_policies fk_leave_policies_branch_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policies
    ADD CONSTRAINT fk_leave_policies_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: leave_policies fk_leave_policies_company_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policies
    ADD CONSTRAINT fk_leave_policies_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: leave_policies fk_leave_policies_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policies
    ADD CONSTRAINT fk_leave_policies_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: leave_policy_rules fk_leave_policy_rules_leave_type_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policy_rules
    ADD CONSTRAINT fk_leave_policy_rules_leave_type_id FOREIGN KEY (leave_type_id) REFERENCES leave.leave_types(id) ON DELETE RESTRICT;


--
-- Name: leave_policy_rules fk_leave_policy_rules_policy_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policy_rules
    ADD CONSTRAINT fk_leave_policy_rules_policy_id FOREIGN KEY (policy_id) REFERENCES leave.leave_policies(id) ON DELETE CASCADE;


--
-- Name: leave_policy_rules fk_leave_policy_rules_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_policy_rules
    ADD CONSTRAINT fk_leave_policy_rules_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: leave_request_days fk_leave_request_days_employee_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_request_days
    ADD CONSTRAINT fk_leave_request_days_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: leave_request_days fk_leave_request_days_leave_request_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_request_days
    ADD CONSTRAINT fk_leave_request_days_leave_request_id FOREIGN KEY (leave_request_id) REFERENCES leave.leave_requests(id) ON DELETE CASCADE;


--
-- Name: leave_request_days fk_leave_request_days_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_request_days
    ADD CONSTRAINT fk_leave_request_days_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: leave_requests fk_leave_requests_branch_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT fk_leave_requests_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE SET NULL;


--
-- Name: leave_requests fk_leave_requests_company_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT fk_leave_requests_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE SET NULL;


--
-- Name: leave_requests fk_leave_requests_employee_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT fk_leave_requests_employee_id FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: leave_requests fk_leave_requests_leave_type_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT fk_leave_requests_leave_type_id FOREIGN KEY (leave_type_id) REFERENCES leave.leave_types(id) ON DELETE RESTRICT;


--
-- Name: leave_requests fk_leave_requests_policy_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT fk_leave_requests_policy_id FOREIGN KEY (policy_id) REFERENCES leave.leave_policies(id) ON DELETE RESTRICT;


--
-- Name: leave_requests fk_leave_requests_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT fk_leave_requests_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: leave_requests fk_leave_requests_workflow_request_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_requests
    ADD CONSTRAINT fk_leave_requests_workflow_request_id FOREIGN KEY (workflow_request_id) REFERENCES workflow.requests(id) ON DELETE RESTRICT;


--
-- Name: leave_types fk_leave_types_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.leave_types
    ADD CONSTRAINT fk_leave_types_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: weekly_off fk_leave_weekly_off_branch_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.weekly_off
    ADD CONSTRAINT fk_leave_weekly_off_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: weekly_off fk_leave_weekly_off_tenant_id; Type: FK CONSTRAINT; Schema: leave; Owner: -
--

ALTER TABLE ONLY leave.weekly_off
    ADD CONSTRAINT fk_leave_weekly_off_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: mobile_accounts fk_mobile_mobile_accounts_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: mobile; Owner: -
--

ALTER TABLE ONLY mobile.mobile_accounts
    ADD CONSTRAINT fk_mobile_mobile_accounts_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: mobile_accounts fk_mobile_mobile_accounts_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: mobile; Owner: -
--

ALTER TABLE ONLY mobile.mobile_accounts
    ADD CONSTRAINT fk_mobile_mobile_accounts_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: mobile_accounts fk_mobile_mobile_accounts_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: mobile; Owner: -
--

ALTER TABLE ONLY mobile.mobile_accounts
    ADD CONSTRAINT fk_mobile_mobile_accounts_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: employee_skills fk_employee_skills_skill_id; Type: FK CONSTRAINT; Schema: skills; Owner: -
--

ALTER TABLE ONLY skills.employee_skills
    ADD CONSTRAINT fk_employee_skills_skill_id FOREIGN KEY (skill_id) REFERENCES skills.skill_taxonomy(id) ON DELETE CASCADE;


--
-- Name: employee_skills fk_skills_employee_skills_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: skills; Owner: -
--

ALTER TABLE ONLY skills.employee_skills
    ADD CONSTRAINT fk_skills_employee_skills_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: employee_skills fk_skills_employee_skills_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: skills; Owner: -
--

ALTER TABLE ONLY skills.employee_skills
    ADD CONSTRAINT fk_skills_employee_skills_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: skill_taxonomy fk_skills_skill_taxonomy_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: skills; Owner: -
--

ALTER TABLE ONLY skills.skill_taxonomy
    ADD CONSTRAINT fk_skills_skill_taxonomy_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: branches fk_branches_company_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.branches
    ADD CONSTRAINT fk_branches_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: branches fk_branches_tenant_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.branches
    ADD CONSTRAINT fk_branches_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: companies fk_companies_tenant_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.companies
    ADD CONSTRAINT fk_companies_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: grades fk_grades_company_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.grades
    ADD CONSTRAINT fk_grades_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: grades fk_grades_tenant_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.grades
    ADD CONSTRAINT fk_grades_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: job_titles fk_job_titles_company_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.job_titles
    ADD CONSTRAINT fk_job_titles_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: job_titles fk_job_titles_tenant_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.job_titles
    ADD CONSTRAINT fk_job_titles_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: org_units fk_org_units_branch_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.org_units
    ADD CONSTRAINT fk_org_units_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE SET NULL;


--
-- Name: org_units fk_org_units_company_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.org_units
    ADD CONSTRAINT fk_org_units_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: org_units fk_org_units_parent_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.org_units
    ADD CONSTRAINT fk_org_units_parent_id FOREIGN KEY (parent_id) REFERENCES tenancy.org_units(id) ON DELETE SET NULL;


--
-- Name: org_units fk_org_units_tenant_id; Type: FK CONSTRAINT; Schema: tenancy; Owner: -
--

ALTER TABLE ONLY tenancy.org_units
    ADD CONSTRAINT fk_org_units_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: artifacts artifacts_job_id_fkey; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.artifacts
    ADD CONSTRAINT artifacts_job_id_fkey FOREIGN KEY (job_id) REFERENCES vision.jobs(id) ON DELETE CASCADE;


--
-- Name: events events_job_id_fkey; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.events
    ADD CONSTRAINT events_job_id_fkey FOREIGN KEY (job_id) REFERENCES vision.jobs(id) ON DELETE CASCADE;


--
-- Name: artifacts fk_vision_artifacts_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.artifacts
    ADD CONSTRAINT fk_vision_artifacts_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: cameras fk_vision_cameras_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.cameras
    ADD CONSTRAINT fk_vision_cameras_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: cameras fk_vision_cameras_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.cameras
    ADD CONSTRAINT fk_vision_cameras_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: events fk_vision_events_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.events
    ADD CONSTRAINT fk_vision_events_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE SET NULL;


--
-- Name: events fk_vision_events_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.events
    ADD CONSTRAINT fk_vision_events_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: jobs fk_vision_jobs_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.jobs
    ADD CONSTRAINT fk_vision_jobs_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: metrics_hourly fk_vision_metrics_hourly_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.metrics_hourly
    ADD CONSTRAINT fk_vision_metrics_hourly_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: tracks fk_vision_tracks_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.tracks
    ADD CONSTRAINT fk_vision_tracks_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE SET NULL;


--
-- Name: tracks fk_vision_tracks_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.tracks
    ADD CONSTRAINT fk_vision_tracks_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: videos fk_vision_videos_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.videos
    ADD CONSTRAINT fk_vision_videos_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: videos fk_vision_videos_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.videos
    ADD CONSTRAINT fk_vision_videos_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: jobs jobs_video_id_fkey; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.jobs
    ADD CONSTRAINT jobs_video_id_fkey FOREIGN KEY (video_id) REFERENCES vision.videos(id) ON DELETE CASCADE;


--
-- Name: metrics_hourly metrics_hourly_job_id_fkey; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.metrics_hourly
    ADD CONSTRAINT metrics_hourly_job_id_fkey FOREIGN KEY (job_id) REFERENCES vision.jobs(id) ON DELETE CASCADE;


--
-- Name: tracks tracks_job_id_fkey; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.tracks
    ADD CONSTRAINT tracks_job_id_fkey FOREIGN KEY (job_id) REFERENCES vision.jobs(id) ON DELETE CASCADE;


--
-- Name: videos videos_camera_id_fkey; Type: FK CONSTRAINT; Schema: vision; Owner: -
--

ALTER TABLE ONLY vision.videos
    ADD CONSTRAINT videos_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES vision.cameras(id) ON DELETE CASCADE;


--
-- Name: task_assignments fk_task_assignments_task_id; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_assignments
    ADD CONSTRAINT fk_task_assignments_task_id FOREIGN KEY (task_id) REFERENCES work.tasks(id) ON DELETE CASCADE;


--
-- Name: task_required_skills fk_task_required_skills_skill_id; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_required_skills
    ADD CONSTRAINT fk_task_required_skills_skill_id FOREIGN KEY (skill_id) REFERENCES skills.skill_taxonomy(id) ON DELETE CASCADE;


--
-- Name: task_required_skills fk_task_required_skills_task_id; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_required_skills
    ADD CONSTRAINT fk_task_required_skills_task_id FOREIGN KEY (task_id) REFERENCES work.tasks(id) ON DELETE CASCADE;


--
-- Name: task_assignments fk_work_task_assignments_employee_id__hr_core_employees; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_assignments
    ADD CONSTRAINT fk_work_task_assignments_employee_id__hr_core_employees FOREIGN KEY (employee_id) REFERENCES hr_core.employees(id) ON DELETE CASCADE;


--
-- Name: task_assignments fk_work_task_assignments_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_assignments
    ADD CONSTRAINT fk_work_task_assignments_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: task_required_skills fk_work_task_required_skills_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.task_required_skills
    ADD CONSTRAINT fk_work_task_required_skills_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: tasks fk_work_tasks_branch_id__tenancy_branches; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.tasks
    ADD CONSTRAINT fk_work_tasks_branch_id__tenancy_branches FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE CASCADE;


--
-- Name: tasks fk_work_tasks_tenant_id__tenancy_tenants; Type: FK CONSTRAINT; Schema: work; Owner: -
--

ALTER TABLE ONLY work.tasks
    ADD CONSTRAINT fk_work_tasks_tenant_id__tenancy_tenants FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: notification_outbox fk_notification_outbox_recipient_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notification_outbox
    ADD CONSTRAINT fk_notification_outbox_recipient_user_id FOREIGN KEY (recipient_user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: notification_outbox fk_notification_outbox_tenant_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notification_outbox
    ADD CONSTRAINT fk_notification_outbox_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: notifications fk_notifications_outbox_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notifications
    ADD CONSTRAINT fk_notifications_outbox_id FOREIGN KEY (outbox_id) REFERENCES workflow.notification_outbox(id) ON DELETE RESTRICT;


--
-- Name: notifications fk_notifications_recipient_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notifications
    ADD CONSTRAINT fk_notifications_recipient_user_id FOREIGN KEY (recipient_user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: notifications fk_notifications_tenant_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.notifications
    ADD CONSTRAINT fk_notifications_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: request_attachments fk_request_attachments_file_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_attachments
    ADD CONSTRAINT fk_request_attachments_file_id FOREIGN KEY (file_id) REFERENCES dms.files(id) ON DELETE CASCADE;


--
-- Name: request_attachments fk_request_attachments_request_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_attachments
    ADD CONSTRAINT fk_request_attachments_request_id FOREIGN KEY (request_id) REFERENCES workflow.requests(id) ON DELETE CASCADE;


--
-- Name: request_attachments fk_request_attachments_tenant_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_attachments
    ADD CONSTRAINT fk_request_attachments_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: request_comments fk_request_comments_author_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_comments
    ADD CONSTRAINT fk_request_comments_author_user_id FOREIGN KEY (author_user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: request_comments fk_request_comments_request_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_comments
    ADD CONSTRAINT fk_request_comments_request_id FOREIGN KEY (request_id) REFERENCES workflow.requests(id) ON DELETE CASCADE;


--
-- Name: request_events fk_request_events_actor_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_events
    ADD CONSTRAINT fk_request_events_actor_user_id FOREIGN KEY (actor_user_id) REFERENCES iam.users(id) ON DELETE SET NULL;


--
-- Name: request_events fk_request_events_request_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_events
    ADD CONSTRAINT fk_request_events_request_id FOREIGN KEY (request_id) REFERENCES workflow.requests(id) ON DELETE CASCADE;


--
-- Name: request_events fk_request_events_tenant_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_events
    ADD CONSTRAINT fk_request_events_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: request_step_assignees fk_request_step_assignees_step_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_step_assignees
    ADD CONSTRAINT fk_request_step_assignees_step_id FOREIGN KEY (step_id) REFERENCES workflow.request_steps(id) ON DELETE CASCADE;


--
-- Name: request_step_assignees fk_request_step_assignees_tenant_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_step_assignees
    ADD CONSTRAINT fk_request_step_assignees_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: request_step_assignees fk_request_step_assignees_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_step_assignees
    ADD CONSTRAINT fk_request_step_assignees_user_id FOREIGN KEY (user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: request_steps fk_request_steps_approver_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_steps
    ADD CONSTRAINT fk_request_steps_approver_user_id FOREIGN KEY (approver_user_id) REFERENCES iam.users(id) ON DELETE CASCADE;


--
-- Name: request_steps fk_request_steps_assignee_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_steps
    ADD CONSTRAINT fk_request_steps_assignee_user_id FOREIGN KEY (assignee_user_id) REFERENCES iam.users(id) ON DELETE SET NULL;


--
-- Name: request_steps fk_request_steps_request_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.request_steps
    ADD CONSTRAINT fk_request_steps_request_id FOREIGN KEY (request_id) REFERENCES workflow.requests(id) ON DELETE CASCADE;


--
-- Name: requests fk_requests_branch_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_branch_id FOREIGN KEY (branch_id) REFERENCES tenancy.branches(id) ON DELETE SET NULL;


--
-- Name: requests fk_requests_company_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: requests fk_requests_created_by_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_created_by_user_id FOREIGN KEY (created_by_user_id) REFERENCES iam.users(id) ON DELETE RESTRICT;


--
-- Name: requests fk_requests_request_type_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_request_type_id FOREIGN KEY (request_type_id) REFERENCES workflow.request_types(id) ON DELETE RESTRICT;


--
-- Name: requests fk_requests_requester_employee_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_requester_employee_id FOREIGN KEY (requester_employee_id) REFERENCES hr_core.employees(id) ON DELETE RESTRICT;


--
-- Name: requests fk_requests_subject_employee_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_subject_employee_id FOREIGN KEY (subject_employee_id) REFERENCES hr_core.employees(id) ON DELETE SET NULL;


--
-- Name: requests fk_requests_tenant_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- Name: requests fk_requests_workflow_definition_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.requests
    ADD CONSTRAINT fk_requests_workflow_definition_id FOREIGN KEY (workflow_definition_id) REFERENCES workflow.workflow_definitions(id) ON DELETE RESTRICT;


--
-- Name: workflow_definition_steps fk_workflow_definition_steps_definition_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definition_steps
    ADD CONSTRAINT fk_workflow_definition_steps_definition_id FOREIGN KEY (workflow_definition_id) REFERENCES workflow.workflow_definitions(id) ON DELETE CASCADE;


--
-- Name: workflow_definition_steps fk_workflow_definition_steps_user_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definition_steps
    ADD CONSTRAINT fk_workflow_definition_steps_user_id FOREIGN KEY (user_id) REFERENCES iam.users(id) ON DELETE SET NULL;


--
-- Name: workflow_definitions fk_workflow_definitions_company_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definitions
    ADD CONSTRAINT fk_workflow_definitions_company_id FOREIGN KEY (company_id) REFERENCES tenancy.companies(id) ON DELETE CASCADE;


--
-- Name: workflow_definitions fk_workflow_definitions_request_type_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definitions
    ADD CONSTRAINT fk_workflow_definitions_request_type_id FOREIGN KEY (request_type_id) REFERENCES workflow.request_types(id) ON DELETE RESTRICT;


--
-- Name: workflow_definitions fk_workflow_definitions_tenant_id; Type: FK CONSTRAINT; Schema: workflow; Owner: -
--

ALTER TABLE ONLY workflow.workflow_definitions
    ADD CONSTRAINT fk_workflow_definitions_tenant_id FOREIGN KEY (tenant_id) REFERENCES tenancy.tenants(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict uIxhcZ52CCNVIRsrwpZlMNP0kzqa8EKahliI25sr5dgNpNu2RbQJYyOIOQgj0MD



-- ------------------------------------------------------------------
-- Baseline seed data (global tables)
-- ------------------------------------------------------------------

--
-- PostgreSQL database dump
--

\restrict RN5aSh7jNi9qnd0OjJvh3W0cPlv22Z9pJodoxUu4i2UViwTAQP1jEBfGUxhPNEK

-- Dumped from database version 17.7 (Debian 17.7-3.pgdg12+1)
-- Dumped by pg_dump version 17.7 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: roles; Type: TABLE DATA; Schema: iam; Owner: attendance
--

INSERT INTO iam.roles (id, code, name, description, created_at, updated_at) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'ADMIN', 'Administrator', 'Full access across the tenant', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.roles (id, code, name, description, created_at, updated_at) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'HR_MANAGER', 'HR Manager', 'HR operations and approvals', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.roles (id, code, name, description, created_at, updated_at) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'MANAGER', 'Manager', 'Line manager approvals and team operations', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.roles (id, code, name, description, created_at, updated_at) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', 'EMPLOYEE', 'Employee', 'Standard employee access', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.roles (id, code, name, description, created_at, updated_at) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'HR_ADMIN', 'HR Administrator', 'Elevated HR access within a scope', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');


--
-- PostgreSQL database dump complete
--

\unrestrict RN5aSh7jNi9qnd0OjJvh3W0cPlv22Z9pJodoxUu4i2UViwTAQP1jEBfGUxhPNEK

--
-- PostgreSQL database dump
--

\restrict B18Gc0nAjYox3UH5pj9wlhEuQDFAC5LksiNWYL8sZPbAZ4VHfuBHfbdmrABWv48

-- Dumped from database version 17.7 (Debian 17.7-3.pgdg12+1)
-- Dumped by pg_dump version 17.7 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: permissions; Type: TABLE DATA; Schema: iam; Owner: attendance
--

INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('a114b629-5e81-4ce5-a26d-3477e6574ba5', 'HR_CORE_READ', 'Read HR core records', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('95b279db-5d89-4bb7-8d14-883ffdbe904f', 'HR_CORE_WRITE', 'Write HR core records', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('e99f7487-fe53-4199-a922-9b5f622c7fa8', 'WORKFLOW_REQUEST_CREATE', 'Create workflow requests', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('80bd7d94-46a0-4d91-a429-f691f726c84e', 'WORKFLOW_REQUEST_APPROVE', 'Approve workflow requests', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('73cd07b8-7de4-4ba5-8cee-b26b2ba11954', 'DMS_READ', 'Read documents', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('a2290824-85b0-4497-8d13-a9f4e34f717e', 'DMS_WRITE', 'Upload/manage documents', '2026-02-11 19:24:57.854611+00', '2026-02-11 19:24:57.854611+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('14ba4f6b-5b79-4e55-9953-3b5f7add0b14', 'tenancy:read', 'Read tenant masters', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('0f6d634d-e132-45e2-9ffe-49233c72c6f5', 'tenancy:write', 'Write tenant masters', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('51fb6b25-1451-4c61-911f-7e3f7f9294c9', 'iam:user:read', 'Read IAM users', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('c94b8233-68b1-4e62-9ab3-3e9af777b87d', 'iam:user:write', 'Write IAM users', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('cbccf184-9822-4606-b76a-d8eeffcbc398', 'iam:role:assign', 'Assign IAM roles', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('11a2dab3-7ecf-4375-9239-a0a15f2608df', 'iam:permission:read', 'Read IAM permissions', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('6cdadfc9-6d8f-4339-a0b2-f8a235e84dd7', 'hr:employee:read', 'Read HR employees', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('defcbdf3-819f-4cf8-be70-e142829dd18c', 'hr:employee:write', 'Write HR employees', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('b0dd0a3e-eb94-427c-bc44-a086fc4ae4d1', 'hr:team:read', 'Read manager team views', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('d4e88883-afe6-4f32-89bc-1f6da7b40665', 'ess:profile:read', 'Read ESS profile', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('6edb08ba-e205-4d06-b115-8f28c0d0b8aa', 'ess:profile:write', 'Write ESS profile', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('48897cab-9c1f-4e0f-9990-551343b4596f', 'notifications:read', 'Read in-app notifications', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('c720fa8e-2b61-4739-baf5-314f2163b704', 'vision:camera:read', 'Read cameras', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('659f07b0-1331-4e66-871b-96158a9e977d', 'vision:camera:write', 'Write cameras', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('9786ad47-396c-48e7-8d3e-27a698972080', 'vision:video:upload', 'Upload videos', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('084bb42d-c4e1-47bb-9a00-330a70ef0a6f', 'vision:job:run', 'Run processing jobs', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('b20edb69-29ff-44fd-9ae5-4ebc04e1828c', 'vision:results:read', 'Read processing results', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('4475c43f-6783-4914-9931-c251b99545ba', 'face:library:read', 'Read face library', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('9fe0dae7-c549-4aaa-9eef-76169c12f590', 'face:library:write', 'Write face library', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('cc3d03f7-2197-4603-9ae0-08fa0432c684', 'face:recognize', 'Run face recognition', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('c0ba80c2-d198-411e-9695-6a7c495b6544', 'work:task:read', 'Read tasks', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('1ba8b8d8-7e28-4859-8977-66a6fb6106b6', 'work:task:write', 'Write tasks', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('419db4f4-0141-470d-b6bd-cb47c61df2db', 'work:task:auto_assign', 'Auto-assign tasks', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('3cc421ee-8621-4fd4-8705-39fe4b64f88b', 'imports:read', 'Read imports', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('8f6a74bf-3b7a-40ec-b1b9-941246375f5c', 'imports:write', 'Write imports', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('b85dde8b-9dba-47a7-8d3b-a914f91958a8', 'mobile:sync', 'Run mobile sync', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('8e7c1049-8834-4612-bf56-40b635acc927', 'mobile:accounts:read', 'Read mobile accounts', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('d6fd20f6-0c55-4428-b04b-b65a8a769543', 'mobile:accounts:write', 'Write mobile accounts', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('265d9df8-34f8-48eb-bcdd-dcb1c902680c', 'hr:recruiting:read', 'Read recruiting pipeline', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('3931e924-e4de-4fc7-b00e-3937a444e52a', 'hr:recruiting:write', 'Write recruiting pipeline', '2026-02-12 18:59:07.390836+00', '2026-02-12 18:59:07.390836+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('86feef17-4b2c-43ba-9163-b2269b70e673', 'workflow:request:submit', 'Submit workflow requests', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('1885a46a-187e-4019-8a3c-a6d326255059', 'workflow:request:read', 'Read workflow requests', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('d7fffd41-76fe-4034-84d3-35ca12d67517', 'workflow:request:approve', 'Approve/reject workflow requests', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('d37b5c27-dad6-413c-aa05-87cf944ea25f', 'workflow:request:admin', 'Admin access to workflow requests', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('06273618-65e6-46a0-bac7-29dc8734ad1d', 'workflow:definition:read', 'Read workflow definitions', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('6f0c6129-1515-4ca9-b781-59c63bf621c6', 'workflow:definition:write', 'Write workflow definitions', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('1200c3e7-c394-44cb-8149-ea1205c60c63', 'dms:file:read', 'Read DMS files', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('775bd65f-2582-42c6-babc-c2f87528d534', 'dms:file:write', 'Write DMS files', '2026-02-16 10:04:25.572482+00', '2026-02-16 10:04:25.572482+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('376da489-843a-4be3-b59d-09ebb2f6d6e5', 'leave:type:read', 'Read leave types', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('4d037438-1c5f-4578-9204-3252bfe7542a', 'leave:type:write', 'Write leave types', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('2ada59dd-a5aa-49fc-8725-b81bf145d33e', 'leave:policy:read', 'Read leave policies', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('0bc1506a-589f-4d1f-90d1-e20e70a3c048', 'leave:policy:write', 'Write leave policies', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('8bafde2f-24d7-4046-8d70-648625c25e60', 'leave:allocation:write', 'Allocate/adjust leave balances', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('b5235d02-7e43-4bf2-969f-f70034b0c379', 'leave:balance:read', 'Read leave balances', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('2bdde810-e194-419b-abb4-aed51690d7bd', 'leave:request:submit', 'Submit leave requests', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('e5b1b48b-32ae-4b2b-b92c-42223d53677e', 'leave:request:read', 'Read leave requests', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('91ffdf49-6153-4b2a-a50d-633cb5f3a61a', 'leave:team:read', 'Read team leave calendar', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');
INSERT INTO iam.permissions (id, code, description, created_at, updated_at) VALUES ('1fc38999-31b5-498d-b0e5-ce1208fa4fac', 'leave:admin:read', 'Read leave admin reports', '2026-02-16 20:43:34.431087+00', '2026-02-16 20:43:34.431087+00');


--
-- PostgreSQL database dump complete
--

\unrestrict B18Gc0nAjYox3UH5pj9wlhEuQDFAC5LksiNWYL8sZPbAZ4VHfuBHfbdmrABWv48

--
-- PostgreSQL database dump
--

\restrict y6NNgcNDTAiAxOeeZGUa6Saa1vT9v7nmChZ2FR056YgdrIyOTkG4aa7yIjpMtgs

-- Dumped from database version 17.7 (Debian 17.7-3.pgdg12+1)
-- Dumped by pg_dump version 17.7 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: request_types; Type: TABLE DATA; Schema: workflow; Owner: attendance
--

INSERT INTO workflow.request_types (id, code, name, description, created_at) VALUES ('2bde088a-c297-422d-a696-596565e5c9f3', 'LEAVE_REQUEST', 'Leave Request', 'Employee leave request', '2026-02-11 19:24:57.854611+00');
INSERT INTO workflow.request_types (id, code, name, description, created_at) VALUES ('18d7cb60-905d-451e-8578-5af4b522e202', 'DOCUMENT_REQUEST', 'Document Request', 'Request a document or verification', '2026-02-11 19:24:57.854611+00');
INSERT INTO workflow.request_types (id, code, name, description, created_at) VALUES ('80ea8ff7-dd52-42a7-8a79-7e191de6b0a1', 'EXPENSE_CLAIM', 'Expense Claim', 'Submit an expense claim for approval', '2026-02-11 19:24:57.854611+00');
INSERT INTO workflow.request_types (id, code, name, description, created_at) VALUES ('cc4502f9-ce47-4d9f-a560-6c6829d28cda', 'GENERAL_REQUEST', 'General Request', 'Generic request type for future workflows', '2026-02-11 19:24:57.854611+00');
INSERT INTO workflow.request_types (id, code, name, description, created_at) VALUES ('8541831d-35ec-4d37-9651-0cd1384e38f1', 'HR_PROFILE_CHANGE', 'HR Profile Change', 'Employee profile change request', '2026-02-16 10:04:25.572482+00');


--
-- PostgreSQL database dump complete
--

\unrestrict y6NNgcNDTAiAxOeeZGUa6Saa1vT9v7nmChZ2FR056YgdrIyOTkG4aa7yIjpMtgs

--
-- PostgreSQL database dump
--

\restrict rytVQBLzQi0td4UjZD06y27pvhI4r8tWF17eFNW4rEIkR1hDDKRJGC2HPTZpyOV

-- Dumped from database version 17.7 (Debian 17.7-3.pgdg12+1)
-- Dumped by pg_dump version 17.7 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: iam; Owner: attendance
--

INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'a114b629-5e81-4ce5-a26d-3477e6574ba5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '95b279db-5d89-4bb7-8d14-883ffdbe904f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'e99f7487-fe53-4199-a922-9b5f622c7fa8');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '80bd7d94-46a0-4d91-a429-f691f726c84e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '73cd07b8-7de4-4ba5-8cee-b26b2ba11954');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'a2290824-85b0-4497-8d13-a9f4e34f717e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'a114b629-5e81-4ce5-a26d-3477e6574ba5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '95b279db-5d89-4bb7-8d14-883ffdbe904f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'e99f7487-fe53-4199-a922-9b5f622c7fa8');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '80bd7d94-46a0-4d91-a429-f691f726c84e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '73cd07b8-7de4-4ba5-8cee-b26b2ba11954');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'a2290824-85b0-4497-8d13-a9f4e34f717e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'a114b629-5e81-4ce5-a26d-3477e6574ba5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'e99f7487-fe53-4199-a922-9b5f622c7fa8');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', '80bd7d94-46a0-4d91-a429-f691f726c84e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', '73cd07b8-7de4-4ba5-8cee-b26b2ba11954');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', 'e99f7487-fe53-4199-a922-9b5f622c7fa8');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '73cd07b8-7de4-4ba5-8cee-b26b2ba11954');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '14ba4f6b-5b79-4e55-9953-3b5f7add0b14');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '0f6d634d-e132-45e2-9ffe-49233c72c6f5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '51fb6b25-1451-4c61-911f-7e3f7f9294c9');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'c94b8233-68b1-4e62-9ab3-3e9af777b87d');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'cbccf184-9822-4606-b76a-d8eeffcbc398');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '11a2dab3-7ecf-4375-9239-a0a15f2608df');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '6cdadfc9-6d8f-4339-a0b2-f8a235e84dd7');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'defcbdf3-819f-4cf8-be70-e142829dd18c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'b0dd0a3e-eb94-427c-bc44-a086fc4ae4d1');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'd4e88883-afe6-4f32-89bc-1f6da7b40665');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '6edb08ba-e205-4d06-b115-8f28c0d0b8aa');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '48897cab-9c1f-4e0f-9990-551343b4596f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'c720fa8e-2b61-4739-baf5-314f2163b704');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '659f07b0-1331-4e66-871b-96158a9e977d');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '9786ad47-396c-48e7-8d3e-27a698972080');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '084bb42d-c4e1-47bb-9a00-330a70ef0a6f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'b20edb69-29ff-44fd-9ae5-4ebc04e1828c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '4475c43f-6783-4914-9931-c251b99545ba');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '9fe0dae7-c549-4aaa-9eef-76169c12f590');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'cc3d03f7-2197-4603-9ae0-08fa0432c684');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'c0ba80c2-d198-411e-9695-6a7c495b6544');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '1ba8b8d8-7e28-4859-8977-66a6fb6106b6');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '419db4f4-0141-470d-b6bd-cb47c61df2db');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '3cc421ee-8621-4fd4-8705-39fe4b64f88b');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '8f6a74bf-3b7a-40ec-b1b9-941246375f5c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'b85dde8b-9dba-47a7-8d3b-a914f91958a8');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '8e7c1049-8834-4612-bf56-40b635acc927');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'd6fd20f6-0c55-4428-b04b-b65a8a769543');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '265d9df8-34f8-48eb-bcdd-dcb1c902680c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '3931e924-e4de-4fc7-b00e-3937a444e52a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '14ba4f6b-5b79-4e55-9953-3b5f7add0b14');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '51fb6b25-1451-4c61-911f-7e3f7f9294c9');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '6cdadfc9-6d8f-4339-a0b2-f8a235e84dd7');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'defcbdf3-819f-4cf8-be70-e142829dd18c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'b0dd0a3e-eb94-427c-bc44-a086fc4ae4d1');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'd4e88883-afe6-4f32-89bc-1f6da7b40665');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '6edb08ba-e205-4d06-b115-8f28c0d0b8aa');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '48897cab-9c1f-4e0f-9990-551343b4596f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '265d9df8-34f8-48eb-bcdd-dcb1c902680c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '3931e924-e4de-4fc7-b00e-3937a444e52a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '14ba4f6b-5b79-4e55-9953-3b5f7add0b14');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '6cdadfc9-6d8f-4339-a0b2-f8a235e84dd7');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'defcbdf3-819f-4cf8-be70-e142829dd18c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'b0dd0a3e-eb94-427c-bc44-a086fc4ae4d1');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'd4e88883-afe6-4f32-89bc-1f6da7b40665');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '6edb08ba-e205-4d06-b115-8f28c0d0b8aa');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '48897cab-9c1f-4e0f-9990-551343b4596f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '265d9df8-34f8-48eb-bcdd-dcb1c902680c');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '3931e924-e4de-4fc7-b00e-3937a444e52a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'b0dd0a3e-eb94-427c-bc44-a086fc4ae4d1');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'd4e88883-afe6-4f32-89bc-1f6da7b40665');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', '6edb08ba-e205-4d06-b115-8f28c0d0b8aa');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', '48897cab-9c1f-4e0f-9990-551343b4596f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', 'd4e88883-afe6-4f32-89bc-1f6da7b40665');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '6edb08ba-e205-4d06-b115-8f28c0d0b8aa');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '48897cab-9c1f-4e0f-9990-551343b4596f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '86feef17-4b2c-43ba-9163-b2269b70e673');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '1885a46a-187e-4019-8a3c-a6d326255059');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'd7fffd41-76fe-4034-84d3-35ca12d67517');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'd37b5c27-dad6-413c-aa05-87cf944ea25f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '06273618-65e6-46a0-bac7-29dc8734ad1d');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '6f0c6129-1515-4ca9-b781-59c63bf621c6');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '1200c3e7-c394-44cb-8149-ea1205c60c63');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '775bd65f-2582-42c6-babc-c2f87528d534');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '86feef17-4b2c-43ba-9163-b2269b70e673');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '1885a46a-187e-4019-8a3c-a6d326255059');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'd7fffd41-76fe-4034-84d3-35ca12d67517');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'd37b5c27-dad6-413c-aa05-87cf944ea25f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '06273618-65e6-46a0-bac7-29dc8734ad1d');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '6f0c6129-1515-4ca9-b781-59c63bf621c6');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '1200c3e7-c394-44cb-8149-ea1205c60c63');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '86feef17-4b2c-43ba-9163-b2269b70e673');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '1885a46a-187e-4019-8a3c-a6d326255059');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'd7fffd41-76fe-4034-84d3-35ca12d67517');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'd37b5c27-dad6-413c-aa05-87cf944ea25f');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '06273618-65e6-46a0-bac7-29dc8734ad1d');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '1200c3e7-c394-44cb-8149-ea1205c60c63');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', '1885a46a-187e-4019-8a3c-a6d326255059');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'd7fffd41-76fe-4034-84d3-35ca12d67517');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', '1200c3e7-c394-44cb-8149-ea1205c60c63');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '86feef17-4b2c-43ba-9163-b2269b70e673');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '1885a46a-187e-4019-8a3c-a6d326255059');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '1200c3e7-c394-44cb-8149-ea1205c60c63');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '376da489-843a-4be3-b59d-09ebb2f6d6e5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '4d037438-1c5f-4578-9204-3252bfe7542a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '2ada59dd-a5aa-49fc-8725-b81bf145d33e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '0bc1506a-589f-4d1f-90d1-e20e70a3c048');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '8bafde2f-24d7-4046-8d70-648625c25e60');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'b5235d02-7e43-4bf2-969f-f70034b0c379');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '2bdde810-e194-419b-abb4-aed51690d7bd');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', 'e5b1b48b-32ae-4b2b-b92c-42223d53677e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '91ffdf49-6153-4b2a-a50d-633cb5f3a61a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('645ed8c2-2599-4191-8a1c-134610ca54f8', '1fc38999-31b5-498d-b0e5-ce1208fa4fac');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '376da489-843a-4be3-b59d-09ebb2f6d6e5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '4d037438-1c5f-4578-9204-3252bfe7542a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '2ada59dd-a5aa-49fc-8725-b81bf145d33e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '0bc1506a-589f-4d1f-90d1-e20e70a3c048');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '8bafde2f-24d7-4046-8d70-648625c25e60');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'b5235d02-7e43-4bf2-969f-f70034b0c379');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', 'e5b1b48b-32ae-4b2b-b92c-42223d53677e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '91ffdf49-6153-4b2a-a50d-633cb5f3a61a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('865ea79d-8df9-4e59-8fe6-871ab0c7e43f', '1fc38999-31b5-498d-b0e5-ce1208fa4fac');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '376da489-843a-4be3-b59d-09ebb2f6d6e5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '4d037438-1c5f-4578-9204-3252bfe7542a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '2ada59dd-a5aa-49fc-8725-b81bf145d33e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '0bc1506a-589f-4d1f-90d1-e20e70a3c048');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '8bafde2f-24d7-4046-8d70-648625c25e60');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'b5235d02-7e43-4bf2-969f-f70034b0c379');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', 'e5b1b48b-32ae-4b2b-b92c-42223d53677e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '91ffdf49-6153-4b2a-a50d-633cb5f3a61a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('400bf3b9-6766-457b-ba70-a180e3a90eb1', '1fc38999-31b5-498d-b0e5-ce1208fa4fac');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'b5235d02-7e43-4bf2-969f-f70034b0c379');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', 'e5b1b48b-32ae-4b2b-b92c-42223d53677e');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('239c2f5e-1e98-41d2-8feb-b77b5deb9ca6', '91ffdf49-6153-4b2a-a50d-633cb5f3a61a');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '376da489-843a-4be3-b59d-09ebb2f6d6e5');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', 'b5235d02-7e43-4bf2-969f-f70034b0c379');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', '2bdde810-e194-419b-abb4-aed51690d7bd');
INSERT INTO iam.role_permissions (role_id, permission_id) VALUES ('1694b388-af7a-4f62-a796-1272af97a6ce', 'e5b1b48b-32ae-4b2b-b92c-42223d53677e');


--
-- PostgreSQL database dump complete
--

\unrestrict rytVQBLzQi0td4UjZD06y27pvhI4r8tWF17eFNW4rEIkR1hDDKRJGC2HPTZpyOV

