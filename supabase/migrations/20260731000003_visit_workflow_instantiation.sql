-- Give the workflow kernel something to do: create the visit's work items.
--
-- node_definition has had 37 rows and work_item has had ZERO since W4. The
-- kernel could transition items and evaluate gates, but nothing ever created
-- one, so the clinic kept running on staff_task. This is the missing writer.
--
-- WHICH NODES. The set is walked from node_dependency starting at whichever
-- node carries config->>'spawn_on' = 'visit.checkin', which returns exactly the
-- seven-node LUOTKHAM spine: tiếp nhận → xác minh → sinh hiệu → chỉ định →
-- đối soát → thanh toán → đóng lượt. Deliberately NOT a hard-coded list in
-- Python (a second source of truth beside node_dependency) and NOT
-- code LIKE 'LUOTKHAM-%' (wrong the day a LUOTKHAM code is added off-spine).
-- KHAM-* and DICHVU-* are the OUTPUT of LUOTKHAM-05 — a clinical decision the
-- seed leaves unlinked on purpose; stamping them at check-in would invent
-- clinical intent nobody expressed.
--
-- WHY THE WHOLE SPINE, not one node at a time. The gate function already stops
-- anyone starting a step out of order, so materialising the chain grants nobody
-- new power — it only makes the visit's remaining work visible. Creating each
-- node lazily needs a second write that can fail after the first commits, and
-- its failure mode is a visit with no open work and no error anywhere, which is
-- the worst outcome available in a clinic.
--
-- LUOTKHAM-01 is born COMPLETED when an actor is supplied, because pressing
-- check-in IS performing "tiếp nhận người bệnh". Leaving it PENDING would hold
-- a blocking FS gate shut in front of the nurse until somebody clicked to
-- assert a fact the database already stores. The NULL-actor branch exists for
-- the clinical paths that open a visit without a check-in.

-- ---------------------------------------------------------------------------
-- 1. Constraints. Free to add: work_item has no rows yet.
-- ---------------------------------------------------------------------------

-- Idempotency, and the reason undo → re-check-in works without a "reopen"
-- command (there isn't one — work_item_event allows only create/start/complete/
-- skip/cancel/reassign). Live rows only: replaying the insert is a no-op, and
-- after a cancellation the same insert mints a fresh generation.
CREATE UNIQUE INDEX IF NOT EXISTS uq_work_item_visit_node_live
    ON public.work_item (clinic_id, visit_id, node_code)
    WHERE visit_id IS NOT NULL AND status <> 'CANCELLED';

-- An item must know which version of the definition it was created under.
ALTER TABLE public.work_item ALTER COLUMN node_version_id SET NOT NULL;

-- node_definition.actor_roles is already constrained to the known role codes;
-- work_item.assigned_role had no check at all.
ALTER TABLE public.work_item DROP CONSTRAINT IF EXISTS work_item_assigned_role_known;
ALTER TABLE public.work_item ADD CONSTRAINT work_item_assigned_role_known
    CHECK (assigned_role IS NULL OR assigned_role = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC',
        'CASHIER_DV']));

-- The spine's entry point. Data, not a constant in code, so a clinic can move
-- its own starting node without a deploy.
UPDATE public.node_definition
   SET config = jsonb_set(coalesce(config, '{}'::jsonb), '{spawn_on}',
                          '"visit.checkin"')
 WHERE code = 'LUOTKHAM-01'
   AND config ->> 'spawn_on' IS DISTINCT FROM 'visit.checkin';

-- ---------------------------------------------------------------------------
-- 2. The writer
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.instantiate_visit_workflow(
    p_clinic_id      uuid,
    p_visit_id       uuid,
    p_actor_staff_id uuid,
    p_actor_role     text DEFAULT NULL,
    p_spawn_on       text DEFAULT 'visit.checkin'
)
RETURNS integer
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $$
DECLARE
    v_appointment_id uuid;
    v_patient_id     uuid;
    v_episode_id     uuid;
    v_created        integer := 0;
