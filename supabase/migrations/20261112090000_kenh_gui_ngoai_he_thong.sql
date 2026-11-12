-- Kênh gửi tệp kết quả thứ năm: NGOAI_HE_THONG (Tuyền duyệt 12/11/2026).
--
-- Chỉ lệnh bù `gmail_bu_cu` ghi kênh này: tờ kết quả email về TRƯỚC 11/11 (ngày bật tự
-- nhận Gmail) mà nhân viên đã trả khách bằng Gmail / Zalo như trước — đánh "đã gửi, ngoài
-- hệ thống" để không đẻ việc CSKH "Kết quả chưa gửi" cho kết quả đã trả. Màn gửi của
-- CSKH KHÔNG có kênh này (`KENH_GUI_HOP_LE` trong tep_ket_qua_service giữ 4 kênh).
-- Thuần mở rộng một CHECK; không đổi dòng nào.

ALTER TABLE public.tep_ket_qua DROP CONSTRAINT IF EXISTS tep_ket_qua_gui_kenh_check;
ALTER TABLE public.tep_ket_qua ADD CONSTRAINT tep_ket_qua_gui_kenh_check CHECK (
    gui_kenh IS NULL
    OR gui_kenh IN ('ZALO', 'SMS', 'TRUC_TIEP', 'EMAIL', 'NGOAI_HE_THONG')
);
