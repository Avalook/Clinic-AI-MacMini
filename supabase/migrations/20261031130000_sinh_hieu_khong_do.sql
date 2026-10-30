-- SINH HIỆU "KHÔNG ĐO" (30/10/2026).
--
-- Người đo bấm [Không đo] + chọn lý do (Trẻ nhỏ · Khách từ chối · Đã đo nơi
-- khác · Khác — Khác phải gõ chữ). Khách đi tiếp như đã đo (encounter_flow
-- `vitals_status = 'recorded'`, cùng sự kiện `vitals.recorded` có cờ), KHÔNG ghi
-- số giả vào `vital_measurement`. Bảng này giữ SỰ THẬT "không đo": lý do, ai,
-- lúc nào — dữ liệu "sai lệch quy trình" quản lý cần thu.
--
-- Mỗi lần bấm là MỘT dòng (đổi lý do = dòng mới, dòng mới nhất là hiện hành).
-- Đo thật sau đó vẫn được: lần đo thật thắng ở mọi màn, dòng ở đây còn nguyên.
--
-- BẤT BIẾN ÉP Ở POSTGRES: mã lý do trong danh sách; "Khác" phải có chữ; sổ chỉ
-- ghi thêm (không sửa, không xoá tay — xoá lượt thì dòng đi theo).
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.sinh_hieu_khong_do (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id     uuid NOT NULL,
    ly_do        text NOT NULL,
    ghi_chu      text,
    ghi_boi      uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    ghi_boi_ten  text,
    ghi_luc      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sinh_hieu_khong_do_luot_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    CONSTRAINT sinh_hieu_khong_do_ly_do_ck
        CHECK (ly_do IN ('TRE_NHO', 'TU_CHOI', 'DO_NOI_KHAC', 'KHAC')),
    CONSTRAINT sinh_hieu_khong_do_ghi_chu_ck
        CHECK (ghi_chu IS NULL OR length(btrim(ghi_chu)) BETWEEN 1 AND 500),
    CONSTRAINT sinh_hieu_khong_do_khac_can_chu_ck
        CHECK (ly_do <> 'KHAC' OR ghi_chu IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS ix_sinh_hieu_khong_do_luot
    ON public.sinh_hieu_khong_do (clinic_id, visit_id, ghi_luc DESC);

COMMENT ON TABLE public.sinh_hieu_khong_do IS
'Sinh hiệu không đo: lý do (TRE_NHO/TU_CHOI/DO_NOI_KHAC/KHAC + chữ), ai, lúc nào. Không có số đo giả; lần đo thật sau đó thắng (30/10/2026).';

ALTER TABLE public.sinh_hieu_khong_do ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sinh_hieu_khong_do_select_own_clinic ON public.sinh_hieu_khong_do;
CREATE POLICY sinh_hieu_khong_do_select_own_clinic ON public.sinh_hieu_khong_do
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.sinh_hieu_khong_do TO service_role;

-- ── Sổ chỉ ghi thêm ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.sinh_hieu_khong_do_chi_ghi_them()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Xoá theo lượt (ON DELETE CASCADE) đi qua đây với pg_trigger_depth() > 1.
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN
        RETURN OLD;
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.ghi_boi IS NULL AND OLD.ghi_boi IS NOT NULL
       AND NEW.id = OLD.id AND NEW.ly_do = OLD.ly_do
       AND NEW.ghi_chu IS NOT DISTINCT FROM OLD.ghi_chu
       AND NEW.ghi_luc = OLD.ghi_luc THEN
        RETURN NEW;  -- Postgres dọn tham chiếu nhân sự (SET NULL), tên đã chụp
    END IF;
    RAISE EXCEPTION 'Sổ "không đo sinh hiệu" chỉ ghi thêm — không sửa / xoá được.'
        USING ERRCODE = 'check_violation';
END;
$$;

DROP TRIGGER IF EXISTS trg_sinh_hieu_khong_do_chi_ghi_them ON public.sinh_hieu_khong_do;
CREATE TRIGGER trg_sinh_hieu_khong_do_chi_ghi_them
    BEFORE UPDATE OR DELETE ON public.sinh_hieu_khong_do
    FOR EACH ROW EXECUTE FUNCTION public.sinh_hieu_khong_do_chi_ghi_them();

-- Màn mở (Đo sinh hiệu, Bàn khám) tự tải lại qua dòng SSE chung khi đổi lý do.
DROP TRIGGER IF EXISTS trg_notify_sinh_hieu_khong_do ON public.sinh_hieu_khong_do;
CREATE TRIGGER trg_notify_sinh_hieu_khong_do
    AFTER INSERT ON public.sinh_hieu_khong_do
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
