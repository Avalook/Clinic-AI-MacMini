-- Contract tiền–thuốc, CP1 (19/09/2026): định danh thuốc kho, số lượng mua,
-- bên thu tiền, và ẢNH CHỤP hoá đơn lúc thu.
--
-- Chỉ THÊM. Không đổi một dòng dữ liệu cũ nào, không backfill:
--   * prescription.drug_catalog_id / purchased_qty mới đều NULL cho dòng cũ —
--     dòng cũ chưa được xác định thuốc kho thì CHƯA thu tiền được (đúng hợp đồng
--     C1: không đoán thuốc từ tên), không phải "tự nối theo tên".
--   * service_price.billing_owner mặc định CLINIC = đúng hành vi hiện tại (mọi
--     dịch vụ đang cộng vào hoá đơn phòng khám). Dịch vụ nào đối tác tự thu là
--     DỮ LIỆU do quản lý khai, không viết cứng trong mã.
--   * payment_bill_line là bảng mới, chỉ thêm, gắn với từng lần thu
--     (payment_cycle_id) — đổi bảng giá hôm sau không đổi nghĩa hoá đơn hôm trước.
-- Chạy lại nhiều lần được.

-- ── Định danh thuốc kho + số lượng mua ────────────────────────────────────
ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS drug_catalog_id uuid
        REFERENCES public.drug_catalog(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS drug_mapped_by uuid
        REFERENCES public.staff(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS drug_mapped_at timestamptz,
    ADD COLUMN IF NOT EXISTS purchased_qty numeric;

ALTER TABLE public.prescription DROP CONSTRAINT IF EXISTS prescription_purchased_qty_check;
ALTER TABLE public.prescription ADD CONSTRAINT prescription_purchased_qty_check
    CHECK (purchased_qty IS NULL
           OR (purchased_qty >= 0
               AND (quantity_num IS NULL OR purchased_qty <= quantity_num)));

ALTER TABLE public.prescription DROP CONSTRAINT IF EXISTS prescription_map_co_dau_vet;
ALTER TABLE public.prescription ADD CONSTRAINT prescription_map_co_dau_vet
    CHECK (drug_catalog_id IS NULL
           OR (drug_mapped_by IS NOT NULL AND drug_mapped_at IS NOT NULL));

COMMENT ON COLUMN public.prescription.drug_catalog_id IS
    'Định danh thuốc kho của dòng đơn (contract tiền–thuốc C1). NULL = chưa xác '
    'định thuốc kho → chưa thu tiền / chưa cấp được. Không suy từ tên.';
COMMENT ON COLUMN public.prescription.purchased_qty IS
    'Số khách đồng ý mua (C2). NULL = chưa khai → hoá đơn dùng quantity_num '
    '(pilot: mua đủ số kê). Khác quantity_num (số kê) và dispensed_qty (đã giao).';

-- ── Bên thu tiền của dịch vụ ─────────────────────────────────────────────
ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS billing_owner text NOT NULL DEFAULT 'CLINIC';
ALTER TABLE public.service_price DROP CONSTRAINT IF EXISTS service_price_billing_owner_check;
ALTER TABLE public.service_price ADD CONSTRAINT service_price_billing_owner_check
    CHECK (billing_owner IN ('CLINIC', 'EXTERNAL_PARTNER'));
COMMENT ON COLUMN public.service_price.billing_owner IS
    'Ai thu tiền dịch vụ này (C5). EXTERNAL_PARTNER: vẫn hiện trong hành trình '
    'nhưng KHÔNG cộng vào hoá đơn Dr4Women.';

-- ── Phiên bản hoá đơn đã thu ────────────────────────────────────────────
ALTER TABLE public.payment ADD COLUMN IF NOT EXISTS bill_revision text;
COMMENT ON COLUMN public.payment.bill_revision IS
    'Dấu của hoá đơn máy chủ tính lúc thu (C3). NULL ở phiếu thu trước CP1.';

-- ── Ảnh chụp từng dòng hoá đơn lúc thu ──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.payment_bill_line (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    payment_id       uuid NOT NULL REFERENCES public.payment(id) ON DELETE RESTRICT,
    payment_cycle_id uuid NOT NULL,
    visit_id         uuid NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('thuoc', 'dich_vu')),
    source_type      text NOT NULL
        CHECK (source_type IN ('exam', 'service_order', 'prescription')),
    source_id        text NOT NULL,
    name_snapshot    text NOT NULL,
    quantity         numeric NOT NULL CHECK (quantity > 0),
    unit             text,
    unit_price       numeric(12, 0) NOT NULL CHECK (unit_price >= 0),
    line_total       numeric(14, 0) NOT NULL CHECK (line_total >= 0),
    billing_owner    text NOT NULL CHECK (billing_owner IN ('CLINIC', 'EXTERNAL_PARTNER')),
    drug_catalog_id  uuid,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payment_bill_line_cycle
    ON public.payment_bill_line (clinic_id, payment_cycle_id);
CREATE INDEX IF NOT EXISTS idx_payment_bill_line_visit
    ON public.payment_bill_line (clinic_id, visit_id);

CREATE OR REPLACE FUNCTION public.payment_bill_line_append_only()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'payment_bill_line là ảnh chụp hoá đơn đã thu — không sửa/xoá (%)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS trg_payment_bill_line_append_only ON public.payment_bill_line;
CREATE TRIGGER trg_payment_bill_line_append_only
    BEFORE UPDATE OR DELETE ON public.payment_bill_line
    FOR EACH ROW EXECUTE FUNCTION public.payment_bill_line_append_only();

ALTER TABLE public.payment_bill_line ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_bill_line_select_own_clinic ON public.payment_bill_line;
CREATE POLICY payment_bill_line_select_own_clinic ON public.payment_bill_line
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
