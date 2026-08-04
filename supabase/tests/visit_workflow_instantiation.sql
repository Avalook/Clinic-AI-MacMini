-- Checking a patient in creates their work items (20260731000003).
--
-- The workflow kernel had 37 node definitions and zero work items for its whole
-- existence: it could transition items and evaluate gates, but nothing ever
-- created one. This asserts the writer, and the three properties that make it
-- safe to run on every arrival — the right node set, idempotency, and that an
-- undone arrival does not erase the fact that the patient came.
--
-- Everything rolls back.

BEGIN;

-- The test owns its fixtures. CI applies migrations ONLY — no seed.sql, no
-- fixtures/local_data.sql — so a test that borrows a patient from the developer
-- machine passes locally and has never once run in CI. Migrations create the
-- clinic; everything below it is ours to create.
INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('a1100000-0000-4000-8000-000000000001',
        'a0000000-0000-4000-8000-000000000001', 'TEST-A', 'Cơ sở A (test)')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient
    (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000f1', 'BN-TEST-A1', 'BN test A1',
        'a1100000-0000-4000-8000-000000000001')
ON CONFLICT (clinic_patient_id) DO NOTHING;

-- The actor. Migrations create no staff — fixtures/staff_logins.sql does, and
-- CI never runs it, so looking one up by display name resolved to NULL and the
-- check-in step was born PENDING instead of COMPLETED. Own the row, address it
-- by id: a display name was never a key.
-- Bài kiểm này tự tạo thêm cơ sở, nên phòng khám có nhiều hơn một chỗ và hệ
-- thống KHÔNG đoán hộ (trigger 20260804000015). Fixture phải chỉ rõ.
INSERT INTO public.staff
    (id, full_name, primary_department, primary_location_id)
VALUES ('a1300000-0000-4000-8000-000000000001', 'BS test A', 'DOCTOR',
        (SELECT id FROM public.clinic_location WHERE is_active
       ORDER BY created_at, id LIMIT 1))
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'a1300000-0000-4000-8000-000000000001', 'DOCTOR', true)
ON CONFLICT DO NOTHING;

INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
VALUES ('aa000000-0000-4000-8000-00000000000f',
        'a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000f1', 'OPEN');

-- ---------------------------------------------------------------------------
-- The spine, walked from the catalogue rather than hard-coded
-- ---------------------------------------------------------------------------
DO $creates_the_spine$
DECLARE
    created integer;
    codes   text;
    actor   uuid;
BEGIN
    actor := 'a1300000-0000-4000-8000-000000000001';

    created := public.instantiate_visit_workflow(
        'a0000000-0000-4000-8000-000000000001',
        'aa000000-0000-4000-8000-00000000000f', actor, 'RECEPTION');

    IF created <> 7 THEN
        RAISE EXCEPTION 'expected the 7-node visit spine, created %', created;
    END IF;

    SELECT string_agg(node_code, ',' ORDER BY node_code) INTO codes
      FROM public.work_item
     WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f';

    IF codes <> 'LUOTKHAM-01,LUOTKHAM-02,LUOTKHAM-03,LUOTKHAM-05,'
                 || 'LUOTKHAM-13,LUOTKHAM-14,LUOTKHAM-15' THEN
        RAISE EXCEPTION 'wrong node set: %', codes;
    END IF;

    -- Pressing check-in IS performing "tiếp nhận người bệnh". Leaving it
    -- PENDING would hold a blocking gate shut in front of the nurse until
    -- somebody clicked to assert what the database already knows.
    IF (SELECT status FROM public.work_item
         WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f'
           AND node_code = 'LUOTKHAM-01') <> 'COMPLETED' THEN
        RAISE EXCEPTION 'the check-in step itself must be born COMPLETED';
    END IF;

    -- Every item pins the definition version it was created under.
    IF EXISTS (SELECT 1 FROM public.work_item
                WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f'
                  AND node_version_id IS NULL) THEN
        RAISE EXCEPTION 'work items must pin a node_definition_version';
    END IF;

    -- One 'create' event per item, or the history is already incomplete.
    IF (SELECT count(*) FROM public.work_item_event e
          JOIN public.work_item w ON w.id = e.work_item_id
         WHERE w.visit_id = 'aa000000-0000-4000-8000-00000000000f'
           AND e.command = 'create') <> 7 THEN
        RAISE EXCEPTION 'every created item needs a create event';
    END IF;
END
$creates_the_spine$;

-- ---------------------------------------------------------------------------
-- The gates actually gate
-- ---------------------------------------------------------------------------
DO $gates_hold$
DECLARE
    verify_blockers integer;
    vitals_blockers integer;
