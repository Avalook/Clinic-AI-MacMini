-- "Khám dở" là trạng thái KHÔNG-CUỐI, và có lý do đi kèm (migration 20260806000004).
--
-- Khách đang khám thì có việc phải về. Trước đây hệ thống không có chỗ nào ghi
-- điều đó, nên cách duy nhất là huỷ lịch hẹn — và hồ sơ trông như người ấy chưa
-- từng đến. Đo được ngày 06/08: 35 lượt đang mở, 18 trong đó check-in từ những
-- ngày trước, không màn hình nào chạm tới.
--
-- File này khẳng định HÀNH VI của lược đồ, không khẳng định hình dạng SQL:
-- trạng thái nào lưu được, đường nào đi được, đường nào bị chặn.
--
-- Mọi thứ rollback.

BEGIN;

CREATE TEMP TABLE _dich ON COMMIT DROP AS
SELECT (SELECT id FROM public.clinic ORDER BY id LIMIT 1)          AS clinic_id,
       (SELECT id FROM public.clinic_location ORDER BY id LIMIT 1) AS location_id;

-- Tự dựng bệnh nhân thay vì đi tìm một dòng có sẵn.
--
-- Bản đầu của bài kiểm này lấy `LIMIT 1` từ bảng patient, và trên lược đồ TRẦN
-- của CI thì bảng đó rỗng — nên nó lặng lẽ tự bỏ qua và báo xanh mà không kiểm
-- gì cả. Một bài kiểm chỉ chạy khi có sẵn dữ liệu là một bài kiểm không chạy.
CREATE TEMP TABLE _bn ON COMMIT DROP AS
WITH moi AS (
    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    SELECT 'BN-KIEMTHU-KHAMDO', 'Kiểm thử khám dở', d.location_id, d.clinic_id
      FROM _dich d
    RETURNING clinic_patient_id
)
SELECT clinic_patient_id FROM moi;

DO $$
DECLARE
    v_clinic  uuid := (SELECT clinic_id FROM _dich);
    v_bn      uuid := (SELECT clinic_patient_id FROM _bn);
    v_visit   uuid;
    v_loi     text;
BEGIN
    -- KHÔNG có nhánh "bỏ qua". Thiếu dữ liệu nghĩa là bài kiểm hỏng, không
    -- phải bài kiểm được miễn.
    IF v_clinic IS NULL OR v_bn IS NULL THEN
        RAISE EXCEPTION 'Không dựng được dữ liệu kiểm (clinic=% bn=%)', v_clinic, v_bn;
    END IF;

    -- ── ① Trạng thái mới lưu được, trạng thái lạ thì không ──────────────────
    INSERT INTO public.visit (clinic_patient_id, status, clinic_id, checked_in_at)
    VALUES (v_bn, 'OPEN', v_clinic, now())
    RETURNING visit_id INTO v_visit;

    UPDATE public.visit
       SET status = 'INCOMPLETE',
           incomplete_at = now(),
           incomplete_reason = 'Khách có việc, xin về giữa chừng'
     WHERE visit_id = v_visit;

    IF (SELECT status FROM public.visit WHERE visit_id = v_visit) <> 'INCOMPLETE' THEN
        RAISE EXCEPTION 'Không lưu được trạng thái khám dở';
    END IF;

    BEGIN
        UPDATE public.visit SET status = 'KHONG_CO_THAT' WHERE visit_id = v_visit;
        RAISE EXCEPTION 'Lược đồ nhận một trạng thái không tồn tại';
    EXCEPTION WHEN check_violation THEN
        NULL;  -- đúng
    END;

    -- ── ② Khám dở PHẢI có lý do ─────────────────────────────────────────────
    -- Một lượt dở không lý do là một người bệnh mà không ai biết phải gọi lại
    -- để nói gì.
    BEGIN
        UPDATE public.visit
           SET incomplete_reason = NULL
         WHERE visit_id = v_visit;
        RAISE EXCEPTION 'Lược đồ cho phép khám dở mà không có lý do';
    EXCEPTION WHEN check_violation THEN
        NULL;  -- đúng
    END;

    BEGIN
        UPDATE public.visit
           SET incomplete_reason = '   '
         WHERE visit_id = v_visit;
        RAISE EXCEPTION 'Lược đồ nhận lý do toàn khoảng trắng';
    EXCEPTION WHEN check_violation THEN
        NULL;  -- đúng
    END;

    -- ── ③ KHÔNG-CUỐI: từ khám dở vẫn ký lên được ────────────────────────────
    -- Đây là tính chất quan trọng nhất. Khách còn quay lại, nên hồ sơ còn phải
    -- chốt được. Nếu bước này hỏng thì "khám dở" đã lặng lẽ trở thành một cái
    -- ngõ cụt.
    UPDATE public.visit
       SET status = 'FINALIZED', finalized_at = now()
     WHERE visit_id = v_visit;

    IF (SELECT status FROM public.visit WHERE visit_id = v_visit) <> 'FINALIZED' THEN
        RAISE EXCEPTION 'Từ khám dở không ký lên FINALIZED được';
    END IF;

    -- ── ④ Ký rồi thì không quay về khám dở được ─────────────────────────────
    BEGIN
        UPDATE public.visit SET status = 'INCOMPLETE' WHERE visit_id = v_visit;
        RAISE EXCEPTION 'Kéo được một hồ sơ ĐÃ KÝ về trạng thái khám dở';
    EXCEPTION WHEN others THEN
        GET STACKED DIAGNOSTICS v_loi = MESSAGE_TEXT;
        IF v_loi LIKE '%Kéo được%' THEN
            RAISE;
        END IF;
    END;

    -- ── ⑤ Vẫn không xoá cứng được ───────────────────────────────────────────
    BEGIN
        DELETE FROM public.visit WHERE visit_id = v_visit;
        RAISE EXCEPTION 'Xoá cứng được một lượt khám';
    EXCEPTION WHEN others THEN
        GET STACKED DIAGNOSTICS v_loi = MESSAGE_TEXT;
        IF v_loi LIKE '%Xoá cứng được%' THEN
            RAISE;
        END IF;
    END;

    RAISE NOTICE 'luot_kham_do: 5/5 tính chất đúng';
END $$;

ROLLBACK;
