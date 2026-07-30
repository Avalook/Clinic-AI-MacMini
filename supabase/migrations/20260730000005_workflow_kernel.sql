-- W4 — The workflow kernel (ADR-0011).
--
-- This is the part of ClinicAI that makes it a workflow product rather than
-- another clinic CRUD app: what happens in the clinic is DATA (node_definition),
-- not Python. Onboarding a clinic with a different flow becomes a seed, not a
-- sprint.
--
-- Six tables, following docs/ClinicAI-Tong-Quan-He-Thong.md §4:
--   node_definition          reusable definition of a station ('LUOTKHAM-01')
--   node_definition_version  frozen config, so changing a definition never
--                            rewrites the history of work already done under it
--   node_dependency          how definitions relate (the template)
--   work_item                one concrete job for one patient/visit
--   work_item_dependency     materialised per work item, so a gate can be
--                            answered without re-deriving the template
--   work_item_event          immutable transition log
--   follow_up_case           non-blocking work that outlived the visit
--
-- Everything is tenant-scoped (ADR-0009) and read-only to clients (ADR-0012):
-- the only way to move a work item is the Command API, which runs as
-- service_role. No INSERT/UPDATE/DELETE policy is created here on purpose.
--
-- staff_task is deliberately left alone. It keeps running the live clinic until
-- the /tasks screen reads work_item instead; ADR-0011 describes the dual-write
-- window and the eventual drop.

-- ---------------------------------------------------------------------------
-- 1. Definitions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.node_definition (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    -- The flow the node belongs to; mirrors the Notion catalogue grouping.
    flow_group text NOT NULL,
    -- The UI template that renders it (§13 "workspace").
    workspace text NOT NULL,
    -- Which clinic roles may act on it. Empty means "nobody yet" rather than
    -- "everybody" — least privilege, same as the rest of the system.
    actor_roles text[] DEFAULT '{}'::text[] NOT NULL,
    priority text DEFAULT 'P1' NOT NULL,
    -- A "nhóm" node (DICHVU-SIEUAM, DICHVU-THUTHUAT ...) stands for a family of
    -- concrete services chosen at run time.
    is_group boolean DEFAULT false NOT NULL,
    -- The 15-part node template (§4.4) lives here rather than in 15 columns:
    -- it is documentation for humans and varies per node.
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    current_version integer DEFAULT 1 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT node_definition_pkey PRIMARY KEY (id),
    CONSTRAINT node_definition_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT uq_node_definition_clinic_code UNIQUE (clinic_id, code),
    CONSTRAINT node_definition_priority_check CHECK (priority IN ('P0', 'P1', 'P2')),
    CONSTRAINT node_definition_roles_known CHECK (
        actor_roles <@ ARRAY[
            'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
            'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC', 'CASHIER_DV'
        ]::text[]
    )
);

CREATE INDEX IF NOT EXISTS idx_node_definition_clinic_id ON public.node_definition (clinic_id);
CREATE INDEX IF NOT EXISTS idx_node_definition_flow ON public.node_definition (clinic_id, flow_group) WHERE is_active;

COMMENT ON TABLE public.node_definition IS
  'A station in the clinic flow. Configuration, not code — a new clinic with a '
  'different flow is a different set of rows.';

-- A work item pins the version it was created under, so editing a definition
-- tomorrow cannot silently rewrite what a nurse was asked to do yesterday.
CREATE TABLE IF NOT EXISTS public.node_definition_version (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    node_definition_id uuid NOT NULL,
    version integer NOT NULL,
    snapshot jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT node_definition_version_pkey PRIMARY KEY (id),
    CONSTRAINT node_definition_version_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT node_definition_version_node_fkey FOREIGN KEY (node_definition_id)
        REFERENCES public.node_definition(id) ON DELETE CASCADE,
    CONSTRAINT uq_node_definition_version UNIQUE (node_definition_id, version)
);

CREATE INDEX IF NOT EXISTS idx_node_definition_version_clinic_id
    ON public.node_definition_version (clinic_id);

