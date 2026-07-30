


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "langgraph";


ALTER SCHEMA "langgraph" OWNER TO "postgres";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "btree_gist" WITH SCHEMA "public";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pg_trgm" WITH SCHEMA "public";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "unaccent" WITH SCHEMA "public";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."doctor_patient_count"("p_doctor_id" "uuid") RETURNS bigint
    LANGUAGE "sql" STABLE
    AS $$
  SELECT count(DISTINCT a.clinic_patient_id)
  FROM appointment a
  WHERE a.doctor_id = p_doctor_id;
$$;


ALTER FUNCTION "public"."doctor_patient_count"("p_doctor_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."doctor_patient_list"("p_doctor_id" "uuid", "p_term" "text" DEFAULT ''::"text", "p_limit" integer DEFAULT 50, "p_offset" integer DEFAULT 0) RETURNS TABLE("clinic_patient_id" "uuid", "patient_code" "text", "full_name" "text", "date_of_birth" "date", "phone_primary" "text", "created_at" timestamp with time zone, "total_count" bigint)
    LANGUAGE "sql" STABLE
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


ALTER FUNCTION "public"."doctor_patient_list"("p_doctor_id" "uuid", "p_term" "text", "p_limit" integer, "p_offset" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."enforce_append_only"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."enforce_append_only"() OWNER TO "postgres";


COMMENT ON FUNCTION "public"."enforce_append_only"() IS 'Enforce append-only invariant on event_log. Used by 3 triggers.
Raises insufficient_privilege error on UPDATE/DELETE/TRUNCATE.';



CREATE OR REPLACE FUNCTION "public"."f_unaccent"("text") RETURNS "text"
    LANGUAGE "sql" IMMUTABLE STRICT PARALLEL SAFE
    AS $_$ SELECT unaccent('unaccent', $1) $_$;


ALTER FUNCTION "public"."f_unaccent"("text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."prevent_hard_delete"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."prevent_hard_delete"() OWNER TO "postgres";


COMMENT ON FUNCTION "public"."prevent_hard_delete"() IS 'Append-only guard for operational tables (patient, appointment): blocks
physical DELETE/TRUNCATE while leaving UPDATE free for lifecycle state changes.
Controlled ETL/seed sets `SET LOCAL app.allow_hard_delete = ''on''` to opt out.';



CREATE OR REPLACE FUNCTION "public"."rls_auto_enable"() RETURNS "event_trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'pg_catalog'
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


ALTER FUNCTION "public"."rls_auto_enable"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."set_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."visit_amendment_append_only"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RAISE EXCEPTION
        'visit_amendment is append-only; UPDATE/DELETE not permitted (TT13/2011/TT-BYT)'
        USING ERRCODE = 'check_violation';
END;
$$;


ALTER FUNCTION "public"."visit_amendment_append_only"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."visit_finalized_block_update"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."visit_finalized_block_update"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "langgraph"."checkpoint_blobs" (
    "thread_id" "text" NOT NULL,
    "checkpoint_ns" "text" DEFAULT ''::"text" NOT NULL,
    "channel" "text" NOT NULL,
    "version" "text" NOT NULL,
    "type" "text" NOT NULL,
    "blob" "bytea"
);


ALTER TABLE "langgraph"."checkpoint_blobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "langgraph"."checkpoint_migrations" (
    "v" integer NOT NULL
);


ALTER TABLE "langgraph"."checkpoint_migrations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "langgraph"."checkpoint_writes" (
    "thread_id" "text" NOT NULL,
    "checkpoint_ns" "text" DEFAULT ''::"text" NOT NULL,
    "checkpoint_id" "text" NOT NULL,
    "task_id" "text" NOT NULL,
    "idx" integer NOT NULL,
    "channel" "text" NOT NULL,
    "type" "text",
    "blob" "bytea" NOT NULL,
    "task_path" "text" DEFAULT ''::"text" NOT NULL
);


ALTER TABLE "langgraph"."checkpoint_writes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "langgraph"."checkpoints" (
    "thread_id" "text" NOT NULL,
    "checkpoint_ns" "text" DEFAULT ''::"text" NOT NULL,
    "checkpoint_id" "text" NOT NULL,
    "parent_checkpoint_id" "text",
    "type" "text",
    "checkpoint" "jsonb" NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL
);


ALTER TABLE "langgraph"."checkpoints" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."appointment" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "doctor_id" "uuid",
    "work_session_id" "uuid",
    "location_id" "uuid" NOT NULL,
    "service_type_id" "uuid" NOT NULL,
    "booking_channel" "text",
    "slot_start" timestamp with time zone NOT NULL,
    "slot_end" timestamp with time zone NOT NULL,
    "assigned_station" "text",
    "queue_number" "text",
    "is_priority_slot" boolean DEFAULT false NOT NULL,
    "is_walkin" boolean DEFAULT false NOT NULL,
    "status" "text" DEFAULT 'SCHEDULED'::"text" NOT NULL,
    "confirmed_at" timestamp with time zone,
    "cancelled_at" timestamp with time zone,
    "cancellation_reason" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "patient_kind" "text",
    "thanh_min" integer,
    "sono_min" integer,
    "need_sono" boolean,
    "episode_id" "uuid",
    CONSTRAINT "appointment_check" CHECK (("slot_end" > "slot_start")),
    CONSTRAINT "appointment_patient_kind_check" CHECK (("patient_kind" = ANY (ARRAY['NEW'::"text", 'RETURN'::"text"]))),
    CONSTRAINT "appointment_sono_min_check" CHECK ((("sono_min" >= 0) AND ("sono_min" <= 60))),
    CONSTRAINT "appointment_status_check" CHECK (("status" = ANY (ARRAY['SCHEDULED'::"text", 'CSKH_CONFIRMED'::"text", 'CONFIRMED'::"text", 'CHECKED_IN'::"text", 'COMPLETED'::"text", 'NO_SHOW'::"text", 'CANCELLED'::"text", 'DOCTOR_DECLINED'::"text"]))),
    CONSTRAINT "appointment_thanh_min_check" CHECK ((("thanh_min" >= 0) AND ("thanh_min" <= 60)))
);

ALTER TABLE ONLY "public"."appointment" REPLICA IDENTITY FULL;


ALTER TABLE "public"."appointment" OWNER TO "postgres";


COMMENT ON TABLE "public"."appointment" IS 'Patient appointments for services scheduled with doctors or work sessions';



CREATE TABLE IF NOT EXISTS "public"."block_budget" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "location_id" "uuid" NOT NULL,
    "doctor_id" "uuid",
    "weekday" integer,
    "hour_start" integer NOT NULL,
    "thanh_budget_min" integer DEFAULT 50 NOT NULL,
    "sono_budget_min" integer DEFAULT 90 NOT NULL,
    "online_quota_min" integer DEFAULT 35 NOT NULL,
    "walkin_quota_min" integer DEFAULT 10 NOT NULL,
    "buffer_min" integer DEFAULT 5 NOT NULL,
    "new_cap" integer DEFAULT 3 NOT NULL,
    "max_total" integer DEFAULT 12 NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "block_budget_hour_start_check" CHECK ((("hour_start" >= 0) AND ("hour_start" <= 23))),
    CONSTRAINT "block_budget_weekday_check" CHECK ((("weekday" >= 0) AND ("weekday" <= 6)))
);


ALTER TABLE "public"."block_budget" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."booking_channel" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "code" "text" NOT NULL,
    "name" "text" NOT NULL,
    "category" "text" NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "booking_channel_category_check" CHECK (("category" = ANY (ARRAY['ZALO'::"text", 'FACEBOOK'::"text", 'HOTLINE'::"text", 'WALK_IN'::"text", 'REFERRAL'::"text", 'OTHER'::"text"])))
);


ALTER TABLE "public"."booking_channel" OWNER TO "postgres";


COMMENT ON TABLE "public"."booking_channel" IS 'Phase 1 master — kênh BN biết đến/đặt lịch với PK (Zalo, FB, Hotline, Walk-in, Referral).';



COMMENT ON COLUMN "public"."booking_channel"."id" IS 'PK kỹ thuật (channel_id trong Onboard doc).';



COMMENT ON COLUMN "public"."booking_channel"."code" IS 'Mã ngắn cố định (ZALO_PK, FB_DR4WOMEN, HOTLINE, WALK_IN, ...).';



COMMENT ON COLUMN "public"."booking_channel"."name" IS 'Tên hiển thị (CSKH thấy khi chọn kênh lúc đặt lịch).';



COMMENT ON COLUMN "public"."booking_channel"."category" IS 'Nhóm kênh (ZALO/FACEBOOK/HOTLINE/WALK_IN/REFERRAL/OTHER) — dùng cho report ROI marketing.';



CREATE TABLE IF NOT EXISTS "public"."care_episode" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "service_type_id" "uuid" NOT NULL,
    "status" "text" DEFAULT 'OPEN'::"text" NOT NULL,
    "opened_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "opened_appointment_id" "uuid",
    "last_visit_at" timestamp with time zone,
    "closed_at" timestamp with time zone,
    "close_reason" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "care_episode_close_reason_check" CHECK (("close_reason" = ANY (ARRAY['doctor_no_followup'::"text", 'cskh_confirmed'::"text", 'manual'::"text", 'new_problem'::"text", 'auto_inactive'::"text"]))),
    CONSTRAINT "care_episode_status_check" CHECK (("status" = ANY (ARRAY['OPEN'::"text", 'PENDING_CLOSE'::"text", 'CLOSED'::"text"])))
);


ALTER TABLE "public"."care_episode" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clinic_location" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "code" "text" NOT NULL,
    "name" "text" NOT NULL,
    "address" "text",
    "is_active" boolean DEFAULT true,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."clinic_location" OWNER TO "postgres";


COMMENT ON TABLE "public"."clinic_location" IS 'Physical locations/branches of the clinic (e.g., Kim Nguu, Hao Nam)';



COMMENT ON COLUMN "public"."clinic_location"."id" IS 'Primary key of the clinic location';



COMMENT ON COLUMN "public"."clinic_location"."code" IS 'Unique code identifier for the clinic location (e.g., KN, HN)';



COMMENT ON COLUMN "public"."clinic_location"."name" IS 'Display name of the location';



COMMENT ON COLUMN "public"."clinic_location"."address" IS 'Physical address of the location';



COMMENT ON COLUMN "public"."clinic_location"."is_active" IS 'Flag indicating whether this location is active';



COMMENT ON COLUMN "public"."clinic_location"."created_at" IS 'Timestamp when the record was created';



CREATE TABLE IF NOT EXISTS "public"."clinical_form_response" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "visit_id" "uuid" NOT NULL,
    "service_code" "text" NOT NULL,
    "form_data" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_by" "text",
    "updated_by" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE ONLY "public"."clinical_form_response" REPLICA IDENTITY FULL;


ALTER TABLE "public"."clinical_form_response" OWNER TO "postgres";


COMMENT ON TABLE "public"."clinical_form_response" IS 'Phản hồi form khám chuyên khoa config-driven theo service_code (engine T-EMR-FORM-ENGINE-01). 1 phiếu / (visit, service_code).';



COMMENT ON COLUMN "public"."clinical_form_response"."form_data" IS 'Toàn bộ giá trị form dạng JSONB { field_key: value }. Schema render do config quyết định.';