BEGIN
    -- Tenancy is asserted here, not trusted. scripts/tests/tenant-scope-audit.py
    -- reads Python string literals under src/clinicai, so nothing in CI would
    -- notice a caller passing a clinic_id that does not own this visit.
    SELECT v.appointment_id, v.clinic_patient_id, a.episode_id
      INTO v_appointment_id, v_patient_id, v_episode_id
      FROM public.visit v
      LEFT JOIN public.appointment a
        ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
     WHERE v.visit_id = p_visit_id
       AND v.clinic_id = p_clinic_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'visit % không thuộc phòng khám %', p_visit_id, p_clinic_id;
    END IF;

    WITH RECURSIVE chain AS (
        SELECT n.code
          FROM public.node_definition n
         WHERE n.clinic_id = p_clinic_id
           AND n.is_active
           AND n.config ->> 'spawn_on' = p_spawn_on
        UNION            -- UNION, not UNION ALL: a future cycle in the
        SELECT d.successor_code   -- catalogue terminates instead of hanging a
          FROM public.node_dependency d   -- P0 front-desk operation.
          JOIN chain c ON c.code = d.predecessor_code
         WHERE d.clinic_id = p_clinic_id
    ),
    spawned AS (
        INSERT INTO public.work_item (
            clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
            appointment_id, care_episode_id, status, assigned_to, assigned_role,
            priority, started_at, finished_at)
        SELECT p_clinic_id, n.code, nv.id, v_patient_id, p_visit_id,
               v_appointment_id, v_episode_id,
               CASE WHEN n.config ->> 'spawn_on' = p_spawn_on
                     AND p_actor_staff_id IS NOT NULL
                    THEN 'COMPLETED' ELSE 'PENDING' END,
               CASE WHEN n.config ->> 'spawn_on' = p_spawn_on
                    THEN p_actor_staff_id END,
               CASE WHEN array_length(n.actor_roles, 1) = 1
                    THEN n.actor_roles[1] END,
               n.priority,
               CASE WHEN n.config ->> 'spawn_on' = p_spawn_on
                     AND p_actor_staff_id IS NOT NULL
                    THEN now() END,
               CASE WHEN n.config ->> 'spawn_on' = p_spawn_on
                     AND p_actor_staff_id IS NOT NULL
                    THEN now() END
          FROM chain c
          JOIN public.node_definition n
            ON n.clinic_id = p_clinic_id AND n.code = c.code AND n.is_active
          JOIN public.node_definition_version nv
            ON nv.node_definition_id = n.id
           AND nv.version = n.current_version
           AND nv.clinic_id = n.clinic_id
        ON CONFLICT (clinic_id, visit_id, node_code)
           WHERE visit_id IS NOT NULL AND status <> 'CANCELLED'
        DO NOTHING
        RETURNING id, node_code, status
    )
    INSERT INTO public.work_item_event (
        clinic_id, work_item_id, command, from_status, to_status,
        actor_staff_id, actor_role, metadata)
    SELECT p_clinic_id, s.id, 'create', NULL, s.status,
           p_actor_staff_id, p_actor_role,
           jsonb_build_object('node_code', s.node_code, 'spawn_on', p_spawn_on)
      FROM spawned s;

    GET DIAGNOSTICS v_created = ROW_COUNT;

    -- Edges join the ONE live item per node code — uq_work_item_visit_node_live
    -- is what makes "one" true, so this join cannot fan out, and a cancelled
    -- generation can never gate a live successor (an FS gate is satisfied only
    -- by COMPLETED or SKIPPED, so a CANCELLED predecessor would block forever).
    WITH live AS (
        SELECT w.id, w.node_code
          FROM public.work_item w
         WHERE w.clinic_id = p_clinic_id
           AND w.visit_id = p_visit_id
           AND w.status <> 'CANCELLED'
    )
    INSERT INTO public.work_item_dependency (
        clinic_id, predecessor_work_item_id, successor_work_item_id,
        dependency_type, is_blocking, gate_group, gate_operator, condition)
    SELECT p_clinic_id, pre.id, suc.id, d.dependency_type, d.is_blocking,
           d.gate_group, d.gate_operator, d.condition
      FROM public.node_dependency d
      JOIN live pre ON pre.node_code = d.predecessor_code
      JOIN live suc ON suc.node_code = d.successor_code
     WHERE d.clinic_id = p_clinic_id
    ON CONFLICT (predecessor_work_item_id, successor_work_item_id) DO NOTHING;

    RETURN v_created;
END
$$;

COMMENT ON FUNCTION public.instantiate_visit_workflow(uuid, uuid, uuid, text, text) IS
  'Create the visit spine walked from the node marked config->>spawn_on. '
  'Idempotent over live rows. Returns how many items were created.';

-- ---------------------------------------------------------------------------
-- 3. Undoing an arrival
-- ---------------------------------------------------------------------------
-- CANCELLED, not SKIPPED. SKIPPED means "this step will not happen" and opens
-- the downstream gates; an undone or cancelled arrival means the whole visit is
-- off. COMPLETED rows are left alone, including LUOTKHAM-01 — the patient did
-- arrive, and history is not rewritten because the front desk changed its mind.
CREATE OR REPLACE FUNCTION public.cancel_visit_workflow(
    p_clinic_id      uuid,
    p_visit_id       uuid,
    p_actor_staff_id uuid,
    p_actor_role     text DEFAULT NULL,
    p_reason         text DEFAULT NULL
)
RETURNS integer
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $$
DECLARE
    v_cancelled integer := 0;
BEGIN
    WITH killed AS (
        UPDATE public.work_item w
           SET status = 'CANCELLED',
               finished_at = now(),
               version = w.version + 1,
               updated_at = now()
         WHERE w.clinic_id = p_clinic_id
           AND w.visit_id = p_visit_id
           AND w.status IN ('PENDING', 'IN_PROGRESS')
        RETURNING w.id, w.node_code
    )
    INSERT INTO public.work_item_event (
        clinic_id, work_item_id, command, from_status, to_status,
        actor_staff_id, actor_role, reason, metadata)
    SELECT p_clinic_id, k.id, 'cancel', NULL, 'CANCELLED',
           p_actor_staff_id, p_actor_role, p_reason,
           jsonb_build_object('node_code', k.node_code)
      FROM killed k;

    GET DIAGNOSTICS v_cancelled = ROW_COUNT;
    RETURN v_cancelled;
END
$$;

COMMENT ON FUNCTION public.cancel_visit_workflow(uuid, uuid, uuid, text, text) IS
  'Cancel every still-open work item of a visit. Completed steps are history '
  'and are left alone.';

-- ---------------------------------------------------------------------------
-- 4. Grants
-- ---------------------------------------------------------------------------
-- work_item grants authenticated SELECT only and the kernel has no client write
-- policies (ADR-0012). The frontend must not be able to call these at all.
REVOKE ALL ON FUNCTION
    public.instantiate_visit_workflow(uuid, uuid, uuid, text, text)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION
    public.cancel_visit_workflow(uuid, uuid, uuid, text, text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION
    public.instantiate_visit_workflow(uuid, uuid, uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION
    public.cancel_visit_workflow(uuid, uuid, uuid, text, text) TO service_role;
