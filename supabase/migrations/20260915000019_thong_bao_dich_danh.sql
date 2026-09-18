-- THÔNG BÁO ĐÍCH DANH MỘT NGƯỜI: CHỐNG GỬI TRÙNG (15/09/2026).
--
-- Kết quả xét nghiệm / tệp kết quả về thì báo CSKH (theo vai) VÀ bác sĩ của
-- khách (đích danh) — Tuyền chốt 15/09. Bảng `thong_bao` đã có
-- `nguoi_nhan_staff_id` từ 20260807000006 nhưng chỉ mục chống trùng chỉ phủ
-- dòng theo vai; sửa kết quả hai lần sẽ báo bác sĩ hai lần.

CREATE UNIQUE INDEX IF NOT EXISTS uq_thong_bao_dang_mo_nguoi
    ON public.thong_bao (clinic_id, nguon, nguon_id, nguoi_nhan_staff_id)
 WHERE da_xu_ly_luc IS NULL AND nguon_id IS NOT NULL AND vai_nhan IS NULL;
