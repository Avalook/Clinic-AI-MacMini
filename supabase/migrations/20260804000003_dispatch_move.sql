-- ĐƯỜNG GHI VỊ TRÍ BỆNH NHÂN — thứ mà cả bảng điều phối đứng lên trên.
--
-- TÌNH TRẠNG TRƯỚC MIGRATION NÀY (đo trên prod 04/08): `work_item` có 0 dòng,
-- và `visit.current_node_code` NULL ở cả 24 lượt khám. Cột và bảng đã có từ
-- lâu, nhưng KHÔNG CÓ GÌ GHI VÀO. Nghĩa là hôm nay hệ thống không biết bệnh
-- nhân đang đứng ở đâu — và một màn hình điều phối đọc từ đó sẽ trống trơn dù
-- viết đúng đến mấy.
--
-- Nên phần thiếu không phải "màn hình", mà là ĐỘNG TÁC DI CHUYỂN. Hàm dưới đây
-- là đường ghi duy nhất, và nó làm bốn việc trong MỘT giao dịch:
--
--   1. đóng bước đang mở (work_item.finished_at)  ← cho timeline & thời gian chờ
--   2. mở bước mới, gắn phòng                      ← cho hàng đợi từng phòng
--   3. cập nhật con trỏ trên visit                 ← cho bảng toàn cảnh đọc nhanh
--   4. ghi event_log                               ← cho nhật ký điều phối
--
-- Bốn việc rời nhau ở tầng ứng dụng thì một lần mất kết nối giữa chừng để lại
-- bệnh nhân ở hai hàng đợi cùng lúc — đúng một trong những cảnh báo mà chính
-- yêu cầu khách hàng liệt kê ("nằm ở hai hàng đợi bất thường").

ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS current_room_id uuid REFERENCES public.clinic_room(id);

COMMENT ON COLUMN public.visit.current_room_id IS
    'Phòng bệnh nhân đang ở. Con trỏ nhanh cho bảng điều phối; timeline đầy đủ '
    'nằm ở work_item.';

CREATE INDEX IF NOT EXISTS idx_visit_current_room
    ON public.visit (clinic_id, current_room_id)
 WHERE status IN ('OPEN', 'IN_PROGRESS');

-- ---------------------------------------------------------------------------
-- Chuyển một lượt khám sang trạm/phòng khác
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.move_visit_to_station(
    p_clinic_id  uuid,
    p_visit_id   uuid,
    p_node_code  text,
    p_room_id    uuid,
    p_actor      uuid,
    p_reason     text DEFAULT NULL,
    p_event_type text DEFAULT 'dispatch.moved'
)
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
    v_new_item uuid;
BEGIN
    SELECT current_node_code, current_room_id, clinic_patient_id, appointment_id
      INTO v_old_node, v_old_room, v_patient, v_appt
      FROM public.visit
     WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id
     FOR UPDATE;                       -- khoá dòng: hai người điều phối cùng
                                       -- một bệnh nhân thì người sau phải đợi,
                                       -- không được ghi đè nửa chừng.
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy lượt khám % ở phòng khám này', p_visit_id;
    END IF;

    -- Phòng phải phục vụ đúng bước. Xếp bệnh nhân vào SA1 cho bước "Thanh toán"
    -- là một lỗi im lặng: hàng đợi hiện ra ở phòng không ai chờ.
    IF p_room_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.clinic_room r
         WHERE r.id = p_room_id AND r.clinic_id = p_clinic_id
           AND r.node_code = p_node_code AND r.is_active
    ) THEN
        RAISE EXCEPTION 'Phòng đã chọn không phục vụ bước %', p_node_code;
    END IF;

    -- node_definition_version không mang node_code — nó trỏ về node_definition
    -- bằng khoá ngoại. Lấy bản mới nhất để work_item ghim đúng phiên bản định
    -- nghĩa đang hiệu lực lúc bệnh nhân đi qua bước này.
    SELECT v.id INTO v_node_version
      FROM public.node_definition_version v
      JOIN public.node_definition n ON n.id = v.node_definition_id
     WHERE n.code = p_node_code AND n.clinic_id = p_clinic_id
     ORDER BY v.version DESC LIMIT 1;
    IF v_node_version IS NULL THEN
        RAISE EXCEPTION 'Bước % chưa được khai trong node_definition', p_node_code;
    END IF;

    -- 1. Đóng bước đang mở. Nhiều bước mở cùng lúc là trạng thái hỏng, nên đóng
    --    TẤT CẢ chứ không chỉ bước khớp con trỏ.
    UPDATE public.work_item
       SET status = 'COMPLETED', finished_at = now(), updated_at = now()
     WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
       AND status IN ('PENDING', 'IN_PROGRESS');

    -- 2. Mở bước mới.
    INSERT INTO public.work_item
        (clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
         appointment_id, status, room_id, started_at, payload)
    VALUES (p_clinic_id, p_node_code, v_node_version, v_patient, p_visit_id,
            v_appt, 'PENDING', p_room_id, now(),
            jsonb_build_object('moved_from', v_old_node, 'reason', p_reason))
    RETURNING id INTO v_new_item;

    -- 3. Con trỏ trên visit.
    UPDATE public.visit
       SET previous_node_code = v_old_node,
           current_node_code   = p_node_code,
           current_room_id     = p_room_id,
           current_node_since  = now(),
           status = CASE WHEN status = 'OPEN' THEN 'IN_PROGRESS' ELSE status END,
           updated_at = now()
     WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id;

    -- 4. Nhật ký. `event_log` là append-only nên đây là bản ghi không sửa được
    --    của "ai chuyển ai, từ đâu sang đâu, vì sao".
    INSERT INTO public.event_log
        (clinic_id, event_type, aggregate_type, aggregate_id, payload, metadata,
         source, event_published)
    VALUES (p_clinic_id, p_event_type, 'visit', p_visit_id,
            jsonb_build_object(
                'from_node', v_old_node, 'to_node', p_node_code,
                'from_room', v_old_room, 'to_room', p_room_id,
                'reason', p_reason, 'work_item_id', v_new_item),
            jsonb_build_object('actor_auth_user_id', p_actor),
            'api:dispatch', FALSE);

    RETURN v_new_item;
