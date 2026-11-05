-- XÉT NGHIỆM ĐỐI TÁC — CHẶNG 4: GHÉP THEO TÊN + SĐT (Tuyền chốt 05/11/2026 chiều).
--
-- Mã ống là mã nội bộ, đối tác không biết để ghi vào tên tệp ⇒ máy quét đọc chữ PDF,
-- khớp tên + SĐT khách (services/xet_nghiem/ghep_khach.py). Thêm lý do chờ ghép tay:
--   KHONG_DOC_DUOC   — PDF không có chữ (ảnh scan) / không phải PDF
--   KHONG_KHOP_KHACH — không khách nào đang chờ của đối tác này khớp cả tên lẫn SĐT
--   NHIEU_KHACH      — hơn một khách cùng khớp (không đoán)
-- Không sửa migration 20261106100000 (đã áp staging) — thay ràng buộc ở đây.
-- Chạy lại được.

ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_ly_do_cho_check;
ALTER TABLE public.drive_tep ADD CONSTRAINT drive_tep_ly_do_cho_check CHECK (
    ly_do_cho IS NULL OR ly_do_cho IN (
        'KHONG_MA', 'SAI_SO_KIEM', 'NHIEU_MA', 'KHONG_THAY_MAU', 'SAI_DOI_TAC',
        'ONG_NHIEU_VIEC', 'LOI_TEP', 'KHONG_DOC_DUOC', 'KHONG_KHOP_KHACH',
        'NHIEU_KHACH'));
