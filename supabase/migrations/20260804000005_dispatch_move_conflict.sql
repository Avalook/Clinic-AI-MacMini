-- ON CONFLICT không nhận ra chỉ mục vì vị từ thiếu một vế.
--
-- 20260804000004 dùng `ON CONFLICT … WHERE status <> 'CANCELLED'`, nhưng chỉ mục
-- thật là:
--
--     WHERE (visit_id IS NOT NULL) AND (status <> 'CANCELLED')
--
-- Postgres đòi vị từ TRÙNG KHỚP, không chấp nhận một vị từ hẹp hơn hay rộng hơn,
-- nên nó báo "no unique or exclusion constraint matching the ON CONFLICT
-- specification" — và nhánh "quay lại một bước đã đi qua" chết ngay lần đầu chạy.
--
-- Lỗi này chỉ lộ ra khi chạy thật với một lượt khám thật: nó không phải lỗi cú
-- pháp, migration trước đó đã áp thành công.

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
     FOR UPDATE;                       -- hai người điều phối cùng một bệnh nhân
                                       -- thì người sau phải đợi, không ghi đè.
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
        -- Sang bước khác: đóng mọi bước đang mở. Nhiều bước mở cùng lúc là
        -- trạng thái hỏng ("nằm ở hai hàng đợi"), nên đóng tất cả chứ không chỉ
        -- bước khớp con trỏ.
        UPDATE public.work_item
           SET status = 'COMPLETED', finished_at = now(), updated_at = now()
         WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
           AND status IN ('PENDING', 'IN_PROGRESS');

        SELECT v.id INTO v_node_version
          FROM public.node_definition_version v
          JOIN public.node_definition n ON n.id = v.node_definition_id
         WHERE n.code = p_node_code AND n.clinic_id = p_clinic_id
         ORDER BY v.version DESC LIMIT 1;
        IF v_node_version IS NULL THEN
            RAISE EXCEPTION 'Bước % chưa được khai trong node_definition',
                p_node_code;
        END IF;

        INSERT INTO public.work_item
            (clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
             appointment_id, status, room_id, started_at, finished_at, payload)
        VALUES (p_clinic_id, p_node_code, v_node_version, v_patient, p_visit_id,
                v_appt, 'PENDING', p_room_id, now(), NULL,
                jsonb_build_object('moved_from', v_old_node, 'reason', p_reason))
        -- Quay lại một bước đã đi qua (đổi tuyến giữa chừng) thì MỞ LẠI dòng cũ.
        -- Vị từ phải TRÙNG KHỚP vị từ của chỉ mục, không chỉ ngụ ý nó. Chỉ mục
        -- là `WHERE visit_id IS NOT NULL AND status <> 'CANCELLED'`; thiếu vế
        -- đầu thì Postgres không nhận ra chỉ mục nào và báo "no unique or
        -- exclusion constraint matching the ON CONFLICT specification".
        ON CONFLICT (clinic_id, visit_id, node_code)
            WHERE visit_id IS NOT NULL AND status <> 'CANCELLED'
        DO UPDATE SET status = 'PENDING',
                      room_id = EXCLUDED.room_id,
                      started_at = now(),
                      finished_at = NULL,
                      updated_at = now(),
                      payload = work_item.payload
                                || jsonb_build_object('reentered_at', now())
        RETURNING id INTO v_item;
    ELSE
        -- Cùng bước, khác phòng: SA1 → SA2. Không tạo bước mới.
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
           -- Đổi phòng KHÔNG làm mới đồng hồ chờ: bệnh nhân đã đợi 20 phút ở
           -- SA1 thì sang SA2 vẫn là người đã đợi 20 phút. Đặt lại mốc ở đây sẽ
           -- xoá sạch mọi cảnh báo quá giờ đúng lúc chúng cần được nhìn thấy.
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

DO $verify$
BEGIN
    RAISE NOTICE 'move_visit_to_station: vị từ ON CONFLICT đã khớp chỉ mục';
END
$verify$;
