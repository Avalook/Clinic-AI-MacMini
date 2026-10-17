-- QUY ĐỔI ĐƠN VỊ LÚC NHẬP KHO (17/10/2026, kế hoạch docs/KE-HOACH-QUY-DOI-DON-VI-VA-THUOC-TRA.md, việc A).
--
-- Bẫy đã cắn: Androgel nhập 6 "hộp" nhưng bán theo "gói" → giao thuốc ghi tiền mà kho
-- không trừ (luật gán lô đúng: không tự quy đổi hộp, vỉ, viên). Cách chữa: kho chỉ giữ
-- MỘT đơn vị = đơn vị bán (`drug_catalog.don_vi_ban`); nhập đơn vị khác thì đổi NGAY ở
-- cửa nhập (`pharmacy_service.nhap_vao_lo`), hệ số nhớ theo (thuốc, đơn vị nhập).
--
-- Chỉ THÊM: một bảng + ba cột nullable. Không đụng dữ liệu cũ, sổ kho vẫn chỉ-thêm.
-- Hoàn tác (nếu cần, trước khi có dữ liệu mới):
--   ALTER TABLE public.phieu_kho_dong DROP CONSTRAINT IF EXISTS phieu_kho_dong_quy_doi_du,
--       DROP COLUMN IF EXISTS so_luong_goc, DROP COLUMN IF EXISTS don_vi_goc,
--       DROP COLUMN IF EXISTS he_so;
--   DROP TABLE IF EXISTS public.thuoc_quy_doi;
--
-- Chạy lại được, không BEGIN/COMMIT.

CREATE TABLE IF NOT EXISTS public.thuoc_quy_doi (
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    drug_catalog_id  uuid NOT NULL REFERENCES public.drug_catalog(id) ON DELETE RESTRICT,
    -- Đơn vị NHẬP đã chuẩn hoá (NFC, thường, một khoảng trắng) — cùng cách so
    -- sánh với `_don_vi()` ở backend. "1 <don_vi> = <he_so> đơn vị bán".
    don_vi           text NOT NULL CHECK (length(btrim(don_vi)) BETWEEN 1 AND 50),
    he_so            numeric(12,3) NOT NULL CHECK (he_so > 0 AND he_so <= 10000),
    cap_nhat_boi     uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    cap_nhat_luc     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, drug_catalog_id, don_vi)
);
COMMENT ON TABLE public.thuoc_quy_doi IS
'Hệ số quy đổi đơn vị NHẬP → đơn vị BÁN của từng thuốc (vd 1 hộp = 10 gói). Nhớ lần đầu, lần sau nhập không phải gõ lại (17/10/2026).';

ALTER TABLE public.thuoc_quy_doi ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS thuoc_quy_doi_select_own_clinic ON public.thuoc_quy_doi;
CREATE POLICY thuoc_quy_doi_select_own_clinic ON public.thuoc_quy_doi
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.thuoc_quy_doi TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.thuoc_quy_doi TO service_role;

-- Số gốc người nhập gõ (6 hộp, hệ số 10) để đối chiếu với số đã quy đổi trên dòng
-- phiếu (60 gói). Trống = dòng không phải quy đổi.
ALTER TABLE public.phieu_kho_dong ADD COLUMN IF NOT EXISTS so_luong_goc numeric(12,3);
ALTER TABLE public.phieu_kho_dong ADD COLUMN IF NOT EXISTS don_vi_goc text;
ALTER TABLE public.phieu_kho_dong ADD COLUMN IF NOT EXISTS he_so numeric(12,3);
ALTER TABLE public.phieu_kho_dong DROP CONSTRAINT IF EXISTS phieu_kho_dong_quy_doi_du;
ALTER TABLE public.phieu_kho_dong ADD CONSTRAINT phieu_kho_dong_quy_doi_du
    CHECK ((so_luong_goc IS NULL) = (don_vi_goc IS NULL)
           AND (so_luong_goc IS NULL) = (he_so IS NULL)
           AND (he_so IS NULL OR (he_so > 0 AND he_so <= 10000)));

NOTIFY pgrst, 'reload schema';
