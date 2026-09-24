-- Người giới thiệu — lưu ở HỒ SƠ khách (Tuyền 24/09/2026).
--
-- "Trong kênh đặt CSKH, bỏ website và hotline, nút giới thiệu cho ghi vào,
-- thông tin này được lưu ở hồ sơ khám luôn." Đặt lịch kênh "Giới thiệu" kèm
-- tên người giới thiệu → ghi vào hồ sơ; phiếu khám đọc từ đây (mang_sang.py).
-- Chạy lại được.

ALTER TABLE public.patient
    ADD COLUMN IF NOT EXISTS nguoi_gioi_thieu text;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'patient_nguoi_gioi_thieu_dai') THEN
        ALTER TABLE public.patient ADD CONSTRAINT patient_nguoi_gioi_thieu_dai
            CHECK (nguoi_gioi_thieu IS NULL OR length(nguoi_gioi_thieu) <= 200);
    END IF;
END $$;

COMMENT ON COLUMN public.patient.nguoi_gioi_thieu IS
    'Ai giới thiệu khách tới (kênh đặt "Giới thiệu") — hiện ở phiếu khám.';
