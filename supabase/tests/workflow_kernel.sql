-- Regression assertions for the workflow kernel (W4, ADR-0011).
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/workflow_kernel.sql
--
-- Two things are worth pinning here. First, that the node catalogue really is
-- data — if the seed drifts from docs §13 the clinic's flow has silently
-- changed. Second, the gate rules, because "can this patient move on yet" is the
-- question the whole kernel exists to answer, and getting FS/SS/FF/SF or
-- AND/OR/XOR subtly wrong is the kind of bug nobody notices until a patient is
-- sent home early.

BEGIN;

DO $catalogue$
DECLARE
    dr4women constant uuid := 'a0000000-0000-4000-8000-000000000001';
    total integer;
    versionless integer;
    roleless text;
BEGIN
    SELECT count(*) INTO total FROM public.node_definition WHERE clinic_id = dr4women;
    -- 37 nodes of docs §13 + THUOC-01..04, the nhà thuốc chain added by
    -- migration 20260802000001 (soạn → kiểm tra → tư vấn → bàn giao).
    IF total <> 41 THEN
        RAISE EXCEPTION 'expected the 41 nodes of docs §13 + nhà thuốc, found %', total;
    END IF;

    -- Spot-check one node per flow group, so a wholesale re-seed cannot quietly
    -- change what a station is called or who is allowed to work it.
    IF NOT EXISTS (
        SELECT 1 FROM public.node_definition
         WHERE clinic_id = dr4women AND code = 'LUOTKHAM-01'
           AND name = 'Tiếp nhận người bệnh (check-in)'
           AND actor_roles = ARRAY['RECEPTION']::text[]
           AND priority = 'P0'
    ) THEN
        RAISE EXCEPTION 'LUOTKHAM-01 does not match the catalogue';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.node_definition
         WHERE clinic_id = dr4women AND code = 'DICHVU-DUYET-KETQUA'
           AND actor_roles = ARRAY['DOCTOR']::text[]
    ) THEN
        -- Releasing a result is a doctor's decision; widening this is a
        -- clinical-governance change, not a refactor.
        RAISE EXCEPTION 'result release must stay doctor-only';
    END IF;

    IF (SELECT count(*) FROM public.node_definition
         WHERE clinic_id = dr4women AND is_group) <> 3 THEN
        RAISE EXCEPTION 'expected 3 group nodes (siêu âm, thủ thuật, hình ảnh ngoài)';
    END IF;

    -- Every definition must be frozen at least once, or a work item created from
    -- it would have no configuration to point at.
    SELECT count(*) INTO versionless
      FROM public.node_definition n
     WHERE NOT EXISTS (
        SELECT 1 FROM public.node_definition_version v
         WHERE v.node_definition_id = n.id AND v.version = n.current_version
     );
    IF versionless > 0 THEN
        RAISE EXCEPTION '% definitions have no frozen version', versionless;
    END IF;

    -- A node nobody may act on can never be completed.
    SELECT string_agg(code, ', ') INTO roleless
      FROM public.node_definition
     WHERE clinic_id = dr4women AND cardinality(actor_roles) = 0;
    IF roleless IS NOT NULL THEN
        RAISE EXCEPTION 'nodes with no actor role: %', roleless;
    END IF;
END
$catalogue$;

DO $dependencies$
DECLARE
    dangling text;
BEGIN
    -- A dependency naming a node that does not exist is a typo that would
    -- silently never block anything.
    SELECT string_agg(d.predecessor_code || '->' || d.successor_code, ', ')
      INTO dangling
      FROM public.node_dependency d
     WHERE NOT EXISTS (
             SELECT 1 FROM public.node_definition n
              WHERE n.clinic_id = d.clinic_id AND n.code = d.predecessor_code)
        OR NOT EXISTS (
             SELECT 1 FROM public.node_definition n
              WHERE n.clinic_id = d.clinic_id AND n.code = d.successor_code);

    IF dangling IS NOT NULL THEN
        RAISE EXCEPTION 'node_dependency references unknown nodes: %', dangling;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.node_dependency
         WHERE predecessor_code = 'LUOTKHAM-14' AND successor_code = 'LUOTKHAM-15'
           AND dependency_type = 'FS' AND is_blocking
    ) THEN
        RAISE EXCEPTION 'a visit must not close before it is paid for';
    END IF;
END
$dependencies$;

-- --------------------------------------------------------------------------
-- Gate behaviour
-- --------------------------------------------------------------------------

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('d0000000-0000-4000-8000-0000000000a1',
        'a0000000-0000-4000-8000-000000000001', 'CS-WI', 'Cơ sở test');

