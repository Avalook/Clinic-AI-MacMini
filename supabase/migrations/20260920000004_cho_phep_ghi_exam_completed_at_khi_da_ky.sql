-- Cho phép ghi nhận mốc khám xong (exam_completed_at) lần đầu khi bác sĩ đã ký bệnh án.
--
-- VÌ SAO CẦN CẬP NHẬT TRIGGER visit_finalized_block_update:
--
-- Trên UI Bàn khám, quy trình thực tế bác sĩ làm việc là:
--   1. Nhập hồ sơ / SOAP / đơn thuốc
--   2. KÝ bệnh án (visit.status -> FINALIZED, finalized_at = now())
--   3. Bấm "Khám xong" trên Bàn khám để hoàn tất phiên khám và đẩy sang Thu ngân / Nhà thuốc.
--
-- Ký bệnh án ≠ Khám xong:
--   - Chữ ký là hành vi chuyên môn chốt hồ sơ bệnh án theo TT13/2011/TT-BYT.
--   - Khám xong là mốc vận hành (exam_completed_at) đóng phiên khám và cho phép thu tiền.
--
-- Trigger cũ chặn MỌI câu UPDATE lên `visit` khi OLD.status = 'FINALIZED',
-- trừ duy nhất đường FINALIZED -> AMENDED. Khi bác sĩ ký trước rồi bấm Khám xong sau,
-- câu lệnh `_ket_thuc_neu_xong` cố ghi mốc `exam_completed_at` lần đầu bị trigger chặn lỗi.
--
-- NGOẠI LỆ AN TOÀN DUY NHẤT:
--   Cho phép ghi `exam_completed_at` khi:
--   1. OLD.exam_completed_at IS NULL và NEW.exam_completed_at IS NOT NULL
--   2. MỌI cột khác của visit (ngoài exam_completed_at và updated_at) phải GIỐNG HỆT OLD:
--      (to_jsonb(NEW) - ARRAY['exam_completed_at', 'updated_at']) =
--      (to_jsonb(OLD) - ARRAY['exam_completed_at', 'updated_at'])
--   Bất kỳ cố gắng đổi trường nào khác (service_type_id, attending_doctor_id,
--   status, appointment_id, v.v.) hoặc sửa đè mốc đã có VẪN BỊ CHẶN TUYỆT ĐỐI (check_violation).

CREATE OR REPLACE FUNCTION public.visit_finalized_block_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.status = 'FINALIZED' AND NEW.status <> 'AMENDED' THEN
        -- Ngoại lệ an toàn duy nhất: ghi nhận mốc khám xong (exam_completed_at) lần đầu
        -- khi bác sĩ ký bệnh án trước rồi bấm khám xong sau.
        -- BẮT BUỘC:
        -- 1. exam_completed_at từ NULL -> NOT NULL
        -- 2. MỌI cột khác của visit (trừ exam_completed_at và updated_at) phải GIỐNG HỆT OLD.
        IF OLD.exam_completed_at IS NULL
           AND NEW.exam_completed_at IS NOT NULL
           AND (to_jsonb(NEW) - ARRAY['exam_completed_at', 'updated_at'])
             = (to_jsonb(OLD) - ARRAY['exam_completed_at', 'updated_at']) THEN
            RETURN NEW;
        END IF;

        RAISE EXCEPTION
            'visit % is FINALIZED; UPDATE blocked except FINALIZED -> AMENDED (TT13/2011/TT-BYT)',
            OLD.visit_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.visit_finalized_block_update() IS
    'Khóa hồ sơ bệnh án theo TT13/2011/TT-BYT khi status=FINALIZED. '
    'Chỉ cho phép: (1) FINALIZED -> AMENDED khi có đính chính, '
    'hoặc (2) ghi mốc exam_completed_at lần đầu nếu bác sĩ ký trước rồi bấm khám xong (mọi cột khác bất biến).';
