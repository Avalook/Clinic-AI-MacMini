-- Bác sĩ quyết có theo dõi sau thủ thuật hay không (Tuyền chốt 16/09/2026).
--
-- Màn CSKH có hai ô "Đã làm thủ thuật" và "Không cần follow-up sau thủ thuật".
-- Trước bản này cả hai là ô CSKH TỰ CHỌN — hệ thống không có nguồn nào để biết,
-- nên người gọi điện đoán thay bác sĩ. Tuyền: hai ô ấy "phụ thuộc bác sĩ", CSKH
-- chỉ được nhìn, không được tích.
--
--   · "Đã làm thủ thuật" KHÔNG cần cột mới: nó là việc DICHVU-THUTHUAT của lượt
--     khám đã COMPLETED (bước dịch vụ chỉ bác sĩ đóng — luật 15/09). Suy ra ở
--     truy vấn đọc.
--   · "Theo dõi sau thủ thuật" là QUYẾT ĐỊNH của bác sĩ, không suy được → cột
--     trên `visit`: CAN (sau N ngày) hoặc KHONG_CAN. Trống = bác sĩ chưa quyết.
--
-- Chạy lại được (ADD COLUMN IF NOT EXISTS, ràng buộc bỏ rồi dựng lại).

ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS theo_doi_thu_thuat text,
    ADD COLUMN IF NOT EXISTS theo_doi_sau_ngay integer,
    ADD COLUMN IF NOT EXISTS theo_doi_boi uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS theo_doi_luc timestamptz;

ALTER TABLE public.visit DROP CONSTRAINT IF EXISTS visit_theo_doi_thu_thuat_hop_le;
ALTER TABLE public.visit ADD CONSTRAINT visit_theo_doi_thu_thuat_hop_le CHECK (
    (theo_doi_thu_thuat IS NULL
        AND theo_doi_sau_ngay IS NULL AND theo_doi_boi IS NULL AND theo_doi_luc IS NULL)
    OR (theo_doi_thu_thuat = 'KHONG_CAN'
        AND theo_doi_sau_ngay IS NULL AND theo_doi_luc IS NOT NULL)
    OR (theo_doi_thu_thuat = 'CAN'
        AND theo_doi_sau_ngay BETWEEN 1 AND 365 AND theo_doi_luc IS NOT NULL)
);

COMMENT ON COLUMN public.visit.theo_doi_thu_thuat IS
    'Bác sĩ quyết theo dõi sau thủ thuật: CAN (sau theo_doi_sau_ngay ngày) / KHONG_CAN / NULL = chưa quyết. 20260916000001.';
