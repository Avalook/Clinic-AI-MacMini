-- Ordering services puts work in the room that performs it (20260801000002).
--
-- This is the output of LUOTKHAM-05, and the point where the spine stops being
-- a straight line: one selection fans out into the ultrasound room, the nurses'
-- station and wherever else the catalogue says. The properties below are the
-- ones that make it safe to run on a real clinic's day.
--
-- Everything rolls back.

BEGIN;

INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
VALUES ('aa000000-0000-4000-8000-0000000000cc',
        'a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000f1', 'OPEN');

-- ---------------------------------------------------------------------------
-- Several services of one kind are ONE trip to the room
-- ---------------------------------------------------------------------------
DO $groups_by_room$
DECLARE
    rooms integer;
    ultrasound_items integer;
    ultrasound_services integer;
    actor uuid;
BEGIN
    SELECT id INTO actor FROM public.staff WHERE full_name = 'BS A local';

    SELECT count(*) INTO rooms FROM public.order_services(
        'a0000000-0000-4000-8000-000000000001',
        'aa000000-0000-4000-8000-0000000000cc',
        ARRAY['CLS_SIEU_AM_O_BUNG', 'CLS_SIEU_AM_VU', 'CLS_XET_NGHIEM_MAU'],
        actor, 'DOCTOR');

    -- Three services, two rooms.
    IF rooms <> 2 THEN
        RAISE EXCEPTION 'expected 2 rooms, got %', rooms;
    END IF;

    SELECT count(*) INTO ultrasound_items
      FROM public.work_item
     WHERE visit_id = 'aa000000-0000-4000-8000-0000000000cc'
       AND node_code = 'DICHVU-SIEUAM' AND status <> 'CANCELLED';

    -- Two ultrasounds are one visit to the ultrasound room, and the catalogue
    -- says so: the node is named "Thực hiện siêu âm (nhóm)".
    IF ultrasound_items <> 1 THEN
        RAISE EXCEPTION 'two ultrasounds must be one work item, got %', ultrasound_items;
    END IF;

    SELECT jsonb_array_length(payload -> 'services') INTO ultrasound_services
      FROM public.work_item
     WHERE visit_id = 'aa000000-0000-4000-8000-0000000000cc'
       AND node_code = 'DICHVU-SIEUAM' AND status <> 'CANCELLED';

    IF ultrasound_services <> 2 THEN
        RAISE EXCEPTION 'the ultrasound item must carry both services, got %',
            ultrasound_services;
    END IF;
END
$groups_by_room$;

-- ---------------------------------------------------------------------------
-- Ordering more of the same kind appends, it does not duplicate
-- ---------------------------------------------------------------------------
DO $appends$
DECLARE
    items integer;
    services integer;
    actor uuid;
BEGIN
    SELECT id INTO actor FROM public.staff WHERE full_name = 'BS A local';

    PERFORM public.order_services(
        'a0000000-0000-4000-8000-000000000001',
        'aa000000-0000-4000-8000-0000000000cc',
        ARRAY['CLS_SIEU_AM_TUYEN_GIAP'], actor, 'DOCTOR');

    SELECT count(*), max(jsonb_array_length(payload -> 'services'))
      INTO items, services
      FROM public.work_item
     WHERE visit_id = 'aa000000-0000-4000-8000-0000000000cc'
       AND node_code = 'DICHVU-SIEUAM' AND status <> 'CANCELLED';

    -- A second live item for the same node would also violate
    -- uq_work_item_visit_node_live, so this is the index and the intent
    -- agreeing rather than two separate rules.
    IF items <> 1 THEN
        RAISE EXCEPTION 'a later order must not create a second room item, got %', items;
    END IF;
    IF services <> 3 THEN
        RAISE EXCEPTION 'the later service must be appended, services = %', services;
    END IF;
END
$appends$;

-- ---------------------------------------------------------------------------
-- A service with no room is REFUSED, and named
-- ---------------------------------------------------------------------------
DO $refuses_unmapped$
DECLARE
    refused boolean := false;
    msg text;
    actor uuid;
