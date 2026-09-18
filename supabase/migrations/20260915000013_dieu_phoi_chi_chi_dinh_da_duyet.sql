-- TRƯỞNG CA CHỈ ĐIỀU PHỐI CHỈ ĐỊNH BÁC SĨ ĐÃ DUYỆT (15/09/2026).
--
-- LUẬT (CONTEXT v1.0): bác sĩ duyệt chỉ định → trưởng ca điều phối. Trưởng ca
-- quyết THỨ TỰ và PHÒNG cho những dịch vụ bác sĩ đã chỉ định; không quyết khách
-- làm THÊM dịch vụ nào, và không quyết một dịch vụ "đã xong".
--
-- `move_visit_to_station` (20260804000013) sai hai chỗ với luật đó, cả hai ở
-- các bước dịch vụ (node_definition.flow_group 'dich_vu' / 'ket_qua'):
--
--   1. Chuyển tới một bước dịch vụ mà lượt khám CHƯA CÓ là hàm tự INSERT
--      work_item mới — tức một chỉ định siêu âm/lấy máu không bác sĩ nào ra.
--      Việc của bước dịch vụ chỉ sinh từ `order_services` (bác sĩ chỉ định,
--      hoặc bác sĩ duyệt bản thư ký nhập — 20260915000008) và chuỗi phụ thuộc
--      của nó. Check-in không sinh bước dịch vụ nào (chuỗi LUOTKHAM-01 chỉ tới
--      tiếp nhận / sinh hiệu / khám / thu ngân).
--
--   2. Rời một bước là hàm đánh work_item của bước đó COMPLETED. Với bước ga
--      (tiếp nhận, khám, thu ngân) đó là mô hình con trỏ đã chọn 04/08. Với bước
--      dịch vụ thì sai: dịch vụ xong khi NGƯỜI THỰC HIỆN bấm hoàn tất
--      (work_item_service, có work_item_event), không phải khi trưởng ca đổi
--      thứ tự vì phòng siêu âm đang đông. Trước bản này, đưa khách từ hàng siêu
--      âm sang lấy máu trước là siêu âm hiện "đã xong" mà chưa ai siêu âm.
--
-- NHÀ THUỐC (THUOC-*) là ngoại lệ của nhóm dịch vụ: nó là một ga điều phối
-- (phòng NHATHUOC, 20260804000001) và không có gì sinh việc sẵn cho nó. Chỉ định
-- của nó là ĐƠN THUỐC — dòng `prescription` chỉ có sau khi bác sĩ kê hoặc duyệt
-- bản thư ký nhập. Nên: chuyển tới nhà thuốc khi lượt khám có đơn, hành xử như ga.
--
-- Bản này: bước dịch vụ đích PHẢI đang có việc mở (PENDING/IN_PROGRESS) —
-- chuyển tới chỉ gắn phòng và con trỏ, KHÔNG đổi trạng thái (người thực hiện
-- bấm bắt đầu). Rời bước dịch vụ KHÔNG đóng việc của nó. Bước ga giữ nguyên
-- hành vi cũ. Đổi phòng trong cùng bước giữ nguyên.

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
            ON CONFLICT (clinic_id, visit_id, node_code)
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
