-- LẦN CHỈ ĐỊNH ỔN ĐỊNH (Tuyền thử thật trên staging 06/10/2026).
--
-- Lỗi: Quản lý thay bác sĩ tick 3 chỉ định, bỏ 2, rời Bàn khám rồi quay lại
-- tick thêm → hệ thống TỰ thành "chỉ định lần 2".
--
-- Gốc: trigger `gan_lan_chi_dinh` (20260926000006, giữ ở 20261002200000) đánh
-- số "mỗi GIAO DỊCH tạo chỉ định = một lần mới" (max + 1). Luật ấy viết lúc
-- danh mục còn gập sau nút "+ Chỉ định thêm" — bấm gửi lần hai NGHĨA LÀ đã bấm
-- nút ấy. Từ C21 (02/10/2026) danh mục MỞ SẴN, nút gửi gửi thẳng, nên mọi lần
-- bấm gửi sau lần đầu (vào lại màn, tải lại trang, hay ngay sau đó) đều nhảy
-- lần — không do vòng khám / phiên khám nào cả.
--
-- Nay: lần chỉ MỞ khi lệnh nói rõ "mở lần mới" (nút "Chỉ định thêm (lần N)").
--   * Mặc định: chỉ định vào LẦN HIỆN TẠI của lượt (= lần lớn nhất đã có, kể cả
--     dòng đã bỏ; chưa có thì 1).
--   * Mở lần mới: lệnh đặt `clinicai.lan_moi_<visit>` = lần hiện tại MÀ NGƯỜI
--     BẤM ĐANG THẤY. Lần ấy còn chỉ định sống → lần + 1. Lần ấy toàn dòng đã bỏ
--     → dùng lại (không đẻ lần rỗng). Người khác đã mở lần mới trong lúc đó
--     (lần hiện tại > lần người bấm thấy) → vào lần ấy, không mở thêm lần nữa.
--     Hai người bấm cùng lúc tuần tự hoá bằng advisory lock theo lượt (giữ như cũ).
--   * Mang sang / làm thêm tại quầy: vẫn không có lần (NULL). Nháp: số lúc duyệt.
--
-- Màn đọc lần hiện tại / lần kế tiếp từ `lan_chi_dinh_cua_luot` — cùng hàm
-- trigger dùng, nên nhãn nút và số máy chủ gán không lệch nhau.
--
-- Chạy lại được.

CREATE OR REPLACE FUNCTION public.lan_chi_dinh_cua_luot(p_clinic_id uuid, p_visit_id uuid)
RETURNS TABLE (hien_tai smallint, ke_tiep smallint, mo_moi_duoc boolean)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH ht AS (
        SELECT max(o.lan_chi_dinh) AS lan
          FROM public.service_order o
         WHERE o.clinic_id = p_clinic_id AND o.visit_id = p_visit_id
           AND o.lan_chi_dinh IS NOT NULL
    ), song AS (
        SELECT EXISTS (
            SELECT 1 FROM public.service_order o, ht
             WHERE o.clinic_id = p_clinic_id AND o.visit_id = p_visit_id
               AND o.lan_chi_dinh = ht.lan
               AND o.exec_status NOT IN ('cancelled', 'draft')
               AND coalesce(o.execution_status, '') <> 'CANCELLED') AS co
    )
    SELECT ht.lan::smallint,
           (CASE WHEN ht.lan IS NULL THEN 1
                 WHEN song.co THEN ht.lan + 1
                 ELSE ht.lan END)::smallint,
           coalesce(song.co, false)
      FROM ht, song;
$$;

COMMENT ON FUNCTION public.lan_chi_dinh_cua_luot(uuid, uuid) IS
'Lần chỉ định của lượt (06/10/2026): hien_tai = lần lớn nhất đã có (NULL = chưa chỉ định), ke_tiep = số lần nút "Chỉ định thêm" sẽ mở, mo_moi_duoc = lần hiện tại còn chỉ định sống. Trigger gan_lan_chi_dinh dùng chung.';

CREATE OR REPLACE FUNCTION public.gan_lan_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  khoa text;
  lan text;
  thay text;
  ht smallint;
  kt smallint;
BEGIN
  -- Mang sang (dòng của lượt trước chuyển visit_id sang lượt này): bỏ số lần của
  -- lượt cũ — nó không thuộc lần nào ở lượt mới.
  -- Làm thêm tại quầy (01/10/2026): không phải lần chốt của bác sĩ.
  IF NEW.mang_tu_visit_id IS NOT NULL OR NEW.nguon_lam_them IS NOT NULL THEN
    NEW.lan_chi_dinh := NULL;
    RETURN NEW;
  END IF;
  IF NEW.lan_chi_dinh IS NOT NULL OR NEW.visit_id IS NULL OR NEW.exec_status IN ('draft', 'cancelled') THEN
    RETURN NEW;
  END IF;
  -- Sửa dòng: chỉ đánh số lúc NHÁP được duyệt (thư ký ghi nháp, bác sĩ duyệt —
  -- lần tính theo lúc duyệt). Dòng cũ chưa có số giữ nguyên NULL.
  IF TG_OP = 'UPDATE' AND OLD.exec_status IS DISTINCT FROM 'draft' THEN
    RETURN NEW;
  END IF;
  khoa := 'clinicai.lan_' || replace(NEW.visit_id::text, '-', '');
  lan := nullif(current_setting(khoa, true), '');
  IF lan IS NULL THEN
    PERFORM pg_advisory_xact_lock(hashtext('lan_chi_dinh:' || NEW.visit_id::text));
    SELECT l.hien_tai, l.ke_tiep INTO ht, kt
      FROM public.lan_chi_dinh_cua_luot(NEW.clinic_id, NEW.visit_id) l;
    -- "Mở lần mới": giá trị = lần hiện tại người bấm đang thấy (0 = chưa có).
    thay := nullif(current_setting(
        'clinicai.lan_moi_' || replace(NEW.visit_id::text, '-', ''), true), '');
    IF thay IS NOT NULL AND thay ~ '^[0-9]{1,4}$'
       AND coalesce(ht, 0) <= thay::int THEN
      lan := kt::text;                      -- mở lần mới (hoặc dùng lại lần rỗng)
    ELSE
      lan := coalesce(ht, 1)::text;         -- vào lần hiện tại
    END IF;
    PERFORM set_config(khoa, lan, true);  -- chỉ sống trong giao dịch này
  END IF;
  NEW.lan_chi_dinh := lan::smallint;
  RETURN NEW;
END;
$$;

COMMENT ON COLUMN public.service_order.lan_chi_dinh IS
'Lần chỉ định trong lượt khám (1, 2, 3…) — mặc định vào lần hiện tại; chỉ lệnh "mở lần mới" (clinicai.lan_moi_<visit>) mới sang lần kế; mang sang / làm thêm tại quầy = NULL (06/10/2026).';
