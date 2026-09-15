-- DỊCH VỤ LÀM LẠI TRONG CÙNG LƯỢT LÀ LẦN MỚI (15/09/2026).
--
-- Tuyền chốt: "nếu phải siêu âm lại thì vẫn tính là lần siêu âm thứ 2 của lần
-- khám". Trước bản này `order_services` gộp dịch vụ mới vào BẤT KỲ việc chưa huỷ
-- nào của cùng bước — kể cả việc đã XONG — nên lần siêu âm thứ 2 chui vào việc
-- lần 1 đã hoàn tất, không hiện ở hàng chờ, không ai làm. Chỉ mục
-- `uq_work_item_visit_node_live` (một việc sống mỗi bước mỗi lượt) cũng chặn
-- việc tạo việc thứ hai.
--
-- Bản này:
--   · thêm `work_item.lan` (lần thứ mấy của bước trong lượt, mặc định 1);
--   · chỉ mục duy nhất thành (phòng khám, lượt, bước, LẦN) — bước ga vẫn đúng
--     một việc (lan = 1), chạy lại check-in vẫn không nhân đôi;
--   · order_services chỉ gộp vào việc CÒN MỞ; bước đã xong/đã miễn thì tạo
--     việc mới với lần kế tiếp;
--   · ba hàng dùng ON CONFLICT theo chỉ mục cũ (instantiate_visit_workflow,
--     move_visit_to_station, check-in lịch siêu âm ở booking_service) đổi theo.
--   · Tiền: mỗi lần là một việc có dịch vụ riêng — hai lần siêu âm tính hai lần.

ALTER TABLE public.work_item
    ADD COLUMN IF NOT EXISTS lan smallint NOT NULL DEFAULT 1;
ALTER TABLE public.work_item DROP CONSTRAINT IF EXISTS work_item_lan_duong;
ALTER TABLE public.work_item ADD CONSTRAINT work_item_lan_duong CHECK (lan >= 1);

COMMENT ON COLUMN public.work_item.lan IS
    'Lần thứ mấy của bước này trong lượt khám (siêu âm lại = lần 2). '
    '20260915000022.';

-- Phiếu siêu âm cũng theo LẦN: một phiếu cho mỗi (lượt × loại × lần). Lần 1 đã
-- ký thì lần 2 mở phiếu mới thay vì đụng chốt uq_ultrasound_visit_type.
ALTER TABLE public.ultrasound_record
    ADD COLUMN IF NOT EXISTS lan smallint NOT NULL DEFAULT 1;
ALTER TABLE public.ultrasound_record DROP CONSTRAINT IF EXISTS ultrasound_record_lan_duong;
ALTER TABLE public.ultrasound_record ADD CONSTRAINT ultrasound_record_lan_duong
    CHECK (lan >= 1);
DROP INDEX IF EXISTS public.uq_ultrasound_visit_type;
CREATE UNIQUE INDEX uq_ultrasound_visit_type
    ON public.ultrasound_record (clinic_id, visit_id, ultrasound_type, lan)
    WHERE visit_id IS NOT NULL;