INSERT INTO public.patient
    (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000a1', 'BN-WI-001', 'BN kernel test',
        'd0000000-0000-4000-8000-0000000000a1');

-- Three items: check-in, vitals, close. Vitals waits on check-in (FS).
-- node_version_id is looked up rather than left NULL: it became NOT NULL in
-- 20260730000003 so every item records the definition version it was created
-- under, and a fixture that skips it is no longer a valid work item.
INSERT INTO public.work_item
    (clinic_id, id, node_code, node_version_id, clinic_patient_id, status, priority)
SELECT 'a0000000-0000-4000-8000-000000000001', v.id, v.code, nv.id,
       'e0000000-0000-4000-8000-0000000000a1', 'PENDING', 'P0'
  FROM (VALUES
        ('f0000000-0000-4000-8000-00000000000a'::uuid, 'LUOTKHAM-01'),
        ('f0000000-0000-4000-8000-00000000000b'::uuid, 'LUOTKHAM-03'),
        ('f0000000-0000-4000-8000-00000000000c'::uuid, 'LUOTKHAM-15')
       ) AS v(id, code)
  JOIN public.node_definition n
    ON n.code = v.code AND n.clinic_id = 'a0000000-0000-4000-8000-000000000001'
  JOIN public.node_definition_version nv
    ON nv.node_definition_id = n.id AND nv.version = n.current_version;

INSERT INTO public.work_item_dependency
    (clinic_id, predecessor_work_item_id, successor_work_item_id, dependency_type)
VALUES ('a0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-00000000000a',
        'f0000000-0000-4000-8000-00000000000b', 'FS');

DO $fs_gate$
BEGIN
    IF (SELECT count(*) FROM public.work_item_gate_blockers(
            'f0000000-0000-4000-8000-00000000000b', 'start')) <> 1 THEN
        RAISE EXCEPTION 'vitals must be blocked while check-in is still pending';
    END IF;

    -- Starting the predecessor is not enough for a finish-to-start gate.
    UPDATE public.work_item
       SET status = 'IN_PROGRESS', started_at = now()
     WHERE id = 'f0000000-0000-4000-8000-00000000000a';

    IF (SELECT count(*) FROM public.work_item_gate_blockers(
            'f0000000-0000-4000-8000-00000000000b', 'start')) <> 1 THEN
        RAISE EXCEPTION 'FS must wait for the predecessor to FINISH, not to start';
    END IF;

    UPDATE public.work_item
       SET status = 'COMPLETED', finished_at = now()
     WHERE id = 'f0000000-0000-4000-8000-00000000000a';

    IF (SELECT count(*) FROM public.work_item_gate_blockers(
            'f0000000-0000-4000-8000-00000000000b', 'start')) <> 0 THEN
        RAISE EXCEPTION 'the gate must open once check-in is complete';
    END IF;

    -- A start gate says nothing about finishing.
    IF (SELECT count(*) FROM public.work_item_gate_blockers(
            'f0000000-0000-4000-8000-00000000000b', 'complete')) <> 0 THEN
        RAISE EXCEPTION 'an FS dependency must not gate `complete`';
    END IF;
END
$fs_gate$;

DO $skip_does_not_deadlock$
BEGIN
    -- Skipping is a decision that the step will not happen. If it left the gate
    -- shut, one skipped step would strand the patient for the rest of the visit.
    UPDATE public.work_item
       SET status = 'SKIPPED', finished_at = now()
     WHERE id = 'f0000000-0000-4000-8000-00000000000a';

    IF (SELECT count(*) FROM public.work_item_gate_blockers(
            'f0000000-0000-4000-8000-00000000000b', 'start')) <> 0 THEN
        RAISE EXCEPTION 'a skipped predecessor must not block its successor';
    END IF;

    -- Cancelling is different: the step was called off, and whatever depended
    -- on it needs a human decision rather than an automatic pass.
    UPDATE public.work_item
       SET status = 'CANCELLED', finished_at = now()
     WHERE id = 'f0000000-0000-4000-8000-00000000000a';

    IF (SELECT count(*) FROM public.work_item_gate_blockers(
            'f0000000-0000-4000-8000-00000000000b', 'start')) <> 1 THEN
        RAISE EXCEPTION 'a cancelled predecessor must still block';
    END IF;
END
$skip_does_not_deadlock$;

DO $non_blocking$
BEGIN
    UPDATE public.work_item_dependency
       SET is_blocking = false
     WHERE successor_work_item_id = 'f0000000-0000-4000-8000-00000000000b';

    IF (SELECT count(*) FROM public.work_item_gate_blockers(
            'f0000000-0000-4000-8000-00000000000b', 'start')) <> 0 THEN
        RAISE EXCEPTION 'a non-blocking dependency must never hold anything up';
    END IF;

    UPDATE public.work_item_dependency
       SET is_blocking = true
     WHERE successor_work_item_id = 'f0000000-0000-4000-8000-00000000000b';
