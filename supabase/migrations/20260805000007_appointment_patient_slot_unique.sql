-- Một bệnh nhân, một khung giờ, một lịch hẹn.
--
-- CHUYỆN ĐÃ XẢY RA. Ngày 04/08 một bệnh nhân có BA lịch hẹn cùng khung 17:15,
-- tạo cách nhau 10 và 5 giây — tức một người bấm "Đặt lịch hẹn" ba lần. Khung
-- đó sức chứa 3, nên một người chiếm trọn khung của cả phòng khám.
--
-- VÌ SAO CÁC LỚP TRƯỚC KHÔNG ĐỦ. Đường ghi hiện có ba lớp, và cả ba đều ở phía
-- trên database:
--
--   1. Nút bị vô hiệu hoá khi đang gửi — chỉ chặn được người, không chặn được
--      hai request đã rời trình duyệt.
--   2. Idempotency-Key — chặn đúng cái "gửi lại cùng một yêu cầu", nhưng không
--      chặn hai yêu cầu KHÁC NHAU cùng nội dung, và nó là header TUỲ CHỌN.
--   3. booking_service._patient_double_booked — SELECT rồi INSERT, không khoá.
--      Docstring của chính nó viết: "Nó không chống được hai request thật sự
--      đồng thời."
--
-- Và một lớp nữa không ai để ý: SchedulingService.create_appointment cũng ghi
-- vào bảng này và KHÔNG hề gọi _patient_double_booked. Chốt đặt ở tầng service
-- chỉ che được cửa nào có người nhớ đặt chốt; chỉ mục thì che mọi cửa.
--
-- Theo ADR-0003, đây là bậc 1 của bậc thang (UNIQUE/CHECK trước, advisory lock
-- sau) và là lý do KHÔNG cài khoá trong Python cho việc này.
--
-- VÌ SAO LÀ LÚC NÀY. Bảng appointment trên prod hiện có 2 dòng và 0 nhóm trùng
-- (đã dò ngày 05/08). Thêm ràng buộc vào bảng 2 dòng là chuyện một giây; thêm
-- vào bảng đã chạy vài năm là phải dọn dữ liệu thật trước.

-- ---------------------------------------------------------------------------
-- 1. Cổng chặn: có dòng trùng thì DỪNG, đừng để index tự đổ với lỗi khó đọc
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_dupes integer;
BEGIN
    SELECT count(*) INTO v_dupes FROM (
        SELECT 1
          FROM public.appointment
         WHERE status <> ALL (ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'])
         GROUP BY clinic_id, clinic_patient_id, slot_start
        HAVING count(*) > 1
    ) AS d;

    IF v_dupes > 0 THEN
        RAISE EXCEPTION
            'Còn % nhóm lịch trùng (cùng phòng khám, cùng bệnh nhân, cùng giờ '
            'bắt đầu). Dọn xong mới tạo được chỉ mục. Câu dò: SELECT clinic_id, '
            'clinic_patient_id, slot_start, count(*) FROM appointment WHERE '
            'status <> ALL (ARRAY[''CANCELLED'',''NO_SHOW'',''DOCTOR_DECLINED'']) '
            'GROUP BY 1,2,3 HAVING count(*) > 1;',
            v_dupes;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. Chỉ mục duy nhất BÁN PHẦN
-- ---------------------------------------------------------------------------
-- BÁN PHẦN, vì lịch đã huỷ không giữ chỗ nào. Một bệnh nhân huỷ lịch 9:00 rồi
-- đặt lại đúng 9:00 là chuyện bình thường và phải làm được — ba trạng thái
-- trong mệnh đề WHERE là đúng ba trạng thái mà DEAD_STATUSES bên Python liệt kê
-- (booking_service.py:68) và trigger sức chứa dùng (20260803000002:178).
--
-- CHỈ KHOÁ slot_start, KHÔNG khoá cả khoảng. Một bệnh nhân có hai lịch KHÁC GIỜ
-- trong cùng buổi là luồng có thật và hợp lệ: khám xong rồi siêu âm sau. Thứ
-- phải chặn là hai lịch CÙNG MỘT MỐC BẮT ĐẦU — đó mới là dấu vết của cú bấm
-- lặp, không phải của một lịch trình hợp lý.
CREATE UNIQUE INDEX IF NOT EXISTS uq_appointment_patient_slot_live
    ON public.appointment (clinic_id, clinic_patient_id, slot_start)
 WHERE status <> ALL (ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED']);

COMMENT ON INDEX public.uq_appointment_patient_slot_live IS
    'Một bệnh nhân chỉ có một lịch còn sống tại mỗi mốc giờ bắt đầu. Bậc 1 của '
    'ADR-0003 — chặn ở database nên che được MỌI đường ghi, kể cả '
    'SchedulingService vốn không gọi _patient_double_booked.';