DROP INDEX IF EXISTS public.uq_work_item_visit_node_live;
CREATE UNIQUE INDEX uq_work_item_visit_node_live
    ON public.work_item (clinic_id, visit_id, node_code, lan)
    WHERE visit_id IS NOT NULL AND status <> 'CANCELLED';

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
        -- `lan` mặc định 1: bước ga không bao giờ có lần 2 (20260915000022).
        ON CONFLICT (clinic_id, visit_id, node_code, lan)
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
    -- Mỗi bước lấy LẦN MỚI NHẤT còn sống (20260915000022): dịch vụ làm lần 2
    -- không được nhân đôi cạnh phụ thuộc.
    WITH live AS (
        SELECT DISTINCT ON (w.node_code) w.id, w.node_code
          FROM public.work_item w
         WHERE w.clinic_id = p_clinic_id
           AND w.visit_id = p_visit_id
           AND w.status <> 'CANCELLED'
         ORDER BY w.node_code, w.lan DESC
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

CREATE OR REPLACE FUNCTION public.move_visit_to_station(p_clinic_id uuid, p_visit_id uuid, p_node_code text, p_room_id uuid, p_actor uuid, p_reason text DEFAULT NULL::text, p_event_type text DEFAULT 'dispatch.moved'::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_old_node text;
    v_old_room uuid;
    v_node_version uuid;
    v_patient uuid;
    v_appt uuid;
    v_item uuid;
    v_old_la_dich_vu boolean;
    v_moi_la_dich_vu boolean;
BEGIN
    SELECT current_node_code, current_room_id, clinic_patient_id, appointment_id
      INTO v_old_node, v_old_room, v_patient, v_appt
      FROM public.visit
     WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy lượt khám % ở phòng khám này', p_visit_id;
    END IF;

    IF p_room_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.clinic_room r
          JOIN public.clinic_room_node rn ON rn.room_id = r.id
         WHERE r.id = p_room_id AND r.clinic_id = p_clinic_id
           AND rn.node_code = p_node_code AND r.is_active
    ) THEN
        RAISE EXCEPTION 'Phòng đã chọn không phục vụ bước %', p_node_code;
    END IF;

    SELECT coalesce(bool_or(n.code = v_old_node AND n.code NOT LIKE 'THUOC-%'
                            AND n.flow_group IN ('dich_vu', 'ket_qua')), false),
           coalesce(bool_or(n.code = p_node_code AND n.code NOT LIKE 'THUOC-%'
                            AND n.flow_group IN ('dich_vu', 'ket_qua')), false)
      INTO v_old_la_dich_vu, v_moi_la_dich_vu
      FROM public.node_definition n
     WHERE n.clinic_id = p_clinic_id AND n.code IN (v_old_node, p_node_code);

    IF p_node_code IS DISTINCT FROM v_old_node THEN
        IF p_node_code LIKE 'THUOC-%' AND NOT EXISTS (
            SELECT 1 FROM public.prescription
             WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
        ) THEN
            RAISE EXCEPTION
                'Lượt khám chưa có đơn thuốc bác sĩ duyệt — chưa đưa sang nhà thuốc được';
        END IF;

        IF v_moi_la_dich_vu THEN
            -- (1) Chỉ điều phối việc đã có. Khoá dòng việc để lệnh hoàn tất
            -- của người thực hiện không chen giữa lúc gắn phòng.
            SELECT id INTO v_item
              FROM public.work_item
             WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
               AND node_code = p_node_code
               AND status IN ('PENDING', 'IN_PROGRESS')
             ORDER BY lan DESC
             LIMIT 1
             FOR UPDATE;
            IF v_item IS NULL THEN
                RAISE EXCEPTION
                    'Bước % chưa có chỉ định bác sĩ đã duyệt (hoặc đã làm xong) — trưởng ca chỉ điều phối dịch vụ bác sĩ đã chỉ định',
                    p_node_code;
                -- Mã lỗi mặc định (P0001) có chủ ý: DispatchService.move bắt
                -- asyncpg.RaiseError và đưa nguyên câu này lên màn hình.
            END IF;
        END IF;

        -- (2) CHỈ đóng bước ga đang rời. Bước dịch vụ đang rời giữ nguyên trạng
        -- thái: còn chờ làm thì vẫn chờ làm.
        IF v_old_node IS NOT NULL AND NOT v_old_la_dich_vu THEN
            UPDATE public.work_item
               SET status = 'COMPLETED', finished_at = now(), updated_at = now()
             WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
               AND node_code = v_old_node
               AND status IN ('PENDING', 'IN_PROGRESS');
        END IF;

        IF v_moi_la_dich_vu THEN
            UPDATE public.work_item
               SET room_id = p_room_id, updated_at = now()
             WHERE id = v_item;
        ELSE
            SELECT v.id INTO v_node_version
              FROM public.node_definition_version v
              JOIN public.node_definition n ON n.id = v.node_definition_id
             WHERE n.code = p_node_code AND n.clinic_id = p_clinic_id
             ORDER BY v.version DESC LIMIT 1;
            IF v_node_version IS NULL THEN
                RAISE EXCEPTION 'Bước % chưa được khai trong node_definition',
                    p_node_code;
            END IF;

            -- IN_PROGRESS, không phải PENDING: bệnh nhân ĐANG Ở đây (bước ga).
            INSERT INTO public.work_item
                (clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
                 appointment_id, status, room_id, started_at, finished_at, payload)
            VALUES (p_clinic_id, p_node_code, v_node_version, v_patient, p_visit_id,
                    v_appt, 'IN_PROGRESS', p_room_id, now(), NULL,
                    jsonb_build_object('moved_from', v_old_node, 'reason', p_reason))
            ON CONFLICT (clinic_id, visit_id, node_code, lan)
                WHERE visit_id IS NOT NULL AND status <> 'CANCELLED'
            DO UPDATE SET status = 'IN_PROGRESS',
                          room_id = EXCLUDED.room_id,
                          started_at = coalesce(work_item.started_at, now()),
                          finished_at = NULL,
                          updated_at = now()
            RETURNING id INTO v_item;
        END IF;
    ELSE
        UPDATE public.work_item
           SET room_id = p_room_id, updated_at = now()
         WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
           AND node_code = p_node_code
           AND status IN ('PENDING', 'IN_PROGRESS')
        RETURNING id INTO v_item;

        IF v_item IS NULL THEN
            RAISE EXCEPTION
                'Lượt khám không có bước % nào đang mở để đổi phòng', p_node_code;
        END IF;
    END IF;

    UPDATE public.visit
       SET previous_node_code = CASE WHEN p_node_code IS DISTINCT FROM v_old_node
                                     THEN v_old_node ELSE previous_node_code END,
           current_node_code   = p_node_code,
           current_room_id     = p_room_id,
           current_node_since  = CASE WHEN p_node_code IS DISTINCT FROM v_old_node
                                      THEN now() ELSE current_node_since END,
           status = CASE WHEN status = 'OPEN' THEN 'IN_PROGRESS' ELSE status END,
           updated_at = now()
     WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id;

    INSERT INTO public.event_log
        (clinic_id, event_type, aggregate_type, aggregate_id, payload, metadata,
         source, event_published)
    VALUES (p_clinic_id, p_event_type, 'visit', p_visit_id,
            jsonb_build_object(
                'from_node', v_old_node, 'to_node', p_node_code,
                'from_room', v_old_room, 'to_room', p_room_id,
                'reason', p_reason, 'work_item_id', v_item),
            jsonb_build_object('actor_auth_user_id', p_actor),
            'api:dispatch', FALSE);

    RETURN v_item;
END
$function$;

CREATE OR REPLACE FUNCTION public.order_services(
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
    -- Việc CÒN MỞ (chưa làm / đang làm) của cùng bước nhận thêm dịch vụ. Việc đã
    -- XONG hoặc đã MIỄN thì KHÔNG gộp nữa (20260915000022, Tuyền chốt 15/09:
    -- siêu âm lại trong cùng lượt là LẦN SIÊU ÂM THỨ 2) — tạo việc mới, lần kế.
    existing AS (
        SELECT w.id, w.node_code, w.payload
          FROM public.work_item w
         WHERE w.clinic_id = p_clinic_id
           AND w.visit_id = p_visit_id
           AND w.status IN ('PENDING', 'IN_PROGRESS')
    ),
    lan_truoc AS (
        SELECT w.node_code, max(w.lan) AS lan
          FROM public.work_item w
         WHERE w.clinic_id = p_clinic_id
           AND w.visit_id = p_visit_id
           AND w.status <> 'CANCELLED'
         GROUP BY w.node_code
    ),
    inserted AS (
        INSERT INTO public.work_item (
            clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
            appointment_id, care_episode_id, status, assigned_role, priority,
            payload, lan)
        SELECT p_clinic_id, n.code, nv.id, v_patient_id, p_visit_id,
               v_appointment_id, v_episode_id, 'PENDING',
               CASE WHEN array_length(n.actor_roles, 1) = 1
                    THEN n.actor_roles[1] END,
               n.priority,
               jsonb_build_object('services', w.svc),
               coalesce(lt.lan, 0) + 1
          FROM wanted w
          LEFT JOIN lan_truoc lt ON lt.node_code = w.node_code
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
           AND w.status IN ('PENDING', 'IN_PROGRESS')
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
