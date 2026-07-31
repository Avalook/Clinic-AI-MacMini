-- Ordering services: turn a doctor's selection into work in the right rooms.
--
-- This is what LUOTKHAM-05 ("Tạo chỉ định dịch vụ") produces. Until now the
-- spine stopped there: check-in created seven steps and the last clinical one
-- had no output, so the ultrasound room and the nurses' station had nothing to
-- read. This closes that.
--
-- ONE WORK ITEM PER NODE, NOT PER SERVICE. Three ultrasounds ordered together
-- are one visit to the ultrasound room, and the catalogue already says so: the
-- nodes are named "Thực hiện siêu âm (nhóm)", "Thực hiện thủ thuật (nhóm)" —
-- group nodes. It also happens to be what uq_work_item_visit_node_live enforces
-- anyway, so the alternative would have meant weakening the index that makes
-- re-check-in safe. The ordered services live in the work item's payload, and
-- ordering more of the same kind appends to the existing item rather than
-- creating a second one.
--
-- UNMAPPED SERVICES ARE REFUSED, not silently dropped and not defaulted to some
-- general node. A work item in the wrong room shows up as a patient waiting
-- outside a door where nobody expects her.

-- Dropped first: the OUT signature changed, and CREATE OR REPLACE cannot
-- change a function's row type.
DROP FUNCTION IF EXISTS public.order_services(uuid, uuid, text[], uuid, text);

CREATE FUNCTION public.order_services(
    p_clinic_id      uuid,
    p_visit_id       uuid,
    p_service_codes  text[],
    p_actor_staff_id uuid,
    p_actor_role     text DEFAULT NULL
)
-- OUT names are prefixed because plpgsql resolves an unqualified `node_code`
-- to the OUT parameter before the table column, and the CTEs below select it
-- from real tables. Without the prefix the body fails with "column reference
-- node_code is ambiguous" — at runtime, not at CREATE time.
RETURNS TABLE (
    out_node_code    text,
    out_work_item_id uuid,
    out_service_count integer,
    out_created      boolean
)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $$
DECLARE
    v_patient_id     uuid;
    v_appointment_id uuid;
    v_episode_id     uuid;
    v_unmapped       text;