CREATE TABLE IF NOT EXISTS "public"."clinical_record" (
    "record_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "visit_id" "uuid" NOT NULL,
    "pregnancy_id" "uuid",
    "soap_subjective" "jsonb",
    "soap_objective" "jsonb",
    "soap_assessment" "jsonb",
    "soap_plan" "jsonb",
    "chief_complaint_at_visit" "text",
    "voice_note_url" "text",
    "voice_transcript" "text",
    "voice_note_reviewed" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE ONLY "public"."clinical_record" REPLICA IDENTITY FULL;


ALTER TABLE "public"."clinical_record" OWNER TO "postgres";


COMMENT ON TABLE "public"."clinical_record" IS 'SOAP clinical record, 1:1 with visit. Spec: final_canon/05 §6.';



COMMENT ON COLUMN "public"."clinical_record"."voice_note_url" IS 'LOCAL storage path only — voice notes MUST NOT be uploaded to cloud.';



CREATE TABLE IF NOT EXISTS "public"."cskh_action" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "source_ref" "text" NOT NULL,
    "clinic_patient_id" "uuid",
    "category" "text",
    "step" "text",
    "status" "text",
    "action_data" "text",
    "description" "text",
    "result_text" "text",
    "deadline_at" timestamp with time zone,
    "source_created_at" timestamp with time zone,
    "source_updated_at" timestamp with time zone,
    "created_by_text" "text",
    "last_edited_by_text" "text",
    "rating" integer,
    "billing_tag" "text",
    "appointment_link_raw" "text",
    "visit_link_raw" "text",
    "lab_link_raw" "text",
    "patient_link_raw" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE ONLY "public"."cskh_action" REPLICA IDENTITY FULL;


ALTER TABLE "public"."cskh_action" OWNER TO "postgres";


COMMENT ON TABLE "public"."cskh_action" IS 'CSKH activity log nhập từ Notion "CSKH - Action" (~31k dòng). 1 dòng = 1 lần CSKH thao tác (đặt lịch, nhắc, tư vấn, ...).';



COMMENT ON COLUMN "public"."cskh_action"."source_ref" IS 'Notion //ID, format ACT-<n>. UNIQUE để re-sync idempotent.';



COMMENT ON COLUMN "public"."cskh_action"."category" IS 'Notion "Phân loại": Đặt hẹn / Tư vấn / Nhắc tái khám / ...';



COMMENT ON COLUMN "public"."cskh_action"."step" IS 'Notion "Step": #request / #report.';



COMMENT ON COLUMN "public"."cskh_action"."status" IS 'Notion "Tình trạng": "Kết thúc / Đã xác nhận lịch hẹn / Đã nhắc" — raw multi-token text.';



COMMENT ON COLUMN "public"."cskh_action"."action_data" IS 'Notion "Dữ liệu thao tác" — nội dung CSKH gõ.';



COMMENT ON COLUMN "public"."cskh_action"."rating" IS 'Notion "Điểm đánh giá" (-2 → +2).';



COMMENT ON COLUMN "public"."cskh_action"."appointment_link_raw" IS 'Notion "//file lịch hẹn" — text "Name SDT (URL)"; resolve sang FK appointment.id ở Phase 2.';



CREATE TABLE IF NOT EXISTS "public"."cskh_log" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid",
    "work_date" "date",
    "slot_time" "text",
    "visit_number" "text",
    "patient_info" "text",
    "phone" "text",
    "visit_type" "text",
    "confirmed" boolean,
    "confirmed_by" "text",
    "arrived" boolean,
    "has_test" boolean,
    "tests" "text",
    "result_eta" "text",
    "result_group" "text",
    "cskh_status" "text",
    "cskh_followup" "text",
    "last_cskh_date" "date",
    "cskh_by" "text",
    "note" "text",
    "source_month" "text",
    "created_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE ONLY "public"."cskh_log" REPLICA IDENTITY FULL;


ALTER TABLE "public"."cskh_log" OWNER TO "postgres";


COMMENT ON TABLE "public"."cskh_log" IS 'Nhật ký CSKH theo lượt khám, gắn theo bệnh nhân (khớp SĐT)';



CREATE TABLE IF NOT EXISTS "public"."drug_catalog" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name_base" "text" NOT NULL,
    "name_raw" "text" NOT NULL,
    "variant" "text",
    "group_label" "text",
    "unit_price" numeric(12,0),
    "needs_review" boolean DEFAULT false NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."drug_catalog" OWNER TO "postgres";


COMMENT ON TABLE "public"."drug_catalog" IS 'Danh mục thuốc (menu BS kê đơn). Nguồn: PHIẾU CHỈ ĐỊNH PK. Giá lazy-fill.';



COMMENT ON COLUMN "public"."drug_catalog"."name_raw" IS 'Tên thuốc VERBATIM từ phiếu (gồm cả biến thể trong ngoặc).';



COMMENT ON COLUMN "public"."drug_catalog"."needs_review" IS 'TRUE: định danh/biến thể chưa chắc, dược xác nhận trước khi dùng thật.';



CREATE TABLE IF NOT EXISTS "public"."event_log" (
    "event_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "event_type" "text" NOT NULL,
    "event_version" integer DEFAULT 1 NOT NULL,
    "aggregate_type" "text" NOT NULL,
    "aggregate_id" "uuid" NOT NULL,
    "payload" "jsonb" NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "correlation_id" "uuid",
    "causation_id" "uuid",
    "source" "text" NOT NULL,
    "occurred_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "recorded_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "event_published" boolean DEFAULT false NOT NULL,
    CONSTRAINT "event_type_format" CHECK (("event_type" ~ '^[a-z_]+\.[a-z_]+$'::"text")),
    CONSTRAINT "event_version_positive" CHECK (("event_version" > 0)),
    CONSTRAINT "source_not_empty" CHECK (("length"("source") > 0))
);


ALTER TABLE "public"."event_log" OWNER TO "postgres";


COMMENT ON TABLE "public"."event_log" IS 'Append-only event sourcing log. Single source of truth for all state changes.
NEVER UPDATE. NEVER DELETE. NEVER TRUNCATE. Enforced by trigger enforce_append_only().';



COMMENT ON COLUMN "public"."event_log"."event_published" IS 'Outbox flag: FALSE=pending publish, TRUE=published to MQ';



CREATE TABLE IF NOT EXISTS "public"."lab_result" (
    "lab_result_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "visit_id" "uuid",
    "appointment_id" "uuid",
    "test_code" "text" NOT NULL,
    "test_name" "text" NOT NULL,
    "panel_code" "text",
    "result_value" "text",
    "result_numeric" numeric,
    "result_unit" "text",
    "reference_range_low" numeric,
    "reference_range_high" numeric,
    "flag" "text",
    "triage_group" "text" DEFAULT 'PENDING'::"text" NOT NULL,
    "triage_reason" "text",
    "triage_classified_at" timestamp with time zone,
    "triage_model" "text",
    "requires_doctor_review" boolean DEFAULT false NOT NULL,
    "reviewed_by_staff_id" "uuid",
    "reviewed_at" timestamp with time zone,
    "is_finalized" boolean DEFAULT false NOT NULL,
    "lab_provider" "text",
    "external_ref" "text",
    "raw_payload" "jsonb",
    "sample_collected_at" timestamp with time zone,
    "result_received_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "lab_result_finalized_requires_reviewer" CHECK ((("is_finalized" = false) OR (("is_finalized" = true) AND ("reviewed_by_staff_id" IS NOT NULL) AND ("reviewed_at" IS NOT NULL)))),
    CONSTRAINT "lab_result_flag_check" CHECK (("flag" = ANY (ARRAY['NORMAL'::"text", 'HIGH'::"text", 'LOW'::"text", 'CRITICAL_HIGH'::"text", 'CRITICAL_LOW'::"text", 'ABNORMAL'::"text"]))),
    CONSTRAINT "lab_result_triage_group_check" CHECK (("triage_group" = ANY (ARRAY['GROUP_A'::"text", 'GROUP_B'::"text", 'GROUP_C'::"text", 'PENDING'::"text"])))
);

ALTER TABLE ONLY "public"."lab_result" REPLICA IDENTITY FULL;


ALTER TABLE "public"."lab_result" OWNER TO "postgres";


COMMENT ON TABLE "public"."lab_result" IS 'Lab results with triage classification. Spec: docs/lab_triage_spec_v1.md. Phase 9.2.';



COMMENT ON COLUMN "public"."lab_result"."triage_group" IS 'GROUP_A=normal, GROUP_B=borderline BS review, GROUP_C=critical HARD BLOCK';



COMMENT ON COLUMN "public"."lab_result"."requires_doctor_review" IS 'HARD BLOCK gate: TRUE blocks BN-facing AI until is_finalized=TRUE';



CREATE TABLE IF NOT EXISTS "public"."mpi_merge_queue" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "patient_id_a" "uuid" NOT NULL,
    "patient_id_b" "uuid" NOT NULL,
    "score" numeric(5,2) NOT NULL,
    "status" "text" DEFAULT 'PENDING'::"text",
    "reviewed_by" "uuid",
    "reviewed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "chk_different_patients" CHECK (("patient_id_a" <> "patient_id_b")),
    CONSTRAINT "mpi_merge_queue_status_check" CHECK (("status" = ANY (ARRAY['PENDING'::"text", 'MERGED'::"text", 'REJECTED'::"text", 'REVIEW'::"text"])))
);


ALTER TABLE "public"."mpi_merge_queue" OWNER TO "postgres";


COMMENT ON TABLE "public"."mpi_merge_queue" IS 'Duplicate patient review queue managed by the Master Patient Index resolution system';



COMMENT ON COLUMN "public"."mpi_merge_queue"."id" IS 'Primary key identifier for the merge review request';



COMMENT ON COLUMN "public"."mpi_merge_queue"."patient_id_a" IS 'Foreign key referencing the first candidate patient';



COMMENT ON COLUMN "public"."mpi_merge_queue"."patient_id_b" IS 'Foreign key referencing the second candidate patient';



COMMENT ON COLUMN "public"."mpi_merge_queue"."score" IS 'Resolution match score ranging from 0.00 to 100.00';



COMMENT ON COLUMN "public"."mpi_merge_queue"."status" IS 'Resolution review status (PENDING, MERGED, REJECTED, REVIEW)';



COMMENT ON COLUMN "public"."mpi_merge_queue"."reviewed_by" IS 'Staff member who finalized the match decision';



COMMENT ON COLUMN "public"."mpi_merge_queue"."reviewed_at" IS 'Timestamp of the review decision';



COMMENT ON COLUMN "public"."mpi_merge_queue"."created_at" IS 'Timestamp of queue entry creation';



CREATE TABLE IF NOT EXISTS "public"."patient" (
    "clinic_patient_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "patient_code" "text" NOT NULL,
    "national_id_number" "text",
    "full_name" "text" NOT NULL,
    "date_of_birth" "date",
    "phone_primary" "text",
    "phone_secondary" "text",
    "location_id" "uuid" NOT NULL,
    "is_active" boolean DEFAULT true,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "gender" "text",
    "ethnicity" "text",
    "nationality" "text",
    "occupation" "text",
    "patient_objection" "text",
    "address" "text",
    "guardian_name" "text",
    "full_name_unaccent" "text" GENERATED ALWAYS AS ("lower"("replace"("replace"("public"."f_unaccent"("full_name"), 'đ'::"text", 'd'::"text"), 'Đ'::"text", 'D'::"text"))) STORED,
    "birth_year" smallint,
    "province_code" "text",
    "province_name" "text",
    "ward_code" "text",
    "ward_name" "text",
    "address_detail" "text",
    "van_de_di_kham" "text",
    "linh_vuc" "text",
    CONSTRAINT "patient_birth_year_check" CHECK ((("birth_year" IS NULL) OR (("birth_year" >= 1900) AND ("birth_year" <= 2100)))),
    CONSTRAINT "patient_gender_check" CHECK ((("gender" IS NULL) OR ("gender" = ANY (ARRAY['Nam'::"text", 'Nữ'::"text", 'Khác'::"text"])))),
    CONSTRAINT "patient_linh_vuc_check" CHECK ((("linh_vuc" IS NULL) OR ("linh_vuc" = ANY (ARRAY['PK'::"text", 'SK'::"text", 'NT'::"text", 'HMVS'::"text", 'NK'::"text"]))))
);

ALTER TABLE ONLY "public"."patient" REPLICA IDENTITY FULL;


ALTER TABLE "public"."patient" OWNER TO "postgres";


COMMENT ON TABLE "public"."patient" IS 'Core patient registration and demographic identity table';



COMMENT ON COLUMN "public"."patient"."clinic_patient_id" IS 'Immutable primary key identifier';



COMMENT ON COLUMN "public"."patient"."patient_code" IS 'Human-readable UX-facing patient identifier (Format: BN-YYYY-XXXXXX)';



COMMENT ON COLUMN "public"."patient"."national_id_number" IS 'Vietnam citizen ID (CCCD), nullable. Note: Phase 13 crypto-erase — hiện plaintext MVP';



COMMENT ON COLUMN "public"."patient"."full_name" IS 'Full legal name of the patient';



COMMENT ON COLUMN "public"."patient"."date_of_birth" IS 'Date of birth';



COMMENT ON COLUMN "public"."patient"."phone_primary" IS 'Primary phone number (E.164 format)';



COMMENT ON COLUMN "public"."patient"."phone_secondary" IS 'Secondary/Alternative contact phone number';



COMMENT ON COLUMN "public"."patient"."location_id" IS 'Home clinic location foreign key reference';



COMMENT ON COLUMN "public"."patient"."is_active" IS 'Active status flag';



COMMENT ON COLUMN "public"."patient"."created_at" IS 'Record creation timestamp';



COMMENT ON COLUMN "public"."patient"."updated_at" IS 'Record modification timestamp';



COMMENT ON COLUMN "public"."patient"."gender" IS 'Giới tính: Nam/Nữ/Khác (mục I.3 form khám)';



COMMENT ON COLUMN "public"."patient"."ethnicity" IS 'Dân tộc (mục I.4)';



COMMENT ON COLUMN "public"."patient"."nationality" IS 'Quốc tịch (mục I.5)';



COMMENT ON COLUMN "public"."patient"."occupation" IS 'Nghề nghiệp (mục I.6)';



COMMENT ON COLUMN "public"."patient"."patient_objection" IS 'Đối tượng: DV/BHYT/... (mục I.7)';



COMMENT ON COLUMN "public"."patient"."address" IS 'Địa chỉ (mục I.8)';



COMMENT ON COLUMN "public"."patient"."guardian_name" IS 'Họ tên người bảo lãnh (mục I.9)';



COMMENT ON COLUMN "public"."patient"."birth_year" IS 'Năm sinh khi BN không nhớ ngày/tháng (feedback B5#4). date_of_birth NULL khi chỉ có năm.';



CREATE TABLE IF NOT EXISTS "public"."patient_contact_channel" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "channel_type" "text" NOT NULL,
    "channel_value" "text" NOT NULL,
    "is_verified" boolean DEFAULT false NOT NULL,
    "is_primary" boolean DEFAULT false NOT NULL,
    "verified_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "patient_contact_channel_channel_type_check" CHECK (("channel_type" = ANY (ARRAY['ZALO'::"text", 'PHONE'::"text", 'FACEBOOK'::"text", 'EMAIL'::"text", 'OTHER'::"text"])))
);


ALTER TABLE "public"."patient_contact_channel" OWNER TO "postgres";


COMMENT ON TABLE "public"."patient_contact_channel" IS 'Phase 1 — kênh liên lạc của 1 BN (Zalo uid / số điện thoại / FB psid / email). 1 BN có thể có nhiều dòng. Phase 3 dùng để route thông báo Zalo trước, fallback Phone.';



COMMENT ON COLUMN "public"."patient_contact_channel"."channel_type" IS 'ZALO / PHONE / FACEBOOK / EMAIL / OTHER.';



COMMENT ON COLUMN "public"."patient_contact_channel"."channel_value" IS 'Zalo: zalo_user_id. Phone: số E.164 chuẩn. FB: PSID. Email: địa chỉ.';



COMMENT ON COLUMN "public"."patient_contact_channel"."is_verified" IS 'Zalo/FB: đã nhắn ít nhất 1 lần. Phone: đã gọi xác nhận.';



COMMENT ON COLUMN "public"."patient_contact_channel"."is_primary" IS 'Kênh ưu tiên gửi thông báo — partial UNIQUE enforce 1 primary per BN.';



CREATE TABLE IF NOT EXISTS "public"."patient_medical_profile" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "blood_type" "text",
    "allergies" "text"[] DEFAULT '{}'::"text"[],
    "chronic_diseases" "text"[] DEFAULT '{}'::"text"[],
    "current_medications" "text"[] DEFAULT '{}'::"text"[],
    "surgical_history" "text"[] DEFAULT '{}'::"text"[],
    "family_history" "jsonb" DEFAULT '{}'::"jsonb",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "patient_medical_profile_blood_type_check" CHECK (("blood_type" = ANY (ARRAY['A'::"text", 'B'::"text", 'AB'::"text", 'O'::"text", 'A+'::"text", 'A-'::"text", 'B+'::"text", 'B-'::"text", 'AB+'::"text", 'AB-'::"text", 'O+'::"text", 'O-'::"text"])))
);

