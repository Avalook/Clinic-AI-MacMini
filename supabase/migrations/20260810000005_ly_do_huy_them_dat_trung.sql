-- Danh mục lý do huỷ có BA bản, không phải hai.
--
-- CHUYỆN VỪA XẢY RA. Thêm mã `DAT_TRUNG` cho nút "Bỏ lịch này" (ad87caf), sửa
-- hai chỗ: `LY_DO_HUY` ở booking_service.py và `lib/ly-do-huy.ts`. Bài kiểm
-- chống lệch `test_ly_do_huy_drift` xanh, vì nó chỉ so hai bản ấy với nhau.
--
-- Bản thứ ba nằm ở đây — ràng buộc `appointment_ly_do_huy_ma_check`
-- (20260809000006) liệt kê cứng bốn mã. Nên Quang bấm "Bỏ lịch này" và nhận
-- "An internal server error occurred.": CheckViolationError từ database, nổi
-- lên thành 500 vì nó không phải ValidationError mà tầng API biết cách dịch.
--
-- Đúng cái mà chính docstring của bài kiểm ấy cảnh báo — *"sửa MÃ ở một bên thì
-- backend từ chối mọi lần huỷ từ màn kia, và lỗi ấy chỉ lộ ra khi có người thật
-- bấm nút thật"* — chỉ là nó canh nhầm hai trong ba bản. Bài kiểm nay đọc thêm
-- ràng buộc này ra từ chính file migration, nên bản thứ ba không trốn được nữa.
--
-- KHÔNG BỎ RÀNG BUỘC, CHỈ NỚI. Nó là thứ duy nhất chặn một mã gõ sai đi vào cột
-- dùng để đếm "khách báo không đến ở khâu nào" — bỏ đi thì con số ấy lặng lẽ
-- sai, và không ai biết cho tới lúc đọc báo cáo.

ALTER TABLE public.appointment
    DROP CONSTRAINT IF EXISTS appointment_ly_do_huy_ma_check;

ALTER TABLE public.appointment
    ADD CONSTRAINT appointment_ly_do_huy_ma_check
    CHECK (ly_do_huy_ma IS NULL
           OR ly_do_huy_ma IN ('BAO_KHI_XAC_NHAN',
                               'BAO_KHI_NHAC_HEN',
                               'BAO_VAO_GIO_KHAM',
                               'DAT_TRUNG',
                               'KHAC'));

COMMENT ON COLUMN public.appointment.ly_do_huy_ma IS
    'Mã lý do huỷ. Ba mã BAO_* là BA THỜI ĐIỂM trong vòng đời lịch hẹn (mỗi '
    'thời điểm tốn của phòng khám một khoản khác nhau). DAT_TRUNG là dọn dẹp — '
    'phòng khám tự đặt trùng rồi tự bỏ bớt, khách không huỷ gì cả, nên đếm '
    'chung với ba mã kia là bơm phồng con số "khách báo không đến". '
    'Danh mục phải khớp LY_DO_HUY ở booking_service.py và lib/ly-do-huy.ts.';