END
$function$;

COMMENT ON FUNCTION public.move_visit_to_station(uuid, uuid, text, uuid, uuid, text, text) IS
    'Đường ghi DUY NHẤT cho vị trí bệnh nhân: đóng bước cũ, mở bước mới, cập '
    'nhật con trỏ visit, ghi event_log — trong một giao dịch. Khoá dòng visit '
    'để hai người điều phối không ghi đè nhau.';

REVOKE ALL ON FUNCTION public.move_visit_to_station(uuid, uuid, text, uuid, uuid, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.move_visit_to_station(uuid, uuid, text, uuid, uuid, text, text)
    TO authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Nhật ký điều phối, đọc được thành bảng
-- ---------------------------------------------------------------------------
-- Không tạo bảng log thứ hai: hai nguồn sự thật cho cùng một câu chuyện là cách
-- chắc chắn để chúng lệch nhau. View này chỉ mở gói event_log ra thành cột.

CREATE OR REPLACE VIEW public.v_dispatch_history
WITH (security_invoker = true) AS
SELECT e.event_id AS id,
       e.clinic_id,
       e.occurred_at AS created_at,
       e.event_type,
       e.aggregate_id                            AS visit_id,
       e.payload ->> 'from_node'                 AS from_node,
       e.payload ->> 'to_node'                   AS to_node,
       rf.code                                   AS from_room,
       rt.code                                   AS to_room,
       e.payload ->> 'reason'                    AS reason,
       s.full_name                               AS actor_name,
       p.full_name                               AS patient_name,
       p.patient_code                            AS patient_code
  FROM public.event_log e
  LEFT JOIN public.clinic_room rf
         ON rf.id = nullif(e.payload ->> 'from_room', '')::uuid
  LEFT JOIN public.clinic_room rt
         ON rt.id = nullif(e.payload ->> 'to_room', '')::uuid
  LEFT JOIN public.staff s
         ON s.auth_user_id = nullif(e.metadata ->> 'actor_auth_user_id', '')::uuid
  LEFT JOIN public.visit v
         ON v.visit_id = e.aggregate_id AND v.clinic_id = e.clinic_id
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = e.clinic_id
 WHERE e.aggregate_type = 'visit'
   AND e.event_type LIKE 'dispatch.%';

COMMENT ON VIEW public.v_dispatch_history IS
    'Nhật ký điều phối. Đọc từ event_log (append-only) chứ không từ một bảng '
    'log riêng — hai nguồn cho cùng một câu chuyện sẽ lệch nhau.';

GRANT SELECT ON public.v_dispatch_history TO authenticated;

DO $verify$
BEGIN
    PERFORM 1 FROM public.v_dispatch_history LIMIT 1;
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'move_visit_to_station') THEN
        RAISE EXCEPTION 'move_visit_to_station chưa được tạo';
    END IF;
    RAISE NOTICE 'đường ghi vị trí + nhật ký điều phối: sẵn sàng';
END
$verify$;
