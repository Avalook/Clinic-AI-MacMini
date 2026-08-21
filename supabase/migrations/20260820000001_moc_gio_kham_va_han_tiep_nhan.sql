-- Hai mốc thời gian riêng cho quầy lễ tân, và hạn chót có thật.
--
-- Tuyền chốt 20/08/2026, hai việc trong một migration vì chúng cùng phục vụ một
-- màn hình và cùng đọc một bảng:
--
--   ① `visit.exam_started_at` — GIỜ BẮT ĐẦU KHÁM, tách khỏi giờ check-in.
--      *"check-in lúc 18h, gọi khách vào lúc 18h10, thì thời gian khám tính từ
--      18h10; check-in chỉ là mốc của buổi khám thôi."*
--      Hai quỹ thời gian khác nhau: `checked_in_at` đo KHÁCH CHỜ BAO LÂU,
--      `exam_started_at` đo BUỔI KHÁM DÀI BAO LÂU. Gộp một cột là mất vĩnh viễn
--      khả năng phân tích cả hai — và số liệu ấy để dành cho việc xếp lịch sau này.
--      Bảng đã có `exam_completed_at` từ trước; cột này là cái đầu còn thiếu của
--      cùng một cặp.
--
--   ② `work_item.due_at` được GHI THẬT lúc sinh việc.
--      Cột `due_at` có từ đầu nhưng CHƯA TỪNG có dòng code nào ghi vào — đo trên
--      staging 19/08: 242 việc, 0 cái có hạn. Nên ô "Quá SLA" của lễ tân vĩnh
--      viễn bằng 0, thanh tiến độ vĩnh viễn 0%, và người ngồi quầy học được một
--      điều sai: "chưa ai quá hạn".
--      Hạn lấy từ `node_definition.config->>'sla_minutes'` chứ không viết cứng,
--      cùng lý lẽ với cửa sổ "đến đúng giờ" trong `queue_order.py`: con số này
--      là CHÍNH SÁCH của phòng khám, không phải hằng số của lập trình viên.
--
-- Bước duy nhất được đặt hạn lúc này là LUOTKHAM-02 (Xác minh người bệnh) — 15
-- phút, bằng đúng một khung giờ khám. Đây là khoảng từ lúc khách check-in tới
-- lúc được gọi vào khám, tức đúng thứ lễ tân kiểm soát được.
-- LUOTKHAM-01 không cần hạn: nó sinh ra đã COMPLETED ngay tại cú check-in.

BEGIN;

-- ① Mốc bắt đầu khám ------------------------------------------------------
ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS exam_started_at timestamptz,
    ADD COLUMN IF NOT EXISTS exam_started_by uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.visit.exam_started_at IS
    'Lúc khách được GỌI VÀO KHÁM. Quỹ thời gian riêng, tách khỏi checked_in_at: '
    'checked_in_at đo thời gian CHỜ, cột này mở đầu thời gian KHÁM.';
COMMENT ON COLUMN public.visit.exam_started_by IS
    'Nhân viên bấm gọi vào khám — để lịch sử thao tác nói được ai làm.';

-- Truy vấn hay hỏi "hôm nay ai đã được gọi vào khám chưa", luôn kèm clinic_id
-- (bất biến đa phòng khám: index phải dẫn đầu bằng clinic_id).
CREATE INDEX IF NOT EXISTS idx_visit_clinic_exam_started
    ON public.visit (clinic_id, exam_started_at)
    WHERE exam_started_at IS NOT NULL;

-- ② Hạn chót cho bước Xác minh -------------------------------------------
UPDATE public.node_definition
   SET config = coalesce(config, '{}'::jsonb) || jsonb_build_object('sla_minutes', 15),
       updated_at = now()
 WHERE code = 'LUOTKHAM-02';

-- ③ Sinh việc thì ghi luôn hạn -------------------------------------------
-- Bản dưới đây là hàm ĐANG CHẠY, chỉ thêm cột `due_at` vào câu INSERT.

CREATE OR REPLACE FUNCTION public.instantiate_visit_workflow(p_clinic_id uuid, p_visit_id uuid, p_actor_staff_id uuid, p_actor_role text DEFAULT NULL::text, p_spawn_on text DEFAULT 'visit.checkin'::text)
 RETURNS integer
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'public'
AS $function$
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
            priority, started_at, finished_at, due_at)
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
                    THEN now() END,
               -- HẠN CHÓT ĐI THEO CẤU HÌNH CỦA TỪNG BƯỚC, không phải hằng số.
               -- Bước nào không khai `sla_minutes` thì due_at = NULL và ô "Quá
               -- SLA" bỏ qua nó — im lặng có chủ ý, hơn là bịa một hạn cho
               -- mọi bước rồi cả bảng đỏ rực.
               CASE WHEN (n.config ->> 'sla_minutes') ~ '^[0-9]+$'
                    THEN now()
                       + ((n.config ->> 'sla_minutes')::int * interval '1 minute')
               END
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
$function$;

COMMIT;
