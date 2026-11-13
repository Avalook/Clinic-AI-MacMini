-- Phiếu khám tự lưu KHÔNG còn phát tin cho cả phòng khám (S2, 17/10/2026).
--
-- VÌ SAO. `trg_notify_phieu_kham_luot` (20261010100001) bắn `notify_row_change` ở
-- MỌI lần UPDATE — kể cả mỗi lần bác sĩ dừng tay gõ và phiếu tự lưu. Tin ấy làm
-- `RealtimeRefresher` dựng lại cả trang ở mọi màn thường của mọi người đang mở
-- (đo log prod 14–16/10: một lượt ghi → 7–10 lần dựng lại trang).
-- Chỉ hai nơi nghe `phieu_kham_luot`: `RealtimeRefresher` (dựng trang) và khung lịch
-- sử đơn thuốc `LichSuDonThuoc.tsx` — khung này đọc NGÀY TÁI KHÁM trên phiếu (ô có
-- mã kết thúc `_follow_date`, xem `hen_tai_kham_service.la_o_ngay_hen`), không đọc
-- chữ bác sĩ đang gõ.
--
-- ĐỔI GÌ. INSERT / DELETE vẫn báo như cũ. UPDATE chỉ báo khi một ô ngày hẹn đổi.
-- Hàm `notify_row_change` giữ nguyên (cùng tin `{t, c}`), chỉ thêm điều kiện WHEN.
--
-- KHÔNG ĐỔI. Dữ liệu lưu, cột, `revision` chống ghi đè (phieu_kham_service), quyền.
--
-- AN TOÀN. Điều kiện WHEN chạy TRONG câu UPDATE của bác sĩ: nếu nó ném lỗi thì lần
-- lưu phiếu hỏng và chữ vừa gõ mất. Nên hàm dưới đây không bao giờ ném: `du_lieu`
-- NULL / mảng / chuỗi / số đều coi như `{}`. Có test cho từng dạng.
--
-- ĐƯỜNG LÙI (chạy tay, một giao dịch):
--   DROP TRIGGER IF EXISTS trg_notify_phieu_kham_luot_hen ON public.phieu_kham_luot;
--   DROP TRIGGER IF EXISTS trg_notify_phieu_kham_luot ON public.phieu_kham_luot;
--   CREATE TRIGGER trg_notify_phieu_kham_luot
--     AFTER INSERT OR UPDATE OR DELETE ON public.phieu_kham_luot
--     FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
--   DROP FUNCTION IF EXISTS public.phieu_kham_doi_ngay_hen(jsonb, jsonb);
BEGIN;

CREATE OR REPLACE FUNCTION public.phieu_kham_doi_ngay_hen(p_cu jsonb, p_moi jsonb)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path TO 'pg_catalog'
AS $$
    WITH cu AS (
        SELECT CASE WHEN jsonb_typeof(p_cu) = 'object' THEN p_cu ELSE '{}'::jsonb END AS j
    ), moi AS (
        SELECT CASE WHEN jsonb_typeof(p_moi) = 'object' THEN p_moi ELSE '{}'::jsonb END AS j
    ), khoa AS (
        SELECT jsonb_object_keys(j) AS k FROM cu
        UNION
        SELECT jsonb_object_keys(j) FROM moi
    )
    SELECT EXISTS (
        SELECT 1
          FROM khoa, cu, moi
         WHERE khoa.k LIKE '%\_follow\_date' ESCAPE '\'
           AND (cu.j -> khoa.k) IS DISTINCT FROM (moi.j -> khoa.k)
    )
$$;

COMMENT ON FUNCTION public.phieu_kham_doi_ngay_hen(jsonb, jsonb) IS
    'true khi một ô ngày tái khám (mã kết thúc _follow_date) trong du_lieu của phiếu '
    'khám đổi giữa OLD và NEW. KHÔNG BAO GIỜ ném lỗi (chạy trong WHEN của trigger '
    'UPDATE: ném là hỏng lần lưu phiếu). Cùng quy ước hen_tai_kham_service.la_o_ngay_hen.';

DROP TRIGGER IF EXISTS trg_notify_phieu_kham_luot ON public.phieu_kham_luot;
CREATE TRIGGER trg_notify_phieu_kham_luot
AFTER INSERT OR DELETE ON public.phieu_kham_luot
FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

DROP TRIGGER IF EXISTS trg_notify_phieu_kham_luot_hen ON public.phieu_kham_luot;
CREATE TRIGGER trg_notify_phieu_kham_luot_hen
AFTER UPDATE ON public.phieu_kham_luot
FOR EACH ROW
WHEN (public.phieu_kham_doi_ngay_hen(OLD.du_lieu, NEW.du_lieu))
EXECUTE FUNCTION public.notify_row_change();

NOTIFY pgrst, 'reload schema';
COMMIT;