ALTER TABLE ONLY "public"."patient_medical_profile" REPLICA IDENTITY FULL;


ALTER TABLE "public"."patient_medical_profile" OWNER TO "postgres";


COMMENT ON TABLE "public"."patient_medical_profile" IS '1:1 medical profile per patient. General medical information.';



COMMENT ON COLUMN "public"."patient_medical_profile"."id" IS 'Primary key identifier';



COMMENT ON COLUMN "public"."patient_medical_profile"."clinic_patient_id" IS 'Unique FK to patient — enforces 1:1 relationship';



COMMENT ON COLUMN "public"."patient_medical_profile"."blood_type" IS 'ABO/Rh blood type classification';



COMMENT ON COLUMN "public"."patient_medical_profile"."allergies" IS 'Known allergies list. Phase 13 crypto-erase cho allergies/medications nếu cần';



COMMENT ON COLUMN "public"."patient_medical_profile"."chronic_diseases" IS 'Chronic disease history';



COMMENT ON COLUMN "public"."patient_medical_profile"."current_medications" IS 'Active medications list. Phase 13 crypto-erase cho allergies/medications nếu cần';



COMMENT ON COLUMN "public"."patient_medical_profile"."surgical_history" IS 'Past surgical procedures';



COMMENT ON COLUMN "public"."patient_medical_profile"."family_history" IS 'Family medical history as structured JSON';



COMMENT ON COLUMN "public"."patient_medical_profile"."notes" IS 'Free-text clinical notes';



COMMENT ON COLUMN "public"."patient_medical_profile"."created_at" IS 'Record creation timestamp';



COMMENT ON COLUMN "public"."patient_medical_profile"."updated_at" IS 'Record modification timestamp';



CREATE TABLE IF NOT EXISTS "public"."patient_next_of_kin" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "full_name" "text" NOT NULL,
    "phone" "text",
    "relation" "text" NOT NULL,
    "is_primary_contact" boolean DEFAULT false NOT NULL,
    "zalo_id" "text",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."patient_next_of_kin" OWNER TO "postgres";


COMMENT ON TABLE "public"."patient_next_of_kin" IS 'Phase 1 — người nhà của BN (chồng/mẹ/con/...) để liên lạc khẩn. 1 BN có nhiều dòng.';



COMMENT ON COLUMN "public"."patient_next_of_kin"."relation" IS 'Tự do: Chồng / Mẹ đẻ / Mẹ chồng / Con / Anh chị em / ...';



COMMENT ON COLUMN "public"."patient_next_of_kin"."is_primary_contact" IS 'Người liên lạc ưu tiên — partial UNIQUE enforce 1 primary per BN.';



COMMENT ON COLUMN "public"."patient_next_of_kin"."zalo_id" IS 'Zalo user id của người nhà (nullable) — tự link khi họ nhắn lần đầu.';



CREATE TABLE IF NOT EXISTS "public"."visit" (
    "visit_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "appointment_id" "uuid",
    "work_session_id" "uuid",
    "attending_doctor_id" "uuid",
    "location_id" "uuid",
    "service_type_id" "uuid",
    "status" "text" DEFAULT 'OPEN'::"text" NOT NULL,
    "finalized_at" timestamp with time zone,
    "finalized_by" "uuid",
    "checked_in_at" timestamp with time zone,
    "checked_in_by" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "visit_status_check" CHECK (("status" = ANY (ARRAY['OPEN'::"text", 'IN_PROGRESS'::"text", 'FINALIZED'::"text", 'AMENDED'::"text"])))
);


ALTER TABLE "public"."visit" OWNER TO "postgres";


COMMENT ON TABLE "public"."visit" IS 'Actual patient encounter (D3 Clinical). Status machine OPEN -> IN_PROGRESS -> FINALIZED -> AMENDED. FINALIZED is DB-enforced immutable (TT13/2011/TT-BYT).';



COMMENT ON COLUMN "public"."visit"."status" IS 'OPEN -> IN_PROGRESS -> FINALIZED -> AMENDED. FINALIZED locked via trigger.';



CREATE OR REPLACE VIEW "public"."patient_summary" AS
 SELECT "p"."clinic_patient_id",
    "p"."patient_code",
    "p"."full_name",
    "p"."date_of_birth",
    "p"."phone_primary",
    "p"."national_id_number",
    "v_agg"."last_visit_at",
    "v_agg"."total_visits",
    "next_appt"."next_appointment_at",
    "next_appt"."next_appointment_status",
    "last_lab"."last_lab_received_at",
    "last_lab"."last_lab_test_code",
    "last_lab"."last_lab_triage_group"
   FROM ((("public"."patient" "p"
     LEFT JOIN LATERAL ( SELECT "max"(COALESCE("v"."checked_in_at", "v"."created_at")) AS "last_visit_at",
            "count"(*) AS "total_visits"
           FROM "public"."visit" "v"
          WHERE ("v"."clinic_patient_id" = "p"."clinic_patient_id")) "v_agg" ON (true))
     LEFT JOIN LATERAL ( SELECT "a"."slot_start" AS "next_appointment_at",
            "a"."status" AS "next_appointment_status"
           FROM "public"."appointment" "a"
          WHERE (("a"."clinic_patient_id" = "p"."clinic_patient_id") AND ("a"."status" = ANY (ARRAY['SCHEDULED'::"text", 'CONFIRMED'::"text"])) AND ("a"."slot_start" > "now"()))
          ORDER BY "a"."slot_start"
         LIMIT 1) "next_appt" ON (true))
     LEFT JOIN LATERAL ( SELECT "lr"."result_received_at" AS "last_lab_received_at",
            "lr"."test_code" AS "last_lab_test_code",
            "lr"."triage_group" AS "last_lab_triage_group"
           FROM "public"."lab_result" "lr"
          WHERE ("lr"."clinic_patient_id" = "p"."clinic_patient_id")
          ORDER BY "lr"."result_received_at" DESC
         LIMIT 1) "last_lab" ON (true));


ALTER VIEW "public"."patient_summary" OWNER TO "postgres";


COMMENT ON VIEW "public"."patient_summary" IS 'On-demand per-patient summary (Q-19 tentative resolution). Reads real-time across patient + visit + appointment + lab_result. Phase 9.7b.';



CREATE TABLE IF NOT EXISTS "public"."payment" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "visit_id" "uuid" NOT NULL,
    "clinic_patient_id" "uuid",
    "kind" "text" NOT NULL,
    "status" "text" DEFAULT 'PAID'::"text" NOT NULL,
    "amount" bigint,
    "paid_by_staff_id" "uuid",
    "paid_by_text" "text",
    "paid_at" timestamp with time zone DEFAULT "now"(),
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "payment_kind_check" CHECK (("kind" = ANY (ARRAY['thuoc'::"text", 'dich_vu'::"text"]))),
    CONSTRAINT "payment_status_check" CHECK (("status" = 'PAID'::"text"))
);


ALTER TABLE "public"."payment" OWNER TO "postgres";


COMMENT ON TABLE "public"."payment" IS 'Chốt thu tiền 1 lượt khám theo khâu (thuoc/dich_vu). 1 dòng (visit_id,kind)=đã thu. RLS SELECT authenticated, ghi qua service-role.';



CREATE TABLE IF NOT EXISTS "public"."pregnancy" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "location_id" "uuid" NOT NULL,
    "lmp_date" "date",
    "edd_date" "date",
    "gestational_age_at_registration" integer,
    "outcome" "text" DEFAULT 'ONGOING'::"text",
    "outcome_date" "date",
    "primary_doctor_id" "uuid",
    "is_high_risk" boolean DEFAULT false,
    "high_risk_reason" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "chk_edd_after_lmp" CHECK (((NOT (("lmp_date" IS NOT NULL) AND ("edd_date" IS NOT NULL))) OR ("edd_date" > "lmp_date"))),
    CONSTRAINT "pregnancy_outcome_check" CHECK (("outcome" = ANY (ARRAY['ONGOING'::"text", 'DELIVERED'::"text", 'MISCARRIAGE'::"text", 'TERMINATED'::"text", 'UNKNOWN'::"text"])))
);

ALTER TABLE ONLY "public"."pregnancy" REPLICA IDENTITY FULL;


ALTER TABLE "public"."pregnancy" OWNER TO "postgres";


COMMENT ON TABLE "public"."pregnancy" IS 'Tracks individual pregnancies per patient. One row per pregnancy.';



COMMENT ON COLUMN "public"."pregnancy"."id" IS 'Primary key identifier';



COMMENT ON COLUMN "public"."pregnancy"."clinic_patient_id" IS 'FK to patient — a patient may have multiple pregnancies';



COMMENT ON COLUMN "public"."pregnancy"."location_id" IS 'Clinic location managing this pregnancy';



COMMENT ON COLUMN "public"."pregnancy"."lmp_date" IS 'Last Menstrual Period date';



COMMENT ON COLUMN "public"."pregnancy"."edd_date" IS 'Estimated Due Date — computed by application layer, NOT a DB trigger';



COMMENT ON COLUMN "public"."pregnancy"."gestational_age_at_registration" IS 'Gestational age in weeks at time of registration';



COMMENT ON COLUMN "public"."pregnancy"."outcome" IS 'Pregnancy outcome status (ONGOING, DELIVERED, MISCARRIAGE, TERMINATED, UNKNOWN)';



COMMENT ON COLUMN "public"."pregnancy"."outcome_date" IS 'Date of pregnancy outcome';



COMMENT ON COLUMN "public"."pregnancy"."primary_doctor_id" IS 'Primary attending doctor FK to staff';



COMMENT ON COLUMN "public"."pregnancy"."is_high_risk" IS 'High-risk pregnancy flag';



COMMENT ON COLUMN "public"."pregnancy"."high_risk_reason" IS 'Reason for high-risk classification';



COMMENT ON COLUMN "public"."pregnancy"."created_at" IS 'Record creation timestamp';



COMMENT ON COLUMN "public"."pregnancy"."updated_at" IS 'Record modification timestamp';



CREATE TABLE IF NOT EXISTS "public"."prescription" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "source_ref" "text" NOT NULL,
    "clinic_patient_id" "uuid",
    "visit_id" "uuid",
    "drug_name_raw" "text",
    "drug_catalog_ref" "text",
    "dosage_instructions" "text",
    "quantity" "text",
    "quantity_note" "text",
    "caution" "text",
    "standardized_form" "text",
    "visit_link_raw" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE ONLY "public"."prescription" REPLICA IDENTITY FULL;


ALTER TABLE "public"."prescription" OWNER TO "postgres";


COMMENT ON TABLE "public"."prescription" IS 'Đơn thuốc kê cho BN. 1 dòng = 1 thuốc trong 1 đơn (1 lượt khám có thể nhiều dòng).';



COMMENT ON COLUMN "public"."prescription"."source_ref" IS 'Notion *ID, format RX-<n>.';



COMMENT ON COLUMN "public"."prescription"."drug_name_raw" IS 'Notion "Tên thuốc" raw, ví dụ "[137] Gynoflor (hộp 12 viên)".';



COMMENT ON COLUMN "public"."prescription"."dosage_instructions" IS 'Notion "Hướng dẫn dùng", ví dụ "đặt 2v/w".';



COMMENT ON COLUMN "public"."prescription"."standardized_form" IS 'Notion "//chuẩn form" — đơn thuốc đã format chuẩn (nhiều dòng).';



CREATE TABLE IF NOT EXISTS "public"."province" (
    "code" "text" NOT NULL,
    "name" "text" NOT NULL,
    "full_name" "text" NOT NULL,
    "code_name" "text"
);


ALTER TABLE "public"."province" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."schema_migrations" (
    "filename" "text" NOT NULL,
    "applied_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."schema_migrations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."service_log" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "source_ref" "text" NOT NULL,
    "clinic_patient_id" "uuid",
    "service_type_id" "uuid",
    "service_name_raw" "text",
    "performer_text" "text",
    "status" "text",
    "result_text" "text",
    "ordered_at" timestamp with time zone,
    "started_at" timestamp with time zone,
    "finished_at" timestamp with time zone,
    "created_by_text" "text",
    "visit_link_raw" "text",
    "patient_link_raw" "text",
    "result_form_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "kind" "text",
    "sent_to_lab_at" timestamp with time zone,
    CONSTRAINT "service_log_kind_check" CHECK ((("kind" IS NULL) OR ("kind" = ANY (ARRAY['SA'::"text", 'XN'::"text"]))))
);

ALTER TABLE ONLY "public"."service_log" REPLICA IDENTITY FULL;


ALTER TABLE "public"."service_log" OWNER TO "postgres";


COMMENT ON TABLE "public"."service_log" IS 'Lần BN dùng dịch vụ cụ thể (siêu âm, thủ thuật, khám). Nhập từ Notion "Dịch vụ" — 1 dòng = 1 lần làm dịch vụ.';



COMMENT ON COLUMN "public"."service_log"."source_ref" IS 'Notion ID, format SERVICE-<n>.';



COMMENT ON COLUMN "public"."service_log"."service_name_raw" IS 'Notion "Tên dịch vụ" raw text + URL — vẫn chưa resolve sang service_type_id khi chưa match tên.';



COMMENT ON COLUMN "public"."service_log"."ordered_at" IS 'Notion "Giờ chỉ định" — lúc BS chỉ định dịch vụ.';



COMMENT ON COLUMN "public"."service_log"."started_at" IS 'Notion "//Giờ bắt đầu" — lúc thực hiện.';



COMMENT ON COLUMN "public"."service_log"."finished_at" IS 'Notion "//Giờ kết thúc" — xong dịch vụ.';



COMMENT ON COLUMN "public"."service_log"."kind" IS 'Phân loại dòng cho màn ĐD siêu âm: SA (siêu âm) | XN (xét nghiệm). NULL = chưa phân loại.';



COMMENT ON COLUMN "public"."service_log"."sent_to_lab_at" IS 'Mốc "đã gửi lab" (giữa lấy mẫu và có KQ) cho hàng đợi XN 3 trạng thái.';