-- Dependencies between DEFINITIONS: the template a visit is stamped from.
CREATE TABLE IF NOT EXISTS public.node_dependency (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    predecessor_code text NOT NULL,
    successor_code text NOT NULL,
    -- FS finish→start · SS start→start · FF finish→finish · SF start→finish
    dependency_type text DEFAULT 'FS' NOT NULL,
    -- Blocking stops the patient moving on. Non-blocking becomes a
    -- follow_up_case when the visit closes, so it cannot just evaporate (§4.2).
    is_blocking boolean DEFAULT true NOT NULL,
    gate_group text,
    gate_operator text DEFAULT 'AND' NOT NULL,
    condition jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT node_dependency_pkey PRIMARY KEY (id),
    CONSTRAINT node_dependency_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT uq_node_dependency UNIQUE (clinic_id, predecessor_code, successor_code),
    CONSTRAINT node_dependency_type_check CHECK (dependency_type IN ('FS', 'SS', 'FF', 'SF')),
    CONSTRAINT node_dependency_operator_check CHECK (gate_operator IN ('AND', 'OR', 'XOR')),
    CONSTRAINT node_dependency_no_self_loop CHECK (predecessor_code <> successor_code)
);

CREATE INDEX IF NOT EXISTS idx_node_dependency_successor
    ON public.node_dependency (clinic_id, successor_code);

