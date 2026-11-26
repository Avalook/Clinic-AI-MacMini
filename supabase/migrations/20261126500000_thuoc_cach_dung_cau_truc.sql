-- PR E (26/11/2026, kế hoạch đơn vị mẹ/con mục 2, 4, 6, 10): cách dùng có cấu trúc.
--
-- * `drug_catalog.cach_dung_ct`: cách dùng MẶC ĐỊNH (kiểu ngày/tuần/cách ngày/chu kỳ
--   kinh/chỉ chữ, mỗi lần, số lần, khoảng, trong N ngày, chữ thêm). Câu chữ cũ
--   `cach_dung` giữ nguyên — kiểu "chỉ chữ" và thuốc chưa khai cấu trúc vẫn dùng nó.
-- * `drug_catalog.so_lieu_moi_don_vi_goc`: "1 [đơn vị kho] có bao nhiêu [viên/gói…]"
--   để tính ngày dùng. NULL = chưa khai → máy báo "chưa khai…", không đoán.
--   (PR C làm câu "1 hộp có bao nhiêu viên?" cho đơn vị BÁN; ô này là đơn vị LIỀU —
--   gộp hai câu về một ô khi C và E cùng lên nếu Tuyền muốn.)
-- * `prescription.cach_dung_ct`: BẢN CHỤP cấu trúc trên dòng đơn lúc kê. Dòng cũ để
--   NULL (không sửa quá khứ); `dosage_instructions` (chữ) vẫn ghi như cũ — bản in,
--   đơn thuốc quốc gia, quầy đọc chữ đó.
--
-- Hình jsonb do `services/thuoc/cach_dung.CachDung` kiểm; DB chỉ chặn kiểu lạ.
-- Chạy lại nhiều lần được.

ALTER TABLE public.drug_catalog
    ADD COLUMN IF NOT EXISTS cach_dung_ct jsonb,
    ADD COLUMN IF NOT EXISTS so_lieu_moi_don_vi_goc numeric(10, 2);

ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS cach_dung_ct jsonb;

ALTER TABLE public.drug_catalog
    DROP CONSTRAINT IF EXISTS drug_catalog_cach_dung_ct_kieu,
    ADD CONSTRAINT drug_catalog_cach_dung_ct_kieu CHECK (
        cach_dung_ct IS NULL
        OR (jsonb_typeof(cach_dung_ct) = 'object'
            AND cach_dung_ct ->> 'kieu' IN ('ngay', 'tuan', 'cach_ngay', 'chu_ky', 'chu'))
    ),
    DROP CONSTRAINT IF EXISTS drug_catalog_so_lieu_duong,
    ADD CONSTRAINT drug_catalog_so_lieu_duong CHECK (
        so_lieu_moi_don_vi_goc IS NULL OR so_lieu_moi_don_vi_goc > 0
    );

ALTER TABLE public.prescription
    DROP CONSTRAINT IF EXISTS prescription_cach_dung_ct_kieu,
    ADD CONSTRAINT prescription_cach_dung_ct_kieu CHECK (
        cach_dung_ct IS NULL
        OR (jsonb_typeof(cach_dung_ct) = 'object'
            AND cach_dung_ct ->> 'kieu' IN ('ngay', 'tuan', 'cach_ngay', 'chu_ky', 'chu'))
    );

COMMENT ON COLUMN public.drug_catalog.cach_dung_ct IS
    'Cách dùng mặc định có cấu trúc (PR E) — hình do services/thuoc/cach_dung.CachDung kiểm.';
COMMENT ON COLUMN public.drug_catalog.so_lieu_moi_don_vi_goc IS
    '1 đơn vị kho (don_vi_ban) có bao nhiêu đơn vị liều (viên/gói…) — NULL = chưa khai.';
COMMENT ON COLUMN public.prescription.cach_dung_ct IS
    'Bản chụp cách dùng có cấu trúc lúc kê (PR E); dòng cũ NULL.';
