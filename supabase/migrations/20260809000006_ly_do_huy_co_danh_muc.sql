-- Lý do huỷ lịch: chọn sẵn HOẶC tự viết.
--
-- DoD (Quang): *"Với chỗ viết lý do hủy lịch gồm 2 trường hợp: tự viết hoặc
-- chọn sẵn lý do. Lý do có sẵn gồm: chờ xác nhận lịch trước 7 ngày — BN báo
-- luôn là ko đến được; khi nhắc hẹn BN báo ko đến được, dù trước đó đã xác nhận
-- có đến; vào giờ khám, lễ tân gọi điện BN mới báo là ko đến."*
--
-- HÔM NAY CHỈ CÓ MỘT Ô CHỮ TỰ DO, và nó được ghi là "(tuỳ chọn)". Nghĩa là:
--   · phần lớn lịch huỷ không có lý do gì cả;
--   · phần có thì mỗi người viết một kiểu — "bận", "Bận", "khách bận việc",
--     "ko đến được" — nên không đếm được cái gì.
--
-- Ba lý do trên KHÔNG phải ba cách nói của "khách bận". Chúng là ba THỜI ĐIỂM
-- khác nhau trong vòng đời lịch hẹn, và mỗi thời điểm tốn của phòng khám một
-- khoản khác nhau:
--   · báo lúc gọi xác nhận (trước 7 ngày) → chỗ trống đó bán lại được
--   · báo lúc nhắc hẹn (trước 1 ngày)     → khó lấp, nhưng còn kịp
--   · báo vào đúng giờ khám               → bác sĩ ngồi không, chỗ mất trắng
-- Đếm được ba con số ấy là biết nên siết khâu nào. Gộp thành một ô chữ thì
-- không.
--
-- MÃ GHIM TRONG CHECK, KHÔNG PHẢI BẢNG CẤU HÌNH. Khác với `luat_cskh` (số ngày
-- là quy ước của từng phòng khám), ba mốc này do CHÍNH HỆ THỐNG định nghĩa:
-- chúng ứng với ba bước trong chuỗi việc CSKH. Phòng khám thêm mã thứ tư thì
-- không có bước nào sinh ra nó. Chữ hiển thị thì để ở code và có bài kiểm chống
-- lệch — xem ly-do-huy.ts và test_ly_do_huy_drift.py.

ALTER TABLE public.appointment
    ADD COLUMN IF NOT EXISTS ly_do_huy_ma text,
    -- AI huỷ. Trước đây không lưu, nên một lịch huỷ nhầm không truy được về ai.
    ADD COLUMN IF NOT EXISTS cancelled_by_staff_id uuid
        REFERENCES public.staff(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.appointment.ly_do_huy_ma IS
    'Mã lý do huỷ. KHAC = tự viết, khi đó cancellation_reason bắt buộc.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointment_ly_do_huy_ma_check'
    ) THEN
        ALTER TABLE public.appointment
            ADD CONSTRAINT appointment_ly_do_huy_ma_check
            CHECK (ly_do_huy_ma IS NULL OR ly_do_huy_ma IN (
                'BAO_KHI_XAC_NHAN',   -- gọi xác nhận trước 7 ngày, khách báo luôn
                'BAO_KHI_NHAC_HEN',   -- đã xác nhận sẽ đến, tới lúc nhắc thì đổi ý
                'BAO_VAO_GIO_KHAM',   -- đúng giờ khám lễ tân gọi mới biết
                'KHAC'));
    END IF;

    -- Huỷ thì phải có mã. Khai NOT VALID: 6 lịch đã huỷ trên bản thật không có
    -- mã nào, và bắt chúng hợp lệ ngược về quá khứ nghĩa là bịa cho mỗi cái một
    -- lý do. Ràng buộc chỉ soi những lần huỷ TỪ NAY.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointment_huy_phai_co_ly_do'
    ) THEN
        ALTER TABLE public.appointment
            ADD CONSTRAINT appointment_huy_phai_co_ly_do
            CHECK (status <> 'CANCELLED' OR ly_do_huy_ma IS NOT NULL) NOT VALID;
    END IF;

    -- Chọn "khác" mà không viết gì thì đúng bằng không chọn gì.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointment_ly_do_khac_phai_viet'
    ) THEN
        ALTER TABLE public.appointment
            ADD CONSTRAINT appointment_ly_do_khac_phai_viet
            CHECK (ly_do_huy_ma IS DISTINCT FROM 'KHAC'
                   OR nullif(btrim(coalesce(cancellation_reason, '')), '') IS NOT NULL)
            NOT VALID;
    END IF;
END $$;

-- Đếm theo mã là việc chính của cột này.
CREATE INDEX IF NOT EXISTS idx_appointment_ly_do_huy
    ON public.appointment (clinic_id, ly_do_huy_ma)
    WHERE status = 'CANCELLED';
