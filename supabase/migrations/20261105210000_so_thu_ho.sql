-- XÉT NGHIỆM ĐỐI TÁC — CHẶNG 2: SỔ THU HỘ (kế hoạch 4.4, câu chốt 1 + 6, ADR-0015).
--
-- 1. `doi_tac_thanh_toan` thêm `tien_mat`, `chuyen_khoan` (một lần thu có thể tách
--    TM + CK), `gia_goi_y` (chụp lúc ghi — giá chỉ là gợi ý, lưu cả hai số) và
--    `ma_giao_dich` (CK chiếm ~75% trên prod). `hinh_thuc` thêm `MIXED` — giá trị SUY
--    RA khi ghi, không cho người gõ. CHECK `so_tien = tien_mat + chuyen_khoan`.
-- 2. Bù dòng cũ (~114 trên prod): CASH → tien_mat = so_tien, TRANSFER → chuyen_khoan
--    = so_tien. Trigger "chỉ được huỷ" chặn UPDATE dòng đã huỷ, nên tắt nó TRONG giao
--    dịch của migration này rồi bật lại — không ai khác ghi được giữa chừng.
-- 3. Hàm trigger `doi_tac_thanh_toan_chi_huy()` so cả cột mới — quên chỗ này là sổ
--    sửa được quá khứ (luật xet-nghiem-doi-tac).
-- 4. `doi_tac_hoan_tien` — trả tiền THẬT lại khách (khác huỷ = ghi sai). Chỉ thêm,
--    không sửa, không xoá. Tổng hoàn ≤ số đã thu: ép ở service dưới khoá dòng thu.
--
-- KHÔNG đụng payment_cycle / payment / payment_bill_line / két / doanh thu.
-- Chạy lại được.

-- ── 1. Cột mới ──────────────────────────────────────────────────────────────
ALTER TABLE public.doi_tac_thanh_toan
    ADD COLUMN IF NOT EXISTS tien_mat      numeric(12, 0) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS chuyen_khoan  numeric(12, 0) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS gia_goi_y     numeric(12, 0),
    ADD COLUMN IF NOT EXISTS ma_giao_dich  text;

-- ── 2. Bù dòng cũ ───────────────────────────────────────────────────────────
ALTER TABLE public.doi_tac_thanh_toan DISABLE TRIGGER trg_doi_tac_thanh_toan_chi_huy;
UPDATE public.doi_tac_thanh_toan
   SET tien_mat = CASE WHEN hinh_thuc = 'CASH' THEN so_tien ELSE 0 END,
       chuyen_khoan = CASE WHEN hinh_thuc = 'TRANSFER' THEN so_tien ELSE 0 END
 WHERE tien_mat + chuyen_khoan <> so_tien;
ALTER TABLE public.doi_tac_thanh_toan ENABLE TRIGGER trg_doi_tac_thanh_toan_chi_huy;

ALTER TABLE public.doi_tac_thanh_toan
    DROP CONSTRAINT IF EXISTS doi_tac_thanh_toan_hinh_thuc_check;
ALTER TABLE public.doi_tac_thanh_toan
    ADD CONSTRAINT doi_tac_thanh_toan_hinh_thuc_check
    CHECK (hinh_thuc IN ('CASH', 'TRANSFER', 'MIXED'));
ALTER TABLE public.doi_tac_thanh_toan
    DROP CONSTRAINT IF EXISTS doi_tac_thanh_toan_tach_khop;
ALTER TABLE public.doi_tac_thanh_toan
    ADD CONSTRAINT doi_tac_thanh_toan_tach_khop CHECK (
        tien_mat >= 0 AND chuyen_khoan >= 0
        AND so_tien = tien_mat + chuyen_khoan
        AND (gia_goi_y IS NULL OR gia_goi_y >= 0)
        AND (ma_giao_dich IS NULL OR length(ma_giao_dich) BETWEEN 1 AND 100)
        -- hình thức là SUY RA từ hai số, không phải chữ người chọn
        AND hinh_thuc = CASE
            WHEN tien_mat > 0 AND chuyen_khoan > 0 THEN 'MIXED'
            WHEN chuyen_khoan > 0 THEN 'TRANSFER'
            WHEN tien_mat > 0 THEN 'CASH'
            ELSE hinh_thuc END);

