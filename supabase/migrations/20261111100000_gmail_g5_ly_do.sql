-- Gmail G5 (Tuyền duyệt 11/11/2026): thư kết quả tự gán vào MỌI chỉ định loại xét
-- nghiệm lab làm (không cần Bàn XN / Lấy mẫu); thư không gán được phải nói rõ LÝ DO.
--
-- 1. Hai lý do chờ mới cho hàng ghép tay:
--    KHONG_THAY_CHI_DINH — tên + SĐT khớp đúng một khách nhưng khách không có chỉ định
--                          loại xét nghiệm của lab trong 60 ngày trước thư.
--    KHONG_RO_MAU_THU    — không nhận ra mẫu tiêu đề thư của lab (người xem).
-- 2. Cột `luu_tru_vi_sao`: vì sao thư chỉ cất ở Kho (ly_do_cho = LUU_TRU). Chỉ có nghĩa
--    khi LUU_TRU — CHECK ép. Dòng Lưu trữ cũ (G2) để NULL (không đoán bù).
-- Thêm cột + nới CHECK, không đổi dữ liệu cũ ⇒ code cũ chạy tiếp được.

ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_ly_do_cho_check;
ALTER TABLE public.drive_tep ADD CONSTRAINT drive_tep_ly_do_cho_check CHECK (
    ly_do_cho IS NULL OR ly_do_cho IN (
        'KHONG_MA', 'SAI_SO_KIEM', 'NHIEU_MA', 'KHONG_THAY_MAU', 'SAI_DOI_TAC',
        'ONG_NHIEU_VIEC', 'LOI_TEP', 'KHONG_DOC_DUOC', 'KHONG_KHOP_KHACH',
        'NHIEU_KHACH', 'LUU_TRU', 'CHUA_LAY_MAU', 'CO_BAN_MOI',
        'KHONG_THAY_CHI_DINH', 'KHONG_RO_MAU_THU'));

ALTER TABLE public.drive_tep ADD COLUMN IF NOT EXISTS luu_tru_vi_sao text;

ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_luu_tru_vi_sao_hop_le;
ALTER TABLE public.drive_tep ADD CONSTRAINT drive_tep_luu_tru_vi_sao_hop_le CHECK (
    luu_tru_vi_sao IS NULL
    OR (ly_do_cho = 'LUU_TRU'
        AND luu_tru_vi_sao IN ('CHUA_DAT_MOC', 'TRUOC_MOC', 'KHONG_XAC_THUC',
                               'CHUA_DU_KET_QUA', 'PHIEU_MA_VACH', 'DA_CO_KET_QUA')));

COMMENT ON COLUMN public.drive_tep.luu_tru_vi_sao IS
'Gmail G5: vì sao thư chỉ cất ở Kho email — CHUA_DAT_MOC (chưa đặt mốc tự ghép) · TRUOC_MOC (thư nhận trước mốc) · KHONG_XAC_THUC (không qua DKIM/DMARC đúng miền) · CHUA_DU_KET_QUA (Greenlab trả từng phần) · PHIEU_MA_VACH (Eurofins) · DA_CO_KET_QUA (chỉ định đã có tờ TỪ GMAIL không cũ hơn thư — thư trùng / cũ; tờ tải tay thì thư vẫn gắn thêm song song). NULL ở dòng Lưu trữ cũ (trước G5).';
