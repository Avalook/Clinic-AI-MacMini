-- `move_visit_to_station` đóng NHẦM cả checklist, không chỉ bước đang rời.
--
-- HAI MÔ HÌNH GẶP NHAU VÀ TÔI CHỈ THẤY MỘT.
--
-- `instantiate_visit_workflow()` (đã có từ trước) tạo TOÀN BỘ các bước của lượt
-- khám ngay lúc check-in, tất cả ở trạng thái PENDING — một danh sách việc phải
-- làm. Đo trên prod: 7 dòng cho một lượt.
--
-- `move_visit_to_station()` (20260804000003, tôi viết) lại giả định mỗi lúc chỉ
-- có MỘT bước mở, nên nó làm:
--
--     UPDATE work_item SET status='COMPLETED'
--      WHERE visit_id = … AND status IN ('PENDING','IN_PROGRESS')
--
-- Ghép hai cái lại: lần đầu Trưởng ca chuyển bệnh nhân đi đâu đó, SÁU bước chưa
-- làm bỗng thành "đã hoàn tất". Sinh hiệu chưa đo, thanh toán chưa thu — tất cả
-- đánh dấu xong. Không có gì báo lỗi; checklist chỉ đơn giản là biến mất.
--
-- Cả hai mô hình đều đúng và đều cần: danh sách việc trả lời "còn gì chưa làm",
-- con trỏ trả lời "người này đang ở đâu". Chỗ sai là câu UPDATE quét quá rộng.
--
-- Bản này chỉ đóng ĐÚNG bước đang rời khỏi. Các bước chưa tới lượt vẫn PENDING,
-- và bước được chuyển tới thành IN_PROGRESS — tức là "đang ở đây", phân biệt
-- được với "đang xếp hàng chờ" mà bảng tải từng phòng đang dựa vào.

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
    v_item uuid;
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
         WHERE r.id = p_room_id AND r.clinic_id = p_clinic_id
           AND r.node_code = p_node_code AND r.is_active
    ) THEN
        RAISE EXCEPTION 'Phòng đã chọn không phục vụ bước %', p_node_code;
    END IF;

    IF p_node_code IS DISTINCT FROM v_old_node THEN
        -- CHỈ đóng bước đang rời. Không đụng tới các bước chưa tới lượt —
        -- chúng là việc còn phải làm, không phải việc đã xong.
        IF v_old_node IS NOT NULL THEN
            UPDATE public.work_item
               SET status = 'COMPLETED', finished_at = now(), updated_at = now()
             WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
               AND node_code = v_old_node
               AND status IN ('PENDING', 'IN_PROGRESS');
        END IF;

        SELECT v.id INTO v_node_version
          FROM public.node_definition_version v
          JOIN public.node_definition n ON n.id = v.node_definition_id
         WHERE n.code = p_node_code AND n.clinic_id = p_clinic_id
         ORDER BY v.version DESC LIMIT 1;
        IF v_node_version IS NULL THEN
            RAISE EXCEPTION 'Bước % chưa được khai trong node_definition',
                p_node_code;
        END IF;

        -- IN_PROGRESS, không phải PENDING: bệnh nhân ĐANG Ở đây. Bảng tải từng
        -- phòng đếm "đang phục vụ" bằng IN_PROGRESS và "đang chờ" bằng PENDING;
        -- để nguyên PENDING thì mọi phòng vĩnh viễn hiện "đang phục vụ 0".
        INSERT INTO public.work_item
            (clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
             appointment_id, status, room_id, started_at, finished_at, payload)
        VALUES (p_clinic_id, p_node_code, v_node_version, v_patient, p_visit_id,
                v_appt, 'IN_PROGRESS', p_room_id, now(), NULL,
                jsonb_build_object('moved_from', v_old_node, 'reason', p_reason))
        ON CONFLICT (clinic_id, visit_id, node_code)
            WHERE visit_id IS NOT NULL AND status <> 'CANCELLED'
        DO UPDATE SET status = 'IN_PROGRESS',
                      room_id = EXCLUDED.room_id,
                      started_at = coalesce(work_item.started_at, now()),
                      finished_at = NULL,
                      updated_at = now()
        RETURNING id INTO v_item;
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
           -- Đổi phòng KHÔNG làm mới đồng hồ chờ: người đã đợi 20 phút ở SA1
           -- sang SA2 vẫn là người đã đợi 20 phút.
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

-- ---------------------------------------------------------------------------
-- Đặt bệnh nhân vào trạm đầu tiên ngay khi check-in
-- ---------------------------------------------------------------------------
-- Đây là mắt xích còn thiếu giữa Lễ tân và bảng điều phối: check-in đã tạo lượt
-- khám và cả danh sách bước, nhưng KHÔNG đặt con trỏ vị trí — nên bảng điều
-- phối không thấy ai, dù bệnh nhân đã đứng trong phòng khám.
--
-- Trạm đầu tiên = bước PENDING sớm nhất CÓ PHÒNG phục vụ. Bỏ qua các bước
-- không gắn phòng (xác minh hồ sơ, đối soát chi phí) vì đặt bệnh nhân vào một
-- bước không có phòng thì bảng hiện họ "đang ở — " và không hàng đợi nào nhận.

CREATE OR REPLACE FUNCTION public.place_visit_at_first_station(
    p_clinic_id uuid,
    p_visit_id  uuid,
    p_actor     uuid
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_node text;
    v_room uuid;
BEGIN
    -- Đã có vị trí thì không đặt lại: check-in lần hai (hoặc một lần bấm nhầm
    -- rồi bấm lại) không được kéo bệnh nhân từ phòng siêu âm về quầy sinh hiệu.
    IF EXISTS (SELECT 1 FROM public.visit
                WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id
                  AND current_node_code IS NOT NULL) THEN
        RETURN NULL;
    END IF;

    SELECT w.node_code, r.id
      INTO v_node, v_room
      FROM public.work_item w
      JOIN public.clinic_room r
        ON r.node_code = w.node_code AND r.clinic_id = w.clinic_id
       AND r.is_active AND r.accepting
     WHERE w.clinic_id = p_clinic_id AND w.visit_id = p_visit_id
       AND w.status = 'PENDING'
     ORDER BY r.sort, w.created_at
     LIMIT 1;

    IF v_node IS NULL THEN
        RETURN NULL;
    END IF;

    RETURN public.move_visit_to_station(
        p_clinic_id, p_visit_id, v_node, v_room, p_actor,
        'Tiếp nhận — vào trạm đầu tiên', 'dispatch.checkin');
END
$function$;

COMMENT ON FUNCTION public.place_visit_at_first_station(uuid, uuid, uuid) IS
    'Đặt lượt khám vừa check-in vào trạm đầu tiên có phòng. Không làm gì nếu '
    'lượt đã có vị trí — check-in lần hai không được kéo bệnh nhân quay lại.';

REVOKE ALL ON FUNCTION public.place_visit_at_first_station(uuid, uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.place_visit_at_first_station(uuid, uuid, uuid)
    TO authenticated, service_role;

DO $verify$
BEGIN
    RAISE NOTICE 'move: chỉ đóng bước đang rời; thêm place_visit_at_first_station';
END
$verify$;
