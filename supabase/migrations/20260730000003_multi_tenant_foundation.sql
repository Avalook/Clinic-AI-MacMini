-- W2 — Multi-tenant foundation (ADR-0009).
--
-- Before this migration the schema had ZERO tenant columns: `grep -c clinic_id`
-- over the baseline returned 0. `clinic_location` is a branch/site, not a
-- tenant. Onboarding a second clinic would have meant every user reading every
-- other clinic's data.
--
-- This migration introduces the tenant and threads it through every business
-- table, but deliberately does NOT change any RLS policy yet — the tenant-scoped
-- policies need `staff.auth_user_id` populated, which is W3. Until then the
-- existing `USING (true)` policies stay in force and behaviour is unchanged.
--
-- TRANSITIONAL DEFAULT: `clinic_id` is NOT NULL with a default of
-- `public.default_clinic_id()`, which resolves to the one and only clinic while
-- exactly one exists and to NULL as soon as a second one is created. That keeps
-- the running V1 code (which knows nothing about tenants) working today, and
-- turns into a hard NOT NULL failure the moment a real second tenant appears —
-- so the default cannot silently mis-assign rows. W5 removes it once the backend
-- always supplies clinic_id from the JWT.

-- ---------------------------------------------------------------------------
-- 1. Tenant tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.clinic (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    legal_name text,
    tax_code text,
    address text,
    timezone text DEFAULT 'Asia/Ho_Chi_Minh' NOT NULL,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT clinic_pkey PRIMARY KEY (id),
    CONSTRAINT clinic_code_key UNIQUE (code)
);

COMMENT ON TABLE public.clinic IS
  'Tenant. One row per phòng khám. Dr4Women is tenant #1.';

-- staff is intentionally NOT tenant-scoped by a column: a doctor may work at
-- more than one clinic. Membership is the join, and it carries the role for
-- that clinic (a person can be MANAGEMENT at one site and DOCTOR at another).
CREATE TABLE IF NOT EXISTS public.clinic_membership (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid NOT NULL,
    staff_id uuid NOT NULL,
    role text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT clinic_membership_pkey PRIMARY KEY (id),
    CONSTRAINT clinic_membership_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT clinic_membership_staff_id_fkey FOREIGN KEY (staff_id)
        REFERENCES public.staff(id) ON DELETE CASCADE,
    CONSTRAINT uq_clinic_membership UNIQUE (clinic_id, staff_id, role),
    -- Mirrors staff_primary_department_check: the 11 department codes in
    -- src/dashboard/lib/roles.ts.
    CONSTRAINT clinic_membership_role_check CHECK (role = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC', 'CASHIER_DV'
    ]))
);

CREATE INDEX IF NOT EXISTS idx_clinic_membership_staff ON public.clinic_membership (staff_id);
CREATE INDEX IF NOT EXISTS idx_clinic_membership_clinic ON public.clinic_membership (clinic_id) WHERE is_active;

-- ---------------------------------------------------------------------------
-- 2. Tenant #1 — Dr4Women. Fixed id so every environment agrees.
-- ---------------------------------------------------------------------------

INSERT INTO public.clinic (id, code, name)
VALUES ('a0000000-0000-4000-8000-000000000001', 'DR4WOMEN', 'Phòng khám Dr4Women')
ON CONFLICT (id) DO NOTHING;


CREATE OR REPLACE FUNCTION public.default_clinic_id()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT c.id FROM public.clinic c
    WHERE (SELECT count(*) FROM public.clinic) = 1
$$;

COMMENT ON FUNCTION public.default_clinic_id() IS
  'TRANSITIONAL (W2 -> W5). Resolves to the single tenant while only one exists, '
  'NULL otherwise, so adding a second clinic turns silent mis-assignment into a '
  'NOT NULL error. Drop the column defaults once the backend always passes clinic_id.';

-- ---------------------------------------------------------------------------
-- 3. clinic_id on every business + per-clinic-config table
-- ---------------------------------------------------------------------------
-- Excluded on purpose:
--   province, ward        national reference data, shared by all tenants
--   staff, staff_capability  scoped through clinic_membership (multi-clinic staff)
--   idempotency_key       infra, already actor-scoped and short-lived
--   schema_migrations     CLI bookkeeping

