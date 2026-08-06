-- Lượt đã đóng không bị kéo ngược (migration 20260807000003).
--
-- Dựng lại ĐÚNG chuỗi đã xảy ra trên production ngày 06/08:
--   14:49  check-in, mở cùng lúc hai bước; "Sinh hiệu" IN_PROGRESS
--   16:50  Lễ tân đóng lượt (bước đóng COMPLETED, closed_at được ghi)
--   18:21  một bước khác đổi trạng thái → trigger chạy lại
--   → trước khi sửa: current_node_code bị ghi đè về "Sinh hiệu"
--   → sau khi sửa:  đứng yên ở bước đóng
--
-- Mọi thứ rollback.

BEGIN;

DO $$
DECLARE
    v_clinic uuid := (SELECT id FROM public.clinic ORDER BY id LIMIT 1);
    v_loc    uuid := (SELECT id FROM public.clinic_location ORDER BY id LIMIT 1);
    v_bn     uuid;
    v_visit  uuid;
    v_node   text;
    v_ver    uuid;
BEGIN
    IF v_clinic IS NULL OR v_loc IS NULL THEN
        RAISE EXCEPTION 'Không dựng được dữ liệu kiểm (clinic=% loc=%)',
            v_clinic, v_loc;
    END IF;

    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-KIEMTHU-DONGYEN', 'Kiểm thử đứng yên', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn;

    INSERT INTO public.visit (clinic_patient_id, status, clinic_id, checked_in_at)
    VALUES (v_bn, 'IN_PROGRESS', v_clinic, now() - interval '4 hours')
    RETURNING visit_id INTO v_visit;

    -- Hai bước, kiểu check-in mở sẵn cả hai.
    FOR v_node IN SELECT unnest(ARRAY['LUOTKHAM-03', 'LUOTKHAM-15']) LOOP
        SELECT nv.id INTO v_ver
          FROM public.node_definition_version nv
          JOIN public.node_definition nd ON nd.id = nv.node_definition_id
         WHERE nd.code = v_node AND nd.clinic_id = v_clinic
         ORDER BY nv.version DESC LIMIT 1;

        INSERT INTO public.work_item
            (clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
             status, started_at)
        VALUES (v_clinic, v_node, v_ver, v_bn, v_visit,
                'IN_PROGRESS', now() - interval '4 hours');
    END LOOP;

    -- Sau bước trên, trigger đã đặt con trỏ vào một trong hai bước.
    IF (SELECT current_node_code FROM public.visit WHERE visit_id = v_visit)
       IS NULL THEN
        RAISE EXCEPTION 'Trigger không đặt con trỏ — bài kiểm dựng sai';
    END IF;

    -- ── Lễ tân đóng lượt: bước đóng COMPLETED + closed_at ──────────────────
    UPDATE public.work_item
       SET status = 'COMPLETED', finished_at = now() - interval '90 minutes'
     WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-15';

    UPDATE public.visit
       SET current_node_code = 'LUOTKHAM-15',
           current_node_since = now() - interval '90 minutes',
           closed_at = now() - interval '90 minutes'
     WHERE visit_id = v_visit;

    -- ── 90 phút sau: một bước khác đổi trạng thái, trigger chạy lại ────────
    -- Đây là cú đánh đã làm hỏng dữ liệu thật. "Sinh hiệu" vẫn IN_PROGRESS.
    UPDATE public.work_item
       SET status = 'IN_PROGRESS', updated_at = now()
     WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-03';

    IF (SELECT current_node_code FROM public.visit WHERE visit_id = v_visit)
       <> 'LUOTKHAM-15' THEN
        RAISE EXCEPTION
            'Lượt đã đóng bị kéo về %, đáng lẽ phải đứng yên ở LUOTKHAM-15',
            (SELECT current_node_code FROM public.visit WHERE visit_id = v_visit);
    END IF;

    -- ── Lượt CHƯA đóng thì trigger vẫn phải chạy bình thường ───────────────
    -- Không có khẳng định này thì một bản vá kiểu "trigger không làm gì nữa"
    -- cũng qua được bài kiểm.
    UPDATE public.visit SET closed_at = NULL WHERE visit_id = v_visit;
    UPDATE public.work_item
       SET status = 'COMPLETED', finished_at = now()
     WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-15';
    UPDATE public.work_item
       SET status = 'IN_PROGRESS', started_at = now(),
           finished_at = NULL, updated_at = now()
     WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-03';

    IF (SELECT current_node_code FROM public.visit WHERE visit_id = v_visit)
       <> 'LUOTKHAM-03' THEN
        RAISE EXCEPTION
            'Lượt CHƯA đóng mà trigger không theo bước đang làm (đang chỉ %)',
            (SELECT current_node_code FROM public.visit WHERE visit_id = v_visit);
    END IF;

    -- ── HUỶ MỘT BƯỚC ĐANG TREO PHẢI ĐẶT ĐƯỢC finished_at ───────────────────
    -- Ràng buộc `work_item_finished_when_terminal` buộc
    -- status ∈ (COMPLETED, SKIPPED, CANCELLED) ⟺ finished_at IS NOT NULL.
    --
    -- Bản đầu của migration 20260807000003 quên điều đó và bị PRODUCTION từ
    -- chối, không phải bài kiểm — vì đoạn dọn của nó khớp 0 dòng trên lược đồ
    -- trần rồi chạy qua trong im lặng. Khẳng định này dựng đúng tình huống ấy:
    -- một lượt ĐÃ ĐÓNG mà vẫn còn bước treo.
    UPDATE public.visit
       SET status = 'IN_PROGRESS', closed_at = now()
     WHERE visit_id = v_visit;
    UPDATE public.work_item
       SET status = 'IN_PROGRESS', started_at = now(),
           finished_at = NULL, updated_at = now()
     WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-03';

    BEGIN
        UPDATE public.work_item
           SET status = 'CANCELLED',
               finished_at = coalesce(finished_at, now()),
               updated_at = now()
         WHERE visit_id = v_visit
           AND status IN ('PENDING', 'IN_PROGRESS');
    EXCEPTION WHEN check_violation THEN
        RAISE EXCEPTION 'Huỷ bước treo bị ràng buộc chặn: %', SQLERRM;
    END;

    IF EXISTS (SELECT 1 FROM public.work_item
                WHERE visit_id = v_visit
                  AND status IN ('PENDING', 'IN_PROGRESS')) THEN
        RAISE EXCEPTION 'Còn bước treo sau khi đã đóng lượt';
    END IF;

    -- ── Hồ sơ đã CHỐT cũng phải đứng yên, dù closed_at trống ───────────────
    UPDATE public.visit SET status = 'FINALIZED', current_node_code = 'LUOTKHAM-15'
     WHERE visit_id = v_visit;
    UPDATE public.work_item
       SET status = 'IN_PROGRESS', started_at = now(),
           finished_at = NULL, updated_at = now()
     WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-03';

    IF (SELECT current_node_code FROM public.visit WHERE visit_id = v_visit)
       <> 'LUOTKHAM-15' THEN
        RAISE EXCEPTION 'Hồ sơ đã chốt vẫn bị kéo ngược';
    END IF;

    RAISE NOTICE 'luot_da_dong_thi_dung_yen: tất cả khẳng định đều đạt';
END $$;

ROLLBACK;
