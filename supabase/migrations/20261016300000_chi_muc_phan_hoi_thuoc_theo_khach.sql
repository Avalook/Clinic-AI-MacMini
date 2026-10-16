-- CHỈ MỤC cho cột + bộ lọc "Phản hồi thuốc" của màn Quản lý khách hàng (16/10/2026).
--
-- Bảng danh sách khách đếm phản hồi sau dùng thuốc (tuong_tac_cskh.loai =
-- 'PHAN_HOI_THUOC', chưa gỡ) cho cả trang 50 khách bằng MỘT câu gộp, và bộ lọc
-- "Có phản hồi sau dùng thuốc" hỏi EXISTS theo từng khách. Chỉ mục riêng (một phần)
-- giữ cả hai gọn khi sổ chăm sóc phình: chỉ chứa dòng phản hồi thuốc còn hiệu lực,
-- nhỏ hơn nhiều so với idx_tuong_tac_theo_khach (cả sổ).
--
-- Chỉ thêm chỉ mục — không đổi cột, không đổi dữ liệu, hoàn tác bằng DROP INDEX.

CREATE INDEX IF NOT EXISTS idx_tuong_tac_phan_hoi_thuoc_khach
    ON public.tuong_tac_cskh (clinic_id, clinic_patient_id, xay_ra_luc DESC)
    WHERE loai = 'PHAN_HOI_THUOC' AND huy_luc IS NULL;