DO $tenant$
DECLARE
    t text;
    tables text[] := ARRAY[
        'appointment', 'block_budget', 'booking_channel', 'care_episode',
        'clinic_location', 'clinical_form_response', 'clinical_record',
        'cskh_action', 'cskh_log', 'drug_catalog', 'event_log', 'lab_result',
        'mpi_merge_queue', 'patient', 'patient_medical_profile', 'payment',
        'pregnancy', 'prescription', 'service_log', 'service_price',
        'service_type', 'staff_task', 'ultrasound_record', 'visit',
        'work_roster', 'work_session', 'work_session_staff'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS clinic_id uuid', t);

        -- Backfill: everything that exists today belongs to Dr4Women.
        EXECUTE format(
            'UPDATE public.%I SET clinic_id = %L WHERE clinic_id IS NULL',
            t, 'a0000000-0000-4000-8000-000000000001'
        );

        EXECUTE format(
            'ALTER TABLE public.%I ALTER COLUMN clinic_id SET DEFAULT public.default_clinic_id()', t
        );
        EXECUTE format('ALTER TABLE public.%I ALTER COLUMN clinic_id SET NOT NULL', t);

        EXECUTE format(
            'ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I', t, t || '_clinic_id_fkey'
        );
        EXECUTE format(
            'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (clinic_id) '
            'REFERENCES public.clinic(id) ON DELETE RESTRICT',
            t, t || '_clinic_id_fkey'
        );

        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS %I ON public.%I (clinic_id)', 'idx_' || t || '_clinic_id', t
        );
    END LOOP;
END
$tenant$;

-- ---------------------------------------------------------------------------
-- 4. Every natural/business unique key now carries the tenant
-- ---------------------------------------------------------------------------
-- Keys on uuid surrogate columns (visit_id, service_type_id, work_session_id,
-- clinic_patient_id ...) are already globally unique by construction and are
-- left alone. Only human-meaningful codes could collide across tenants.

ALTER TABLE public.booking_channel DROP CONSTRAINT IF EXISTS booking_channel_code_key;
ALTER TABLE public.booking_channel DROP CONSTRAINT IF EXISTS uq_booking_channel_clinic_code;
ALTER TABLE public.booking_channel ADD CONSTRAINT uq_booking_channel_clinic_code UNIQUE (clinic_id, code);

ALTER TABLE public.clinic_location DROP CONSTRAINT IF EXISTS clinic_location_code_key;
ALTER TABLE public.clinic_location DROP CONSTRAINT IF EXISTS uq_clinic_location_clinic_code;
ALTER TABLE public.clinic_location ADD CONSTRAINT uq_clinic_location_clinic_code UNIQUE (clinic_id, code);

ALTER TABLE public.service_type DROP CONSTRAINT IF EXISTS service_type_code_key;
ALTER TABLE public.service_type DROP CONSTRAINT IF EXISTS uq_service_type_clinic_code;
ALTER TABLE public.service_type ADD CONSTRAINT uq_service_type_clinic_code UNIQUE (clinic_id, code);

ALTER TABLE public.drug_catalog DROP CONSTRAINT IF EXISTS drug_catalog_name_raw_key;
ALTER TABLE public.drug_catalog DROP CONSTRAINT IF EXISTS uq_drug_catalog_clinic_name_raw;
ALTER TABLE public.drug_catalog ADD CONSTRAINT uq_drug_catalog_clinic_name_raw UNIQUE (clinic_id, name_raw);

ALTER TABLE public.patient DROP CONSTRAINT IF EXISTS patient_patient_code_key;
ALTER TABLE public.patient DROP CONSTRAINT IF EXISTS uq_patient_clinic_code;
ALTER TABLE public.patient ADD CONSTRAINT uq_patient_clinic_code UNIQUE (clinic_id, patient_code);

-- Same national id at two clinics = two patient records. That is correct:
-- each clinic owns its own chart for that person.
DROP INDEX IF EXISTS public.idx_patient_national_id_unique;
DROP INDEX IF EXISTS public.idx_patient_clinic_national_id_unique;
CREATE UNIQUE INDEX idx_patient_clinic_national_id_unique
    ON public.patient (clinic_id, national_id_number)
    WHERE national_id_number IS NOT NULL;

DROP INDEX IF EXISTS public.uq_service_price_code_group;
DROP INDEX IF EXISTS public.uq_service_price_clinic_code_group;
CREATE UNIQUE INDEX uq_service_price_clinic_code_group
    ON public.service_price (clinic_id, "group", service_code);