BEGIN
    SELECT id INTO actor FROM public.staff WHERE full_name = 'BS A local';
    BEGIN
        PERFORM public.order_services(
            'a0000000-0000-4000-8000-000000000001',
            'aa000000-0000-4000-8000-0000000000cc',
            ARRAY['CLS_KHAM_PHU_KHOA'], actor, 'DOCTOR');
    EXCEPTION WHEN raise_exception THEN
        refused := true;
        GET STACKED DIAGNOSTICS msg = MESSAGE_TEXT;
    END;

    IF NOT refused THEN
        RAISE EXCEPTION
            'a service with no node_code must be refused — defaulting it to some '
            'general node puts a patient outside a door nobody expects her at';
    END IF;
    -- Named, not counted: whoever reads this has to decide where that service
    -- is performed, and cannot do it from "1 service could not be ordered".
    IF position('CLS_KHAM_PHU_KHOA' IN msg) = 0 THEN
        RAISE EXCEPTION 'the refusal must name the service; got: %', msg;
    END IF;
END
$refuses_unmapped$;

-- ---------------------------------------------------------------------------
-- Another clinic's visit is refused
-- ---------------------------------------------------------------------------
DO $tenancy$
DECLARE
    refused boolean := false;
    actor uuid;
BEGIN
    SELECT id INTO actor FROM public.staff WHERE full_name = 'BS A local';
    INSERT INTO public.clinic (id, code, name)
    VALUES ('ac000000-0000-4000-8000-0000000000ac', 'ORDOTHER', 'PK khác')
    ON CONFLICT (id) DO NOTHING;

    BEGIN
        PERFORM public.order_services(
            'ac000000-0000-4000-8000-0000000000ac',
            'aa000000-0000-4000-8000-0000000000cc',
            ARRAY['CLS_SIEU_AM_VU'], actor, 'DOCTOR');
    EXCEPTION WHEN raise_exception THEN
        refused := true;
    END;

    IF NOT refused THEN
        RAISE EXCEPTION
            'ordering onto a visit another clinic owns must fail — the backend '
            'bypasses RLS, so this function is the only check';
    END IF;
END
$tenancy$;

-- ---------------------------------------------------------------------------
-- The duplicate warning reads the work items, because the work item IS the order
-- ---------------------------------------------------------------------------
DO $duplicates$
DECLARE
    hits integer;
BEGIN
    SELECT count(*) INTO hits
      FROM public.recent_duplicate_services(
          'a0000000-0000-4000-8000-000000000001',
          'e0000000-0000-4000-8000-0000000000f1',
          ARRAY['CLS_SIEU_AM_VU'], 30);
    IF hits = 0 THEN
        RAISE EXCEPTION 'a service ordered moments ago must show as a duplicate';
    END IF;

    SELECT count(*) INTO hits
      FROM public.recent_duplicate_services(
          'a0000000-0000-4000-8000-000000000001',
          'e0000000-0000-4000-8000-0000000000f1',
          ARRAY['CLS_SIEU_AM_KHOP'], 30);
    IF hits <> 0 THEN
        RAISE EXCEPTION 'a service never ordered must not show as a duplicate';
    END IF;
END
$duplicates$;

-- ---------------------------------------------------------------------------
-- Ordering does not close the doctor's step
-- ---------------------------------------------------------------------------
DO $does_not_close_05$
DECLARE
    st text;
BEGIN
    -- A doctor often orders, looks at something, orders again. Closing
    -- LUOTKHAM-05 on the first submit would need a reopen command, and there
    -- isn't one.
    SELECT status INTO st FROM public.work_item
     WHERE visit_id = 'aa000000-0000-4000-8000-0000000000cc'
       AND node_code = 'LUOTKHAM-05';
    IF st IS NOT NULL AND st = 'COMPLETED' THEN
        RAISE EXCEPTION 'ordering must not complete LUOTKHAM-05';
    END IF;
END
$does_not_close_05$;

ROLLBACK;