BEGIN
    IF p_service_codes IS NULL OR cardinality(p_service_codes) = 0 THEN
        RAISE EXCEPTION 'Chưa chọn dịch vụ nào';
    END IF;

    -- Tenancy asserted here, not trusted from the caller: the backend connects
    -- as the database owner and RLS never narrows what it sees.
    SELECT v.clinic_patient_id, v.appointment_id, a.episode_id
      INTO v_patient_id, v_appointment_id, v_episode_id
      FROM public.visit v
      LEFT JOIN public.appointment a
        ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
     WHERE v.visit_id = p_visit_id AND v.clinic_id = p_clinic_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'visit % không thuộc phòng khám %', p_visit_id, p_clinic_id;
    END IF;

    -- Name the offending service rather than failing with a count. Whoever sees
    -- this has to decide where that service is performed, and cannot do that
    -- from "3 services could not be ordered".
    SELECT string_agg(s.service_code, ', ')
      INTO v_unmapped
      FROM unnest(p_service_codes) AS c(code)
      LEFT JOIN public.service_price s
        ON s.service_code = c.code AND s.clinic_id = p_clinic_id AND s.active
     WHERE s.service_code IS NULL OR s.node_code IS NULL;

    IF v_unmapped IS NOT NULL THEN
        RAISE EXCEPTION
            'Dịch vụ chưa gắn với bước thực hiện (hoặc không còn hiệu lực): %',
            v_unmapped;
    END IF;

    RETURN QUERY
    WITH wanted AS (
        SELECT s.node_code,
               jsonb_agg(jsonb_build_object(
                   'service_code', s.service_code,
                   'name', s.name,
                   'unit_price', s.unit_price
               ) ORDER BY s.service_code) AS svc
          FROM unnest(p_service_codes) AS c(code)
          JOIN public.service_price s
            ON s.service_code = c.code AND s.clinic_id = p_clinic_id AND s.active
         GROUP BY s.node_code
    ),
    -- An existing live item for the same node absorbs the new services.
    existing AS (
        SELECT w.id, w.node_code, w.payload
          FROM public.work_item w
         WHERE w.clinic_id = p_clinic_id
           AND w.visit_id = p_visit_id
           AND w.status <> 'CANCELLED'
    ),
    inserted AS (
        INSERT INTO public.work_item (
            clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
            appointment_id, care_episode_id, status, assigned_role, priority,
            payload)
        SELECT p_clinic_id, n.code, nv.id, v_patient_id, p_visit_id,
               v_appointment_id, v_episode_id, 'PENDING',
               CASE WHEN array_length(n.actor_roles, 1) = 1
                    THEN n.actor_roles[1] END,
               n.priority,
               jsonb_build_object('services', w.svc)
          FROM wanted w
          JOIN public.node_definition n
            ON n.clinic_id = p_clinic_id AND n.code = w.node_code AND n.is_active
          JOIN public.node_definition_version nv
            ON nv.node_definition_id = n.id
           AND nv.version = n.current_version
           AND nv.clinic_id = n.clinic_id
         WHERE NOT EXISTS (SELECT 1 FROM existing e WHERE e.node_code = w.node_code)
        RETURNING id, work_item.node_code, payload
    ),
    appended AS (
        UPDATE public.work_item w
           SET payload = jsonb_set(
                   coalesce(w.payload, '{}'::jsonb), '{services}',
                   coalesce(w.payload -> 'services', '[]'::jsonb) || x.svc),
               version = w.version + 1,
               updated_at = now()
          FROM wanted x
         WHERE w.clinic_id = p_clinic_id
           AND w.visit_id = p_visit_id
           AND w.node_code = x.node_code
           AND w.status <> 'CANCELLED'
        RETURNING w.id, w.node_code, w.payload
    ),
    all_rows AS (
        SELECT id, node_code, payload, true AS was_created FROM inserted
        UNION ALL
        SELECT id, node_code, payload, false FROM appended
    ),
    evented AS (
        INSERT INTO public.work_item_event (
            clinic_id, work_item_id, command, from_status, to_status,
            actor_staff_id, actor_role, metadata)
        SELECT p_clinic_id, r.id,
               CASE WHEN r.was_created THEN 'create' ELSE 'reassign' END,
               NULL, 'PENDING', p_actor_staff_id, p_actor_role,
               jsonb_build_object('node_code', r.node_code,
                                  'reason', 'order_services')
          FROM all_rows r
        RETURNING work_item_id
    )
    SELECT r.node_code,
           r.id,
           jsonb_array_length(coalesce(r.payload -> 'services', '[]'::jsonb))::integer,
           r.was_created
      FROM all_rows r
     WHERE (SELECT count(*) FROM evented) >= 0;
END
$$;

COMMENT ON FUNCTION public.order_services(uuid, uuid, text[], uuid, text) IS
  'Create (or extend) one work item per performing node for the services '
  'ordered on a visit. Refuses services with no node_code.';

-- ---------------------------------------------------------------------------
-- Has this patient had the same service recently?
-- ---------------------------------------------------------------------------
-- The design shows a duplicate warning ("đã chỉ định trùng trong 30 ngày").
-- It reads the work items themselves rather than a separate order log, because
-- the work item IS the order — a second store would be a second truth.
CREATE OR REPLACE FUNCTION public.recent_duplicate_services(
    p_clinic_id  uuid,
    p_patient_id uuid,
    p_codes      text[],
    p_days       integer DEFAULT 30
)
RETURNS TABLE (service_code text, name text, ordered_at timestamptz)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $$
    SELECT s ->> 'service_code',
           s ->> 'name',
           w.created_at
      FROM public.work_item w
     CROSS JOIN LATERAL jsonb_array_elements(
           coalesce(w.payload -> 'services', '[]'::jsonb)) AS s
     WHERE w.clinic_id = p_clinic_id
       AND w.clinic_patient_id = p_patient_id
       AND w.status <> 'CANCELLED'
       AND w.created_at >= now() - make_interval(days => p_days)
       AND s ->> 'service_code' = ANY (p_codes)
     ORDER BY w.created_at DESC;
$$;

COMMENT ON FUNCTION public.recent_duplicate_services(uuid, uuid, text[], integer) IS
  'Services among p_codes this patient already had ordered within p_days. '
  'Reads work_item payloads — the work item is the order.';

REVOKE ALL ON FUNCTION
    public.order_services(uuid, uuid, text[], uuid, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION
    public.recent_duplicate_services(uuid, uuid, text[], integer)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION
    public.order_services(uuid, uuid, text[], uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION
    public.recent_duplicate_services(uuid, uuid, text[], integer) TO service_role;