DROP INDEX IF EXISTS public.uq_block_budget_key;
CREATE UNIQUE INDEX uq_block_budget_key
    ON public.block_budget (
        clinic_id,
        location_id,
        COALESCE(doctor_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(weekday, 9),
        hour_start
    );

DROP INDEX IF EXISTS public.uq_care_episode_live;
CREATE UNIQUE INDEX uq_care_episode_live
    ON public.care_episode (clinic_id, clinic_patient_id, service_type_id)
    WHERE (status <> 'CLOSED'::text);

-- ---------------------------------------------------------------------------
-- 5. Membership backfill — every existing staff belongs to Dr4Women
-- ---------------------------------------------------------------------------

INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
SELECT 'a0000000-0000-4000-8000-000000000001', s.id, s.primary_department,
       COALESCE(s.is_active, true)
FROM public.staff s
ON CONFLICT ON CONSTRAINT uq_clinic_membership DO NOTHING;

-- ---------------------------------------------------------------------------
-- 6. Identity helpers used by the W3 tenant-scoped policies
-- ---------------------------------------------------------------------------
-- SECURITY DEFINER so a policy can consult staff/clinic_membership without the
-- caller needing read access to them — otherwise the policies would be
-- recursive. Both are read-only and take no arguments, so there is nothing to
-- inject.

CREATE OR REPLACE FUNCTION public.current_staff_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT s.id
    FROM public.staff s
    WHERE s.auth_user_id = auth.uid()
      AND COALESCE(s.is_active, true)
    LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.current_clinic_ids()
RETURNS SETOF uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT m.clinic_id
    FROM public.clinic_membership m
    WHERE m.staff_id = public.current_staff_id()
      AND m.is_active
$$;

CREATE OR REPLACE FUNCTION public.current_clinic_roles(p_clinic_id uuid)
RETURNS SETOF text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT m.role
    FROM public.clinic_membership m
    WHERE m.staff_id = public.current_staff_id()
      AND m.clinic_id = p_clinic_id
      AND m.is_active
$$;

REVOKE ALL ON FUNCTION public.current_staff_id() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.current_clinic_ids() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.current_clinic_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_staff_id() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.current_clinic_ids() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.current_clinic_roles(uuid) TO authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 7. Tenant tables are readable by their own members, writable by service_role
-- ---------------------------------------------------------------------------

ALTER TABLE public.clinic ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_membership ENABLE ROW LEVEL SECURITY;

-- Read-only for end users; every write goes through the backend (ADR-0012).
GRANT SELECT ON public.clinic, public.clinic_membership TO authenticated;
GRANT ALL ON public.clinic, public.clinic_membership TO service_role;

DROP POLICY IF EXISTS clinic_select_own ON public.clinic;
CREATE POLICY clinic_select_own
    ON public.clinic
    FOR SELECT
    TO authenticated
    USING (id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS clinic_membership_select_own ON public.clinic_membership;
CREATE POLICY clinic_membership_select_own
    ON public.clinic_membership
    FOR SELECT
    TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- ---------------------------------------------------------------------------
-- MỘT PHÒNG KHÁM PHẢI CÓ ÍT NHẤT MỘT CƠ SỞ, ngay từ lúc được tạo.
--
-- Đây không phải luật mới — 20260803000007 đã khẳng định đúng điều đó, và
-- 20260804000012 đặt clinic_room.location_id NOT NULL. Nhưng cả hai đều nằm sau
-- migration này, nên trên một database TRẮNG có một quãng mà phòng khám tồn tại
-- và chưa có cơ sở nào; mọi thứ dựng trong quãng đó (phòng, nhân sự) đều lơ
-- lửng, và cả chuỗi migration đứt ở đúng chỗ đầu tiên đòi hỏi cơ sở.
--
-- Trên production không đổi gì: cơ sở đã có sẵn từ seed, ON CONFLICT bỏ qua.
INSERT INTO public.clinic_location (clinic_id, code, name, is_active)
SELECT c.id, 'MAIN', c.name, true
  FROM public.clinic c
 WHERE NOT EXISTS (SELECT 1 FROM public.clinic_location l
                    WHERE l.clinic_id = c.id)
ON CONFLICT ON CONSTRAINT uq_clinic_location_clinic_code DO NOTHING;