END
$non_blocking$;

DO $or_and_xor$
DECLARE
    a constant uuid := 'f0000000-0000-4000-8000-00000000000a';
    b constant uuid := 'f0000000-0000-4000-8000-00000000000b';
    c constant uuid := 'f0000000-0000-4000-8000-00000000000c';
BEGIN
    -- Two predecessors of the close step, in one OR group: either route through
    -- the clinic is enough to allow closing.
    UPDATE public.work_item SET status = 'PENDING', started_at = NULL, finished_at = NULL
     WHERE id IN (a, b);

    INSERT INTO public.work_item_dependency
        (predecessor_work_item_id, successor_work_item_id, dependency_type,
         gate_group, gate_operator)
    VALUES (a, c, 'FS', 'either', 'OR'),
           (b, c, 'FS', 'either', 'OR');

    IF (SELECT count(*) FROM public.work_item_gate_blockers(c, 'start')) <> 2 THEN
        RAISE EXCEPTION 'with neither branch done, both must be reported as blockers';
    END IF;

    UPDATE public.work_item SET status = 'COMPLETED', started_at = now(), finished_at = now()
     WHERE id = a;

    IF (SELECT count(*) FROM public.work_item_gate_blockers(c, 'start')) <> 0 THEN
        RAISE EXCEPTION 'one satisfied member must open an OR gate';
    END IF;

    -- The same pair as XOR: exactly one, so finishing both closes the gate again.
    UPDATE public.work_item_dependency SET gate_operator = 'XOR'
     WHERE successor_work_item_id = c;

    IF (SELECT count(*) FROM public.work_item_gate_blockers(c, 'start')) <> 0 THEN
        RAISE EXCEPTION 'XOR with exactly one satisfied member must be open';
    END IF;

    UPDATE public.work_item SET status = 'COMPLETED', started_at = now(), finished_at = now()
     WHERE id = b;

    IF (SELECT count(*) FROM public.work_item_gate_blockers(c, 'start')) = 0 THEN
        RAISE EXCEPTION 'XOR must close again when both branches were taken';
    END IF;
END
$or_and_xor$;

DO $status_and_timestamps_agree$
DECLARE
    ok boolean;
BEGIN
    -- A completed item without a finish time is unauditable, so the table
    -- refuses it rather than trusting every writer to remember.
    BEGIN
        UPDATE public.work_item SET status = 'COMPLETED', finished_at = NULL
         WHERE id = 'f0000000-0000-4000-8000-00000000000c';
        ok := false;
    EXCEPTION WHEN check_violation THEN
        ok := true;
    END;

    IF NOT ok THEN
        RAISE EXCEPTION 'COMPLETED without finished_at must be rejected';
    END IF;
END
$status_and_timestamps_agree$;

DO $history_is_tenant_scoped$
DECLARE
    other_clinic uuid := 'c9000000-0000-4000-8000-0000000000ff';
    rejected boolean := false;
BEGIN
    INSERT INTO public.work_item_event
        (work_item_id, command, from_status, to_status)
    VALUES ('f0000000-0000-4000-8000-00000000000c', 'complete', 'IN_PROGRESS', 'COMPLETED');

    IF (SELECT clinic_id FROM public.work_item_event
         WHERE work_item_id = 'f0000000-0000-4000-8000-00000000000c')
       <> 'a0000000-0000-4000-8000-000000000001'::uuid THEN
        RAISE EXCEPTION 'events must inherit the tenant';
    END IF;

    -- Inherited from the parent, not from a column DEFAULT: the default is gone
    -- (20260730000014), and a caller naming a different clinic is refused
    -- rather than quietly relabelled.
    INSERT INTO public.clinic (id, code, name)
    VALUES (other_clinic, 'WK-OTHER', 'Phòng khám khác')
    ON CONFLICT (id) DO NOTHING;

    BEGIN
        INSERT INTO public.work_item_event
            (work_item_id, clinic_id, command, from_status, to_status)
        VALUES ('f0000000-0000-4000-8000-00000000000c', other_clinic,
                'complete', 'IN_PROGRESS', 'COMPLETED');
    EXCEPTION WHEN raise_exception THEN
        rejected := true;
    END;

    IF NOT rejected THEN
        RAISE EXCEPTION
            'an event claiming another clinic must be refused, not relabelled';
    END IF;
END
$history_is_tenant_scoped$;

ROLLBACK;
