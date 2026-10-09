-- Liệu trình MINH BẠCH (Tuyền 09/10/2026, sau bấm thử staging).
--
-- Lỗi thấy trên staging: bác sĩ đề xuất lộ trình 4 buổi, khách CHƯA làm buổi nào,
-- đặt lượt Điều trị cùng dịch vụ → lượt ấy hiện "Buổi 2/4". Hai gốc:
--   1. `buoi_so` cấp lúc GẮN (bác sĩ bấm tạo → chỉ định hôm nay thành buổi 1;
--      trigger tự gắn chỉ định mới vào cả liệu trình mới ĐỀ XUẤT — mig
--      20261008900000), không phải lúc LÀM XONG.
--   2. Đề xuất của bác sĩ bị coi như khách đã nhận lộ trình.
--
-- Luật mới:
--   * Mặc định mỗi chỉ định điều trị là BUỔI LẺ. Chỉ khi KHÁCH CHỌN lộ trình
--     (lệnh đăng ký / gắn tay) mới vào liệu trình → trigger tự gắn chỉ còn nhắm
--     liệu trình ĐANG LÀM (bỏ bậc DE_XUAT của 20261008900000).
--   * Số buổi HIỆN = thứ tự LÀM XONG; buổi chưa làm đứng sau mọi buổi đã làm và
--     ghi rõ "chưa làm". `buoi_so` lưu trong bảng giữ nguyên (khoá duy nhất, chia
--     tiền trả trước) — mọi màn đọc số qua view `v_lieu_trinh_buoi`.

CREATE OR REPLACE FUNCTION public.lieu_trinh_ung_vien_duy_nhat(
    p_clinic uuid, p_visit uuid, p_service_code text
) RETURNS uuid
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT CASE WHEN count(*) = 1 THEN (array_agg(lt.id))[1] END
      FROM public.lieu_trinh lt
      JOIN public.visit v
        ON v.clinic_id = lt.clinic_id AND v.clinic_patient_id = lt.clinic_patient_id
     WHERE lt.clinic_id = p_clinic AND v.visit_id = p_visit
       AND lt.service_code = p_service_code AND lt.trang_thai = 'DANG_LAM';
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
    -- Đường nhanh: phòng khám không có liệu trình đang làm nào của dịch vụ này.
    IF NOT EXISTS (SELECT 1 FROM public.lieu_trinh
                    WHERE clinic_id = NEW.clinic_id AND service_code = NEW.service_code
                      AND trang_thai = 'DANG_LAM') THEN
        RETURN NULL;
    END IF;
    lt := public.lieu_trinh_ung_vien_duy_nhat(NEW.clinic_id, NEW.visit_id, NEW.service_code);
    IF lt IS NOT NULL THEN
        PERFORM public.lieu_trinh_gan_buoi(NEW.clinic_id, lt, NEW.id, 'TU_DONG', NULL);
    END IF;
    RETURN NULL;
END $$;

-- Buổi + số HIỆN. `da_lam` cùng luật đếm "đã làm" của liệu trình
-- (COMPLETED, hoặc chỉ định đời cũ performed). Buổi đã gỡ giữ số lúc gắn (chỉ
-- để kể lịch sử).
CREATE OR REPLACE VIEW public.v_lieu_trinh_buoi
    WITH (security_invoker = true) AS
WITH x AS (
    SELECT b.*,
           (coalesce(o.execution_status, '') = 'COMPLETED'
            OR (o.execution_status IS NULL AND o.exec_status = 'performed')) AS da_lam,
           o.finished_at AS xong_luc
      FROM public.lieu_trinh_buoi b
      JOIN public.service_order o
        ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
)
SELECT x.id, x.clinic_id, x.lieu_trinh_id, x.service_order_id,
       x.buoi_so AS buoi_so_goc, x.tra_truoc, x.gan_luc, x.gan_boi, x.gan_cach,
       x.go_luc, x.go_boi, x.go_cach, x.da_lam, x.xong_luc,
       CASE
           WHEN x.go_luc IS NOT NULL THEN x.buoi_so
           WHEN x.da_lam THEN
               row_number() OVER (
                   PARTITION BY x.lieu_trinh_id, (x.go_luc IS NULL), x.da_lam
                   ORDER BY x.xong_luc NULLS LAST, x.buoi_so, x.gan_luc)
           ELSE
               count(*) FILTER (WHERE x.da_lam AND x.go_luc IS NULL)
                   OVER (PARTITION BY x.lieu_trinh_id)
               + row_number() OVER (
                   PARTITION BY x.lieu_trinh_id, (x.go_luc IS NULL), x.da_lam
                   ORDER BY x.buoi_so, x.gan_luc)
       END::integer AS buoi_so
  FROM x;

COMMENT ON VIEW public.v_lieu_trinh_buoi IS
    'Buổi liệu trình + số HIỆN (buoi_so) theo thứ tự làm xong; buoi_so_goc = số lưu lúc gắn. Màn đọc số buổi qua đây.';
