-- Thêm cột email cho hồ sơ bệnh nhân (G1 đợt 14/10/2026).
-- CHECK độ dài <= 254, không UNIQUE, không backfill.
-- Chạy lại được (idempotent).

ALTER TABLE public.patient
    ADD COLUMN IF NOT EXISTS email text;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'patient_email_check') THEN
        ALTER TABLE public.patient ADD CONSTRAINT patient_email_check
            CHECK (email IS NULL OR length(email) <= 254);
    END IF;
END $$;

COMMENT ON COLUMN public.patient.email IS
    'Email của bệnh nhân — phục vụ liên hệ và xuất hoá đơn kế toán.';
