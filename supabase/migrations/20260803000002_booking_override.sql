-- C.4 — Per-doctor and per-slot booking capacity overrides.
--
-- C.3 made the slot length and the two seat counts per-clinic. This migration
-- adds two override layers on top:
--
--   Tầng 2: doctor_booking_override  — per doctor, optionally per weekday
--   Tầng 3: slot_booking_override    — per doctor × date range × hour range
--
-- The resolve order is: slot_override → doctor_override → clinic default.
-- When no override exists, the system behaves exactly as before C.4.
--
-- Both tables carry clinic_id (tenant isolation) and created_by (audit).
-- The trigger enforce_slot_capacity() is updated to call the new resolver.

-- ---------------------------------------------------------------------------
-- 1. Tầng 2 — Doctor default override
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.doctor_booking_override (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic(id),
    doctor_id      uuid NOT NULL REFERENCES public.staff(id),
    weekday        smallint,   -- NULL = every day, 0=CN 1=T2 .. 6=T7
    slot_minutes   integer,    -- NULL = use clinic default
    regular_cap    integer,    -- NULL = use clinic default
    walkin_cap     integer,    -- NULL = use clinic default
    effective_from date NOT NULL DEFAULT current_date,
    effective_to   date,       -- NULL = indefinite
    created_by     uuid NOT NULL,
    reason         text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT doctor_override_weekday_range
        CHECK (weekday IS NULL OR weekday BETWEEN 0 AND 6),
    CONSTRAINT doctor_override_slot_minutes_range
        CHECK (slot_minutes IS NULL OR (slot_minutes BETWEEN 1 AND 60 AND 60 % slot_minutes = 0)),
    CONSTRAINT doctor_override_regular_cap_range
        CHECK (regular_cap IS NULL OR regular_cap BETWEEN 1 AND 100),
    CONSTRAINT doctor_override_walkin_cap_range
        CHECK (walkin_cap IS NULL OR walkin_cap BETWEEN 0 AND 100),
    CONSTRAINT doctor_override_date_order
        CHECK (effective_to IS NULL OR effective_to >= effective_from),

    UNIQUE (clinic_id, doctor_id, weekday, effective_from)
);

COMMENT ON TABLE public.doctor_booking_override IS
  'C.4 Tầng 2: per-doctor booking capacity override. '
  'NULL fields fall back to clinic.settings.booking (Tầng 1).';

CREATE INDEX IF NOT EXISTS idx_doctor_override_lookup
    ON public.doctor_booking_override (clinic_id, doctor_id, effective_from);

-- ---------------------------------------------------------------------------
-- 2. Tầng 3 — Slot override (date range + hour range)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.slot_booking_override (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       uuid NOT NULL REFERENCES public.clinic(id),
    doctor_id       uuid REFERENCES public.staff(id), -- NULL = any doctor
    date_start      date NOT NULL,
    date_end        date NOT NULL,              -- inclusive
    hour_start      smallint NOT NULL,          -- 0–23
    hour_end        smallint NOT NULL,           -- 1–24, exclusive
    regular_cap     integer,                    -- NULL = use lower tier
    walkin_cap      integer,                    -- NULL = use lower tier
    reason          text NOT NULL,              -- Trưởng ca phải ghi lý do
    created_by      uuid NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT slot_override_date_order
        CHECK (date_end >= date_start),
    CONSTRAINT slot_override_hour_range
        CHECK (hour_start BETWEEN 0 AND 23 AND hour_end BETWEEN 1 AND 24
               AND hour_end > hour_start),
    CONSTRAINT slot_override_regular_cap_range
        CHECK (regular_cap IS NULL OR regular_cap BETWEEN 1 AND 100),
    CONSTRAINT slot_override_walkin_cap_range
        CHECK (walkin_cap IS NULL OR walkin_cap BETWEEN 0 AND 100),
    CONSTRAINT slot_override_has_cap
        CHECK (regular_cap IS NOT NULL OR walkin_cap IS NOT NULL),
    CONSTRAINT slot_override_max_range
        CHECK (date_end - date_start <= 90)
);

COMMENT ON TABLE public.slot_booking_override IS
  'C.4 Tầng 3: per-date-range + per-hour slot capacity override. '
  'doctor_id NULL = applies to any doctor. reason is mandatory. '
  'Max range 90 days. NULL cap fields fall back to lower tiers.';

CREATE INDEX IF NOT EXISTS idx_slot_override_lookup
    ON public.slot_booking_override (clinic_id, date_start, date_end);

-- ---------------------------------------------------------------------------
-- 3. Resolver — 3-tier fallback
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.resolve_effective_cap(
    p_clinic_id uuid,
    p_doctor_id uuid,
    p_slot_start timestamptz
)
RETURNS TABLE (slot_minutes integer, regular_cap integer, walkin_cap integer)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_date    date;
    v_hour    smallint;
    v_weekday smallint;
    v_slot    record;
    v_doc     record;
    v_clinic  record;