-- ── 3. Trigger so đủ cột ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.doi_tac_thanh_toan_chi_huy()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'doi_tac_thanh_toan: không xoá — huỷ kèm lý do'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.huy_luc IS NOT NULL
       OR (NEW.clinic_id, NEW.service_order_id, NEW.so_tien, NEW.hinh_thuc,
           NEW.ghi_chu, NEW.ghi_boi, NEW.ghi_luc,
           NEW.tien_mat, NEW.chuyen_khoan, NEW.gia_goi_y, NEW.ma_giao_dich)
          IS DISTINCT FROM
          (OLD.clinic_id, OLD.service_order_id, OLD.so_tien, OLD.hinh_thuc,
           OLD.ghi_chu, OLD.ghi_boi, OLD.ghi_luc,
           OLD.tien_mat, OLD.chuyen_khoan, OLD.gia_goi_y, OLD.ma_giao_dich) THEN
        RAISE EXCEPTION 'doi_tac_thanh_toan: chỉ được huỷ ghi nhận đang hiệu lực'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;

-- Tab "Tiền thu hộ" lọc theo ngày ghi nhận (giờ VN).
CREATE INDEX IF NOT EXISTS ix_doi_tac_thanh_toan_ghi_luc
    ON public.doi_tac_thanh_toan (clinic_id, ghi_luc);

-- ── 4. Hoàn tiền ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.doi_tac_hoan_tien (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    thanh_toan_id   uuid NOT NULL REFERENCES public.doi_tac_thanh_toan (id)
                         ON DELETE RESTRICT,
    so_tien         numeric(12, 0) NOT NULL,
    tien_mat        numeric(12, 0) NOT NULL DEFAULT 0,
    chuyen_khoan    numeric(12, 0) NOT NULL DEFAULT 0,
    ly_do           text NOT NULL,
    hoan_boi        uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    hoan_luc        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT doi_tac_hoan_tien_tach_khop CHECK (
        tien_mat >= 0 AND chuyen_khoan >= 0 AND so_tien > 0
        AND so_tien = tien_mat + chuyen_khoan),
    CONSTRAINT doi_tac_hoan_tien_ly_do CHECK (length(btrim(ly_do)) BETWEEN 3 AND 2000)
);
CREATE INDEX IF NOT EXISTS ix_doi_tac_hoan_tien_thanh_toan
    ON public.doi_tac_hoan_tien (clinic_id, thanh_toan_id);
CREATE INDEX IF NOT EXISTS ix_doi_tac_hoan_tien_luc
    ON public.doi_tac_hoan_tien (clinic_id, hoan_luc);
COMMENT ON TABLE public.doi_tac_hoan_tien IS
'Hoàn tiền thu hộ cho khách (05/11/2026, ADR-0015). Chỉ thêm. Khác huỷ ghi nhận (ghi sai). Không phải tiền phòng khám.';

CREATE OR REPLACE FUNCTION public.doi_tac_hoan_tien_chi_them()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'doi_tac_hoan_tien: chỉ thêm — không sửa, không xoá'
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS trg_doi_tac_hoan_tien_chi_them ON public.doi_tac_hoan_tien;
CREATE TRIGGER trg_doi_tac_hoan_tien_chi_them
    BEFORE UPDATE OR DELETE ON public.doi_tac_hoan_tien
    FOR EACH ROW EXECUTE FUNCTION public.doi_tac_hoan_tien_chi_them();

ALTER TABLE public.doi_tac_hoan_tien ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS doi_tac_hoan_tien_select_own_clinic ON public.doi_tac_hoan_tien;
CREATE POLICY doi_tac_hoan_tien_select_own_clinic ON public.doi_tac_hoan_tien
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.doi_tac_hoan_tien TO service_role;

-- Báo tin: bàn XN thấy ngay ghi nhận / huỷ / hoàn của người khác.
DROP TRIGGER IF EXISTS trg_notify_doi_tac_thanh_toan ON public.doi_tac_thanh_toan;
CREATE TRIGGER trg_notify_doi_tac_thanh_toan
    AFTER INSERT OR UPDATE OR DELETE ON public.doi_tac_thanh_toan
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
DROP TRIGGER IF EXISTS trg_notify_doi_tac_hoan_tien ON public.doi_tac_hoan_tien;
CREATE TRIGGER trg_notify_doi_tac_hoan_tien
    AFTER INSERT OR UPDATE OR DELETE ON public.doi_tac_hoan_tien
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
