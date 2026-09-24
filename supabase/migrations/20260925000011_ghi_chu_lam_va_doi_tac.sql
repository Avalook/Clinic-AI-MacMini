-- GHI CHÚ khi bấm xong / đã lấy mẫu (Tuyền 24/09/2026: "cả cái điều dưỡng lấy
-- mẫu cũng vậy… không để chỉ cho ấn đã lấy mẫu là xong, phải có ghi chú lại
-- chứ. Đối tác xử lý cho xong đi").
--
--   service_execution_attempt.ghi_chu   — ghi chú của LẦN LÀM (phòng bấm Xong /
--                                         Đã lấy mẫu); bảng của khối Thực hiện.
--   doi_tac_nhan_viec.ghi_chu_lay_mau   — đối tác bấm "Đã lấy mẫu";
--   doi_tac_nhan_viec.ghi_chu_tai_lieu  — đối tác bấm "Chờ tài liệu";
--                                         bảng của khối Đối tác.
-- Độ dài canh ở service (≤ 2000). Chạy lại được.

ALTER TABLE public.service_execution_attempt
    ADD COLUMN IF NOT EXISTS ghi_chu text;

ALTER TABLE public.doi_tac_nhan_viec
    ADD COLUMN IF NOT EXISTS ghi_chu_lay_mau text,
    ADD COLUMN IF NOT EXISTS ghi_chu_tai_lieu text;