BEGIN
    v_date    := (p_slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    v_hour    := EXTRACT(HOUR FROM p_slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::smallint;
    v_weekday := EXTRACT(DOW FROM p_slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::smallint;

    -- Tầng 3: slot override (doctor-specific wins over any-doctor).
    SELECT s.regular_cap, s.walkin_cap
      INTO v_slot
      FROM public.slot_booking_override s
     WHERE s.clinic_id = p_clinic_id
       AND (s.doctor_id = p_doctor_id OR s.doctor_id IS NULL)
       AND v_date BETWEEN s.date_start AND s.date_end
       AND v_hour >= s.hour_start AND v_hour < s.hour_end
     ORDER BY s.doctor_id IS NULL,
              s.date_start DESC
     LIMIT 1;

    -- Tầng 2: doctor override (weekday-specific wins over any-day).
    IF p_doctor_id IS NOT NULL THEN
        SELECT d.slot_minutes, d.regular_cap, d.walkin_cap
          INTO v_doc
          FROM public.doctor_booking_override d
         WHERE d.clinic_id = p_clinic_id
           AND d.doctor_id = p_doctor_id
           AND d.effective_from <= v_date
           AND (d.effective_to IS NULL OR d.effective_to >= v_date)
           AND (d.weekday IS NULL OR d.weekday = v_weekday)
         ORDER BY d.weekday IS NULL,
                  d.effective_from DESC
         LIMIT 1;
    END IF;

    -- Tầng 1: clinic default.
    SELECT p.slot_minutes, p.regular_cap, p.walkin_cap
      INTO v_clinic
      FROM public.clinic_booking_policy(p_clinic_id) p;

    -- Merge: slot > doctor > clinic, per field.
    RETURN QUERY SELECT
        coalesce(v_doc.slot_minutes, v_clinic.slot_minutes)   AS slot_minutes,
        coalesce(v_slot.regular_cap, v_doc.regular_cap, v_clinic.regular_cap) AS regular_cap,
        coalesce(v_slot.walkin_cap, v_doc.walkin_cap, v_clinic.walkin_cap)     AS walkin_cap;
END;
$function$;

COMMENT ON FUNCTION public.resolve_effective_cap(uuid, uuid, timestamptz) IS
  'C.4: 3-tier booking capacity resolver. '
  'slot_override -> doctor_override -> clinic_booking_policy. '
  'Returns one row with the effective (slot_minutes, regular_cap, walkin_cap).';

-- ---------------------------------------------------------------------------
-- 4. Updated enforcer — uses the 3-tier resolver
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.enforce_slot_capacity()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    dead         text[] := ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'];
    none         text   := '~none~';
    bucket_start timestamptz;
    bucket_end   timestamptz;
    v_walkin     boolean;
    v_minutes    integer;
    v_seconds    integer;
    cap          integer;
    live_count   integer;
    lock_key     bigint;
BEGIN
    IF NEW.status = ANY (dead) THEN
        RETURN NEW;
    END IF;

    v_walkin := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';

    -- C.4: resolve from 3-tier override stack instead of clinic-only.
    SELECT p.slot_minutes,
           CASE WHEN v_walkin THEN p.walkin_cap ELSE p.regular_cap END
      INTO v_minutes, cap
      FROM public.resolve_effective_cap(NEW.clinic_id, NEW.doctor_id, NEW.slot_start) AS p;

    v_seconds    := v_minutes * 60;
    bucket_start := to_timestamp(
        floor(extract(epoch FROM NEW.slot_start) / v_seconds) * v_seconds);
    bucket_end   := bucket_start + make_interval(mins => v_minutes);

    lock_key := hashtextextended(
        NEW.clinic_id::text || '|'
        || coalesce(NEW.doctor_id::text, none) || '|'
        || to_char(bucket_start, 'YYYYMMDDHH24MI') || '|'
        || (CASE WHEN v_walkin THEN 'w' ELSE 'r' END),
        0);
    PERFORM pg_advisory_xact_lock(lock_key);

    SELECT count(*) INTO live_count
    FROM public.appointment a
    WHERE a.id <> NEW.id
      AND a.clinic_id = NEW.clinic_id
      AND coalesce(a.doctor_id::text, none) = coalesce(NEW.doctor_id::text, none)
      AND a.slot_start >= bucket_start
      AND a.slot_start <  bucket_end
      AND NOT (a.status = ANY (dead))
      AND (upper(coalesce(a.booking_channel, '')) = 'WALK_IN') = v_walkin;

    IF live_count >= cap THEN
        RAISE EXCEPTION
            'Khung giờ đã đầy: tối đa % chỗ % cho bác sĩ này trong khung % phút.',
            cap,
            CASE WHEN v_walkin THEN 'vãng lai' ELSE 'lịch hẹn' END,
            v_minutes
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.enforce_slot_capacity() IS
  'CAP-01 per (clinic, doctor, bucket, walk-in/booked). C.4: reads from '
  'resolve_effective_cap() (3-tier: slot -> doctor -> clinic).';

-- ---------------------------------------------------------------------------
-- 5. Grants
-- ---------------------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE ON public.doctor_booking_override TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.slot_booking_override TO service_role;

-- ---------------------------------------------------------------------------
-- 6. Display config seed for existing clinics
-- ---------------------------------------------------------------------------

UPDATE public.clinic
   SET settings = jsonb_set(
           settings,
           '{display}',
           '{
             "zones": [
               {"key": "kham", "label": "Khám bác sĩ", "prefix": "C"},
               {"key": "sa1",  "label": "SA1", "prefix": "SA"},
               {"key": "sa2",  "label": "SA2", "prefix": "SA"},
               {"key": "sa3",  "label": "SA3", "prefix": "SA"},
               {"key": "xn",   "label": "Xét nghiệm", "prefix": "X"},
               {"key": "tt",   "label": "Thanh toán", "prefix": "T"}
             ],
             "footer_text": "Vui lòng chờ đến lượt số của mình",
             "footer_info": "WiFi: Dr4Women · Hotline: 1900 0000",
             "clinic_name": "ClinicAI"
           }'::jsonb,
           true
       )
 WHERE NOT (settings ? 'display');
