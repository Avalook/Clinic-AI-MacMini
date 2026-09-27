-- Ô CHỮ TƯ VẤN ĐƯỢC XOÁ TRẮNG (27/09/2026 — bản giao diện mẫu mục 12).
--
-- Ô chữ tự do của bác sĩ tư vấn lưu mỗi lần một dòng `consultation_note` (giữ
-- lịch sử, không sửa đè). Xoá hết chữ rồi để tự lưu = một dòng RỖNG — nhưng
-- CHECK cũ bắt `btrim(body)` phải có chữ nên lệnh `noi-dung-tu-van` vỡ 500
-- (lỗi ngủ đông từ 24/09; lộ ra khi bác sĩ chính cũng sửa được ô này). Không có
-- cách nào khác để ghi "đã xoá" mà không xoá lịch sử.
--
-- Ghi chú khám cũ (`save_note`, phiên PRIMARY) vẫn chặn rỗng ở hàm dịch vụ.
-- Phần "mang sang" đã bỏ dòng rỗng (`mang_sang.py`: `WHERE body <> ''`).

ALTER TABLE public.consultation_note
    DROP CONSTRAINT IF EXISTS consultation_note_body;

ALTER TABLE public.consultation_note
    ADD CONSTRAINT consultation_note_body CHECK (length(body) <= 20000);
