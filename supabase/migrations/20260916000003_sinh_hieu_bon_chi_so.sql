-- SINH HIỆU: THÊM NHỊP THỞ, SpO₂, BMI, THANG ĐAU (Tuyền chốt 16/09/2026).
--
-- Bốn chỉ số này đã có Ô NHẬP trên màn hồ sơ từ lâu, nhưng `vital_measurement`
-- không có cột nào cho chúng — nên chúng rơi vào JSONB của hồ sơ khám. Hệ quả:
-- chúng KHÔNG vào bảng lịch sử chỉ-thêm, không so được giữa các lần đo, không
-- ra được báo cáo. Thang đau thì không tồn tại ở đâu cả, dù phiếu giấy có.
--
-- Chạy lại được: ADD COLUMN IF NOT EXISTS + CHECK đặt tên, tạo lại nếu thiếu.

ALTER TABLE public.vital_measurement
    ADD COLUMN IF NOT EXISTS respiratory_rate int,
    ADD COLUMN IF NOT EXISTS spo2             int,
    ADD COLUMN IF NOT EXISTS bmi              numeric(4, 1),
    ADD COLUMN IF NOT EXISTS pain_score       int;

COMMENT ON COLUMN public.vital_measurement.respiratory_rate IS 'Nhịp thở, lần/phút';
COMMENT ON COLUMN public.vital_measurement.spo2 IS 'Độ bão hoà oxy máu ngoại vi, %';
COMMENT ON COLUMN public.vital_measurement.bmi IS
    'Chỉ số khối cơ thể. LƯU GIÁ TRỊ ĐÃ GHI chứ không tính lại khi đọc: người '
    'đo có thể sửa tay, và một con số hiện ra khác con số đã ghi là con số không '
    'ai tin được.';
COMMENT ON COLUMN public.vital_measurement.pain_score IS
    'Thang đau 0–10 (0 = không đau, 10 = đau dữ dội)';

DO $nguong$
BEGIN
    -- Khoảng cho phép lấy theo đời thật, KHÔNG theo "số nào cũng nhận": nhập
    -- nhầm 160 vào ô nhịp thở mà database nhận thì sai số ấy đi thẳng vào hồ sơ.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'vital_respiratory_rate_sane') THEN
        ALTER TABLE public.vital_measurement
            ADD CONSTRAINT vital_respiratory_rate_sane
            CHECK (respiratory_rate IS NULL
                   OR respiratory_rate BETWEEN 4 AND 80);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vital_spo2_sane') THEN
        ALTER TABLE public.vital_measurement
            ADD CONSTRAINT vital_spo2_sane
            CHECK (spo2 IS NULL OR spo2 BETWEEN 50 AND 100);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vital_bmi_sane') THEN
        ALTER TABLE public.vital_measurement
            ADD CONSTRAINT vital_bmi_sane
            CHECK (bmi IS NULL OR bmi BETWEEN 5 AND 100);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vital_pain_score_sane') THEN
        ALTER TABLE public.vital_measurement
            ADD CONSTRAINT vital_pain_score_sane
            CHECK (pain_score IS NULL OR pain_score BETWEEN 0 AND 10);
    END IF;
END
$nguong$;