CREATE TABLE IF NOT EXISTS "public"."service_price" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "service_code" "text" NOT NULL,
    "name" "text" NOT NULL,
    "group" "text" NOT NULL,
    "unit_price" numeric(12,0),
    "active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "category" "text",
    "tang" "text",
    CONSTRAINT "service_price_group_check" CHECK (("group" = ANY (ARRAY['thuoc'::"text", 'dich_vu'::"text"])))
);


ALTER TABLE "public"."service_price" OWNER TO "postgres";


COMMENT ON TABLE "public"."service_price" IS 'Bảng giá khung dịch vụ/thuốc cho màn Thu ngân (unit_price nhập sau)';



COMMENT ON COLUMN "public"."service_price"."category" IS 'Nhóm CLS để picker Chỉ định CLS gom nhóm (NULL cho dòng nhập tay ở Thu ngân).';



CREATE TABLE IF NOT EXISTS "public"."service_type" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "code" "text" NOT NULL,
    "name" "text" NOT NULL,
    "default_duration_minutes" integer DEFAULT 30,
    "is_active" boolean DEFAULT true,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."service_type" OWNER TO "postgres";


COMMENT ON TABLE "public"."service_type" IS 'Clinic service offerings and catalog (e.g., Ultrasound, Consultation)';



COMMENT ON COLUMN "public"."service_type"."id" IS 'Primary key of the service type';



COMMENT ON COLUMN "public"."service_type"."code" IS 'Unique code identifier for the service type';



COMMENT ON COLUMN "public"."service_type"."name" IS 'Display name of the service type';



COMMENT ON COLUMN "public"."service_type"."default_duration_minutes" IS 'Standard duration of this service in minutes';



COMMENT ON COLUMN "public"."service_type"."is_active" IS 'Flag indicating whether this service is active';



COMMENT ON COLUMN "public"."service_type"."created_at" IS 'Timestamp when the record was created';



CREATE TABLE IF NOT EXISTS "public"."staff" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "primary_location_id" "uuid",
    "full_name" "text" NOT NULL,
    "is_active" boolean DEFAULT true,
    "is_training" boolean DEFAULT false,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "primary_department" "text" NOT NULL,
    "short_name" "text",
    "employment_type" "text" DEFAULT 'FULL_TIME'::"text" NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "auth_user_id" "uuid",
    CONSTRAINT "staff_employment_type_check" CHECK (("employment_type" = ANY (ARRAY['FULL_TIME'::"text", 'PART_TIME'::"text", 'CONTRACT'::"text"]))),
    CONSTRAINT "staff_primary_department_check" CHECK (("primary_department" = ANY (ARRAY['DOCTOR'::"text", 'ULTRASOUND_DOCTOR'::"text", 'NURSE_ULTRASOUND'::"text", 'RECEPTION'::"text", 'CSKH'::"text", 'MANAGEMENT'::"text", 'CASHIER'::"text", 'TKYK'::"text", 'TRUONG_CA'::"text", 'CASHIER_THUOC'::"text", 'CASHIER_DV'::"text"])))
);

ALTER TABLE ONLY "public"."staff" REPLICA IDENTITY FULL;


ALTER TABLE "public"."staff" OWNER TO "postgres";


COMMENT ON TABLE "public"."staff" IS 'Clinic staff members and their metadata. StaffCapability junction deferred to Phase 9 (D-staff-capability)';



COMMENT ON COLUMN "public"."staff"."id" IS 'Primary key of the staff member';



COMMENT ON COLUMN "public"."staff"."primary_location_id" IS 'Foreign key referencing the staff member''s primary/assigned clinic location';



COMMENT ON COLUMN "public"."staff"."full_name" IS 'Full legal name of the staff member';



COMMENT ON COLUMN "public"."staff"."is_active" IS 'Flag indicating whether this staff member is active';



COMMENT ON COLUMN "public"."staff"."is_training" IS 'Flag indicating whether this staff member is currently a trainee';



COMMENT ON COLUMN "public"."staff"."created_at" IS 'Timestamp when the record was created';



COMMENT ON COLUMN "public"."staff"."primary_department" IS 'Primary department of the staff member';



COMMENT ON COLUMN "public"."staff"."short_name" IS 'Short display/abbreviated name of the staff member';



COMMENT ON COLUMN "public"."staff"."employment_type" IS 'Employment type: FULL_TIME, PART_TIME, CONTRACT';



COMMENT ON COLUMN "public"."staff"."updated_at" IS 'Timestamp when the record was last updated';



COMMENT ON COLUMN "public"."staff"."auth_user_id" IS 'Supabase Auth user UUID — login mapping. Null cho NV chưa cấp acc dashboard.';



CREATE TABLE IF NOT EXISTS "public"."staff_capability" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "staff_id" "uuid" NOT NULL,
    "capability" "text" NOT NULL,
    "proficiency_level" "text" DEFAULT 'COMPETENT'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."staff_capability" OWNER TO "postgres";


COMMENT ON TABLE "public"."staff_capability" IS 'Capabilities a staff member can perform. Junction-like, app-enforced enum (D019).';



COMMENT ON COLUMN "public"."staff_capability"."capability" IS 'Free-form TEXT; app layer enforces allowed values via Capability schema.';



COMMENT ON COLUMN "public"."staff_capability"."proficiency_level" IS 'TRAINEE / COMPETENT / EXPERT — informational, no scheduling logic depends on it yet.';



CREATE TABLE IF NOT EXISTS "public"."staff_task" (
    "task_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "location_id" "uuid",
    "task_type" "text" NOT NULL,
    "priority" "text" DEFAULT 'NORMAL'::"text" NOT NULL,
    "status" "text" DEFAULT 'PENDING'::"text" NOT NULL,
    "assigned_to" "uuid",
    "source_type" "text",
    "source_id" "uuid",
    "title" "text" NOT NULL,
    "description" "text",
    "due_at" timestamp with time zone,
    "sla_hours" integer DEFAULT 24 NOT NULL,
    "completed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "staff_task_done_requires_completed_at" CHECK ((("status" <> 'DONE'::"text") OR ("completed_at" IS NOT NULL))),
    CONSTRAINT "staff_task_priority_check" CHECK (("priority" = ANY (ARRAY['URGENT'::"text", 'HIGH'::"text", 'NORMAL'::"text"]))),
    CONSTRAINT "staff_task_sla_hours_check" CHECK (("sla_hours" > 0)),
    CONSTRAINT "staff_task_status_check" CHECK (("status" = ANY (ARRAY['PENDING'::"text", 'IN_PROGRESS'::"text", 'DONE'::"text", 'CANCELLED'::"text"])))
);

ALTER TABLE ONLY "public"."staff_task" REPLICA IDENTITY FULL;


ALTER TABLE "public"."staff_task" OWNER TO "postgres";


COMMENT ON TABLE "public"."staff_task" IS 'Cross-cutting work queue for clinic staff. Phase 9.3 Task Manager.';



COMMENT ON COLUMN "public"."staff_task"."task_type" IS 'Free-form category (e.g. LAB_REVIEW, SLOT_FILL, PATIENT_CALLBACK). No CHECK — kinds evolve.';



COMMENT ON COLUMN "public"."staff_task"."source_type" IS 'Polymorphic source label (e.g. LAB_RESULT, APPOINTMENT). Application-enforced.';



COMMENT ON COLUMN "public"."staff_task"."source_id" IS 'UUID of the source entity. Pair with source_type for back-reference.';



COMMENT ON COLUMN "public"."staff_task"."sla_hours" IS 'Service-level target in hours from created_at. 24 default, 4 for GROUP_C lab review.';



CREATE TABLE IF NOT EXISTS "public"."ultrasound_record" (
    "ultrasound_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "visit_id" "uuid" NOT NULL,
    "clinic_patient_id" "uuid" NOT NULL,
    "performed_by" "uuid",
    "pregnancy_id" "uuid",
    "ultrasound_type" "text",
    "findings" "jsonb",
    "impression" "text",
    "image_refs" "text"[],
    "gestational_age_weeks" numeric,
    "performed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE ONLY "public"."ultrasound_record" REPLICA IDENTITY FULL;


ALTER TABLE "public"."ultrasound_record" OWNER TO "postgres";


COMMENT ON TABLE "public"."ultrasound_record" IS 'Ultrasound study attached to a visit. ultrasound_type is open-category TEXT (2D/4D/Doppler/...). image_refs MUST be LOCAL paths only — no cloud storage.';



COMMENT ON COLUMN "public"."ultrasound_record"."findings" IS 'Free-form JSONB measurement payload (BPD/FL/AC/EFW etc.). No schema enforced — evolves with practice.';



COMMENT ON COLUMN "public"."ultrasound_record"."image_refs" IS 'Array of LOCAL image paths. Cloud upload is forbidden (canon §6).';



CREATE TABLE IF NOT EXISTS "public"."visit_amendment" (
    "amendment_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "visit_id" "uuid" NOT NULL,
    "amended_by" "uuid" NOT NULL,
    "amended_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "reason" "text" NOT NULL,
    "corrected_fields" "text"[] NOT NULL,
    "original_values" "jsonb" NOT NULL,
    "corrected_values" "jsonb" NOT NULL
);


ALTER TABLE "public"."visit_amendment" OWNER TO "postgres";


COMMENT ON TABLE "public"."visit_amendment" IS 'APPEND-ONLY amendments to FINALIZED visits. Append-only enforced by trg_visit_amendment_no_update / trg_visit_amendment_no_delete (TT13/2011/TT-BYT).';



CREATE TABLE IF NOT EXISTS "public"."ward" (
    "code" "text" NOT NULL,
    "name" "text" NOT NULL,
    "full_name" "text" NOT NULL,
    "code_name" "text",
    "province_code" "text" NOT NULL
);


ALTER TABLE "public"."ward" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."work_roster" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "week_start" "date" NOT NULL,
    "work_date" "date" NOT NULL,
    "shift" "text" DEFAULT 'FULL'::"text" NOT NULL,
    "station" "text" NOT NULL,
    "staff_id" "uuid",
    "staff_name" "text" NOT NULL,
    "sort" integer DEFAULT 0 NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "status" "text" DEFAULT 'APPROVED'::"text" NOT NULL,
    "reject_reason" "text",
    CONSTRAINT "work_roster_shift_check" CHECK (("shift" = ANY (ARRAY['FULL'::"text", 'SANG'::"text", 'CHIEU'::"text"]))),
    CONSTRAINT "work_roster_status_check" CHECK (("status" = ANY (ARRAY['PENDING'::"text", 'APPROVED'::"text", 'REJECTED'::"text"])))
);


ALTER TABLE "public"."work_roster" OWNER TO "postgres";


COMMENT ON TABLE "public"."work_roster" IS 'Lịch phân công ca trực theo phòng/trạm (weekly roster)';



COMMENT ON COLUMN "public"."work_roster"."reject_reason" IS 'Lý do quỉan lý từ chối ca (chỉ có nghĩa khi status = REJECT).';



CREATE TABLE IF NOT EXISTS "public"."work_session" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "location_id" "uuid" NOT NULL,
    "session_date" "date" NOT NULL,
    "session_type" "text" NOT NULL,
    "start_time" time without time zone NOT NULL,
    "end_time" time without time zone NOT NULL,
    "max_patients" integer,
    "created_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "work_session_check" CHECK (("end_time" > "start_time")),
    CONSTRAINT "work_session_session_type_check" CHECK (("session_type" = ANY (ARRAY['EVENING'::"text", 'WEEKEND_MORNING'::"text", 'WEEKEND_AFTERNOON'::"text"])))
);

ALTER TABLE ONLY "public"."work_session" REPLICA IDENTITY FULL;


ALTER TABLE "public"."work_session" OWNER TO "postgres";


COMMENT ON TABLE "public"."work_session" IS 'Work sessions/shifts scheduled for a clinic location';



CREATE TABLE IF NOT EXISTS "public"."work_session_staff" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "work_session_id" "uuid" NOT NULL,
    "staff_id" "uuid" NOT NULL,
    "role" "text" NOT NULL,
    "station" "text" NOT NULL,
    "on_call_flag" boolean DEFAULT false NOT NULL,
    "is_training" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."work_session_staff" OWNER TO "postgres";


COMMENT ON TABLE "public"."work_session_staff" IS 'Junction table linking staff members to work sessions and stations';



COMMENT ON COLUMN "public"."work_session_staff"."station" IS 'Free text TEXT instead of ENUM — Q-28 station list still evolving';



ALTER TABLE ONLY "langgraph"."checkpoint_blobs"
    ADD CONSTRAINT "checkpoint_blobs_pkey" PRIMARY KEY ("thread_id", "checkpoint_ns", "channel", "version");



ALTER TABLE ONLY "langgraph"."checkpoint_migrations"
    ADD CONSTRAINT "checkpoint_migrations_pkey" PRIMARY KEY ("v");



ALTER TABLE ONLY "langgraph"."checkpoint_writes"
    ADD CONSTRAINT "checkpoint_writes_pkey" PRIMARY KEY ("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx");



ALTER TABLE ONLY "langgraph"."checkpoints"
    ADD CONSTRAINT "checkpoints_pkey" PRIMARY KEY ("thread_id", "checkpoint_ns", "checkpoint_id");



ALTER TABLE ONLY "public"."appointment"
    ADD CONSTRAINT "appointment_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."block_budget"
    ADD CONSTRAINT "block_budget_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."booking_channel"
    ADD CONSTRAINT "booking_channel_code_key" UNIQUE ("code");



ALTER TABLE ONLY "public"."booking_channel"
    ADD CONSTRAINT "booking_channel_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."care_episode"
    ADD CONSTRAINT "care_episode_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."clinic_location"
    ADD CONSTRAINT "clinic_location_code_key" UNIQUE ("code");



ALTER TABLE ONLY "public"."clinic_location"
    ADD CONSTRAINT "clinic_location_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."clinical_form_response"
    ADD CONSTRAINT "clinical_form_response_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."clinical_record"
    ADD CONSTRAINT "clinical_record_pkey" PRIMARY KEY ("record_id");



ALTER TABLE ONLY "public"."clinical_record"
    ADD CONSTRAINT "clinical_record_visit_id_key" UNIQUE ("visit_id");



