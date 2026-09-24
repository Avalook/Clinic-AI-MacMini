-- Quầy thuốc chỉnh đơn trước khi thu (Tuyền 24/09/2026).
--
-- "Ở màn thu tiền thuốc cho thêm ô lấy thêm thuốc, có cả số lượng, hướng dẫn sử
-- dụng… như phiếu khám của bác sĩ để thu ngân thuốc chỉnh được, bỏ tick thuốc
-- nếu bệnh nhân không muốn, lưu hết lịch sử, có event phát ra là đã bỏ thuốc
-- này ở bản cuối cùng thanh toán."
--
-- NGUỒN của dòng: BAC_SI (bác sĩ / thư ký kê — mặc định, mọi dòng cũ) hay QUAY
-- (quầy thuốc thêm lúc bán). Đơn của bác sĩ (phiếu khám, đính chính, ký) CHỈ
-- đọc và sửa dòng BAC_SI — không thì lần bác sĩ lưu lại đơn sẽ coi dòng quầy
-- thêm là "bị xoá". Hoá đơn, nhà thuốc, giao thuốc đọc CẢ HAI.
-- Chạy lại được.

ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS nguon text NOT NULL DEFAULT 'BAC_SI';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'prescription_nguon_hop_le') THEN
        ALTER TABLE public.prescription ADD CONSTRAINT prescription_nguon_hop_le
            CHECK (nguon IN ('BAC_SI', 'QUAY'));
    END IF;
END $$;

COMMENT ON COLUMN public.prescription.nguon IS
    'BAC_SI = bác sĩ kê; QUAY = quầy thuốc thêm lúc bán (không nằm trong đơn bác sĩ).';
