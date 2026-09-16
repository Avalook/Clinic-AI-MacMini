-- "CA KHÁM CỦA BÁC SĨ" THEO LỊCH MỚI (17/09/2026).
--
-- Đặt lịch, cảnh báo mất bác sĩ, trang chủ và lưới lịch hẹn tuần đều hỏi "hôm ấy
-- bác sĩ này có ngồi khám không" bằng `station = 'LICH_KHAM'` — mã của mẫu lịch
-- cũ. Lịch Kim Ngưu xếp bác sĩ vào vị trí cụ thể (BS Nội tiết, BS Sản, BS siêu
-- âm…), nên với lịch mới câu hỏi ấy luôn ra "không", và màn đặt lịch mất sạch bác
-- sĩ. Một hàm duy nhất trả lời, để mọi nơi hỏi cùng một câu.
CREATE OR REPLACE FUNCTION public.la_ca_kham_bac_si(p_clinic_id uuid, p_station text)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path TO 'public', 'pg_temp'
AS $$
    SELECT p_station = 'LICH_KHAM'
        OR EXISTS (
            SELECT 1
              FROM public.vi_tri_lam_viec v
             WHERE v.clinic_id = p_clinic_id
               AND v.code = p_station
               AND v.nhom_nghe = 'BAC_SI'
               AND v.is_active
        );
$$;

GRANT EXECUTE ON FUNCTION public.la_ca_kham_bac_si(uuid, text) TO authenticated, service_role;
