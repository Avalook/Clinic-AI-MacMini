-- Hai mốc mới cho luồng demo 17/09 (Tuyền):
--
-- 1. ĐIỀU DƯỠNG GỌI KHÁCH VÀO ĐO SINH HIỆU. Trước đây màn Đo sinh hiệu chỉ có
--    danh sách + ô điền; khách ngồi ngoài không biết tới lượt mình. Mốc gọi nằm
--    ở encounter_flow cạnh `vitals_status` — cùng một bước, cùng một dòng.
--
-- 2. ĐỐI TÁC BÁO "CHỜ TÀI LIỆU". Giữa "đã lấy mẫu" và "đã có kết quả" có một
--    quãng dài (lab đang chạy). Đối tác bấm nhận việc → CSKH thấy "đang chờ tài
--    liệu từ đối tác" thay vì đoán. Kết quả về vẫn là `ket_qua_luc` như cũ.

ALTER TABLE public.encounter_flow
    ADD COLUMN IF NOT EXISTS goi_do_luc timestamptz,
    ADD COLUMN IF NOT EXISTS goi_do_boi uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.encounter_flow.goi_do_luc IS
'Lần gần nhất điều dưỡng bấm "Gọi vào đo" cho lượt này. Gọi lại thì cập nhật.';

ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS doi_tac_cho_tai_lieu_luc timestamptz,
    ADD COLUMN IF NOT EXISTS doi_tac_cho_tai_lieu_boi uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.service_order.doi_tac_cho_tai_lieu_luc IS
'Đối tác đã nhận việc, đang làm và sẽ gửi tài liệu kết quả. NULL = chưa nhận.';
