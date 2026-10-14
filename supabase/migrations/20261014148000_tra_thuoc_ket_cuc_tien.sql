-- G4d · R3 (Tuyền chốt E, 14/10/2026): khách trả thuốc BẮT chọn kết cục tiền.
-- Trước đây `khach_tra_thuoc` chỉ ghi "thuốc vật lý đã quay lại" (CP5) — hàng
-- về kho, tiền không ra, không màn nào báo. Nay mỗi lần trả MỚI mang một trong:
--   * HOAN    — tạo đúng khoản hoàn (payment_refund) cho phần trả, mặc định theo
--               hình thức hiệu lực của lần thu gốc;
--   * DOI     — đổi thuốc khác: cũng là khoản hoàn (tiền trả về) — đơn mới thu
--               như thường, chênh lệch ra ở quầy;
--   * GIU_LAI — khách để lại tiền, ghi lý do: vẫn là nợ khách (sổ PHAI_TRA).
-- Lần trả cũ (trước migration) để NULL — không đoán ngược.
-- Ghi lúc INSERT (trigger drug_return_guard đã cấm UPDATE) → không nới guard.

ALTER TABLE public.drug_return
    ADD COLUMN IF NOT EXISTS ket_cuc_tien text,
    ADD COLUMN IF NOT EXISTS ly_do_tien   text,
    ADD COLUMN IF NOT EXISTS refund_id    uuid;

ALTER TABLE public.drug_return DROP CONSTRAINT IF EXISTS drug_return_refund_fkey;
ALTER TABLE public.drug_return ADD CONSTRAINT drug_return_refund_fkey
    FOREIGN KEY (refund_id) REFERENCES public.payment_refund (refund_id)
    ON DELETE RESTRICT;

ALTER TABLE public.drug_return DROP CONSTRAINT IF EXISTS drug_return_ket_cuc_tien_hop_le;
ALTER TABLE public.drug_return ADD CONSTRAINT drug_return_ket_cuc_tien_hop_le CHECK (
    ket_cuc_tien IS NULL AND refund_id IS NULL AND ly_do_tien IS NULL
    OR ket_cuc_tien IN ('HOAN', 'DOI') AND refund_id IS NOT NULL
    OR ket_cuc_tien = 'GIU_LAI' AND refund_id IS NULL
       AND length(btrim(coalesce(ly_do_tien, ''))) >= 3
);

CREATE INDEX IF NOT EXISTS idx_drug_return_prescription
    ON public.drug_return (clinic_id, prescription_id);

-- Sổ nợ ghi lần trả bằng sự kiện riêng `medicine.returned` (khách thường trả vài
-- giờ / vài ngày SAU check-out — sổ đã ghi xong lần về, vòng đối chiếu chỉ quét
-- 48 giờ): thêm loại "Khách trả thuốc".
ALTER TABLE public.so_no DROP CONSTRAINT IF EXISTS so_no_loai_check;
ALTER TABLE public.so_no ADD CONSTRAINT so_no_loai_check CHECK (loai IN (
    'DAU_KY', 'KHI_VE', 'MO_LAI_LUOT', 'GHI_NO', 'THU', 'HUY_PHIEU', 'HOAN_TIEN',
    'DOI_CHI_DINH', 'TRA_THUOC', 'DOI_CHIEU'));