BEGIN
    SELECT count(*) INTO verify_blockers
      FROM public.work_item_gate_blockers(
          (SELECT id FROM public.work_item
            WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f'
              AND node_code = 'LUOTKHAM-02'), 'start');

    SELECT count(*) INTO vitals_blockers
      FROM public.work_item_gate_blockers(
          (SELECT id FROM public.work_item
            WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f'
              AND node_code = 'LUOTKHAM-03'), 'start');

    -- Verification is next: its predecessor is the completed check-in.
    IF verify_blockers <> 0 THEN
        RAISE EXCEPTION
            'verification should be startable right after check-in, % blocker(s)',
            verify_blockers;
    END IF;
    -- Vitals waits on verification. Materialising the chain must not let
    -- anyone jump it.
    IF vitals_blockers = 0 THEN
        RAISE EXCEPTION 'vitals must be blocked until verification completes';
    END IF;
END
$gates_hold$;

-- ---------------------------------------------------------------------------
-- Idempotent: a repeat call creates nothing
-- ---------------------------------------------------------------------------
DO $idempotent$
DECLARE
    again integer;
    actor uuid;
BEGIN
    actor := 'a1300000-0000-4000-8000-000000000001';
    again := public.instantiate_visit_workflow(
        'a0000000-0000-4000-8000-000000000001',
        'aa000000-0000-4000-8000-00000000000f', actor, 'RECEPTION');

    IF again <> 0 THEN
        RAISE EXCEPTION 'a repeat instantiation created % item(s)', again;
    END IF;
    IF (SELECT count(*) FROM public.work_item
         WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f') <> 7 THEN
        RAISE EXCEPTION 'a repeat instantiation duplicated the spine';
    END IF;
END
$idempotent$;

-- ---------------------------------------------------------------------------
-- Undo cancels what is open and keeps what happened
-- ---------------------------------------------------------------------------
DO $undo_keeps_history$
DECLARE
    cancelled integer;
    actor uuid;
BEGIN
    actor := 'a1300000-0000-4000-8000-000000000001';
    cancelled := public.cancel_visit_workflow(
        'a0000000-0000-4000-8000-000000000001',
        'aa000000-0000-4000-8000-00000000000f', actor, 'RECEPTION',
        'undo_checkin');

    IF cancelled <> 6 THEN
        RAISE EXCEPTION 'expected the 6 open steps to be cancelled, got %', cancelled;
    END IF;

    -- The patient did arrive. Undoing a mis-click does not make that untrue.
    IF (SELECT status FROM public.work_item
         WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f'
           AND node_code = 'LUOTKHAM-01') <> 'COMPLETED' THEN
        RAISE EXCEPTION 'cancelling open work must not rewrite completed steps';
    END IF;
END
$undo_keeps_history$;

-- ---------------------------------------------------------------------------
-- Re-check-in mints a fresh generation beside the cancelled one
-- ---------------------------------------------------------------------------
DO $recheckin_reopens$
DECLARE
    created integer;
    live    integer;
    actor   uuid;
BEGIN
    actor := 'a1300000-0000-4000-8000-000000000001';
    created := public.instantiate_visit_workflow(
        'a0000000-0000-4000-8000-000000000001',
        'aa000000-0000-4000-8000-00000000000f', actor, 'RECEPTION');

    -- Six: the arrival step is still live and COMPLETED, so the partial unique
    -- index refuses a second one. That is the index doing its job, not a gap.
    IF created <> 6 THEN
        RAISE EXCEPTION 'a re-check-in should reopen the 6 cancelled steps, got %',
            created;
    END IF;

    SELECT count(*) INTO live FROM public.work_item
     WHERE visit_id = 'aa000000-0000-4000-8000-00000000000f'
       AND status <> 'CANCELLED';
    IF live <> 7 THEN
        RAISE EXCEPTION 'expected exactly one live spine, found % live items', live;
    END IF;
END
$recheckin_reopens$;

-- ---------------------------------------------------------------------------
-- A visit belonging to another clinic is refused, not silently instantiated
-- ---------------------------------------------------------------------------
DO $tenancy_is_asserted$
DECLARE
    refused boolean := false;
    actor uuid;
BEGIN
    actor := 'a1300000-0000-4000-8000-000000000001';
    INSERT INTO public.clinic (id, code, name)
    VALUES ('ab000000-0000-4000-8000-0000000000ab', 'WFOTHER', 'PK khác')
    ON CONFLICT (id) DO NOTHING;

    BEGIN
        PERFORM public.instantiate_visit_workflow(
            'ab000000-0000-4000-8000-0000000000ab',
            'aa000000-0000-4000-8000-00000000000f', actor, 'RECEPTION');
    EXCEPTION WHEN raise_exception THEN
        refused := true;
    END;

    IF NOT refused THEN
        RAISE EXCEPTION
            'instantiating a visit for a clinic that does not own it must fail — '
            'the backend bypasses RLS, so this function is the only check';
    END IF;
END
$tenancy_is_asserted$;

ROLLBACK;
