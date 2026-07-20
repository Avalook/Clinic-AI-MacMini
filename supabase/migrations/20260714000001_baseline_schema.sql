--
-- PostgreSQL database dump
--

\restrict IX6t3anCaHfavJhpZgvih68WbDVsiRdflltnRkff4qOaK5nAK33WnuqtFLin8cB

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.3

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
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS public;


--
-- Name: doctor_patient_count(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.doctor_patient_count(p_doctor_id uuid) RETURNS bigint
    LANGUAGE sql STABLE
    AS $$
  SELECT count(DISTINCT a.clinic_patient_id)
  FROM appointment a
  WHERE a.doctor_id = p_doctor_id;
$$;


--
-- Name: doctor_patient_list(uuid, text, integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.doctor_patient_list(p_doctor_id uuid, p_term text DEFAULT ''::text, p_limit integer DEFAULT 50, p_offset integer DEFAULT 0) RETURNS TABLE(clinic_patient_id uuid, patient_code text, full_name text, date_of_birth date, phone_primary text, created_at timestamp with time zone, total_count bigint)
    LANGUAGE sql STABLE
    AS $$
  WITH mine AS (
    SELECT DISTINCT a.clinic_patient_id AS pid
    FROM appointment a
    WHERE a.doctor_id = p_doctor_id
  ),
  filtered AS (
    SELECT p.clinic_patient_id, p.patient_code, p.full_name,
           p.date_of_birth, p.phone_primary, p.created_at
    FROM patient p
    JOIN mine ON mine.pid = p.clinic_patient_id
    WHERE COALESCE(p_term, '') = ''
       OR p.patient_code ILIKE '%' || p_term || '%'
       OR p.full_name   ILIKE '%' || p_term || '%'
       OR p.phone_primary ILIKE '%' || p_term || '%'
  )
  SELECT f.clinic_patient_id, f.patient_code, f.full_name, f.date_of_birth,
         f.phone_primary, f.created_at,
         count(*) OVER() AS total_count
  FROM filtered f
  ORDER BY f.created_at DESC
  LIMIT p_limit OFFSET p_offset;
$$;


--
-- Name: enforce_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enforce_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'event_log is append-only: DELETE not allowed (event_id: %)', OLD.event_id
            USING ERRCODE = 'insufficient_privilege';
    ELSIF TG_OP = 'TRUNCATE' THEN
        RAISE EXCEPTION 'event_log is append-only: TRUNCATE not allowed'
            USING ERRCODE = 'insufficient_privilege';
    ELSIF TG_OP = 'UPDATE' THEN
        -- Only allow flipping event_published from FALSE to TRUE.
        -- All other columns must remain unchanged.
        IF OLD.event_published = FALSE AND NEW.event_published = TRUE
           AND OLD.event_id = NEW.event_id
           AND OLD.event_type = NEW.event_type
           AND OLD.aggregate_id = NEW.aggregate_id
           AND OLD.payload = NEW.payload THEN
            RETURN NEW;
        END IF;
        
        RAISE EXCEPTION 'event_log is append-only: UPDATE not allowed (event_id: %)', OLD.event_id
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: event_log_append_only_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.event_log_append_only_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION
      'Table % is append-only [Loại A #1]. Thao tác % bị từ chối.',
      TG_TABLE_NAME, TG_OP;
END;
$$;


--
-- Name: f_unaccent(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.f_unaccent(text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
    AS $_$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $_$;


--
-- Name: generate_lab_result_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_lab_result_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    next_id BIGINT;
BEGIN
    next_id := nextval('lab_result_code_seq');
    RETURN 'LAB-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' || LPAD(next_id::TEXT, 6, '0');
END;
$$;


--
-- Name: generate_patient_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_patient_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    year_part TEXT;
    seq_part  TEXT;
BEGIN
    year_part := to_char(NOW(), 'YYYY');
    seq_part  := lpad(nextval('patient_code_seq')::TEXT, 6, '0');
    RETURN 'BN-' || year_part || '-' || seq_part;
END;
$$;


--
-- Name: kb_page_update_search_vector(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.kb_page_update_search_vector() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.summary, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'C');
    RETURN NEW;
END;
$$;


--
-- Name: kb_version_append_only_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.kb_version_append_only_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'kb_version is append-only [Loại A #1]. Thao tác % bị từ chối.', TG_OP;
END;
$$;


--
-- Name: prevent_dead_letter_modification(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_dead_letter_modification() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'dead_letter_event is append-only — UPDATE/DELETE not allowed';
END;
$$;


--
-- Name: prevent_hard_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_hard_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Escape hatch for controlled ETL/seed jobs (see header). The custom GUC
    -- is unset on normal app connections → current_setting(..., true) = NULL.
    IF current_setting('app.allow_hard_delete', true) = 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;   -- allow the row delete to proceed
        END IF;
        RETURN NULL;       -- TRUNCATE (statement-level): return value ignored
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            '% is append-only: DELETE not allowed — cancel via status / is_active update (row id kept for audit)',
            TG_TABLE_NAME
            USING ERRCODE = 'insufficient_privilege';
    ELSIF TG_OP = 'TRUNCATE' THEN
        RAISE EXCEPTION '% is append-only: TRUNCATE not allowed', TG_TABLE_NAME
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: rls_auto_enable(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rls_auto_enable() RETURNS event_trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog'
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%' AND cmd.schema_name NOT LIKE 'pg_temp%' THEN
      BEGIN
        EXECUTE format('alter table if exists %s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip % (either system schema or not in enforced list: %.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: set_updated_at_timestamp(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: visit_finalized_block_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.visit_finalized_block_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.status = 'FINALIZED' AND NEW.status <> 'AMENDED' THEN
        RAISE EXCEPTION
            'visit % is FINALIZED; UPDATE blocked except FINALIZED -> AMENDED (TT13/2011/TT-BYT)',
            OLD.visit_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: appointment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointment (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    doctor_id uuid,
    work_session_id uuid,
    location_id uuid NOT NULL,
    service_type_id uuid NOT NULL,
    booking_channel text,
    slot_start timestamp with time zone NOT NULL,
    slot_end timestamp with time zone NOT NULL,
    assigned_station text,
    queue_number text,
    is_priority_slot boolean DEFAULT false NOT NULL,
    is_walkin boolean DEFAULT false NOT NULL,
    status text DEFAULT 'SCHEDULED'::text NOT NULL,
    confirmed_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    cancellation_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    patient_kind text,
    thanh_min integer,
    sono_min integer,
    need_sono boolean,
    episode_id uuid,
    CONSTRAINT appointment_check CHECK ((slot_end > slot_start)),
    CONSTRAINT appointment_patient_kind_check CHECK ((patient_kind = ANY (ARRAY['NEW'::text, 'RETURN'::text]))),
    CONSTRAINT appointment_sono_min_check CHECK (((sono_min >= 0) AND (sono_min <= 60))),
    CONSTRAINT appointment_status_check CHECK ((status = ANY (ARRAY['SCHEDULED'::text, 'CSKH_CONFIRMED'::text, 'CONFIRMED'::text, 'CHECKED_IN'::text, 'COMPLETED'::text, 'NO_SHOW'::text, 'CANCELLED'::text, 'DOCTOR_DECLINED'::text]))),
    CONSTRAINT appointment_thanh_min_check CHECK (((thanh_min >= 0) AND (thanh_min <= 60)))
);


--
-- Name: block_budget; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.block_budget (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    location_id uuid NOT NULL,
    doctor_id uuid,
    weekday integer,
    hour_start integer NOT NULL,
    thanh_budget_min integer DEFAULT 50 NOT NULL,
    sono_budget_min integer DEFAULT 90 NOT NULL,
    online_quota_min integer DEFAULT 35 NOT NULL,
    walkin_quota_min integer DEFAULT 10 NOT NULL,
    buffer_min integer DEFAULT 5 NOT NULL,
    new_cap integer DEFAULT 3 NOT NULL,
    max_total integer DEFAULT 12 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT block_budget_hour_start_check CHECK (((hour_start >= 0) AND (hour_start <= 23))),
    CONSTRAINT block_budget_weekday_check CHECK (((weekday >= 0) AND (weekday <= 6)))
);


--
-- Name: booking_channel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_channel (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    category text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT booking_channel_category_check CHECK ((category = ANY (ARRAY['ZALO'::text, 'FACEBOOK'::text, 'HOTLINE'::text, 'WALK_IN'::text, 'REFERRAL'::text, 'OTHER'::text])))
);


--
-- Name: care_episode; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.care_episode (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    service_type_id uuid NOT NULL,
    status text DEFAULT 'OPEN'::text NOT NULL,
    opened_at timestamp with time zone DEFAULT now() NOT NULL,
    opened_appointment_id uuid,
    last_visit_at timestamp with time zone,
    closed_at timestamp with time zone,
    close_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT care_episode_close_reason_check CHECK ((close_reason = ANY (ARRAY['doctor_no_followup'::text, 'cskh_confirmed'::text, 'manual'::text, 'new_problem'::text, 'auto_inactive'::text]))),
    CONSTRAINT care_episode_status_check CHECK ((status = ANY (ARRAY['OPEN'::text, 'PENDING_CLOSE'::text, 'CLOSED'::text])))
);


--
-- Name: clinic_location; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clinic_location (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    address text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: clinical_form_response; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clinical_form_response (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    visit_id uuid NOT NULL,
    service_code text NOT NULL,
    form_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_by text,
    updated_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: clinical_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clinical_record (
    record_id uuid DEFAULT gen_random_uuid() NOT NULL,
    visit_id uuid NOT NULL,
    pregnancy_id uuid,
    soap_subjective jsonb,
    soap_objective jsonb,
    soap_assessment jsonb,
    soap_plan jsonb,
    chief_complaint_at_visit text,
    voice_note_url text,
    voice_transcript text,
    voice_note_reviewed boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: cskh_action; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cskh_action (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_ref text NOT NULL,
    clinic_patient_id uuid,
    category text,
    step text,
    status text,
    action_data text,
    description text,
    result_text text,
    deadline_at timestamp with time zone,
    source_created_at timestamp with time zone,
    source_updated_at timestamp with time zone,
    created_by_text text,
    last_edited_by_text text,
    rating integer,
    billing_tag text,
    appointment_link_raw text,
    visit_link_raw text,
    lab_link_raw text,
    patient_link_raw text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: cskh_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cskh_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid,
    work_date date,
    slot_time text,
    visit_number text,
    patient_info text,
    phone text,
    visit_type text,
    confirmed boolean,
    confirmed_by text,
    arrived boolean,
    has_test boolean,
    tests text,
    result_eta text,
    result_group text,
    cskh_status text,
    cskh_followup text,
    last_cskh_date date,
    cskh_by text,
    note text,
    source_month text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: drug_catalog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.drug_catalog (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name_base text NOT NULL,
    name_raw text NOT NULL,
    variant text,
    group_label text,
    unit_price numeric(12,0),
    needs_review boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: event_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_log (
    event_id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_type text NOT NULL,
    event_version integer DEFAULT 1 NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    payload jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    correlation_id uuid,
    causation_id uuid,
    source text NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    event_published boolean DEFAULT false NOT NULL,
    CONSTRAINT event_type_format CHECK ((event_type ~ '^[a-z_]+\.[a-z_]+$'::text)),
    CONSTRAINT event_version_positive CHECK ((event_version > 0)),
    CONSTRAINT source_not_empty CHECK ((length(source) > 0))
);


--
-- Name: lab_result; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_result (
    lab_result_id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    visit_id uuid,
    appointment_id uuid,
    test_code text NOT NULL,
    test_name text NOT NULL,
    panel_code text,
    result_value text,
    result_numeric numeric,
    result_unit text,
    reference_range_low numeric,
    reference_range_high numeric,
    flag text,
    triage_group text DEFAULT 'PENDING'::text NOT NULL,
    triage_reason text,
    triage_classified_at timestamp with time zone,
    triage_model text,
    requires_doctor_review boolean DEFAULT false NOT NULL,
    reviewed_by_staff_id uuid,
    reviewed_at timestamp with time zone,
    is_finalized boolean DEFAULT false NOT NULL,
    lab_provider text,
    external_ref text,
    raw_payload jsonb,
    sample_collected_at timestamp with time zone,
    result_received_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT lab_result_finalized_requires_reviewer CHECK (((is_finalized = false) OR ((is_finalized = true) AND (reviewed_by_staff_id IS NOT NULL) AND (reviewed_at IS NOT NULL)))),
    CONSTRAINT lab_result_flag_check CHECK ((flag = ANY (ARRAY['NORMAL'::text, 'HIGH'::text, 'LOW'::text, 'CRITICAL_HIGH'::text, 'CRITICAL_LOW'::text, 'ABNORMAL'::text]))),
    CONSTRAINT lab_result_triage_group_check CHECK ((triage_group = ANY (ARRAY['GROUP_A'::text, 'GROUP_B'::text, 'GROUP_C'::text, 'PENDING'::text])))
);


--
-- Name: lab_result_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lab_result_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mpi_merge_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mpi_merge_queue (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    patient_id_a uuid NOT NULL,
    patient_id_b uuid NOT NULL,
    score numeric(5,2) NOT NULL,
    status text DEFAULT 'PENDING'::text,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_different_patients CHECK ((patient_id_a <> patient_id_b)),
    CONSTRAINT mpi_merge_queue_status_check CHECK ((status = ANY (ARRAY['PENDING'::text, 'MERGED'::text, 'REJECTED'::text, 'REVIEW'::text])))
);


--
-- Name: patient; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient (
    clinic_patient_id uuid DEFAULT gen_random_uuid() NOT NULL,
    patient_code text NOT NULL,
    national_id_number text,
    full_name text NOT NULL,
    date_of_birth date,
    phone_primary text,
    phone_secondary text,
    location_id uuid NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    gender text,
    ethnicity text,
    nationality text,
    occupation text,
    patient_objection text,
    address text,
    guardian_name text,
    full_name_unaccent text GENERATED ALWAYS AS (lower(replace(replace(public.f_unaccent(full_name), 'đ'::text, 'd'::text), 'Đ'::text, 'D'::text))) STORED,
    birth_year smallint,
    province_code text,
    province_name text,
    ward_code text,
    ward_name text,
    address_detail text,
    van_de_di_kham text,
    linh_vuc text,
    CONSTRAINT patient_birth_year_check CHECK (((birth_year IS NULL) OR ((birth_year >= 1900) AND (birth_year <= 2100)))),
    CONSTRAINT patient_gender_check CHECK (((gender IS NULL) OR (gender = ANY (ARRAY['Nam'::text, 'Nữ'::text, 'Khác'::text])))),
    CONSTRAINT patient_linh_vuc_check CHECK (((linh_vuc IS NULL) OR (linh_vuc = ANY (ARRAY['PK'::text, 'SK'::text, 'NT'::text, 'HMVS'::text, 'NK'::text]))))
);


--
-- Name: patient_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.patient_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patient_medical_profile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_medical_profile (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    blood_type text,
    allergies text[] DEFAULT '{}'::text[],
    chronic_diseases text[] DEFAULT '{}'::text[],
    current_medications text[] DEFAULT '{}'::text[],
    surgical_history text[] DEFAULT '{}'::text[],
    family_history jsonb DEFAULT '{}'::jsonb,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT patient_medical_profile_blood_type_check CHECK ((blood_type = ANY (ARRAY['A'::text, 'B'::text, 'AB'::text, 'O'::text, 'A+'::text, 'A-'::text, 'B+'::text, 'B-'::text, 'AB+'::text, 'AB-'::text, 'O+'::text, 'O-'::text])))
);


--
-- Name: visit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.visit (
    visit_id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    appointment_id uuid,
    work_session_id uuid,
    attending_doctor_id uuid,
    location_id uuid,
    service_type_id uuid,
    status text DEFAULT 'OPEN'::text NOT NULL,
    finalized_at timestamp with time zone,
    finalized_by uuid,
    checked_in_at timestamp with time zone,
    checked_in_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    exam_completed_at timestamp with time zone,
    CONSTRAINT visit_status_check CHECK ((status = ANY (ARRAY['OPEN'::text, 'IN_PROGRESS'::text, 'FINALIZED'::text, 'AMENDED'::text])))
);


--
-- Name: patient_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.patient_summary AS
 SELECT p.clinic_patient_id,
    p.patient_code,
    p.full_name,
    p.date_of_birth,
    p.phone_primary,
    p.national_id_number,
    v_agg.last_visit_at,
    v_agg.total_visits,
    next_appt.next_appointment_at,
    next_appt.next_appointment_status,
    last_lab.last_lab_received_at,
    last_lab.last_lab_test_code,
    last_lab.last_lab_triage_group
   FROM (((public.patient p
     LEFT JOIN LATERAL ( SELECT max(COALESCE(v.checked_in_at, v.created_at)) AS last_visit_at,
            count(*) AS total_visits
           FROM public.visit v
          WHERE (v.clinic_patient_id = p.clinic_patient_id)) v_agg ON (true))
     LEFT JOIN LATERAL ( SELECT a.slot_start AS next_appointment_at,
            a.status AS next_appointment_status
           FROM public.appointment a
          WHERE ((a.clinic_patient_id = p.clinic_patient_id) AND (a.status = ANY (ARRAY['SCHEDULED'::text, 'CONFIRMED'::text])) AND (a.slot_start > now()))
          ORDER BY a.slot_start
         LIMIT 1) next_appt ON (true))
     LEFT JOIN LATERAL ( SELECT lr.result_received_at AS last_lab_received_at,
            lr.test_code AS last_lab_test_code,
            lr.triage_group AS last_lab_triage_group
           FROM public.lab_result lr
          WHERE (lr.clinic_patient_id = p.clinic_patient_id)
          ORDER BY lr.result_received_at DESC
         LIMIT 1) last_lab ON (true));


--
-- Name: payment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    visit_id uuid NOT NULL,
    clinic_patient_id uuid,
    kind text NOT NULL,
    status text DEFAULT 'PAID'::text NOT NULL,
    amount bigint,
    paid_by_staff_id uuid,
    paid_by_text text,
    paid_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT payment_kind_check CHECK ((kind = ANY (ARRAY['thuoc'::text, 'dich_vu'::text]))),
    CONSTRAINT payment_status_check CHECK ((status = 'PAID'::text))
);


--
-- Name: pregnancy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pregnancy (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    location_id uuid NOT NULL,
    lmp_date date,
    edd_date date,
    gestational_age_at_registration integer,
    outcome text DEFAULT 'ONGOING'::text,
    outcome_date date,
    primary_doctor_id uuid,
    is_high_risk boolean DEFAULT false,
    high_risk_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_edd_after_lmp CHECK (((NOT ((lmp_date IS NOT NULL) AND (edd_date IS NOT NULL))) OR (edd_date > lmp_date))),
    CONSTRAINT pregnancy_outcome_check CHECK ((outcome = ANY (ARRAY['ONGOING'::text, 'DELIVERED'::text, 'MISCARRIAGE'::text, 'TERMINATED'::text, 'UNKNOWN'::text])))
);


--
-- Name: prescription; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prescription (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_ref text NOT NULL,
    clinic_patient_id uuid,
    visit_id uuid,
    drug_name_raw text,
    drug_catalog_ref text,
    dosage_instructions text,
    quantity text,
    quantity_note text,
    caution text,
    standardized_form text,
    visit_link_raw text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: province; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.province (
    code text NOT NULL,
    name text NOT NULL,
    full_name text NOT NULL,
    code_name text
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    filename text NOT NULL,
    applied_at timestamp with time zone DEFAULT now()
);


--
-- Name: service_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_ref text NOT NULL,
    clinic_patient_id uuid,
    service_type_id uuid,
    service_name_raw text,
    performer_text text,
    status text,
    result_text text,
    ordered_at timestamp with time zone,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    created_by_text text,
    visit_link_raw text,
    patient_link_raw text,
    result_form_url text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    kind text,
    sent_to_lab_at timestamp with time zone,
    CONSTRAINT service_log_kind_check CHECK (((kind IS NULL) OR (kind = ANY (ARRAY['SA'::text, 'XN'::text]))))
);


--
-- Name: service_price; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_price (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    service_code text NOT NULL,
    name text NOT NULL,
    "group" text NOT NULL,
    unit_price numeric(12,0),
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    category text,
    tang text,
    CONSTRAINT service_price_group_check CHECK (("group" = ANY (ARRAY['thuoc'::text, 'dich_vu'::text])))
);


--
-- Name: service_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_type (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    default_duration_minutes integer DEFAULT 30,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: staff; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staff (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    primary_location_id uuid,
    full_name text NOT NULL,
    is_active boolean DEFAULT true,
    is_training boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    primary_department text NOT NULL,
    short_name text,
    employment_type text DEFAULT 'FULL_TIME'::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    auth_user_id uuid,
    CONSTRAINT staff_employment_type_check CHECK ((employment_type = ANY (ARRAY['FULL_TIME'::text, 'PART_TIME'::text, 'CONTRACT'::text]))),
    CONSTRAINT staff_primary_department_check CHECK ((primary_department = ANY (ARRAY['DOCTOR'::text, 'ULTRASOUND_DOCTOR'::text, 'NURSE_ULTRASOUND'::text, 'RECEPTION'::text, 'CSKH'::text, 'MANAGEMENT'::text, 'CASHIER'::text, 'TKYK'::text, 'TRUONG_CA'::text, 'CASHIER_THUOC'::text, 'CASHIER_DV'::text])))
);


--
-- Name: staff_capability; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staff_capability (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    staff_id uuid NOT NULL,
    capability text NOT NULL,
    proficiency_level text DEFAULT 'COMPETENT'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: staff_task; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staff_task (
    task_id uuid DEFAULT gen_random_uuid() NOT NULL,
    location_id uuid,
    task_type text NOT NULL,
    priority text DEFAULT 'NORMAL'::text NOT NULL,
    status text DEFAULT 'PENDING'::text NOT NULL,
    assigned_to uuid,
    source_type text,
    source_id uuid,
    title text NOT NULL,
    description text,
    due_at timestamp with time zone,
    sla_hours integer DEFAULT 24 NOT NULL,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT staff_task_done_requires_completed_at CHECK (((status <> 'DONE'::text) OR (completed_at IS NOT NULL))),
    CONSTRAINT staff_task_priority_check CHECK ((priority = ANY (ARRAY['URGENT'::text, 'HIGH'::text, 'NORMAL'::text]))),
    CONSTRAINT staff_task_sla_hours_check CHECK ((sla_hours > 0)),
    CONSTRAINT staff_task_status_check CHECK ((status = ANY (ARRAY['PENDING'::text, 'IN_PROGRESS'::text, 'DONE'::text, 'CANCELLED'::text])))
);


--
-- Name: ultrasound_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ultrasound_record (
    ultrasound_id uuid DEFAULT gen_random_uuid() NOT NULL,
    visit_id uuid NOT NULL,
    clinic_patient_id uuid NOT NULL,
    performed_by uuid,
    pregnancy_id uuid,
    ultrasound_type text,
    findings jsonb,
    impression text,
    image_refs text[],
    gestational_age_weeks numeric,
    performed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ward; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ward (
    code text NOT NULL,
    name text NOT NULL,
    full_name text NOT NULL,
    code_name text,
    province_code text NOT NULL
);


--
-- Name: work_roster; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_roster (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    week_start date NOT NULL,
    work_date date NOT NULL,
    shift text DEFAULT 'FULL'::text NOT NULL,
    station text NOT NULL,
    staff_id uuid,
    staff_name text NOT NULL,
    sort integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    status text DEFAULT 'APPROVED'::text NOT NULL,
    reject_reason text,
    CONSTRAINT work_roster_shift_check CHECK ((shift = ANY (ARRAY['FULL'::text, 'SANG'::text, 'CHIEU'::text]))),
    CONSTRAINT work_roster_status_check CHECK ((status = ANY (ARRAY['PENDING'::text, 'APPROVED'::text, 'REJECTED'::text])))
);


--
-- Name: work_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_session (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    location_id uuid NOT NULL,
    session_date date NOT NULL,
    session_type text NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    max_patients integer,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT work_session_check CHECK ((end_time > start_time)),
    CONSTRAINT work_session_session_type_check CHECK ((session_type = ANY (ARRAY['EVENING'::text, 'WEEKEND_MORNING'::text, 'WEEKEND_AFTERNOON'::text])))
);


--
-- Name: work_session_staff; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_session_staff (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    work_session_id uuid NOT NULL,
    staff_id uuid NOT NULL,
    role text NOT NULL,
    station text NOT NULL,
    on_call_flag boolean DEFAULT false NOT NULL,
    is_training boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: appointment appointment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment
    ADD CONSTRAINT appointment_pkey PRIMARY KEY (id);


--
-- Name: block_budget block_budget_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.block_budget
    ADD CONSTRAINT block_budget_pkey PRIMARY KEY (id);


--
-- Name: booking_channel booking_channel_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_channel
    ADD CONSTRAINT booking_channel_code_key UNIQUE (code);


--
-- Name: booking_channel booking_channel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_channel
    ADD CONSTRAINT booking_channel_pkey PRIMARY KEY (id);


--
-- Name: care_episode care_episode_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.care_episode
    ADD CONSTRAINT care_episode_pkey PRIMARY KEY (id);


--
-- Name: clinic_location clinic_location_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinic_location
    ADD CONSTRAINT clinic_location_code_key UNIQUE (code);


--
-- Name: clinic_location clinic_location_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinic_location
    ADD CONSTRAINT clinic_location_pkey PRIMARY KEY (id);


--
-- Name: clinical_form_response clinical_form_response_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_form_response
    ADD CONSTRAINT clinical_form_response_pkey PRIMARY KEY (id);


--
-- Name: clinical_record clinical_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_record
    ADD CONSTRAINT clinical_record_pkey PRIMARY KEY (record_id);


--
-- Name: clinical_record clinical_record_visit_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_record
    ADD CONSTRAINT clinical_record_visit_id_key UNIQUE (visit_id);


--
-- Name: cskh_action cskh_action_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cskh_action
    ADD CONSTRAINT cskh_action_pkey PRIMARY KEY (id);


--
-- Name: cskh_action cskh_action_source_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cskh_action
    ADD CONSTRAINT cskh_action_source_ref_key UNIQUE (source_ref);


--
-- Name: cskh_log cskh_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cskh_log
    ADD CONSTRAINT cskh_log_pkey PRIMARY KEY (id);


--
-- Name: drug_catalog drug_catalog_name_raw_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drug_catalog
    ADD CONSTRAINT drug_catalog_name_raw_key UNIQUE (name_raw);


--
-- Name: drug_catalog drug_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drug_catalog
    ADD CONSTRAINT drug_catalog_pkey PRIMARY KEY (id);


--
-- Name: event_log event_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_log
    ADD CONSTRAINT event_log_pkey PRIMARY KEY (event_id);


--
-- Name: lab_result lab_result_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_result
    ADD CONSTRAINT lab_result_pkey PRIMARY KEY (lab_result_id);


--
-- Name: mpi_merge_queue mpi_merge_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mpi_merge_queue
    ADD CONSTRAINT mpi_merge_queue_pkey PRIMARY KEY (id);


--
-- Name: patient_medical_profile patient_medical_profile_clinic_patient_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_medical_profile
    ADD CONSTRAINT patient_medical_profile_clinic_patient_id_key UNIQUE (clinic_patient_id);


--
-- Name: patient_medical_profile patient_medical_profile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_medical_profile
    ADD CONSTRAINT patient_medical_profile_pkey PRIMARY KEY (id);


--
-- Name: patient patient_patient_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT patient_patient_code_key UNIQUE (patient_code);


--
-- Name: patient patient_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT patient_pkey PRIMARY KEY (clinic_patient_id);


--
-- Name: payment payment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_pkey PRIMARY KEY (id);


--
-- Name: payment payment_visit_id_kind_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_visit_id_kind_key UNIQUE (visit_id, kind);


--
-- Name: pregnancy pregnancy_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pregnancy
    ADD CONSTRAINT pregnancy_pkey PRIMARY KEY (id);


--
-- Name: prescription prescription_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescription
    ADD CONSTRAINT prescription_pkey PRIMARY KEY (id);


--
-- Name: prescription prescription_source_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescription
    ADD CONSTRAINT prescription_source_ref_key UNIQUE (source_ref);


--
-- Name: province province_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.province
    ADD CONSTRAINT province_pkey PRIMARY KEY (code);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (filename);


--
-- Name: service_log service_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_log
    ADD CONSTRAINT service_log_pkey PRIMARY KEY (id);


--
-- Name: service_log service_log_source_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_log
    ADD CONSTRAINT service_log_source_ref_key UNIQUE (source_ref);


--
-- Name: service_price service_price_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_price
    ADD CONSTRAINT service_price_pkey PRIMARY KEY (id);


--
-- Name: service_type service_type_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_type
    ADD CONSTRAINT service_type_code_key UNIQUE (code);


--
-- Name: service_type service_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_type
    ADD CONSTRAINT service_type_pkey PRIMARY KEY (id);


--
-- Name: staff_capability staff_capability_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_capability
    ADD CONSTRAINT staff_capability_pkey PRIMARY KEY (id);


--
-- Name: staff staff_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff
    ADD CONSTRAINT staff_pkey PRIMARY KEY (id);


--
-- Name: staff_task staff_task_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_task
    ADD CONSTRAINT staff_task_pkey PRIMARY KEY (task_id);


--
-- Name: ultrasound_record ultrasound_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ultrasound_record
    ADD CONSTRAINT ultrasound_record_pkey PRIMARY KEY (ultrasound_id);


--
-- Name: clinical_form_response uq_clinical_form_visit_service; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_form_response
    ADD CONSTRAINT uq_clinical_form_visit_service UNIQUE (visit_id, service_code);


--
-- Name: staff_capability uq_staff_capability; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_capability
    ADD CONSTRAINT uq_staff_capability UNIQUE (staff_id, capability);


--
-- Name: visit visit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_pkey PRIMARY KEY (visit_id);


--
-- Name: ward ward_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ward
    ADD CONSTRAINT ward_pkey PRIMARY KEY (code);


--
-- Name: work_roster work_roster_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_roster
    ADD CONSTRAINT work_roster_pkey PRIMARY KEY (id);


--
-- Name: work_session work_session_location_id_session_date_session_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_session
    ADD CONSTRAINT work_session_location_id_session_date_session_type_key UNIQUE (location_id, session_date, session_type);


--
-- Name: work_session work_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_session
    ADD CONSTRAINT work_session_pkey PRIMARY KEY (id);


--
-- Name: work_session_staff work_session_staff_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_session_staff
    ADD CONSTRAINT work_session_staff_pkey PRIMARY KEY (id);


--
-- Name: work_session_staff work_session_staff_work_session_id_staff_id_station_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_session_staff
    ADD CONSTRAINT work_session_staff_work_session_id_staff_id_station_key UNIQUE (work_session_id, staff_id, station);


--
-- Name: idx_appointment_doctor_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointment_doctor_date ON public.appointment USING btree (doctor_id, slot_start);


--
-- Name: idx_appointment_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointment_patient ON public.appointment USING btree (clinic_patient_id);


--
-- Name: idx_appointment_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointment_session ON public.appointment USING btree (work_session_id);


--
-- Name: idx_appointment_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointment_status ON public.appointment USING btree (status) WHERE (status = ANY (ARRAY['SCHEDULED'::text, 'CONFIRMED'::text, 'CHECKED_IN'::text]));


--
-- Name: idx_booking_channel_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_channel_active ON public.booking_channel USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_booking_channel_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_channel_category ON public.booking_channel USING btree (category);


--
-- Name: idx_care_episode_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_care_episode_lookup ON public.care_episode USING btree (clinic_patient_id, service_type_id, status);


--
-- Name: idx_clinical_form_visit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clinical_form_visit ON public.clinical_form_response USING btree (visit_id);


--
-- Name: idx_cskh_action_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cskh_action_category ON public.cskh_action USING btree (category);


--
-- Name: idx_cskh_action_deadline; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cskh_action_deadline ON public.cskh_action USING btree (deadline_at) WHERE (deadline_at IS NOT NULL);


--
-- Name: idx_cskh_action_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cskh_action_patient ON public.cskh_action USING btree (clinic_patient_id) WHERE (clinic_patient_id IS NOT NULL);


--
-- Name: idx_cskh_action_source_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cskh_action_source_created ON public.cskh_action USING btree (source_created_at DESC NULLS LAST);


--
-- Name: idx_cskh_log_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cskh_log_date ON public.cskh_log USING btree (work_date DESC);


--
-- Name: idx_cskh_log_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cskh_log_patient ON public.cskh_log USING btree (clinic_patient_id);


--
-- Name: idx_drug_catalog_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_drug_catalog_active ON public.drug_catalog USING btree (name_base) WHERE is_active;


--
-- Name: idx_event_log_aggregate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_log_aggregate ON public.event_log USING btree (aggregate_type, aggregate_id, occurred_at);


--
-- Name: idx_event_log_correlation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_log_correlation ON public.event_log USING btree (correlation_id) WHERE (correlation_id IS NOT NULL);


--
-- Name: idx_event_log_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_log_event_type ON public.event_log USING btree (event_type, occurred_at);


--
-- Name: idx_event_log_occurred_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_log_occurred_at ON public.event_log USING btree (occurred_at);


--
-- Name: idx_event_log_unpublished; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_log_unpublished ON public.event_log USING btree (event_published) WHERE (event_published = false);


--
-- Name: idx_lab_result_appointment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_result_appointment ON public.lab_result USING btree (appointment_id) WHERE (appointment_id IS NOT NULL);


--
-- Name: idx_lab_result_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_result_patient ON public.lab_result USING btree (clinic_patient_id, result_received_at DESC);


--
-- Name: idx_lab_result_safety_gate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_result_safety_gate ON public.lab_result USING btree (requires_doctor_review, is_finalized) WHERE ((requires_doctor_review = true) AND (is_finalized = false));


--
-- Name: idx_lab_result_triage_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_result_triage_pending ON public.lab_result USING btree (triage_group) WHERE (triage_group = 'PENDING'::text);


--
-- Name: idx_mpi_merge_queue_status_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mpi_merge_queue_status_score ON public.mpi_merge_queue USING btree (status, score DESC);


--
-- Name: idx_patient_full_name_unaccent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_patient_full_name_unaccent ON public.patient USING gin (full_name_unaccent public.gin_trgm_ops);


--
-- Name: idx_patient_national_id_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_patient_national_id_unique ON public.patient USING btree (national_id_number) WHERE (national_id_number IS NOT NULL);


--
-- Name: idx_patient_patient_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_patient_patient_code ON public.patient USING btree (patient_code);


--
-- Name: idx_patient_phone_primary; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_patient_phone_primary ON public.patient USING btree (phone_primary);


--
-- Name: idx_payment_visit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payment_visit ON public.payment USING btree (visit_id);


--
-- Name: idx_pregnancy_clinic_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pregnancy_clinic_patient_id ON public.pregnancy USING btree (clinic_patient_id);


--
-- Name: idx_pregnancy_outcome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pregnancy_outcome ON public.pregnancy USING btree (outcome);


--
-- Name: idx_pregnancy_primary_doctor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pregnancy_primary_doctor_id ON public.pregnancy USING btree (primary_doctor_id);


--
-- Name: idx_prescription_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prescription_patient ON public.prescription USING btree (clinic_patient_id) WHERE (clinic_patient_id IS NOT NULL);


--
-- Name: idx_prescription_visit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prescription_visit ON public.prescription USING btree (visit_id) WHERE (visit_id IS NOT NULL);


--
-- Name: idx_service_log_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_service_log_kind ON public.service_log USING btree (kind) WHERE (kind IS NOT NULL);


--
-- Name: idx_service_log_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_service_log_patient ON public.service_log USING btree (clinic_patient_id) WHERE (clinic_patient_id IS NOT NULL);


--
-- Name: idx_service_log_service_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_service_log_service_type ON public.service_log USING btree (service_type_id) WHERE (service_type_id IS NOT NULL);


--
-- Name: idx_service_log_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_service_log_started ON public.service_log USING btree (started_at DESC NULLS LAST);


--
-- Name: idx_service_log_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_service_log_status ON public.service_log USING btree (status);


--
-- Name: idx_service_price_group_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_service_price_group_active ON public.service_price USING btree ("group") WHERE active;


--
-- Name: idx_staff_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_staff_active ON public.staff USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_staff_auth_user_id_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_staff_auth_user_id_unique ON public.staff USING btree (auth_user_id) WHERE (auth_user_id IS NOT NULL);


--
-- Name: idx_staff_capability_capability; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_staff_capability_capability ON public.staff_capability USING btree (capability);


--
-- Name: idx_staff_capability_staff_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_staff_capability_staff_id ON public.staff_capability USING btree (staff_id);


--
-- Name: idx_staff_primary_location; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_staff_primary_location ON public.staff USING btree (primary_location_id);


--
-- Name: idx_staff_task_assigned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_staff_task_assigned ON public.staff_task USING btree (assigned_to, status);


--
-- Name: idx_staff_task_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_staff_task_due ON public.staff_task USING btree (due_at) WHERE (status = 'PENDING'::text);


--
-- Name: idx_staff_task_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_staff_task_source ON public.staff_task USING btree (source_type, source_id);


--
-- Name: idx_ultrasound_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ultrasound_patient ON public.ultrasound_record USING btree (clinic_patient_id);


--
-- Name: idx_ultrasound_visit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ultrasound_visit ON public.ultrasound_record USING btree (visit_id);


--
-- Name: idx_visit_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_visit_patient ON public.visit USING btree (clinic_patient_id);


--
-- Name: idx_ward_province_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ward_province_code ON public.ward USING btree (province_code);


--
-- Name: idx_work_roster_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_work_roster_date ON public.work_roster USING btree (work_date);


--
-- Name: idx_work_roster_staff; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_work_roster_staff ON public.work_roster USING btree (staff_id);


--
-- Name: idx_work_roster_week; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_work_roster_week ON public.work_roster USING btree (week_start);


--
-- Name: idx_work_roster_week_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_work_roster_week_status ON public.work_roster USING btree (week_start, status);


--
-- Name: idx_work_session_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_work_session_date ON public.work_session USING btree (session_date DESC);


--
-- Name: idx_wss_staff; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wss_staff ON public.work_session_staff USING btree (staff_id);


--
-- Name: idx_wss_work_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wss_work_session ON public.work_session_staff USING btree (work_session_id);


--
-- Name: uq_block_budget_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_block_budget_key ON public.block_budget USING btree (location_id, COALESCE(doctor_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(weekday, 9), hour_start);


--
-- Name: uq_care_episode_live; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_care_episode_live ON public.care_episode USING btree (clinic_patient_id, service_type_id) WHERE (status <> 'CLOSED'::text);


--
-- Name: uq_service_price_code_group; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_service_price_code_group ON public.service_price USING btree ("group", service_code);


--
-- Name: uq_visit_appointment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_visit_appointment_id ON public.visit USING btree (appointment_id) WHERE (appointment_id IS NOT NULL);


--
-- Name: clinical_record clinical_record_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER clinical_record_set_updated_at BEFORE UPDATE ON public.clinical_record FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: lab_result lab_result_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER lab_result_set_updated_at BEFORE UPDATE ON public.lab_result FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: staff_task staff_task_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staff_task_set_updated_at BEFORE UPDATE ON public.staff_task FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: appointment trg_appointment_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_appointment_no_delete BEFORE DELETE ON public.appointment FOR EACH ROW EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: appointment trg_appointment_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_appointment_no_truncate BEFORE TRUNCATE ON public.appointment FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: clinical_record trg_clinical_record_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clinical_record_no_delete BEFORE DELETE ON public.clinical_record FOR EACH ROW EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: clinical_record trg_clinical_record_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clinical_record_no_truncate BEFORE TRUNCATE ON public.clinical_record FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: event_log trg_event_log_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_event_log_no_delete BEFORE DELETE ON public.event_log FOR EACH ROW EXECUTE FUNCTION public.enforce_append_only();


--
-- Name: event_log trg_event_log_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_event_log_no_truncate BEFORE TRUNCATE ON public.event_log FOR EACH STATEMENT EXECUTE FUNCTION public.enforce_append_only();


--
-- Name: event_log trg_event_log_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_event_log_no_update BEFORE UPDATE ON public.event_log FOR EACH ROW EXECUTE FUNCTION public.enforce_append_only();


--
-- Name: lab_result trg_lab_result_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_lab_result_no_delete BEFORE DELETE ON public.lab_result FOR EACH ROW EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: lab_result trg_lab_result_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_lab_result_no_truncate BEFORE TRUNCATE ON public.lab_result FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: patient trg_patient_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_patient_no_delete BEFORE DELETE ON public.patient FOR EACH ROW EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: patient trg_patient_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_patient_no_truncate BEFORE TRUNCATE ON public.patient FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: visit trg_visit_finalized_block; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_visit_finalized_block BEFORE UPDATE ON public.visit FOR EACH ROW EXECUTE FUNCTION public.visit_finalized_block_update();


--
-- Name: visit trg_visit_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_visit_no_delete BEFORE DELETE ON public.visit FOR EACH ROW EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: visit trg_visit_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_visit_no_truncate BEFORE TRUNCATE ON public.visit FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_hard_delete();


--
-- Name: ultrasound_record ultrasound_record_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ultrasound_record_set_updated_at BEFORE UPDATE ON public.ultrasound_record FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: visit visit_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER visit_set_updated_at BEFORE UPDATE ON public.visit FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: appointment appointment_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment
    ADD CONSTRAINT appointment_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE RESTRICT;


--
-- Name: appointment appointment_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment
    ADD CONSTRAINT appointment_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.staff(id);


--
-- Name: appointment appointment_episode_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment
    ADD CONSTRAINT appointment_episode_id_fkey FOREIGN KEY (episode_id) REFERENCES public.care_episode(id);


--
-- Name: appointment appointment_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment
    ADD CONSTRAINT appointment_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.clinic_location(id);


--
-- Name: appointment appointment_service_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment
    ADD CONSTRAINT appointment_service_type_id_fkey FOREIGN KEY (service_type_id) REFERENCES public.service_type(id);


--
-- Name: appointment appointment_work_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment
    ADD CONSTRAINT appointment_work_session_id_fkey FOREIGN KEY (work_session_id) REFERENCES public.work_session(id);


--
-- Name: block_budget block_budget_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.block_budget
    ADD CONSTRAINT block_budget_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.staff(id);


--
-- Name: block_budget block_budget_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.block_budget
    ADD CONSTRAINT block_budget_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.clinic_location(id);


--
-- Name: care_episode care_episode_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.care_episode
    ADD CONSTRAINT care_episode_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE RESTRICT;


--
-- Name: care_episode care_episode_opened_appointment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.care_episode
    ADD CONSTRAINT care_episode_opened_appointment_id_fkey FOREIGN KEY (opened_appointment_id) REFERENCES public.appointment(id);


--
-- Name: care_episode care_episode_service_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.care_episode
    ADD CONSTRAINT care_episode_service_type_id_fkey FOREIGN KEY (service_type_id) REFERENCES public.service_type(id);


--
-- Name: clinical_form_response clinical_form_response_visit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_form_response
    ADD CONSTRAINT clinical_form_response_visit_id_fkey FOREIGN KEY (visit_id) REFERENCES public.visit(visit_id) ON DELETE RESTRICT;


--
-- Name: clinical_record clinical_record_pregnancy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_record
    ADD CONSTRAINT clinical_record_pregnancy_id_fkey FOREIGN KEY (pregnancy_id) REFERENCES public.pregnancy(id) ON DELETE RESTRICT;


--
-- Name: clinical_record clinical_record_visit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_record
    ADD CONSTRAINT clinical_record_visit_id_fkey FOREIGN KEY (visit_id) REFERENCES public.visit(visit_id) ON DELETE RESTRICT;


--
-- Name: cskh_action cskh_action_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cskh_action
    ADD CONSTRAINT cskh_action_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE SET NULL;


--
-- Name: cskh_log cskh_log_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cskh_log
    ADD CONSTRAINT cskh_log_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE SET NULL;


--
-- Name: event_log event_log_causation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_log
    ADD CONSTRAINT event_log_causation_id_fkey FOREIGN KEY (causation_id) REFERENCES public.event_log(event_id);


--
-- Name: lab_result lab_result_appointment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_result
    ADD CONSTRAINT lab_result_appointment_id_fkey FOREIGN KEY (appointment_id) REFERENCES public.appointment(id);


--
-- Name: lab_result lab_result_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_result
    ADD CONSTRAINT lab_result_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id);


--
-- Name: lab_result lab_result_reviewed_by_staff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_result
    ADD CONSTRAINT lab_result_reviewed_by_staff_id_fkey FOREIGN KEY (reviewed_by_staff_id) REFERENCES public.staff(id);


--
-- Name: mpi_merge_queue mpi_merge_queue_patient_id_a_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mpi_merge_queue
    ADD CONSTRAINT mpi_merge_queue_patient_id_a_fkey FOREIGN KEY (patient_id_a) REFERENCES public.patient(clinic_patient_id);


--
-- Name: mpi_merge_queue mpi_merge_queue_patient_id_b_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mpi_merge_queue
    ADD CONSTRAINT mpi_merge_queue_patient_id_b_fkey FOREIGN KEY (patient_id_b) REFERENCES public.patient(clinic_patient_id);


--
-- Name: mpi_merge_queue mpi_merge_queue_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mpi_merge_queue
    ADD CONSTRAINT mpi_merge_queue_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.staff(id);


--
-- Name: patient patient_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT patient_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.clinic_location(id);


--
-- Name: patient_medical_profile patient_medical_profile_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_medical_profile
    ADD CONSTRAINT patient_medical_profile_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id);


--
-- Name: patient patient_province_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT patient_province_code_fkey FOREIGN KEY (province_code) REFERENCES public.province(code);


--
-- Name: patient patient_ward_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT patient_ward_code_fkey FOREIGN KEY (ward_code) REFERENCES public.ward(code);


--
-- Name: payment payment_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE SET NULL;


--
-- Name: payment payment_paid_by_staff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_paid_by_staff_id_fkey FOREIGN KEY (paid_by_staff_id) REFERENCES public.staff(id) ON DELETE SET NULL;


--
-- Name: payment payment_visit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_visit_id_fkey FOREIGN KEY (visit_id) REFERENCES public.visit(visit_id) ON DELETE CASCADE;


--
-- Name: pregnancy pregnancy_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pregnancy
    ADD CONSTRAINT pregnancy_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id);


--
-- Name: pregnancy pregnancy_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pregnancy
    ADD CONSTRAINT pregnancy_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.clinic_location(id);


--
-- Name: pregnancy pregnancy_primary_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pregnancy
    ADD CONSTRAINT pregnancy_primary_doctor_id_fkey FOREIGN KEY (primary_doctor_id) REFERENCES public.staff(id);


--
-- Name: prescription prescription_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescription
    ADD CONSTRAINT prescription_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE SET NULL;


--
-- Name: prescription prescription_visit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescription
    ADD CONSTRAINT prescription_visit_id_fkey FOREIGN KEY (visit_id) REFERENCES public.visit(visit_id) ON DELETE SET NULL;


--
-- Name: service_log service_log_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_log
    ADD CONSTRAINT service_log_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE SET NULL;


--
-- Name: service_log service_log_service_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_log
    ADD CONSTRAINT service_log_service_type_id_fkey FOREIGN KEY (service_type_id) REFERENCES public.service_type(id) ON DELETE SET NULL;


--
-- Name: staff staff_auth_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff
    ADD CONSTRAINT staff_auth_user_id_fkey FOREIGN KEY (auth_user_id) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: staff_capability staff_capability_staff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_capability
    ADD CONSTRAINT staff_capability_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(id) ON DELETE CASCADE;


--
-- Name: staff staff_primary_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff
    ADD CONSTRAINT staff_primary_location_id_fkey FOREIGN KEY (primary_location_id) REFERENCES public.clinic_location(id) ON DELETE RESTRICT;


--
-- Name: staff_task staff_task_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_task
    ADD CONSTRAINT staff_task_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.staff(id) ON DELETE SET NULL;


--
-- Name: staff_task staff_task_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_task
    ADD CONSTRAINT staff_task_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.clinic_location(id) ON DELETE RESTRICT;


--
-- Name: ultrasound_record ultrasound_record_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ultrasound_record
    ADD CONSTRAINT ultrasound_record_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE RESTRICT;


--
-- Name: ultrasound_record ultrasound_record_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ultrasound_record
    ADD CONSTRAINT ultrasound_record_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.staff(id) ON DELETE RESTRICT;


--
-- Name: ultrasound_record ultrasound_record_pregnancy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ultrasound_record
    ADD CONSTRAINT ultrasound_record_pregnancy_id_fkey FOREIGN KEY (pregnancy_id) REFERENCES public.pregnancy(id) ON DELETE RESTRICT;


--
-- Name: ultrasound_record ultrasound_record_visit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ultrasound_record
    ADD CONSTRAINT ultrasound_record_visit_id_fkey FOREIGN KEY (visit_id) REFERENCES public.visit(visit_id) ON DELETE RESTRICT;


--
-- Name: visit visit_appointment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_appointment_id_fkey FOREIGN KEY (appointment_id) REFERENCES public.appointment(id) ON DELETE RESTRICT;


--
-- Name: visit visit_attending_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_attending_doctor_id_fkey FOREIGN KEY (attending_doctor_id) REFERENCES public.staff(id) ON DELETE RESTRICT;


--
-- Name: visit visit_checked_in_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_checked_in_by_fkey FOREIGN KEY (checked_in_by) REFERENCES public.staff(id) ON DELETE RESTRICT;


--
-- Name: visit visit_clinic_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_clinic_patient_id_fkey FOREIGN KEY (clinic_patient_id) REFERENCES public.patient(clinic_patient_id) ON DELETE RESTRICT;


--
-- Name: visit visit_finalized_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_finalized_by_fkey FOREIGN KEY (finalized_by) REFERENCES public.staff(id) ON DELETE RESTRICT;


--
-- Name: visit visit_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.clinic_location(id) ON DELETE RESTRICT;


--
-- Name: visit visit_service_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_service_type_id_fkey FOREIGN KEY (service_type_id) REFERENCES public.service_type(id) ON DELETE RESTRICT;


--
-- Name: visit visit_work_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit
    ADD CONSTRAINT visit_work_session_id_fkey FOREIGN KEY (work_session_id) REFERENCES public.work_session(id) ON DELETE RESTRICT;


--
-- Name: ward ward_province_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ward
    ADD CONSTRAINT ward_province_code_fkey FOREIGN KEY (province_code) REFERENCES public.province(code);


--
-- Name: work_roster work_roster_staff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_roster
    ADD CONSTRAINT work_roster_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(id) ON DELETE SET NULL;


--
-- Name: work_session work_session_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_session
    ADD CONSTRAINT work_session_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.clinic_location(id);


--
-- Name: work_session_staff work_session_staff_staff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_session_staff
    ADD CONSTRAINT work_session_staff_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(id) ON DELETE RESTRICT;


--
-- Name: work_session_staff work_session_staff_work_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_session_staff
    ADD CONSTRAINT work_session_staff_work_session_id_fkey FOREIGN KEY (work_session_id) REFERENCES public.work_session(id) ON DELETE CASCADE;


--
-- Name: appointment; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.appointment ENABLE ROW LEVEL SECURITY;

--
-- Name: appointment appointment_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY appointment_select_authenticated ON public.appointment FOR SELECT TO authenticated USING (true);


--
-- Name: block_budget; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.block_budget ENABLE ROW LEVEL SECURITY;

--
-- Name: booking_channel; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.booking_channel ENABLE ROW LEVEL SECURITY;

--
-- Name: care_episode; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.care_episode ENABLE ROW LEVEL SECURITY;

--
-- Name: clinic_location; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clinic_location ENABLE ROW LEVEL SECURITY;

--
-- Name: clinic_location clinic_location_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY clinic_location_select_authenticated ON public.clinic_location FOR SELECT TO authenticated USING (true);


--
-- Name: clinical_form_response; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clinical_form_response ENABLE ROW LEVEL SECURITY;

--
-- Name: clinical_form_response clinical_form_response_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY clinical_form_response_select_authenticated ON public.clinical_form_response FOR SELECT TO authenticated USING (true);


--
-- Name: clinical_record; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clinical_record ENABLE ROW LEVEL SECURITY;

--
-- Name: clinical_record clinical_record_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY clinical_record_select_authenticated ON public.clinical_record FOR SELECT TO authenticated USING (true);


--
-- Name: cskh_action; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cskh_action ENABLE ROW LEVEL SECURITY;

--
-- Name: cskh_action cskh_action_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY cskh_action_select_authenticated ON public.cskh_action FOR SELECT TO authenticated USING (true);


--
-- Name: cskh_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cskh_log ENABLE ROW LEVEL SECURITY;

--
-- Name: cskh_log cskh_log_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY cskh_log_select_authenticated ON public.cskh_log FOR SELECT TO authenticated USING (true);


--
-- Name: drug_catalog; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.drug_catalog ENABLE ROW LEVEL SECURITY;

--
-- Name: drug_catalog drug_catalog_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY drug_catalog_select_authenticated ON public.drug_catalog FOR SELECT TO authenticated USING (true);


--
-- Name: event_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.event_log ENABLE ROW LEVEL SECURITY;

--
-- Name: event_log event_log_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY event_log_select_authenticated ON public.event_log FOR SELECT TO authenticated USING (true);


--
-- Name: lab_result; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.lab_result ENABLE ROW LEVEL SECURITY;

--
-- Name: lab_result lab_result_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY lab_result_select_authenticated ON public.lab_result FOR SELECT TO authenticated USING (true);


--
-- Name: mpi_merge_queue; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.mpi_merge_queue ENABLE ROW LEVEL SECURITY;

--
-- Name: patient; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.patient ENABLE ROW LEVEL SECURITY;

--
-- Name: patient_medical_profile; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.patient_medical_profile ENABLE ROW LEVEL SECURITY;

--
-- Name: patient_medical_profile patient_medical_profile_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY patient_medical_profile_select_authenticated ON public.patient_medical_profile FOR SELECT TO authenticated USING (true);


--
-- Name: patient patient_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY patient_select_authenticated ON public.patient FOR SELECT TO authenticated USING (true);


--
-- Name: payment; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.payment ENABLE ROW LEVEL SECURITY;

--
-- Name: payment payment_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY payment_select_authenticated ON public.payment FOR SELECT TO authenticated USING (true);


--
-- Name: pregnancy; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.pregnancy ENABLE ROW LEVEL SECURITY;

--
-- Name: pregnancy pregnancy_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY pregnancy_select_authenticated ON public.pregnancy FOR SELECT TO authenticated USING (true);


--
-- Name: prescription; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.prescription ENABLE ROW LEVEL SECURITY;

--
-- Name: prescription prescription_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY prescription_select_authenticated ON public.prescription FOR SELECT TO authenticated USING (true);


--
-- Name: province; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.province ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: service_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.service_log ENABLE ROW LEVEL SECURITY;

--
-- Name: service_log service_log_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_log_select_authenticated ON public.service_log FOR SELECT TO authenticated USING (true);


--
-- Name: service_price; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.service_price ENABLE ROW LEVEL SECURITY;

--
-- Name: service_price service_price_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_price_select_authenticated ON public.service_price FOR SELECT TO authenticated USING (true);


--
-- Name: service_type; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.service_type ENABLE ROW LEVEL SECURITY;

--
-- Name: service_type service_type_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_type_select_authenticated ON public.service_type FOR SELECT TO authenticated USING (true);


--
-- Name: staff; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.staff ENABLE ROW LEVEL SECURITY;

--
-- Name: staff_capability; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.staff_capability ENABLE ROW LEVEL SECURITY;

--
-- Name: staff staff_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY staff_select_authenticated ON public.staff FOR SELECT TO authenticated USING (true);


--
-- Name: staff_task; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.staff_task ENABLE ROW LEVEL SECURITY;

--
-- Name: staff_task staff_task_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY staff_task_select_authenticated ON public.staff_task FOR SELECT TO authenticated USING (true);


--
-- Name: ultrasound_record; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ultrasound_record ENABLE ROW LEVEL SECURITY;

--
-- Name: visit; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.visit ENABLE ROW LEVEL SECURITY;

--
-- Name: visit visit_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY visit_select_authenticated ON public.visit FOR SELECT TO authenticated USING (true);


--
-- Name: ward; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ward ENABLE ROW LEVEL SECURITY;

--
-- Name: work_roster; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_roster ENABLE ROW LEVEL SECURITY;

--
-- Name: work_roster work_roster_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY work_roster_select_authenticated ON public.work_roster FOR SELECT TO authenticated USING (true);


--
-- Name: work_session; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_session ENABLE ROW LEVEL SECURITY;

--
-- Name: work_session work_session_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY work_session_select_authenticated ON public.work_session FOR SELECT TO authenticated USING (true);


--
-- Name: work_session_staff; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_session_staff ENABLE ROW LEVEL SECURITY;

--
-- Name: work_session_staff work_session_staff_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY work_session_staff_select_authenticated ON public.work_session_staff FOR SELECT TO authenticated USING (true);


--
-- PostgreSQL database dump complete
--

\unrestrict IX6t3anCaHfavJhpZgvih68WbDVsiRdflltnRkff4qOaK5nAK33WnuqtFLin8cB

