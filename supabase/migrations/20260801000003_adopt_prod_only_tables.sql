-- Ba bảng chỉ có ở production, đưa vào schema đích trước khi bàn chuyển dữ liệu.
--
-- The dry-run diff found three tables that exist in production and NOT in this
-- repo's schema. One of them is production's LARGEST table:
--
--     visit_amendment            3,326 rows   record-amendment trail
--     patient_contact_channel       14 rows   Zalo/phone/email channels
--     patient_next_of_kin           10 rows   next of kin
--
-- visit_amendment is the trail of corrections to clinical records — precisely
-- what Thông tư 13 requires an electronic medical record to keep, and
-- production's own trigger message cites it. A cutover that took this repo's
-- schema as the target would have deleted 3,326 rows of medico-legal history,
-- and would have done it without a word. That is why the diff was run before
-- the migration and not after.
--
-- Definitions are lifted from the production dump so the shapes match exactly
-- and the data can move across without transformation. What is ADDED here is
-- what the rest of this schema already has and production's copies lack:
-- clinic_id, tenant-scoped RLS, and foreign keys.

-- ---------------------------------------------------------------------------
-- 1. visit_amendment — append-only by construction
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.visit_amendment (
    amendment_id     uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id        uuid NOT NULL,
    visit_id         uuid NOT NULL,
    amended_by       uuid NOT NULL,
    amended_at       timestamptz DEFAULT now() NOT NULL,
    reason           text NOT NULL,
    corrected_fields text[] NOT NULL,
    original_values  jsonb NOT NULL,
    corrected_values jsonb NOT NULL,
    CONSTRAINT visit_amendment_pkey PRIMARY KEY (amendment_id),
    CONSTRAINT visit_amendment_clinic_fk
        FOREIGN KEY (clinic_id) REFERENCES public.clinic (id),
    CONSTRAINT visit_amendment_visit_fk
        FOREIGN KEY (visit_id) REFERENCES public.visit (visit_id),
    -- A correction that names no field and gives no reason is not a correction.
    CONSTRAINT visit_amendment_has_fields CHECK (cardinality(corrected_fields) > 0),
    CONSTRAINT visit_amendment_has_reason CHECK (btrim(reason) <> '')
);

CREATE INDEX IF NOT EXISTS idx_visit_amendment_visit
    ON public.visit_amendment (clinic_id, visit_id, amended_at DESC);

-- Production's own guard, kept verbatim in intent: the whole value of an
-- amendment trail is that it cannot be amended.
CREATE OR REPLACE FUNCTION public.visit_amendment_append_only()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    RAISE EXCEPTION
        'visit_amendment is append-only; UPDATE/DELETE not permitted (TT13/2011/TT-BYT)'
        USING ERRCODE = 'check_violation';
END;
$$;

DROP TRIGGER IF EXISTS trg_visit_amendment_append_only ON public.visit_amendment;
CREATE TRIGGER trg_visit_amendment_append_only
    BEFORE UPDATE OR DELETE ON public.visit_amendment
    FOR EACH ROW EXECUTE FUNCTION public.visit_amendment_append_only();

-- ---------------------------------------------------------------------------
-- 2. patient_contact_channel
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.patient_contact_channel (
    id                uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id         uuid NOT NULL,
    clinic_patient_id uuid NOT NULL,
    channel_type      text NOT NULL,
    channel_value     text NOT NULL,
    is_verified       boolean DEFAULT false NOT NULL,
    is_primary        boolean DEFAULT false NOT NULL,
    verified_at       timestamptz,
    created_at        timestamptz DEFAULT now(),
    CONSTRAINT patient_contact_channel_pkey PRIMARY KEY (id),
    CONSTRAINT patient_contact_channel_clinic_fk
        FOREIGN KEY (clinic_id) REFERENCES public.clinic (id),
    CONSTRAINT patient_contact_channel_patient_fk
        FOREIGN KEY (clinic_patient_id) REFERENCES public.patient (clinic_patient_id),
    CONSTRAINT patient_contact_channel_channel_type_check
        CHECK (channel_type = ANY (ARRAY['ZALO', 'PHONE', 'FACEBOOK', 'EMAIL', 'OTHER']))
);

CREATE INDEX IF NOT EXISTS idx_patient_contact_channel_patient
    ON public.patient_contact_channel (clinic_id, clinic_patient_id);

-- One primary channel per patient. Two "primary" numbers means the recall job
-- picks whichever the planner returns first.
CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_contact_channel_primary
    ON public.patient_contact_channel (clinic_id, clinic_patient_id)
    WHERE is_primary;

-- ---------------------------------------------------------------------------
-- 3. patient_next_of_kin
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.patient_next_of_kin (
    id                 uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id          uuid NOT NULL,
    clinic_patient_id  uuid NOT NULL,
    full_name          text NOT NULL,
    phone              text,
    relation           text NOT NULL,
    is_primary_contact boolean DEFAULT false NOT NULL,
    zalo_id            text,
    notes              text,
    created_at         timestamptz DEFAULT now(),
    updated_at         timestamptz DEFAULT now(),
    CONSTRAINT patient_next_of_kin_pkey PRIMARY KEY (id),
    CONSTRAINT patient_next_of_kin_clinic_fk
        FOREIGN KEY (clinic_id) REFERENCES public.clinic (id),
    CONSTRAINT patient_next_of_kin_patient_fk
        FOREIGN KEY (clinic_patient_id) REFERENCES public.patient (clinic_patient_id)
);

CREATE INDEX IF NOT EXISTS idx_patient_next_of_kin_patient
    ON public.patient_next_of_kin (clinic_id, clinic_patient_id);

-- ---------------------------------------------------------------------------
-- 4. Tenancy. Same shape as every other clinical table in this schema.
-- ---------------------------------------------------------------------------
ALTER TABLE public.visit_amendment          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_contact_channel  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_next_of_kin      ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS visit_amendment_tenant_select ON public.visit_amendment;
CREATE POLICY visit_amendment_tenant_select ON public.visit_amendment
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinical_clinic_ids()));

DROP POLICY IF EXISTS patient_contact_channel_tenant_select ON public.patient_contact_channel;
CREATE POLICY patient_contact_channel_tenant_select ON public.patient_contact_channel
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS patient_next_of_kin_tenant_select ON public.patient_next_of_kin;
CREATE POLICY patient_next_of_kin_tenant_select ON public.patient_next_of_kin
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- Amendments are clinical: only the roles that may read a record may read its
-- corrections. Contact channels and next of kin are administrative — reception
-- and CSKH need them to reach the patient.
GRANT SELECT ON public.visit_amendment          TO authenticated;
GRANT SELECT ON public.patient_contact_channel  TO authenticated;
GRANT SELECT ON public.patient_next_of_kin      TO authenticated;

COMMENT ON TABLE public.visit_amendment IS
  'Append-only trail of corrections to a visit (TT13). Adopted from the '
  'production schema during the cutover diff — 3,326 rows live there.';