ALTER TABLE ONLY "public"."cskh_action"
    ADD CONSTRAINT "cskh_action_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cskh_action"
    ADD CONSTRAINT "cskh_action_source_ref_key" UNIQUE ("source_ref");



ALTER TABLE ONLY "public"."cskh_log"
    ADD CONSTRAINT "cskh_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."drug_catalog"
    ADD CONSTRAINT "drug_catalog_name_raw_key" UNIQUE ("name_raw");



ALTER TABLE ONLY "public"."drug_catalog"
    ADD CONSTRAINT "drug_catalog_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."event_log"
    ADD CONSTRAINT "event_log_pkey" PRIMARY KEY ("event_id");



ALTER TABLE ONLY "public"."lab_result"
    ADD CONSTRAINT "lab_result_pkey" PRIMARY KEY ("lab_result_id");



ALTER TABLE ONLY "public"."mpi_merge_queue"
    ADD CONSTRAINT "mpi_merge_queue_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."patient_contact_channel"
    ADD CONSTRAINT "patient_contact_channel_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."patient_medical_profile"
    ADD CONSTRAINT "patient_medical_profile_clinic_patient_id_key" UNIQUE ("clinic_patient_id");



ALTER TABLE ONLY "public"."patient_medical_profile"
    ADD CONSTRAINT "patient_medical_profile_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."patient_next_of_kin"
    ADD CONSTRAINT "patient_next_of_kin_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."patient"
    ADD CONSTRAINT "patient_patient_code_key" UNIQUE ("patient_code");



ALTER TABLE ONLY "public"."patient"
    ADD CONSTRAINT "patient_pkey" PRIMARY KEY ("clinic_patient_id");



ALTER TABLE ONLY "public"."payment"
    ADD CONSTRAINT "payment_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."payment"
    ADD CONSTRAINT "payment_visit_id_kind_key" UNIQUE ("visit_id", "kind");



ALTER TABLE ONLY "public"."pregnancy"
    ADD CONSTRAINT "pregnancy_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."prescription"
    ADD CONSTRAINT "prescription_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."prescription"
    ADD CONSTRAINT "prescription_source_ref_key" UNIQUE ("source_ref");



ALTER TABLE ONLY "public"."province"
    ADD CONSTRAINT "province_pkey" PRIMARY KEY ("code");



ALTER TABLE ONLY "public"."schema_migrations"
    ADD CONSTRAINT "schema_migrations_pkey" PRIMARY KEY ("filename");



ALTER TABLE ONLY "public"."service_log"
    ADD CONSTRAINT "service_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."service_log"
    ADD CONSTRAINT "service_log_source_ref_key" UNIQUE ("source_ref");



ALTER TABLE ONLY "public"."service_price"
    ADD CONSTRAINT "service_price_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."service_type"
    ADD CONSTRAINT "service_type_code_key" UNIQUE ("code");



ALTER TABLE ONLY "public"."service_type"
    ADD CONSTRAINT "service_type_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."staff_capability"
    ADD CONSTRAINT "staff_capability_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."staff"
    ADD CONSTRAINT "staff_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."staff_task"
    ADD CONSTRAINT "staff_task_pkey" PRIMARY KEY ("task_id");



ALTER TABLE ONLY "public"."ultrasound_record"
    ADD CONSTRAINT "ultrasound_record_pkey" PRIMARY KEY ("ultrasound_id");



ALTER TABLE ONLY "public"."clinical_form_response"
    ADD CONSTRAINT "uq_clinical_form_visit_service" UNIQUE ("visit_id", "service_code");



ALTER TABLE ONLY "public"."staff_capability"
    ADD CONSTRAINT "uq_staff_capability" UNIQUE ("staff_id", "capability");



ALTER TABLE ONLY "public"."visit_amendment"
    ADD CONSTRAINT "visit_amendment_pkey" PRIMARY KEY ("amendment_id");



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_pkey" PRIMARY KEY ("visit_id");



ALTER TABLE ONLY "public"."ward"
    ADD CONSTRAINT "ward_pkey" PRIMARY KEY ("code");



ALTER TABLE ONLY "public"."work_roster"
    ADD CONSTRAINT "work_roster_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."work_session"
    ADD CONSTRAINT "work_session_location_id_session_date_session_type_key" UNIQUE ("location_id", "session_date", "session_type");



ALTER TABLE ONLY "public"."work_session"
    ADD CONSTRAINT "work_session_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."work_session_staff"
    ADD CONSTRAINT "work_session_staff_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."work_session_staff"
    ADD CONSTRAINT "work_session_staff_work_session_id_staff_id_station_key" UNIQUE ("work_session_id", "staff_id", "station");



CREATE INDEX "checkpoint_blobs_thread_id_idx" ON "langgraph"."checkpoint_blobs" USING "btree" ("thread_id");



CREATE INDEX "checkpoint_writes_thread_id_idx" ON "langgraph"."checkpoint_writes" USING "btree" ("thread_id");



CREATE INDEX "checkpoints_thread_id_idx" ON "langgraph"."checkpoints" USING "btree" ("thread_id");



CREATE INDEX "idx_appointment_doctor_date" ON "public"."appointment" USING "btree" ("doctor_id", "slot_start");



CREATE INDEX "idx_appointment_patient" ON "public"."appointment" USING "btree" ("clinic_patient_id");



CREATE INDEX "idx_appointment_session" ON "public"."appointment" USING "btree" ("work_session_id");



CREATE INDEX "idx_appointment_status" ON "public"."appointment" USING "btree" ("status") WHERE ("status" = ANY (ARRAY['SCHEDULED'::"text", 'CONFIRMED'::"text", 'CHECKED_IN'::"text"]));



CREATE INDEX "idx_booking_channel_active" ON "public"."booking_channel" USING "btree" ("is_active") WHERE ("is_active" = true);



CREATE INDEX "idx_booking_channel_category" ON "public"."booking_channel" USING "btree" ("category");



CREATE INDEX "idx_care_episode_lookup" ON "public"."care_episode" USING "btree" ("clinic_patient_id", "service_type_id", "status");



CREATE INDEX "idx_clinical_form_visit" ON "public"."clinical_form_response" USING "btree" ("visit_id");



CREATE INDEX "idx_cskh_action_category" ON "public"."cskh_action" USING "btree" ("category");



CREATE INDEX "idx_cskh_action_deadline" ON "public"."cskh_action" USING "btree" ("deadline_at") WHERE ("deadline_at" IS NOT NULL);



CREATE INDEX "idx_cskh_action_patient" ON "public"."cskh_action" USING "btree" ("clinic_patient_id") WHERE ("clinic_patient_id" IS NOT NULL);



CREATE INDEX "idx_cskh_action_source_created" ON "public"."cskh_action" USING "btree" ("source_created_at" DESC NULLS LAST);



CREATE INDEX "idx_cskh_log_date" ON "public"."cskh_log" USING "btree" ("work_date" DESC);



CREATE INDEX "idx_cskh_log_patient" ON "public"."cskh_log" USING "btree" ("clinic_patient_id");



CREATE INDEX "idx_drug_catalog_active" ON "public"."drug_catalog" USING "btree" ("name_base") WHERE "is_active";



CREATE INDEX "idx_event_log_aggregate" ON "public"."event_log" USING "btree" ("aggregate_type", "aggregate_id", "occurred_at");



CREATE INDEX "idx_event_log_correlation" ON "public"."event_log" USING "btree" ("correlation_id") WHERE ("correlation_id" IS NOT NULL);



CREATE INDEX "idx_event_log_event_type" ON "public"."event_log" USING "btree" ("event_type", "occurred_at");



CREATE INDEX "idx_event_log_occurred_at" ON "public"."event_log" USING "btree" ("occurred_at");



CREATE INDEX "idx_event_log_unpublished" ON "public"."event_log" USING "btree" ("event_published") WHERE ("event_published" = false);



CREATE INDEX "idx_lab_result_appointment" ON "public"."lab_result" USING "btree" ("appointment_id") WHERE ("appointment_id" IS NOT NULL);



CREATE INDEX "idx_lab_result_patient" ON "public"."lab_result" USING "btree" ("clinic_patient_id", "result_received_at" DESC);



CREATE INDEX "idx_lab_result_safety_gate" ON "public"."lab_result" USING "btree" ("requires_doctor_review", "is_finalized") WHERE (("requires_doctor_review" = true) AND ("is_finalized" = false));



CREATE INDEX "idx_lab_result_triage_pending" ON "public"."lab_result" USING "btree" ("triage_group") WHERE ("triage_group" = 'PENDING'::"text");



CREATE INDEX "idx_mpi_merge_queue_status_score" ON "public"."mpi_merge_queue" USING "btree" ("status", "score" DESC);



CREATE INDEX "idx_patient_contact_channel_lookup" ON "public"."patient_contact_channel" USING "btree" ("channel_type", "channel_value");



CREATE UNIQUE INDEX "idx_patient_contact_channel_primary" ON "public"."patient_contact_channel" USING "btree" ("clinic_patient_id") WHERE ("is_primary" = true);



CREATE UNIQUE INDEX "idx_patient_contact_channel_uniq" ON "public"."patient_contact_channel" USING "btree" ("clinic_patient_id", "channel_type", "channel_value");



CREATE INDEX "idx_patient_full_name_unaccent" ON "public"."patient" USING "gin" ("full_name_unaccent" "public"."gin_trgm_ops");



CREATE UNIQUE INDEX "idx_patient_national_id_unique" ON "public"."patient" USING "btree" ("national_id_number") WHERE ("national_id_number" IS NOT NULL);



CREATE INDEX "idx_patient_next_of_kin_patient" ON "public"."patient_next_of_kin" USING "btree" ("clinic_patient_id");



CREATE UNIQUE INDEX "idx_patient_next_of_kin_primary" ON "public"."patient_next_of_kin" USING "btree" ("clinic_patient_id") WHERE ("is_primary_contact" = true);



CREATE INDEX "idx_patient_patient_code" ON "public"."patient" USING "btree" ("patient_code");



CREATE INDEX "idx_patient_phone_primary" ON "public"."patient" USING "btree" ("phone_primary");



CREATE INDEX "idx_payment_visit" ON "public"."payment" USING "btree" ("visit_id");



CREATE INDEX "idx_pregnancy_clinic_patient_id" ON "public"."pregnancy" USING "btree" ("clinic_patient_id");



CREATE INDEX "idx_pregnancy_outcome" ON "public"."pregnancy" USING "btree" ("outcome");



CREATE INDEX "idx_pregnancy_primary_doctor_id" ON "public"."pregnancy" USING "btree" ("primary_doctor_id");



CREATE INDEX "idx_prescription_patient" ON "public"."prescription" USING "btree" ("clinic_patient_id") WHERE ("clinic_patient_id" IS NOT NULL);



CREATE INDEX "idx_prescription_visit" ON "public"."prescription" USING "btree" ("visit_id") WHERE ("visit_id" IS NOT NULL);



CREATE INDEX "idx_service_log_kind" ON "public"."service_log" USING "btree" ("kind") WHERE ("kind" IS NOT NULL);



CREATE INDEX "idx_service_log_patient" ON "public"."service_log" USING "btree" ("clinic_patient_id") WHERE ("clinic_patient_id" IS NOT NULL);



CREATE INDEX "idx_service_log_service_type" ON "public"."service_log" USING "btree" ("service_type_id") WHERE ("service_type_id" IS NOT NULL);



CREATE INDEX "idx_service_log_started" ON "public"."service_log" USING "btree" ("started_at" DESC NULLS LAST);



CREATE INDEX "idx_service_log_status" ON "public"."service_log" USING "btree" ("status");



CREATE INDEX "idx_service_price_group_active" ON "public"."service_price" USING "btree" ("group") WHERE "active";



CREATE INDEX "idx_staff_active" ON "public"."staff" USING "btree" ("is_active") WHERE ("is_active" = true);



CREATE UNIQUE INDEX "idx_staff_auth_user_id_unique" ON "public"."staff" USING "btree" ("auth_user_id") WHERE ("auth_user_id" IS NOT NULL);



CREATE INDEX "idx_staff_capability_capability" ON "public"."staff_capability" USING "btree" ("capability");



CREATE INDEX "idx_staff_capability_staff_id" ON "public"."staff_capability" USING "btree" ("staff_id");



CREATE INDEX "idx_staff_primary_location" ON "public"."staff" USING "btree" ("primary_location_id");



CREATE INDEX "idx_staff_task_assigned" ON "public"."staff_task" USING "btree" ("assigned_to", "status");



CREATE INDEX "idx_staff_task_due" ON "public"."staff_task" USING "btree" ("due_at") WHERE ("status" = 'PENDING'::"text");



CREATE INDEX "idx_staff_task_source" ON "public"."staff_task" USING "btree" ("source_type", "source_id");



CREATE INDEX "idx_ultrasound_patient" ON "public"."ultrasound_record" USING "btree" ("clinic_patient_id");



CREATE INDEX "idx_ultrasound_visit" ON "public"."ultrasound_record" USING "btree" ("visit_id");



CREATE INDEX "idx_visit_amendment_visit" ON "public"."visit_amendment" USING "btree" ("visit_id");



CREATE INDEX "idx_visit_patient" ON "public"."visit" USING "btree" ("clinic_patient_id");



CREATE INDEX "idx_ward_province_code" ON "public"."ward" USING "btree" ("province_code");



CREATE INDEX "idx_work_roster_date" ON "public"."work_roster" USING "btree" ("work_date");



CREATE INDEX "idx_work_roster_staff" ON "public"."work_roster" USING "btree" ("staff_id");



CREATE INDEX "idx_work_roster_week" ON "public"."work_roster" USING "btree" ("week_start");



CREATE INDEX "idx_work_roster_week_status" ON "public"."work_roster" USING "btree" ("week_start", "status");



CREATE INDEX "idx_work_session_date" ON "public"."work_session" USING "btree" ("session_date" DESC);



CREATE INDEX "idx_wss_staff" ON "public"."work_session_staff" USING "btree" ("staff_id");



CREATE INDEX "idx_wss_work_session" ON "public"."work_session_staff" USING "btree" ("work_session_id");



CREATE UNIQUE INDEX "uq_block_budget_key" ON "public"."block_budget" USING "btree" ("location_id", COALESCE("doctor_id", '00000000-0000-0000-0000-000000000000'::"uuid"), COALESCE("weekday", 9), "hour_start");



