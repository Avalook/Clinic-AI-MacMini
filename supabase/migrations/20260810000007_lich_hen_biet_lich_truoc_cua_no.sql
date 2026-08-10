-- Lịch hẹn phải biết nó là tái khám CỦA LỊCH NÀO.
--
-- QUANG 10/08/2026: nút "Tái khám" và nút "Đặt lịch khám mới" phải sinh trạng
-- thái thật, để cả màn Đặt lịch lẫn màn Quản lý khách hàng hiện được nhãn nhỏ
-- "khám lần 2/3/4" hay "tái khám" — *"vì mình phân biệt kĩ hơn là tái khám cho
-- dịch vụ nào nên tôi muốn như vậy cho dễ hiểu hơn"*.
--
-- HÔM NAY HỆ THỐNG KHÔNG BIẾT ĐIỀU ĐÓ. Đã tra 8 tên cột khả dĩ
-- (parent_appointment, previous_appointment, follow_up_of, source_appointment,
-- from_appointment, tai_kham_cua, lich_truoc, prev_appointment) trên toàn bộ
-- src/clinicai, src/dashboard và supabase/ — không cái nào tồn tại. Bảng
-- `appointment` có 24 cột và không cột nào trỏ về một lịch hẹn khác.
--
-- BA THỨ TRÔNG GIỐNG, VÀ VÌ SAO KHÔNG DÙNG ĐƯỢC. Ghi lại để lần sau không ai
-- mất một buổi đi thử lại ba con đường này:
--
--   `episode_id`      TẬP HỢP, không phải MŨI TÊN. Nó gom theo (phòng khám,
--                     khách, dịch vụ), nên nói được "cùng đợt" nhưng không nói
--                     được lịch nào nối lịch nào. Tệ hơn: đợt chỉ đóng khi có
--                     lịch mới đánh dấu patient_kind='NEW', còn PENDING_CLOSE
--                     thì KHÔNG MÃ NÀO ĐẶT — nên một đợt mở vĩnh viễn và mọi
--                     lần khám cùng dịch vụ qua nhiều năm dồn vào một chuỗi.
--   `patient_kind`    LẬP LUẬN VÒNG TRÒN. Màn đặt lịch suy "RETURN" TỪ việc có
--                     đợt đang mở, rồi _attach_episode lại dùng patient_kind để
--                     quyết định đợt. Chính booking_service đã tự cảnh báo.
--   `nhac_tai_kham.nguon_visit_id`
--                     Mối nối THẬT duy nhất giữa lời dặn tái khám và lượt khám
--                     sinh ra nó — nhưng chỉ lượt gọi 1 ghi nó. Đúng mắt xích
--                     cần (lượt khám cũ → lịch hẹn mới) thì nó đứt.
--
-- VÌ SAO KHÔNG SUY RA TỪ "lịch gần nhất trước đó cùng dịch vụ". Vì đó là ĐOÁN.
-- Khách khám phụ khoa tháng 3 vì một chuyện, tháng 9 vì chuyện khác — suy diễn
-- ấy nối hai lần khám không liên quan thành một chuỗi, và không ai phát hiện
-- được vì kết quả trông vẫn hợp lý.
--
-- NULL LÀ CÂU TRẢ LỜI ĐÚNG, không phải thiếu dữ liệu: lịch khám mới, lịch của
-- khách mới, và mọi lịch đặt trước hôm nay đều không có lịch trước. Chỉ nút
-- "Tái khám" mới điền cột này.

ALTER TABLE public.appointment
    ADD COLUMN IF NOT EXISTS lich_truoc_id uuid
        REFERENCES public.appointment (id) ON DELETE SET NULL;

COMMENT ON COLUMN public.appointment.lich_truoc_id IS
    'Lịch hẹn mà lịch này là TÁI KHÁM của nó. NULL = khám mới hoặc lần đầu — '
    'đó là câu trả lời đúng, không phải dữ liệu thiếu. Chỉ nút "Tái khám" ở màn '
    'Quản lý khách hàng ghi cột này; nút "Đặt lịch khám mới" cố ý để NULL.';

-- ON DELETE SET NULL chứ không CASCADE: xoá một lịch cũ không được kéo theo
-- lịch tái khám của nó. Chuỗi đứt một mắt còn hơn mất cả lượt khám sắp tới.

-- Truy vấn sẽ đi NGƯỢC chuỗi ("lịch này tái khám của ai") lẫn XUÔI ("lịch nào
-- tái khám lịch này") khi dựng lịch sử khám. Index cho chiều xuôi; chiều ngược
-- đã có khoá chính.
CREATE INDEX IF NOT EXISTS idx_appointment_lich_truoc
    ON public.appointment (lich_truoc_id)
    WHERE lich_truoc_id IS NOT NULL;

-- CHỐT CHẶN: một lịch không thể là tái khám của chính nó. Vòng lặp dài hơn thì
-- ràng buộc này không bắt được — nhưng vòng độ dài 1 là lỗi lập trình duy nhất
-- thực sự có khả năng xảy ra ở đây (truyền nhầm id của chính lịch đang tạo), và
-- nó sẽ làm mọi truy vấn đệ quy dựng lịch sử treo vô hạn.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'appointment_lich_truoc_khong_tu_tro'
    ) THEN
        ALTER TABLE public.appointment
            ADD CONSTRAINT appointment_lich_truoc_khong_tu_tro
            CHECK (lich_truoc_id IS NULL OR lich_truoc_id <> id);
    END IF;
END $$;
