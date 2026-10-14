-- G4d · R1 (Tuyền chốt C, 14/10/2026): xác minh chuyển khoản nhập SỐ TIỀN
-- NGÂN HÀNG THẬT NHẬN. Trước đây "Đã nhận tiền" ghi theo số hoá đơn — khách
-- chuyển thiếu / thừa thì sổ không có dấu. Nay:
--   * `so_tien_thuc_nhan` (tuỳ chọn) ghi lúc chờ → đã thu, bất biến sau đó;
--   * lệch phần chuyển khoản của lần thu → mã đối soát `SO_TIEN_LECH` (cờ
--     `can_doi_soat` bật theo CHECK có sẵn). Sổ vẫn ghi số hoá đơn — người đối
--     soát quyết thu thêm / trả lại, máy không tự ghi nợ.
-- Không đổi luồng trạng thái: CANCELLED vẫn là trạng thái cuối.

ALTER TABLE public.payment_cycle
    ADD COLUMN IF NOT EXISTS so_tien_thuc_nhan bigint;

ALTER TABLE public.payment_cycle DROP CONSTRAINT IF EXISTS payment_cycle_so_tien_thuc_nhan_khong_am;
ALTER TABLE public.payment_cycle ADD CONSTRAINT payment_cycle_so_tien_thuc_nhan_khong_am
    CHECK (so_tien_thuc_nhan IS NULL OR so_tien_thuc_nhan >= 0);

ALTER TABLE public.payment_cycle DROP CONSTRAINT IF EXISTS payment_cycle_doi_soat_ma_hop_le;
ALTER TABLE public.payment_cycle ADD CONSTRAINT payment_cycle_doi_soat_ma_hop_le CHECK (
    doi_soat_ly_do <@ ARRAY['HOA_DON_DOI', 'CHUA_GHI_BAN', 'SO_TIEN_LECH']::text[]
    AND array_position(doi_soat_ly_do, NULL) IS NULL);

-- Bản 20261013100000 + một điều: số thật nhận chỉ ghi cùng lúc chờ → đã thu.
CREATE OR REPLACE FUNCTION public.payment_cycle_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'payment_cycle là sổ các lần thu — không xoá'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT (
        (OLD.status = 'PENDING_VERIFICATION' AND NEW.status IN ('PAID', 'CANCELLED'))
        OR (OLD.status = 'PAID' AND NEW.status = 'VOIDED')
        OR (OLD.status = NEW.status AND OLD.payment_id IS NULL
            AND NEW.payment_id IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'payment_cycle: không chuyển % → % được', OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.payment_cycle_id <> OLD.payment_cycle_id
       OR NEW.clinic_id <> OLD.clinic_id OR NEW.visit_id <> OLD.visit_id
       OR NEW.kind <> OLD.kind OR NEW.amount <> OLD.amount
       OR NEW.bill_revision IS DISTINCT FROM OLD.bill_revision
       OR NEW.method IS DISTINCT FROM OLD.method
       OR NEW.legacy <> OLD.legacy
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at <> OLD.created_at
       OR (OLD.paid_at IS NOT NULL AND NEW.paid_at IS DISTINCT FROM OLD.paid_at)
       OR (OLD.confirmed_by IS NOT NULL
           AND NEW.confirmed_by IS DISTINCT FROM OLD.confirmed_by)
       OR (OLD.reference IS NOT NULL AND NEW.reference IS DISTINCT FROM OLD.reference)
       OR (OLD.payment_id IS NOT NULL AND NEW.payment_id IS DISTINCT FROM OLD.payment_id)
       -- Cờ, mã nguyên nhân đối soát và số ngân hàng thật nhận chỉ hình thành
       -- cùng lúc chờ → đã thu.
       OR ((NEW.can_doi_soat IS DISTINCT FROM OLD.can_doi_soat
            OR NEW.doi_soat_ly_do IS DISTINCT FROM OLD.doi_soat_ly_do
            OR NEW.so_tien_thuc_nhan IS DISTINCT FROM OLD.so_tien_thuc_nhan)
           AND NOT (OLD.status = 'PENDING_VERIFICATION' AND NEW.status = 'PAID'))
       -- Giảm giá ghi lúc INSERT, không sửa được.
       OR NEW.discount_type   IS DISTINCT FROM OLD.discount_type
       OR NEW.discount_value  IS DISTINCT FROM OLD.discount_value
       OR NEW.discount_amount <> OLD.discount_amount
       OR NEW.discount_reason IS DISTINCT FROM OLD.discount_reason
       OR NEW.discount_by     IS DISTINCT FROM OLD.discount_by
       OR NEW.original_amount IS DISTINCT FROM OLD.original_amount
    THEN
        RAISE EXCEPTION 'payment_cycle: cột đã ghi không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