CREATE UNIQUE INDEX "uq_care_episode_live" ON "public"."care_episode" USING "btree" ("clinic_patient_id", "service_type_id") WHERE ("status" <> 'CLOSED'::"text");



CREATE UNIQUE INDEX "uq_service_price_code_group" ON "public"."service_price" USING "btree" ("group", "service_code");



CREATE UNIQUE INDEX "uq_visit_appointment_id" ON "public"."visit" USING "btree" ("appointment_id") WHERE ("appointment_id" IS NOT NULL);



CREATE OR REPLACE TRIGGER "clinical_record_set_updated_at" BEFORE UPDATE ON "public"."clinical_record" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "lab_result_set_updated_at" BEFORE UPDATE ON "public"."lab_result" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "staff_task_set_updated_at" BEFORE UPDATE ON "public"."staff_task" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_appointment_no_delete" BEFORE DELETE ON "public"."appointment" FOR EACH ROW EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_appointment_no_truncate" BEFORE TRUNCATE ON "public"."appointment" FOR EACH STATEMENT EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_clinical_record_no_delete" BEFORE DELETE ON "public"."clinical_record" FOR EACH ROW EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_clinical_record_no_truncate" BEFORE TRUNCATE ON "public"."clinical_record" FOR EACH STATEMENT EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_event_log_no_delete" BEFORE DELETE ON "public"."event_log" FOR EACH ROW EXECUTE FUNCTION "public"."enforce_append_only"();



CREATE OR REPLACE TRIGGER "trg_event_log_no_truncate" BEFORE TRUNCATE ON "public"."event_log" FOR EACH STATEMENT EXECUTE FUNCTION "public"."enforce_append_only"();



CREATE OR REPLACE TRIGGER "trg_event_log_no_update" BEFORE UPDATE ON "public"."event_log" FOR EACH ROW EXECUTE FUNCTION "public"."enforce_append_only"();



CREATE OR REPLACE TRIGGER "trg_lab_result_no_delete" BEFORE DELETE ON "public"."lab_result" FOR EACH ROW EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_lab_result_no_truncate" BEFORE TRUNCATE ON "public"."lab_result" FOR EACH STATEMENT EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_patient_no_delete" BEFORE DELETE ON "public"."patient" FOR EACH ROW EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_patient_no_truncate" BEFORE TRUNCATE ON "public"."patient" FOR EACH STATEMENT EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_visit_amendment_no_delete" BEFORE DELETE ON "public"."visit_amendment" FOR EACH ROW EXECUTE FUNCTION "public"."visit_amendment_append_only"();



CREATE OR REPLACE TRIGGER "trg_visit_amendment_no_update" BEFORE UPDATE ON "public"."visit_amendment" FOR EACH ROW EXECUTE FUNCTION "public"."visit_amendment_append_only"();



CREATE OR REPLACE TRIGGER "trg_visit_finalized_block" BEFORE UPDATE ON "public"."visit" FOR EACH ROW EXECUTE FUNCTION "public"."visit_finalized_block_update"();



CREATE OR REPLACE TRIGGER "trg_visit_no_delete" BEFORE DELETE ON "public"."visit" FOR EACH ROW EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "trg_visit_no_truncate" BEFORE TRUNCATE ON "public"."visit" FOR EACH STATEMENT EXECUTE FUNCTION "public"."prevent_hard_delete"();



CREATE OR REPLACE TRIGGER "ultrasound_record_set_updated_at" BEFORE UPDATE ON "public"."ultrasound_record" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "visit_set_updated_at" BEFORE UPDATE ON "public"."visit" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



ALTER TABLE ONLY "public"."appointment"
    ADD CONSTRAINT "appointment_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."appointment"
    ADD CONSTRAINT "appointment_doctor_id_fkey" FOREIGN KEY ("doctor_id") REFERENCES "public"."staff"("id");



ALTER TABLE ONLY "public"."appointment"
    ADD CONSTRAINT "appointment_episode_id_fkey" FOREIGN KEY ("episode_id") REFERENCES "public"."care_episode"("id");



ALTER TABLE ONLY "public"."appointment"
    ADD CONSTRAINT "appointment_location_id_fkey" FOREIGN KEY ("location_id") REFERENCES "public"."clinic_location"("id");



ALTER TABLE ONLY "public"."appointment"
    ADD CONSTRAINT "appointment_service_type_id_fkey" FOREIGN KEY ("service_type_id") REFERENCES "public"."service_type"("id");



ALTER TABLE ONLY "public"."appointment"
    ADD CONSTRAINT "appointment_work_session_id_fkey" FOREIGN KEY ("work_session_id") REFERENCES "public"."work_session"("id");



ALTER TABLE ONLY "public"."block_budget"
    ADD CONSTRAINT "block_budget_doctor_id_fkey" FOREIGN KEY ("doctor_id") REFERENCES "public"."staff"("id");



ALTER TABLE ONLY "public"."block_budget"
    ADD CONSTRAINT "block_budget_location_id_fkey" FOREIGN KEY ("location_id") REFERENCES "public"."clinic_location"("id");



ALTER TABLE ONLY "public"."care_episode"
    ADD CONSTRAINT "care_episode_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."care_episode"
    ADD CONSTRAINT "care_episode_opened_appointment_id_fkey" FOREIGN KEY ("opened_appointment_id") REFERENCES "public"."appointment"("id");



ALTER TABLE ONLY "public"."care_episode"
    ADD CONSTRAINT "care_episode_service_type_id_fkey" FOREIGN KEY ("service_type_id") REFERENCES "public"."service_type"("id");



ALTER TABLE ONLY "public"."clinical_form_response"
    ADD CONSTRAINT "clinical_form_response_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "public"."visit"("visit_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."clinical_record"
    ADD CONSTRAINT "clinical_record_pregnancy_id_fkey" FOREIGN KEY ("pregnancy_id") REFERENCES "public"."pregnancy"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."clinical_record"
    ADD CONSTRAINT "clinical_record_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "public"."visit"("visit_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."cskh_action"
    ADD CONSTRAINT "cskh_action_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."cskh_log"
    ADD CONSTRAINT "cskh_log_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."event_log"
    ADD CONSTRAINT "event_log_causation_id_fkey" FOREIGN KEY ("causation_id") REFERENCES "public"."event_log"("event_id");



ALTER TABLE ONLY "public"."lab_result"
    ADD CONSTRAINT "lab_result_appointment_id_fkey" FOREIGN KEY ("appointment_id") REFERENCES "public"."appointment"("id");



ALTER TABLE ONLY "public"."lab_result"
    ADD CONSTRAINT "lab_result_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id");



ALTER TABLE ONLY "public"."lab_result"
    ADD CONSTRAINT "lab_result_reviewed_by_staff_id_fkey" FOREIGN KEY ("reviewed_by_staff_id") REFERENCES "public"."staff"("id");



ALTER TABLE ONLY "public"."mpi_merge_queue"
    ADD CONSTRAINT "mpi_merge_queue_patient_id_a_fkey" FOREIGN KEY ("patient_id_a") REFERENCES "public"."patient"("clinic_patient_id");



ALTER TABLE ONLY "public"."mpi_merge_queue"
    ADD CONSTRAINT "mpi_merge_queue_patient_id_b_fkey" FOREIGN KEY ("patient_id_b") REFERENCES "public"."patient"("clinic_patient_id");



ALTER TABLE ONLY "public"."mpi_merge_queue"
    ADD CONSTRAINT "mpi_merge_queue_reviewed_by_fkey" FOREIGN KEY ("reviewed_by") REFERENCES "public"."staff"("id");



ALTER TABLE ONLY "public"."patient_contact_channel"
    ADD CONSTRAINT "patient_contact_channel_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."patient"
    ADD CONSTRAINT "patient_location_id_fkey" FOREIGN KEY ("location_id") REFERENCES "public"."clinic_location"("id");



ALTER TABLE ONLY "public"."patient_medical_profile"
    ADD CONSTRAINT "patient_medical_profile_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id");



ALTER TABLE ONLY "public"."patient_next_of_kin"
    ADD CONSTRAINT "patient_next_of_kin_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."patient"
    ADD CONSTRAINT "patient_province_code_fkey" FOREIGN KEY ("province_code") REFERENCES "public"."province"("code");



ALTER TABLE ONLY "public"."patient"
    ADD CONSTRAINT "patient_ward_code_fkey" FOREIGN KEY ("ward_code") REFERENCES "public"."ward"("code");



ALTER TABLE ONLY "public"."payment"
    ADD CONSTRAINT "payment_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."payment"
    ADD CONSTRAINT "payment_paid_by_staff_id_fkey" FOREIGN KEY ("paid_by_staff_id") REFERENCES "public"."staff"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."payment"
    ADD CONSTRAINT "payment_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "public"."visit"("visit_id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."pregnancy"
    ADD CONSTRAINT "pregnancy_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id");



ALTER TABLE ONLY "public"."pregnancy"
    ADD CONSTRAINT "pregnancy_location_id_fkey" FOREIGN KEY ("location_id") REFERENCES "public"."clinic_location"("id");



ALTER TABLE ONLY "public"."pregnancy"
    ADD CONSTRAINT "pregnancy_primary_doctor_id_fkey" FOREIGN KEY ("primary_doctor_id") REFERENCES "public"."staff"("id");



