-- Kết quả sẵn sàng, và sửa lại được sau khi đã hoàn tất (23/09/2026).
--
-- HAI SỰ THẬT KHÁC NHAU, MỘT NÚT BẤM. ChatGPT #156, Tuyền chốt #157: người làm
-- chỉ bấm [Hoàn tất] một lần; phía sau hệ thống ghi CẢ HAI:
--
--     service.completed   dịch vụ đã làm xong
--     result.ready        đã có kết quả để đọc
--
-- Chúng KHÔNG phải một. Lấy mẫu xét nghiệm gửi ra ngoài thì dịch vụ xong ngay
-- hôm nay, còn kết quả hai ngày sau mới về. Gộp hai thứ này làm một là lý do
-- các hệ cũ báo "đã có kết quả" khi chưa ai đọc được gì.
--
--     result_mode = INLINE   kết quả có ngay tại phòng (siêu âm, thủ thuật)
--                            → Hoàn tất phiếu thì phát luôn `result.ready`
--                   LATER    làm xong nhưng kết quả về sau (mẫu gửi đi)
--                   NONE     dịch vụ này không sinh kết quả để đọc
--
-- SỬA ĐƯỢC SAU KHI HOÀN TẤT (Tuyền 23/09: *"vẫn cho sửa được vì audit log
-- được mà"*). Đây là cùng một luật đã áp cho sinh hiệu (`VitalsCorrected`,
-- ChatGPT #144): hệ thống không khoá người dùng, nó GHI LẠI.
--
-- `dang_sua` chứ không phải đưa phiếu về nháp: kết quả cũ vẫn là kết quả chính
-- thức trong suốt lúc sửa. Không có khoảnh khắc nào bác sĩ mở ra mà thấy trống.

ALTER TABLE public.form_instance
    ADD COLUMN IF NOT EXISTS dang_sua boolean NOT NULL DEFAULT false;

-- Chỉ phiếu ĐÃ hoàn tất mới có chuyện "đang sửa lại". Phiếu nháp thì sửa là
-- chuyện đương nhiên, không cần cờ.
ALTER TABLE public.form_instance
    DROP CONSTRAINT IF EXISTS form_instance_dang_sua_phai_da_xong;
ALTER TABLE public.form_instance
    ADD CONSTRAINT form_instance_dang_sua_phai_da_xong
    CHECK (NOT dang_sua OR trang_thai = 'READY');

ALTER TABLE public.dich_vu_mau_ket_qua
    ADD COLUMN IF NOT EXISTS result_mode text NOT NULL DEFAULT 'INLINE';
ALTER TABLE public.dich_vu_mau_ket_qua
    DROP CONSTRAINT IF EXISTS dich_vu_mau_ket_qua_result_mode;
ALTER TABLE public.dich_vu_mau_ket_qua
    ADD CONSTRAINT dich_vu_mau_ket_qua_result_mode
    CHECK (result_mode IN ('INLINE', 'LATER', 'NONE'));

COMMENT ON COLUMN public.dich_vu_mau_ket_qua.result_mode IS
    'INLINE = kết quả có ngay tại phòng · LATER = về sau · NONE = không sinh kết quả';
COMMENT ON COLUMN public.form_instance.dang_sua IS
    'Phiếu đã hoàn tất, người dùng đang sửa lại. Bấm Hoàn tất lần nữa → result.corrected';