-- ---------------------------------------------------------------------------
-- 2. Instances
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.work_item (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    node_code text NOT NULL,
    node_version_id uuid,
    -- What the work is about. A work item always has a patient; visit and
    -- appointment are filled in as the encounter takes shape.
    clinic_patient_id uuid,
    visit_id uuid,
    appointment_id uuid,
    care_episode_id uuid,
    status text DEFAULT 'PENDING' NOT NULL,
    assigned_to uuid,
    assigned_role text,
    priority text DEFAULT 'P1' NOT NULL,
    due_at timestamp with time zone,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    -- Optimistic locking (§4.3 step 5): two people finishing the same item at
    -- once must not both win.
    version integer DEFAULT 1 NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT work_item_pkey PRIMARY KEY (id),
    CONSTRAINT work_item_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT work_item_node_version_fkey FOREIGN KEY (node_version_id)
        REFERENCES public.node_definition_version(id) ON DELETE RESTRICT,
    CONSTRAINT work_item_patient_fkey FOREIGN KEY (clinic_patient_id)
        REFERENCES public.patient(clinic_patient_id) ON DELETE RESTRICT,
    CONSTRAINT work_item_visit_fkey FOREIGN KEY (visit_id)
        REFERENCES public.visit(visit_id) ON DELETE RESTRICT,
    CONSTRAINT work_item_appointment_fkey FOREIGN KEY (appointment_id)
        REFERENCES public.appointment(id) ON DELETE RESTRICT,
    CONSTRAINT work_item_episode_fkey FOREIGN KEY (care_episode_id)
        REFERENCES public.care_episode(id) ON DELETE RESTRICT,
    CONSTRAINT work_item_assignee_fkey FOREIGN KEY (assigned_to)
        REFERENCES public.staff(id) ON DELETE SET NULL,
    CONSTRAINT work_item_status_check CHECK (
        status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'SKIPPED', 'CANCELLED')
    ),
    CONSTRAINT work_item_priority_check CHECK (priority IN ('P0', 'P1', 'P2')),
    -- Timestamps must agree with the status rather than drift from it.
    CONSTRAINT work_item_started_when_progressed CHECK (
        status = ANY (ARRAY['PENDING', 'CANCELLED', 'SKIPPED']) OR started_at IS NOT NULL
    ),
    CONSTRAINT work_item_finished_when_terminal CHECK (
        (status IN ('COMPLETED', 'SKIPPED', 'CANCELLED')) = (finished_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_work_item_clinic_id ON public.work_item (clinic_id);
CREATE INDEX IF NOT EXISTS idx_work_item_open
    ON public.work_item (clinic_id, node_code, status)
    WHERE status IN ('PENDING', 'IN_PROGRESS');
CREATE INDEX IF NOT EXISTS idx_work_item_visit ON public.work_item (visit_id)
    WHERE visit_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_work_item_assignee ON public.work_item (assigned_to)
    WHERE assigned_to IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.work_item_dependency (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    predecessor_work_item_id uuid NOT NULL,
    successor_work_item_id uuid NOT NULL,
    dependency_type text DEFAULT 'FS' NOT NULL,
    is_blocking boolean DEFAULT true NOT NULL,
    gate_group text,
    gate_operator text DEFAULT 'AND' NOT NULL,
    condition jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT work_item_dependency_pkey PRIMARY KEY (id),
    CONSTRAINT work_item_dependency_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT work_item_dependency_pred_fkey FOREIGN KEY (predecessor_work_item_id)
        REFERENCES public.work_item(id) ON DELETE CASCADE,
    CONSTRAINT work_item_dependency_succ_fkey FOREIGN KEY (successor_work_item_id)
        REFERENCES public.work_item(id) ON DELETE CASCADE,
    CONSTRAINT uq_work_item_dependency UNIQUE (predecessor_work_item_id, successor_work_item_id),
    CONSTRAINT work_item_dependency_type_check CHECK (dependency_type IN ('FS', 'SS', 'FF', 'SF')),
    CONSTRAINT work_item_dependency_operator_check CHECK (gate_operator IN ('AND', 'OR', 'XOR')),
    CONSTRAINT work_item_dependency_no_self_loop CHECK (
        predecessor_work_item_id <> successor_work_item_id
    )
);

CREATE INDEX IF NOT EXISTS idx_work_item_dependency_successor
    ON public.work_item_dependency (successor_work_item_id);
CREATE INDEX IF NOT EXISTS idx_work_item_dependency_clinic_id
    ON public.work_item_dependency (clinic_id);

-- Append-only. There is no UPDATE or DELETE path to this table by design: it is
-- the answer to "who moved this, when, and from what".
CREATE TABLE IF NOT EXISTS public.work_item_event (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    work_item_id uuid NOT NULL,
    command text NOT NULL,
    from_status text,
    to_status text NOT NULL,
    actor_staff_id uuid,
    actor_role text,
    reason text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT work_item_event_pkey PRIMARY KEY (id),
    CONSTRAINT work_item_event_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT work_item_event_item_fkey FOREIGN KEY (work_item_id)
        REFERENCES public.work_item(id) ON DELETE CASCADE,
    CONSTRAINT work_item_event_actor_fkey FOREIGN KEY (actor_staff_id)
        REFERENCES public.staff(id) ON DELETE SET NULL,
    CONSTRAINT work_item_event_command_check CHECK (
        command IN ('create', 'start', 'complete', 'skip', 'cancel', 'reassign')
    )
);

CREATE INDEX IF NOT EXISTS idx_work_item_event_item
    ON public.work_item_event (work_item_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_work_item_event_clinic_id
    ON public.work_item_event (clinic_id);

-- Non-blocking work that was still open when the visit closed (§4.2). The point
-- of the table is that such work has a named owner and a date, instead of being
-- quietly dropped on the floor.
CREATE TABLE IF NOT EXISTS public.follow_up_case (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    origin_work_item_id uuid,
    care_episode_id uuid,
    reason text NOT NULL,
    status text DEFAULT 'OPEN' NOT NULL,
    owner_staff_id uuid,
    owner_role text,
    due_at timestamp with time zone,
    closed_at timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT follow_up_case_pkey PRIMARY KEY (id),
    CONSTRAINT follow_up_case_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT follow_up_case_patient_fkey FOREIGN KEY (clinic_patient_id)
        REFERENCES public.patient(clinic_patient_id) ON DELETE RESTRICT,
    CONSTRAINT follow_up_case_origin_fkey FOREIGN KEY (origin_work_item_id)
        REFERENCES public.work_item(id) ON DELETE SET NULL,
    CONSTRAINT follow_up_case_episode_fkey FOREIGN KEY (care_episode_id)
        REFERENCES public.care_episode(id) ON DELETE SET NULL,
    CONSTRAINT follow_up_case_owner_fkey FOREIGN KEY (owner_staff_id)
        REFERENCES public.staff(id) ON DELETE SET NULL,
    CONSTRAINT follow_up_case_status_check CHECK (status IN ('OPEN', 'DONE', 'CANCELLED')),
    CONSTRAINT follow_up_case_closed_when_terminal CHECK (
        (status IN ('DONE', 'CANCELLED')) = (closed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_follow_up_case_open
    ON public.follow_up_case (clinic_id, status, due_at) WHERE status = 'OPEN';
CREATE INDEX IF NOT EXISTS idx_follow_up_case_patient
    ON public.follow_up_case (clinic_patient_id);

-- ---------------------------------------------------------------------------
-- 3. Gate evaluation — in SQL, so no caller can forget it
-- ---------------------------------------------------------------------------
-- Which dependency types gate which command (§4.2):
--   start    ← FS (predecessor finished), SS (predecessor started)
--   complete ← FF (predecessor finished), SF (predecessor started)
--
-- A predecessor is "finished" when it is COMPLETED or SKIPPED — skipping is an
-- explicit decision that the step will not happen, not an omission, so it must
-- not deadlock everything behind it. CANCELLED does not satisfy a gate.

CREATE OR REPLACE FUNCTION public.work_item_gate_blockers(
    p_work_item_id uuid,
    p_phase text
)
RETURNS TABLE (predecessor_work_item_id uuid, node_code text, dependency_type text)
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
    WITH relevant AS (
        SELECT d.predecessor_work_item_id,
               d.dependency_type,
               d.gate_group,
               d.gate_operator,
               p.node_code,
               CASE
                   WHEN d.dependency_type IN ('FS', 'FF')
                       THEN p.status IN ('COMPLETED', 'SKIPPED')
                   ELSE p.status IN ('IN_PROGRESS', 'COMPLETED', 'SKIPPED')
               END AS satisfied
          FROM public.work_item_dependency d
          JOIN public.work_item p ON p.id = d.predecessor_work_item_id
         WHERE d.successor_work_item_id = p_work_item_id
           AND d.is_blocking
           AND d.dependency_type = ANY (
                   CASE WHEN p_phase = 'start'
                        THEN ARRAY['FS', 'SS']
                        ELSE ARRAY['FF', 'SF']
                   END
               )
    ),
    -- Grouped gates are decided per group; an OR group with one satisfied
    -- member blocks nothing, an XOR group needs exactly one.
    grouped AS (
        SELECT gate_group,
               gate_operator,
               count(*) FILTER (WHERE satisfied) AS satisfied_count,
               count(*) AS total
          FROM relevant
         WHERE gate_group IS NOT NULL
         GROUP BY gate_group, gate_operator
    ),
    open_groups AS (
        SELECT gate_group, gate_operator
          FROM grouped
         WHERE (gate_operator = 'AND' AND satisfied_count < total)
            OR (gate_operator = 'OR' AND satisfied_count = 0)
            OR (gate_operator = 'XOR' AND satisfied_count <> 1)
    )
    -- Ungrouped dependencies each stand on their own.
    SELECT r.predecessor_work_item_id, r.node_code, r.dependency_type
      FROM relevant r
     WHERE r.gate_group IS NULL
       AND NOT r.satisfied
    UNION ALL
    -- For a group that is still shut, report every member. In an AND group only
    -- the unfinished members matter, but a shut XOR group can be shut *because
    -- two mutually exclusive branches were both taken* — there the satisfied
    -- rows are exactly the problem, and returning nothing would read as "clear".
    SELECT r.predecessor_work_item_id, r.node_code, r.dependency_type
      FROM relevant r
      JOIN open_groups g ON g.gate_group = r.gate_group
     WHERE g.gate_operator <> 'AND' OR NOT r.satisfied
$$;

COMMENT ON FUNCTION public.work_item_gate_blockers(uuid, text) IS
  'Blocking predecessors that still stand in the way of `start` or `complete`. '
  'Empty result = the gate is open.';

-- ---------------------------------------------------------------------------
-- 4. Reads: own clinic only. Writes: Command API (service_role) only.
-- ---------------------------------------------------------------------------

DO $rls$
DECLARE
    t text;
    tables text[] := ARRAY[
        'node_definition', 'node_definition_version', 'node_dependency',
        'work_item', 'work_item_dependency', 'work_item_event', 'follow_up_case'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('GRANT SELECT ON public.%I TO authenticated', t);
        EXECUTE format('GRANT ALL ON public.%I TO service_role', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_select_own_clinic', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated '
            'USING (clinic_id IN (SELECT public.current_clinic_ids()))',
            t || '_select_own_clinic', t
        );
    END LOOP;
END
$rls$;
