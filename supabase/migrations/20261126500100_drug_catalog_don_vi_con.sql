-- Tuyền 26/11/2026: Danh mục & giá chỉ cần đơn vị MẸ (đơn vị tính, kho đếm theo nó) +
-- khối "Đơn vị con và tính số ngày dùng hết thuốc":
--   "Đơn vị con của [hộp] là [viên]" · "1 [hộp] có bao nhiêu [viên]" · "Giá 1 [viên]".
--
-- * `don_vi_con`: tên đơn vị con (viên, gói, ống…). NULL = chưa khai.
-- * Số con trong 1 mẹ: dùng lại `so_lieu_moi_don_vi_goc` (PR E, 20261126500000).
-- * `gia_con`: giá 1 đơn vị con người khai sửa tay. NULL = máy tự chia
--   (giá mẹ ÷ số con, làm tròn), không cần nhập.
-- * Cách dùng thêm kiểu "thang" (tháng N lần) — mở ràng buộc kiểu ở hai bảng.
-- Chạy lại nhiều lần được.

ALTER TABLE public.drug_catalog
    ADD COLUMN IF NOT EXISTS don_vi_con text,
    ADD COLUMN IF NOT EXISTS gia_con numeric(14, 0);

ALTER TABLE public.drug_catalog
    DROP CONSTRAINT IF EXISTS drug_catalog_don_vi_con_ten,
    ADD CONSTRAINT drug_catalog_don_vi_con_ten CHECK (
        don_vi_con IS NULL OR (length(btrim(don_vi_con)) BETWEEN 1 AND 20
                               AND don_vi_con !~ '[0-9]')
    ),
    DROP CONSTRAINT IF EXISTS drug_catalog_gia_con_duong,
    ADD CONSTRAINT drug_catalog_gia_con_duong CHECK (gia_con IS NULL OR gia_con > 0),
    DROP CONSTRAINT IF EXISTS drug_catalog_cach_dung_ct_kieu,
    ADD CONSTRAINT drug_catalog_cach_dung_ct_kieu CHECK (
        cach_dung_ct IS NULL
        OR (jsonb_typeof(cach_dung_ct) = 'object'
            AND cach_dung_ct ->> 'kieu' IN ('ngay', 'tuan', 'thang', 'cach_ngay', 'chu_ky', 'chu'))
    );

ALTER TABLE public.prescription
    DROP CONSTRAINT IF EXISTS prescription_cach_dung_ct_kieu,
    ADD CONSTRAINT prescription_cach_dung_ct_kieu CHECK (
        cach_dung_ct IS NULL
        OR (jsonb_typeof(cach_dung_ct) = 'object'
            AND cach_dung_ct ->> 'kieu' IN ('ngay', 'tuan', 'thang', 'cach_ngay', 'chu_ky', 'chu'))
    );

COMMENT ON COLUMN public.drug_catalog.don_vi_con IS
    'Đơn vị con (viên, gói…) của đơn vị mẹ don_vi_ban; số con/mẹ ở so_lieu_moi_don_vi_goc.';
COMMENT ON COLUMN public.drug_catalog.gia_con IS
    'Giá 1 đơn vị con khai tay; NULL = giá mẹ ÷ số con (máy tự chia).';
