-- Liệu trình ĐỀ XUẤT cũng tự gắn buổi (Tuyền 08/10/2026, thử staging).
--
-- Trước: chỉ liệu trình DANG_LAM được tự gắn buổi. Bác sĩ bấm "Chỉ đề xuất
-- liệu trình (không làm hôm nay)" — hoặc khách bỏ tick buổi 1 ở quầy (#4) —
-- thì liệu trình nằm ở DE_XUAT; lần sau khách đặt lịch Điều trị đến làm đúng
-- dịch vụ ấy, chỉ định KHÔNG vào liệu trình (trừ khi CSKH đã bấm Đăng ký), buổi
-- 1 của lộ trình "tính từ buổi sau" phải gắn tay trên thẻ.
--
-- Giờ: ứng viên tự gắn =
--   1. đúng MỘT liệu trình DANG_LAM cùng dịch vụ → liệu trình ấy (như cũ);
--   2. không có DANG_LAM nào → đúng MỘT liệu trình DE_XUAT cùng dịch vụ;
--   3. còn lại (≥ 2 cùng bậc, hoặc 1 DANG_LAM + nhiều) → không gắn, thẻ bắt chọn.
-- Buổi gắn vào liệu trình DE_XUAT mà khách chốt làm thì `lieu_trinh_truoc_khi_ghi`
-- tự đẩy liệu trình sang DANG_LAM (trạng thái suy ra) — không ghi tay.

CREATE OR REPLACE FUNCTION public.lieu_trinh_ung_vien_duy_nhat(
    p_clinic uuid, p_visit uuid, p_service_code text
) RETURNS uuid
LANGUAGE sql STABLE
SET search_path = public
AS $$
    WITH ung AS (
        SELECT lt.id, lt.trang_thai
          FROM public.lieu_trinh lt
          JOIN public.visit v
            ON v.clinic_id = lt.clinic_id AND v.clinic_patient_id = lt.clinic_patient_id
         WHERE lt.clinic_id = p_clinic AND v.visit_id = p_visit
           AND lt.service_code = p_service_code
           AND lt.trang_thai IN ('DANG_LAM', 'DE_XUAT')
    )
    SELECT CASE
        WHEN (SELECT count(*) FROM ung WHERE trang_thai = 'DANG_LAM') = 1
            THEN (SELECT id FROM ung WHERE trang_thai = 'DANG_LAM')
        WHEN (SELECT count(*) FROM ung WHERE trang_thai = 'DANG_LAM') = 0
         AND (SELECT count(*) FROM ung WHERE trang_thai = 'DE_XUAT') = 1
            THEN (SELECT id FROM ung WHERE trang_thai = 'DE_XUAT')
    END;
$$;

CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_them_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    lt uuid;
BEGIN
    IF NOT public.lieu_trinh_chi_dinh_song(
           NEW.exec_status, NEW.execution_status, NEW.selection_status) THEN
        RETURN NULL;
    END IF;
    -- Đường nhanh: phòng khám không có liệu trình đang mở nào của dịch vụ này.
    IF NOT EXISTS (SELECT 1 FROM public.lieu_trinh
                    WHERE clinic_id = NEW.clinic_id AND service_code = NEW.service_code
                      AND trang_thai IN ('DANG_LAM', 'DE_XUAT')) THEN
        RETURN NULL;
    END IF;
    lt := public.lieu_trinh_ung_vien_duy_nhat(NEW.clinic_id, NEW.visit_id, NEW.service_code);
    IF lt IS NOT NULL THEN
        PERFORM public.lieu_trinh_gan_buoi(NEW.clinic_id, lt, NEW.id, 'TU_DONG', NULL);
    END IF;
    RETURN NULL;
END $$;
