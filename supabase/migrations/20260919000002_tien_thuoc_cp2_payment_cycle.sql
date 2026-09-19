-- Contract tiền–thuốc, CP2 (19/09/2026): MỖI LẦN THU LÀ MỘT DÒNG.
--
-- `payment` giữ một dòng cho (visit, kind) và TÁI DÙNG dòng ấy sau khi huỷ →
-- lịch sử "A đã thu / A huỷ / B đã thu" chỉ còn trong event_log (B7). Bảng này
-- là sổ các lần thu: một dòng mỗi `payment_cycle_id`, không xoá, chỉ chuyển
-- trạng thái theo đúng đường:
--     PENDING_VERIFICATION → PAID | CANCELLED     (chuyển khoản / QR chờ xác minh)
--     PAID → VOIDED                               (huỷ phiếu, có lý do)
-- `payment` vẫn là HÌNH CHIẾU "khoản hiện đã thu" mà checkout/thu ngân đọc.
--
-- Bằng chứng (A2): tiền mặt = nhân viên xác nhận đã nhận đủ; chuyển khoản/QR chỉ
-- PAID khi có người xác minh kèm MÃ GIAO DỊCH — khách quét mã không phải bằng
-- chứng đã trả.
--
-- Dữ liệu cũ: chỉ chuyển các dòng `payment` HIỆN CÓ, đánh `legacy`, phương thức
-- NULL (không rõ) — không dựng lại lần thu nào từ suy đoán. Chạy lại được.

CREATE TABLE IF NOT EXISTS public.payment_cycle (
    payment_cycle_id uuid PRIMARY KEY,
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('thuoc', 'dich_vu')),
    payment_id       uuid REFERENCES public.payment(id) ON DELETE RESTRICT,
    amount           bigint NOT NULL CHECK (amount > 0),
    bill_revision    text,
    method           text CHECK (method IN ('CASH', 'TRANSFER', 'QR')),
    status           text NOT NULL
        CHECK (status IN ('PENDING_VERIFICATION', 'PAID', 'VOIDED', 'CANCELLED')),
    legacy           boolean NOT NULL DEFAULT false,
    created_by       uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    created_at       timestamptz NOT NULL DEFAULT now(),
    paid_at          timestamptz,
    confirmed_by     uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    reference        text,
    closed_at        timestamptz,
    closed_by        uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    close_reason     text,
    CONSTRAINT payment_cycle_visit_fkey FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT,
    -- Lần thu mới (không legacy) luôn biết phương thức, người tạo, dấu hoá đơn.
    CONSTRAINT payment_cycle_moi_du_dau_vet CHECK (
        legacy OR (method IS NOT NULL AND created_by IS NOT NULL
                   AND bill_revision IS NOT NULL)),
    -- Đã thu: có lúc thu; lần thu mới còn phải có người xác nhận.
    CONSTRAINT payment_cycle_paid_co_xac_nhan CHECK (
        status NOT IN ('PAID', 'VOIDED')
        OR (paid_at IS NOT NULL AND (legacy OR confirmed_by IS NOT NULL))),
    -- Chuyển khoản / QR chỉ PAID khi có MÃ GIAO DỊCH đã xác minh.
    CONSTRAINT payment_cycle_dien_tu_co_ma CHECK (
        method NOT IN ('TRANSFER', 'QR')
        OR status NOT IN ('PAID', 'VOIDED')
        OR nullif(btrim(coalesce(reference, '')), '') IS NOT NULL),
    -- Huỷ phiếu / huỷ chờ xác minh: ai, lúc nào, vì sao.
    CONSTRAINT payment_cycle_dong_co_ly_do CHECK (
        status NOT IN ('VOIDED', 'CANCELLED')
        OR (closed_at IS NOT NULL AND closed_by IS NOT NULL
            AND char_length(btrim(coalesce(close_reason, ''))) BETWEEN 5 AND 500))
);

-- Một lần thu ĐANG SỐNG (chờ xác minh hoặc đã thu) cho mỗi (lượt, loại).
CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_cycle_mot_lan_song
    ON public.payment_cycle (clinic_id, visit_id, kind)
    WHERE status IN ('PENDING_VERIFICATION', 'PAID');
CREATE INDEX IF NOT EXISTS idx_payment_cycle_ngay
    ON public.payment_cycle (clinic_id, created_at DESC);

-- Chỉ chuyển trạng thái theo đúng đường; mọi cột đã ghi thì bất biến.
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
    THEN
        RAISE EXCEPTION 'payment_cycle: cột đã ghi không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_payment_cycle_guard ON public.payment_cycle;
CREATE TRIGGER trg_payment_cycle_guard
    BEFORE UPDATE OR DELETE ON public.payment_cycle
    FOR EACH ROW EXECUTE FUNCTION public.payment_cycle_guard();

-- Dữ liệu cũ: đúng các dòng `payment` hiện có, không thêm, không đoán.
DO $backfill_legacy$
BEGIN
    INSERT INTO public.payment_cycle (
        payment_cycle_id, clinic_id, visit_id, kind, payment_id, amount,
        bill_revision, method, status, legacy, created_by, created_at, paid_at,
        confirmed_by, closed_at, closed_by, close_reason
    )
    SELECT p.payment_cycle_id, p.clinic_id, p.visit_id, p.kind, p.id, p.amount,
           p.bill_revision, NULL, p.status, true, p.paid_by_staff_id,
           coalesce(p.paid_at, p.created_at), coalesce(p.paid_at, p.created_at),
           p.paid_by_staff_id, p.voided_at, p.voided_by_staff_id, p.void_reason
      FROM public.payment p
     WHERE p.amount IS NOT NULL AND p.amount > 0
       AND p.status IN ('PAID', 'VOIDED')
       AND EXISTS (SELECT 1 FROM public.visit v
                    WHERE v.visit_id = p.visit_id AND v.clinic_id = p.clinic_id)
    ON CONFLICT (payment_cycle_id) DO NOTHING;
END
$backfill_legacy$;

-- Ảnh chụp hoá đơn thuộc về LẦN THU, kể cả lần thu chờ xác minh (chưa có dòng
-- payment) → payment_id được rỗng, khoá theo payment_cycle.
ALTER TABLE public.payment_bill_line ALTER COLUMN payment_id DROP NOT NULL;
ALTER TABLE public.payment_bill_line DROP CONSTRAINT IF EXISTS payment_bill_line_cycle_fkey;
ALTER TABLE public.payment_bill_line ADD CONSTRAINT payment_bill_line_cycle_fkey
    FOREIGN KEY (payment_cycle_id) REFERENCES public.payment_cycle (payment_cycle_id)
    ON DELETE RESTRICT;

ALTER TABLE public.payment_cycle ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_cycle_select_own_clinic ON public.payment_cycle;
CREATE POLICY payment_cycle_select_own_clinic ON public.payment_cycle
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.payment_cycle TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.payment_cycle TO service_role;

COMMENT ON TABLE public.payment_cycle IS
    'Sổ các lần thu (contract tiền–thuốc CP2). Một dòng mỗi lần thu; payment là '
    'hình chiếu khoản hiện đã thu.';
