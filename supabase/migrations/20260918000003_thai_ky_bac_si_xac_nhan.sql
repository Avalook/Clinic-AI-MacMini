-- Thai kỳ: bác sĩ tạo / xác nhận / chuyển kết cục trên bảng `pregnancy` SẴN CÓ
-- (batch pilot 18/09/2026). Không tạo bảng thai kỳ thứ hai.
--
-- Trước đây bảng này chỉ đọc được: RLS chỉ có SELECT và backend không có lối
-- ghi nào, nên không vai nào — kể cả bác sĩ — tạo được thai kỳ trong app. Dự
-- kiến sinh nằm rải ở ba chỗ (phiếu Sản, SOAP, `pregnancy.edd_date`).
--
-- Thêm đúng những gì cần để biết NGUỒN của dự kiến sinh và AI chịu trách nhiệm:
--   * `edd_nguon`: bác sĩ ghi dự kiến sinh lấy từ đâu (kỳ kinh cuối / siêu âm /
--     khác). Hệ thống KHÔNG tự tính dự kiến sinh — chưa có quy tắc Dr4Women.
--   * `created_by`, `updated_by`, `xac_nhan_visit_id`: bác sĩ nào, ở lượt nào.
-- Chỉ bác sĩ ghi được — gác ở FastAPI (`thai_ky_service`), RLS giữ chỉ-đọc.
--
-- MỘT THAI KỲ ĐANG THEO DÕI MỖI KHÁCH: chỉ mục duy nhất bảo đảm ở Postgres.
-- Dữ liệu cũ có thể đã trùng (không có lối ghi nào kiểm), nên chỉ tạo chỉ mục
-- khi sạch; trùng thì báo NOTICE và để người xem — không tự xoá hay sửa dòng.

ALTER TABLE public.pregnancy
    ADD COLUMN IF NOT EXISTS edd_nguon text,
    ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS updated_by uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS xac_nhan_visit_id uuid;

ALTER TABLE public.pregnancy DROP CONSTRAINT IF EXISTS pregnancy_edd_nguon_check;
ALTER TABLE public.pregnancy ADD CONSTRAINT pregnancy_edd_nguon_check
    CHECK (edd_nguon IS NULL OR edd_nguon IN ('KY_KINH_CUOI', 'SIEU_AM', 'KHAC'));

DO $$
DECLARE
    so_trung integer;
BEGIN
    SELECT count(*) INTO so_trung FROM (
        SELECT clinic_id, clinic_patient_id FROM public.pregnancy
         WHERE outcome = 'ONGOING'
         GROUP BY clinic_id, clinic_patient_id HAVING count(*) > 1
    ) t;
    IF so_trung = 0 THEN
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pregnancy_mot_thai_ky_dang_theo_doi
            ON public.pregnancy (clinic_id, clinic_patient_id)
            WHERE outcome = 'ONGOING';
    ELSE
        RAISE NOTICE 'pregnancy: % khách có hơn một thai kỳ ONGOING — chưa tạo chỉ mục duy nhất, cần người xem.', so_trung;
    END IF;
END $$;

COMMENT ON COLUMN public.pregnancy.edd_nguon IS
    'Dự kiến sinh lấy từ đâu — bác sĩ chọn khi xác nhận (KY_KINH_CUOI | SIEU_AM '
    '| KHAC). Hệ thống không tự tính dự kiến sinh. 20260918000003.';