ALTER TABLE ONLY "public"."prescription"
    ADD CONSTRAINT "prescription_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."prescription"
    ADD CONSTRAINT "prescription_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "public"."visit"("visit_id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."service_log"
    ADD CONSTRAINT "service_log_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."service_log"
    ADD CONSTRAINT "service_log_service_type_id_fkey" FOREIGN KEY ("service_type_id") REFERENCES "public"."service_type"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."staff"
    ADD CONSTRAINT "staff_auth_user_id_fkey" FOREIGN KEY ("auth_user_id") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."staff_capability"
    ADD CONSTRAINT "staff_capability_staff_id_fkey" FOREIGN KEY ("staff_id") REFERENCES "public"."staff"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."staff"
    ADD CONSTRAINT "staff_primary_location_id_fkey" FOREIGN KEY ("primary_location_id") REFERENCES "public"."clinic_location"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."staff_task"
    ADD CONSTRAINT "staff_task_assigned_to_fkey" FOREIGN KEY ("assigned_to") REFERENCES "public"."staff"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."staff_task"
    ADD CONSTRAINT "staff_task_location_id_fkey" FOREIGN KEY ("location_id") REFERENCES "public"."clinic_location"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."ultrasound_record"
    ADD CONSTRAINT "ultrasound_record_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."ultrasound_record"
    ADD CONSTRAINT "ultrasound_record_performed_by_fkey" FOREIGN KEY ("performed_by") REFERENCES "public"."staff"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."ultrasound_record"
    ADD CONSTRAINT "ultrasound_record_pregnancy_id_fkey" FOREIGN KEY ("pregnancy_id") REFERENCES "public"."pregnancy"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."ultrasound_record"
    ADD CONSTRAINT "ultrasound_record_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "public"."visit"("visit_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit_amendment"
    ADD CONSTRAINT "visit_amendment_amended_by_fkey" FOREIGN KEY ("amended_by") REFERENCES "public"."staff"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit_amendment"
    ADD CONSTRAINT "visit_amendment_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "public"."visit"("visit_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_appointment_id_fkey" FOREIGN KEY ("appointment_id") REFERENCES "public"."appointment"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_attending_doctor_id_fkey" FOREIGN KEY ("attending_doctor_id") REFERENCES "public"."staff"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_checked_in_by_fkey" FOREIGN KEY ("checked_in_by") REFERENCES "public"."staff"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_clinic_patient_id_fkey" FOREIGN KEY ("clinic_patient_id") REFERENCES "public"."patient"("clinic_patient_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_finalized_by_fkey" FOREIGN KEY ("finalized_by") REFERENCES "public"."staff"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_location_id_fkey" FOREIGN KEY ("location_id") REFERENCES "public"."clinic_location"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_service_type_id_fkey" FOREIGN KEY ("service_type_id") REFERENCES "public"."service_type"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."visit"
    ADD CONSTRAINT "visit_work_session_id_fkey" FOREIGN KEY ("work_session_id") REFERENCES "public"."work_session"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."ward"
    ADD CONSTRAINT "ward_province_code_fkey" FOREIGN KEY ("province_code") REFERENCES "public"."province"("code");



ALTER TABLE ONLY "public"."work_roster"
    ADD CONSTRAINT "work_roster_staff_id_fkey" FOREIGN KEY ("staff_id") REFERENCES "public"."staff"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."work_session"
    ADD CONSTRAINT "work_session_location_id_fkey" FOREIGN KEY ("location_id") REFERENCES "public"."clinic_location"("id");



ALTER TABLE ONLY "public"."work_session_staff"
    ADD CONSTRAINT "work_session_staff_staff_id_fkey" FOREIGN KEY ("staff_id") REFERENCES "public"."staff"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."work_session_staff"
    ADD CONSTRAINT "work_session_staff_work_session_id_fkey" FOREIGN KEY ("work_session_id") REFERENCES "public"."work_session"("id") ON DELETE CASCADE;



ALTER TABLE "public"."appointment" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "appointment_select_authenticated" ON "public"."appointment" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."block_budget" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."booking_channel" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."care_episode" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clinic_location" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "clinic_location_select_authenticated" ON "public"."clinic_location" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."clinical_form_response" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "clinical_form_response_select_authenticated" ON "public"."clinical_form_response" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."clinical_record" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "clinical_record_select_authenticated" ON "public"."clinical_record" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."cskh_action" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "cskh_action_select_authenticated" ON "public"."cskh_action" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."cskh_log" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "cskh_log_select_authenticated" ON "public"."cskh_log" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."drug_catalog" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "drug_catalog_select_authenticated" ON "public"."drug_catalog" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."event_log" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "event_log_select_authenticated" ON "public"."event_log" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."lab_result" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "lab_result_select_authenticated" ON "public"."lab_result" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."mpi_merge_queue" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."patient" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."patient_contact_channel" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."patient_medical_profile" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "patient_medical_profile_select_authenticated" ON "public"."patient_medical_profile" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."patient_next_of_kin" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "patient_select_authenticated" ON "public"."patient" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."payment" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "payment_select_authenticated" ON "public"."payment" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."pregnancy" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "pregnancy_select_authenticated" ON "public"."pregnancy" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."prescription" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "prescription_select_authenticated" ON "public"."prescription" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."province" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."schema_migrations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."service_log" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "service_log_select_authenticated" ON "public"."service_log" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."service_price" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "service_price_select_authenticated" ON "public"."service_price" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."service_type" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "service_type_select_authenticated" ON "public"."service_type" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."staff" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."staff_capability" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "staff_select_authenticated" ON "public"."staff" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."staff_task" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "staff_task_select_authenticated" ON "public"."staff_task" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."ultrasound_record" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."visit" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."visit_amendment" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "visit_select_authenticated" ON "public"."visit" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."ward" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."work_roster" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "work_roster_select_authenticated" ON "public"."work_roster" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."work_session" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "work_session_select_authenticated" ON "public"."work_session" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."work_session_staff" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "work_session_staff_select_authenticated" ON "public"."work_session_staff" FOR SELECT TO "authenticated" USING (true);





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";






ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."appointment";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."clinical_form_response";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."clinical_record";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."cskh_action";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."cskh_log";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."lab_result";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."patient";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."patient_medical_profile";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."payment";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."pregnancy";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."prescription";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."service_log";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."staff";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."staff_task";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."ultrasound_record";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."visit";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."work_roster";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."work_session";



GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey16_in"("cstring") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey16_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey16_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey16_in"("cstring") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey16_out"("public"."gbtreekey16") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey16_out"("public"."gbtreekey16") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey16_out"("public"."gbtreekey16") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey16_out"("public"."gbtreekey16") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey2_in"("cstring") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey2_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey2_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey2_in"("cstring") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey2_out"("public"."gbtreekey2") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey2_out"("public"."gbtreekey2") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey2_out"("public"."gbtreekey2") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey2_out"("public"."gbtreekey2") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey32_in"("cstring") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey32_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey32_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey32_in"("cstring") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey32_out"("public"."gbtreekey32") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey32_out"("public"."gbtreekey32") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey32_out"("public"."gbtreekey32") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey32_out"("public"."gbtreekey32") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey4_in"("cstring") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey4_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey4_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey4_in"("cstring") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey4_out"("public"."gbtreekey4") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey4_out"("public"."gbtreekey4") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey4_out"("public"."gbtreekey4") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey4_out"("public"."gbtreekey4") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey8_in"("cstring") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey8_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey8_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey8_in"("cstring") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey8_out"("public"."gbtreekey8") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey8_out"("public"."gbtreekey8") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey8_out"("public"."gbtreekey8") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey8_out"("public"."gbtreekey8") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey_var_in"("cstring") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey_var_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey_var_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey_var_in"("cstring") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbtreekey_var_out"("public"."gbtreekey_var") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbtreekey_var_out"("public"."gbtreekey_var") TO "anon";
GRANT ALL ON FUNCTION "public"."gbtreekey_var_out"("public"."gbtreekey_var") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbtreekey_var_out"("public"."gbtreekey_var") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "service_role";






















































































































































GRANT ALL ON FUNCTION "public"."cash_dist"("money", "money") TO "postgres";
GRANT ALL ON FUNCTION "public"."cash_dist"("money", "money") TO "anon";
GRANT ALL ON FUNCTION "public"."cash_dist"("money", "money") TO "authenticated";
GRANT ALL ON FUNCTION "public"."cash_dist"("money", "money") TO "service_role";



GRANT ALL ON FUNCTION "public"."date_dist"("date", "date") TO "postgres";
GRANT ALL ON FUNCTION "public"."date_dist"("date", "date") TO "anon";
GRANT ALL ON FUNCTION "public"."date_dist"("date", "date") TO "authenticated";
GRANT ALL ON FUNCTION "public"."date_dist"("date", "date") TO "service_role";



REVOKE ALL ON FUNCTION "public"."doctor_patient_count"("p_doctor_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."doctor_patient_count"("p_doctor_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."doctor_patient_count"("p_doctor_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."doctor_patient_list"("p_doctor_id" "uuid", "p_term" "text", "p_limit" integer, "p_offset" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."doctor_patient_list"("p_doctor_id" "uuid", "p_term" "text", "p_limit" integer, "p_offset" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."doctor_patient_list"("p_doctor_id" "uuid", "p_term" "text", "p_limit" integer, "p_offset" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."enforce_append_only"() TO "anon";
GRANT ALL ON FUNCTION "public"."enforce_append_only"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."enforce_append_only"() TO "service_role";



GRANT ALL ON FUNCTION "public"."f_unaccent"("text") TO "anon";
GRANT ALL ON FUNCTION "public"."f_unaccent"("text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."f_unaccent"("text") TO "service_role";



GRANT ALL ON FUNCTION "public"."float4_dist"(real, real) TO "postgres";
GRANT ALL ON FUNCTION "public"."float4_dist"(real, real) TO "anon";
GRANT ALL ON FUNCTION "public"."float4_dist"(real, real) TO "authenticated";
GRANT ALL ON FUNCTION "public"."float4_dist"(real, real) TO "service_role";



GRANT ALL ON FUNCTION "public"."float8_dist"(double precision, double precision) TO "postgres";
GRANT ALL ON FUNCTION "public"."float8_dist"(double precision, double precision) TO "anon";
GRANT ALL ON FUNCTION "public"."float8_dist"(double precision, double precision) TO "authenticated";
GRANT ALL ON FUNCTION "public"."float8_dist"(double precision, double precision) TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bit_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bit_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bit_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bit_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bit_consistent"("internal", bit, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bit_consistent"("internal", bit, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bit_consistent"("internal", bit, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bit_consistent"("internal", bit, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bit_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bit_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bit_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bit_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bit_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bit_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bit_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bit_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bit_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bit_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bit_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bit_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bit_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bit_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bit_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bit_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bool_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bool_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bool_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bool_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bool_consistent"("internal", boolean, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bool_consistent"("internal", boolean, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bool_consistent"("internal", boolean, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bool_consistent"("internal", boolean, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bool_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bool_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bool_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bool_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bool_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bool_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bool_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bool_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bool_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bool_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bool_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bool_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bool_same"("public"."gbtreekey2", "public"."gbtreekey2", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bool_same"("public"."gbtreekey2", "public"."gbtreekey2", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bool_same"("public"."gbtreekey2", "public"."gbtreekey2", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bool_same"("public"."gbtreekey2", "public"."gbtreekey2", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bool_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bool_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bool_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bool_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bpchar_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bpchar_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bpchar_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bpchar_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bpchar_consistent"("internal", character, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bpchar_consistent"("internal", character, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bpchar_consistent"("internal", character, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bpchar_consistent"("internal", character, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bytea_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bytea_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bytea_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bytea_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bytea_consistent"("internal", "bytea", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bytea_consistent"("internal", "bytea", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bytea_consistent"("internal", "bytea", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bytea_consistent"("internal", "bytea", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bytea_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bytea_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bytea_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bytea_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bytea_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bytea_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bytea_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bytea_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bytea_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bytea_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bytea_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bytea_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_bytea_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_bytea_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_bytea_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_bytea_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_consistent"("internal", "money", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_consistent"("internal", "money", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_consistent"("internal", "money", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_consistent"("internal", "money", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_distance"("internal", "money", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_distance"("internal", "money", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_distance"("internal", "money", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_distance"("internal", "money", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_cash_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_cash_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_cash_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_cash_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_consistent"("internal", "date", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_consistent"("internal", "date", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_consistent"("internal", "date", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_consistent"("internal", "date", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_distance"("internal", "date", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_distance"("internal", "date", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_distance"("internal", "date", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_distance"("internal", "date", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_date_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_date_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_date_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_date_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_decompress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_decompress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_decompress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_decompress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_enum_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_enum_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_enum_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_enum_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_enum_consistent"("internal", "anyenum", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_enum_consistent"("internal", "anyenum", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_enum_consistent"("internal", "anyenum", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_enum_consistent"("internal", "anyenum", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_enum_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_enum_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_enum_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_enum_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_enum_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_enum_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_enum_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_enum_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_enum_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_enum_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_enum_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_enum_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_enum_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_enum_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_enum_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_enum_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_enum_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_enum_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_enum_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_enum_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_consistent"("internal", real, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_consistent"("internal", real, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_consistent"("internal", real, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_consistent"("internal", real, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_distance"("internal", real, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_distance"("internal", real, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_distance"("internal", real, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_distance"("internal", real, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float4_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float4_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float4_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float4_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_consistent"("internal", double precision, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_consistent"("internal", double precision, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_consistent"("internal", double precision, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_consistent"("internal", double precision, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_distance"("internal", double precision, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_distance"("internal", double precision, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_distance"("internal", double precision, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_distance"("internal", double precision, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_float8_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_float8_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_float8_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_float8_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_inet_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_inet_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_inet_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_inet_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_inet_consistent"("internal", "inet", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_inet_consistent"("internal", "inet", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_inet_consistent"("internal", "inet", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_inet_consistent"("internal", "inet", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_inet_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_inet_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_inet_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_inet_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_inet_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_inet_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_inet_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_inet_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_inet_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_inet_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_inet_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_inet_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_inet_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_inet_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_inet_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_inet_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_consistent"("internal", smallint, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_consistent"("internal", smallint, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_consistent"("internal", smallint, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_consistent"("internal", smallint, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_distance"("internal", smallint, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_distance"("internal", smallint, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_distance"("internal", smallint, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_distance"("internal", smallint, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_same"("public"."gbtreekey4", "public"."gbtreekey4", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_same"("public"."gbtreekey4", "public"."gbtreekey4", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_same"("public"."gbtreekey4", "public"."gbtreekey4", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_same"("public"."gbtreekey4", "public"."gbtreekey4", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int2_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int2_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int2_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int2_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_consistent"("internal", integer, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_consistent"("internal", integer, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_consistent"("internal", integer, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_consistent"("internal", integer, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_distance"("internal", integer, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_distance"("internal", integer, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_distance"("internal", integer, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_distance"("internal", integer, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int4_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int4_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int4_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int4_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_consistent"("internal", bigint, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_consistent"("internal", bigint, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_consistent"("internal", bigint, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_consistent"("internal", bigint, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_distance"("internal", bigint, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_distance"("internal", bigint, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_distance"("internal", bigint, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_distance"("internal", bigint, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_int8_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_int8_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_int8_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_int8_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_consistent"("internal", interval, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_consistent"("internal", interval, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_consistent"("internal", interval, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_consistent"("internal", interval, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_decompress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_decompress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_decompress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_decompress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_distance"("internal", interval, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_distance"("internal", interval, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_distance"("internal", interval, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_distance"("internal", interval, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_intv_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_intv_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_intv_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_intv_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad8_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad8_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad8_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad8_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad8_consistent"("internal", "macaddr8", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad8_consistent"("internal", "macaddr8", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad8_consistent"("internal", "macaddr8", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad8_consistent"("internal", "macaddr8", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad8_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad8_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad8_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad8_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad8_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad8_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad8_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad8_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad8_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad8_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad8_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad8_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad8_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad8_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad8_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad8_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad8_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad_consistent"("internal", "macaddr", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad_consistent"("internal", "macaddr", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad_consistent"("internal", "macaddr", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad_consistent"("internal", "macaddr", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_macad_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_macad_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_macad_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_macad_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_numeric_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_numeric_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_numeric_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_numeric_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_numeric_consistent"("internal", numeric, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_numeric_consistent"("internal", numeric, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_numeric_consistent"("internal", numeric, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_numeric_consistent"("internal", numeric, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_numeric_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_numeric_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_numeric_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_numeric_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_numeric_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_numeric_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_numeric_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_numeric_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_numeric_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_numeric_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_numeric_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_numeric_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_numeric_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_numeric_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_numeric_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_numeric_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_consistent"("internal", "oid", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_consistent"("internal", "oid", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_consistent"("internal", "oid", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_consistent"("internal", "oid", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_distance"("internal", "oid", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_distance"("internal", "oid", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_distance"("internal", "oid", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_distance"("internal", "oid", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_same"("public"."gbtreekey8", "public"."gbtreekey8", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_oid_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_oid_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_oid_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_oid_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_text_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_text_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_text_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_text_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_text_consistent"("internal", "text", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_text_consistent"("internal", "text", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_text_consistent"("internal", "text", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_text_consistent"("internal", "text", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_text_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_text_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_text_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_text_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_text_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_text_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_text_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_text_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_text_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_text_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_text_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_text_same"("public"."gbtreekey_var", "public"."gbtreekey_var", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_text_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_text_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_text_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_text_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_consistent"("internal", time without time zone, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_consistent"("internal", time without time zone, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_consistent"("internal", time without time zone, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_consistent"("internal", time without time zone, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_distance"("internal", time without time zone, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_distance"("internal", time without time zone, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_distance"("internal", time without time zone, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_distance"("internal", time without time zone, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_time_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_time_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_time_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_time_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_timetz_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_timetz_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_timetz_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_timetz_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_timetz_consistent"("internal", time with time zone, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_timetz_consistent"("internal", time with time zone, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_timetz_consistent"("internal", time with time zone, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_timetz_consistent"("internal", time with time zone, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_consistent"("internal", timestamp without time zone, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_consistent"("internal", timestamp without time zone, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_consistent"("internal", timestamp without time zone, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_consistent"("internal", timestamp without time zone, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_distance"("internal", timestamp without time zone, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_distance"("internal", timestamp without time zone, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_distance"("internal", timestamp without time zone, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_distance"("internal", timestamp without time zone, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_same"("public"."gbtreekey16", "public"."gbtreekey16", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_ts_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_ts_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_ts_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_ts_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_tstz_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_tstz_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_tstz_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_tstz_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_tstz_consistent"("internal", timestamp with time zone, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_tstz_consistent"("internal", timestamp with time zone, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_tstz_consistent"("internal", timestamp with time zone, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_tstz_consistent"("internal", timestamp with time zone, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_tstz_distance"("internal", timestamp with time zone, smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_tstz_distance"("internal", timestamp with time zone, smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_tstz_distance"("internal", timestamp with time zone, smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_tstz_distance"("internal", timestamp with time zone, smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_uuid_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_uuid_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_uuid_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_uuid_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_uuid_consistent"("internal", "uuid", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_uuid_consistent"("internal", "uuid", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_uuid_consistent"("internal", "uuid", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_uuid_consistent"("internal", "uuid", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_uuid_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_uuid_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_uuid_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_uuid_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_uuid_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_uuid_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_uuid_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_uuid_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_uuid_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_uuid_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_uuid_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_uuid_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_uuid_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_uuid_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_uuid_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_uuid_same"("public"."gbtreekey32", "public"."gbtreekey32", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_uuid_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_uuid_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_uuid_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_uuid_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_var_decompress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_var_decompress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_var_decompress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_var_decompress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gbt_var_fetch"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gbt_var_fetch"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gbt_var_fetch"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gbt_var_fetch"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."int2_dist"(smallint, smallint) TO "postgres";
GRANT ALL ON FUNCTION "public"."int2_dist"(smallint, smallint) TO "anon";
GRANT ALL ON FUNCTION "public"."int2_dist"(smallint, smallint) TO "authenticated";
GRANT ALL ON FUNCTION "public"."int2_dist"(smallint, smallint) TO "service_role";



GRANT ALL ON FUNCTION "public"."int4_dist"(integer, integer) TO "postgres";
GRANT ALL ON FUNCTION "public"."int4_dist"(integer, integer) TO "anon";
GRANT ALL ON FUNCTION "public"."int4_dist"(integer, integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."int4_dist"(integer, integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."int8_dist"(bigint, bigint) TO "postgres";
GRANT ALL ON FUNCTION "public"."int8_dist"(bigint, bigint) TO "anon";
GRANT ALL ON FUNCTION "public"."int8_dist"(bigint, bigint) TO "authenticated";
GRANT ALL ON FUNCTION "public"."int8_dist"(bigint, bigint) TO "service_role";



GRANT ALL ON FUNCTION "public"."interval_dist"(interval, interval) TO "postgres";
GRANT ALL ON FUNCTION "public"."interval_dist"(interval, interval) TO "anon";
GRANT ALL ON FUNCTION "public"."interval_dist"(interval, interval) TO "authenticated";
GRANT ALL ON FUNCTION "public"."interval_dist"(interval, interval) TO "service_role";



GRANT ALL ON FUNCTION "public"."oid_dist"("oid", "oid") TO "postgres";
GRANT ALL ON FUNCTION "public"."oid_dist"("oid", "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."oid_dist"("oid", "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."oid_dist"("oid", "oid") TO "service_role";



GRANT ALL ON FUNCTION "public"."prevent_hard_delete"() TO "anon";
GRANT ALL ON FUNCTION "public"."prevent_hard_delete"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."prevent_hard_delete"() TO "service_role";



GRANT ALL ON FUNCTION "public"."rls_auto_enable"() TO "anon";
GRANT ALL ON FUNCTION "public"."rls_auto_enable"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."rls_auto_enable"() TO "service_role";



GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "postgres";
GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "anon";
GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "service_role";



GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."show_limit"() TO "postgres";
GRANT ALL ON FUNCTION "public"."show_limit"() TO "anon";
GRANT ALL ON FUNCTION "public"."show_limit"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."show_limit"() TO "service_role";



GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "postgres";
GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "anon";
GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "service_role";



GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."time_dist"(time without time zone, time without time zone) TO "postgres";
GRANT ALL ON FUNCTION "public"."time_dist"(time without time zone, time without time zone) TO "anon";
GRANT ALL ON FUNCTION "public"."time_dist"(time without time zone, time without time zone) TO "authenticated";
GRANT ALL ON FUNCTION "public"."time_dist"(time without time zone, time without time zone) TO "service_role";



GRANT ALL ON FUNCTION "public"."ts_dist"(timestamp without time zone, timestamp without time zone) TO "postgres";
GRANT ALL ON FUNCTION "public"."ts_dist"(timestamp without time zone, timestamp without time zone) TO "anon";
GRANT ALL ON FUNCTION "public"."ts_dist"(timestamp without time zone, timestamp without time zone) TO "authenticated";
GRANT ALL ON FUNCTION "public"."ts_dist"(timestamp without time zone, timestamp without time zone) TO "service_role";



GRANT ALL ON FUNCTION "public"."tstz_dist"(timestamp with time zone, timestamp with time zone) TO "postgres";
GRANT ALL ON FUNCTION "public"."tstz_dist"(timestamp with time zone, timestamp with time zone) TO "anon";
GRANT ALL ON FUNCTION "public"."tstz_dist"(timestamp with time zone, timestamp with time zone) TO "authenticated";
GRANT ALL ON FUNCTION "public"."tstz_dist"(timestamp with time zone, timestamp with time zone) TO "service_role";



GRANT ALL ON FUNCTION "public"."unaccent"("text") TO "postgres";
GRANT ALL ON FUNCTION "public"."unaccent"("text") TO "anon";
GRANT ALL ON FUNCTION "public"."unaccent"("text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."unaccent"("text") TO "service_role";



GRANT ALL ON FUNCTION "public"."unaccent"("regdictionary", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."unaccent"("regdictionary", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."unaccent"("regdictionary", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."unaccent"("regdictionary", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."unaccent_init"("internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."unaccent_init"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."unaccent_init"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."unaccent_init"("internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."unaccent_lexize"("internal", "internal", "internal", "internal") TO "postgres";
GRANT ALL ON FUNCTION "public"."unaccent_lexize"("internal", "internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."unaccent_lexize"("internal", "internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."unaccent_lexize"("internal", "internal", "internal", "internal") TO "service_role";



GRANT ALL ON FUNCTION "public"."visit_amendment_append_only"() TO "anon";
GRANT ALL ON FUNCTION "public"."visit_amendment_append_only"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."visit_amendment_append_only"() TO "service_role";



GRANT ALL ON FUNCTION "public"."visit_finalized_block_update"() TO "anon";
GRANT ALL ON FUNCTION "public"."visit_finalized_block_update"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."visit_finalized_block_update"() TO "service_role";



GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "service_role";


















GRANT ALL ON TABLE "public"."appointment" TO "anon";
GRANT ALL ON TABLE "public"."appointment" TO "authenticated";
GRANT ALL ON TABLE "public"."appointment" TO "service_role";



GRANT ALL ON TABLE "public"."block_budget" TO "anon";
GRANT ALL ON TABLE "public"."block_budget" TO "authenticated";
GRANT ALL ON TABLE "public"."block_budget" TO "service_role";



GRANT ALL ON TABLE "public"."booking_channel" TO "anon";
GRANT ALL ON TABLE "public"."booking_channel" TO "authenticated";
GRANT ALL ON TABLE "public"."booking_channel" TO "service_role";



GRANT ALL ON TABLE "public"."care_episode" TO "anon";
GRANT ALL ON TABLE "public"."care_episode" TO "authenticated";
GRANT ALL ON TABLE "public"."care_episode" TO "service_role";



GRANT ALL ON TABLE "public"."clinic_location" TO "anon";
GRANT ALL ON TABLE "public"."clinic_location" TO "authenticated";
GRANT ALL ON TABLE "public"."clinic_location" TO "service_role";



GRANT ALL ON TABLE "public"."clinical_form_response" TO "anon";
GRANT ALL ON TABLE "public"."clinical_form_response" TO "authenticated";
GRANT ALL ON TABLE "public"."clinical_form_response" TO "service_role";



GRANT ALL ON TABLE "public"."clinical_record" TO "anon";
GRANT ALL ON TABLE "public"."clinical_record" TO "authenticated";
GRANT ALL ON TABLE "public"."clinical_record" TO "service_role";



GRANT ALL ON TABLE "public"."cskh_action" TO "anon";
GRANT ALL ON TABLE "public"."cskh_action" TO "authenticated";
GRANT ALL ON TABLE "public"."cskh_action" TO "service_role";



GRANT ALL ON TABLE "public"."cskh_log" TO "anon";
GRANT ALL ON TABLE "public"."cskh_log" TO "authenticated";
GRANT ALL ON TABLE "public"."cskh_log" TO "service_role";



GRANT ALL ON TABLE "public"."drug_catalog" TO "anon";
GRANT ALL ON TABLE "public"."drug_catalog" TO "authenticated";
GRANT ALL ON TABLE "public"."drug_catalog" TO "service_role";



GRANT ALL ON TABLE "public"."event_log" TO "anon";
GRANT ALL ON TABLE "public"."event_log" TO "authenticated";
GRANT ALL ON TABLE "public"."event_log" TO "service_role";



GRANT ALL ON TABLE "public"."lab_result" TO "anon";
GRANT ALL ON TABLE "public"."lab_result" TO "authenticated";
GRANT ALL ON TABLE "public"."lab_result" TO "service_role";



GRANT ALL ON TABLE "public"."mpi_merge_queue" TO "anon";
GRANT ALL ON TABLE "public"."mpi_merge_queue" TO "authenticated";
GRANT ALL ON TABLE "public"."mpi_merge_queue" TO "service_role";



GRANT ALL ON TABLE "public"."patient" TO "anon";
GRANT ALL ON TABLE "public"."patient" TO "authenticated";
GRANT ALL ON TABLE "public"."patient" TO "service_role";



GRANT ALL ON TABLE "public"."patient_contact_channel" TO "anon";
GRANT ALL ON TABLE "public"."patient_contact_channel" TO "authenticated";
GRANT ALL ON TABLE "public"."patient_contact_channel" TO "service_role";



GRANT ALL ON TABLE "public"."patient_medical_profile" TO "anon";
GRANT ALL ON TABLE "public"."patient_medical_profile" TO "authenticated";
GRANT ALL ON TABLE "public"."patient_medical_profile" TO "service_role";



GRANT ALL ON TABLE "public"."patient_next_of_kin" TO "anon";
GRANT ALL ON TABLE "public"."patient_next_of_kin" TO "authenticated";
GRANT ALL ON TABLE "public"."patient_next_of_kin" TO "service_role";



GRANT ALL ON TABLE "public"."visit" TO "anon";
GRANT ALL ON TABLE "public"."visit" TO "authenticated";
GRANT ALL ON TABLE "public"."visit" TO "service_role";



GRANT ALL ON TABLE "public"."patient_summary" TO "anon";
GRANT ALL ON TABLE "public"."patient_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."patient_summary" TO "service_role";



GRANT ALL ON TABLE "public"."payment" TO "anon";
GRANT ALL ON TABLE "public"."payment" TO "authenticated";
GRANT ALL ON TABLE "public"."payment" TO "service_role";



GRANT ALL ON TABLE "public"."pregnancy" TO "anon";
GRANT ALL ON TABLE "public"."pregnancy" TO "authenticated";
GRANT ALL ON TABLE "public"."pregnancy" TO "service_role";



GRANT ALL ON TABLE "public"."prescription" TO "anon";
GRANT ALL ON TABLE "public"."prescription" TO "authenticated";
GRANT ALL ON TABLE "public"."prescription" TO "service_role";



GRANT ALL ON TABLE "public"."province" TO "anon";
GRANT ALL ON TABLE "public"."province" TO "authenticated";
GRANT ALL ON TABLE "public"."province" TO "service_role";



GRANT ALL ON TABLE "public"."schema_migrations" TO "anon";
GRANT ALL ON TABLE "public"."schema_migrations" TO "authenticated";
GRANT ALL ON TABLE "public"."schema_migrations" TO "service_role";



GRANT ALL ON TABLE "public"."service_log" TO "anon";
GRANT ALL ON TABLE "public"."service_log" TO "authenticated";
GRANT ALL ON TABLE "public"."service_log" TO "service_role";



GRANT ALL ON TABLE "public"."service_price" TO "anon";
GRANT ALL ON TABLE "public"."service_price" TO "authenticated";
GRANT ALL ON TABLE "public"."service_price" TO "service_role";



GRANT ALL ON TABLE "public"."service_type" TO "anon";
GRANT ALL ON TABLE "public"."service_type" TO "authenticated";
GRANT ALL ON TABLE "public"."service_type" TO "service_role";



GRANT ALL ON TABLE "public"."staff" TO "anon";
GRANT ALL ON TABLE "public"."staff" TO "authenticated";
GRANT ALL ON TABLE "public"."staff" TO "service_role";



GRANT ALL ON TABLE "public"."staff_capability" TO "anon";
GRANT ALL ON TABLE "public"."staff_capability" TO "authenticated";
GRANT ALL ON TABLE "public"."staff_capability" TO "service_role";



GRANT ALL ON TABLE "public"."staff_task" TO "anon";
GRANT ALL ON TABLE "public"."staff_task" TO "authenticated";
GRANT ALL ON TABLE "public"."staff_task" TO "service_role";



GRANT ALL ON TABLE "public"."ultrasound_record" TO "anon";
GRANT ALL ON TABLE "public"."ultrasound_record" TO "authenticated";
GRANT ALL ON TABLE "public"."ultrasound_record" TO "service_role";



GRANT ALL ON TABLE "public"."visit_amendment" TO "anon";
GRANT ALL ON TABLE "public"."visit_amendment" TO "authenticated";
GRANT ALL ON TABLE "public"."visit_amendment" TO "service_role";



GRANT ALL ON TABLE "public"."ward" TO "anon";
GRANT ALL ON TABLE "public"."ward" TO "authenticated";
GRANT ALL ON TABLE "public"."ward" TO "service_role";



GRANT ALL ON TABLE "public"."work_roster" TO "anon";
GRANT ALL ON TABLE "public"."work_roster" TO "authenticated";
GRANT ALL ON TABLE "public"."work_roster" TO "service_role";



GRANT ALL ON TABLE "public"."work_session" TO "anon";
GRANT ALL ON TABLE "public"."work_session" TO "authenticated";
GRANT ALL ON TABLE "public"."work_session" TO "service_role";



GRANT ALL ON TABLE "public"."work_session_staff" TO "anon";
GRANT ALL ON TABLE "public"."work_session_staff" TO "authenticated";
GRANT ALL ON TABLE "public"."work_session_staff" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";



































