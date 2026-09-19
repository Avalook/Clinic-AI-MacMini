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
-- Dữ liệu cũ (review CP2 #2): lần thu cũ lấy từ HAI nguồn có bằng chứng — dòng
-- `payment` hiện có, và sự kiện `payment.recorded` / `payment.voided` đủ dữ liệu
-- (payment_cycle_id, visit, kind, amount — đều do code cũ ghi). Đánh `legacy`,
-- phương thức NULL. Sự kiện thiếu dữ liệu, lượt không còn, hoặc mâu thuẫn với
-- lần thu đang sống thì BỎ QUA và ĐẾM — không đoán. Chạy lại được.

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
    -- Xác minh tiền THẬT đã nhận nhưng hoá đơn hiện tại đã khác ảnh chụp của lần
    -- thu (vd bảng giá đổi trong lúc chờ): vẫn ghi đã thu, đánh dấu cần đối soát
    -- (review CP2 #3). Chỉ đặt được đúng lúc chờ → đã thu.
    can_doi_soat     boolean NOT NULL DEFAULT false,
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
        OR (closed_at IS NOT NULL
            AND (legacy OR (closed_by IS NOT NULL
                 AND char_length(btrim(coalesce(close_reason, ''))) BETWEEN 5 AND 500))))
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
       OR (NEW.can_doi_soat IS DISTINCT FROM OLD.can_doi_soat
           AND NOT (OLD.status = 'PENDING_VERIFICATION' AND NEW.status = 'PAID'))
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

-- Dữ liệu cũ → sổ các lần thu. Hàm để chạy lại được và test gọi được.
CREATE OR REPLACE FUNCTION public.payment_cycle_backfill_legacy()
RETURNS TABLE (tu_payment integer, tu_su_kien integer, su_kien_bo_qua integer)
LANGUAGE plpgsql AS $fn$
DECLARE
    a integer;
    b integer;
    uuid_re constant text :=
        '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';
BEGIN
    -- 1. Dòng `payment` hiện có (trạng thái mới nhất của lần thu hiện hành).
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
    GET DIAGNOSTICS a = ROW_COUNT;

    -- 2. Lần thu cũ chỉ còn trong sổ sự kiện (dòng payment đã bị tái dùng).
    WITH ghi AS (
        SELECT DISTINCT ON (e.payload ->> 'payment_cycle_id')
               e.clinic_id,
               (e.payload ->> 'payment_cycle_id')::uuid AS cid,
               (e.payload ->> 'visit_id')::uuid         AS vid,
               e.payload ->> 'kind'                     AS kind,
               (e.payload ->> 'amount')::bigint         AS amount,
               e.occurred_at,
               e.metadata ->> 'clinic_staff_id'         AS ai
          FROM public.event_log e
         WHERE e.event_type = 'payment.recorded'
           AND e.payload ->> 'payment_cycle_id' ~ uuid_re
           AND e.payload ->> 'visit_id' ~ uuid_re
           AND e.payload ->> 'kind' IN ('thuoc', 'dich_vu')
           AND e.payload ->> 'amount' ~ '^[0-9]+$'
           AND (e.payload ->> 'amount')::bigint > 0
         ORDER BY e.payload ->> 'payment_cycle_id', e.occurred_at
    ), huy AS (
        SELECT DISTINCT ON (e.payload ->> 'payment_cycle_id')
               (e.payload ->> 'payment_cycle_id')::uuid AS cid,
               e.occurred_at,
               e.payload ->> 'void_reason'              AS ly_do,
               e.metadata ->> 'clinic_staff_id'         AS ai
          FROM public.event_log e
         WHERE e.event_type = 'payment.voided'
           AND e.payload ->> 'payment_cycle_id' ~ uuid_re
         ORDER BY e.payload ->> 'payment_cycle_id', e.occurred_at
    )
    INSERT INTO public.payment_cycle (
        payment_cycle_id, clinic_id, visit_id, kind, amount, method, status,
        legacy, created_by, created_at, paid_at, confirmed_by,
        closed_at, closed_by, close_reason
    )
    SELECT g.cid, g.clinic_id, g.vid, g.kind, g.amount, NULL,
           CASE WHEN h.cid IS NULL THEN 'PAID' ELSE 'VOIDED' END,
           true,
           (SELECT s.id FROM public.staff s WHERE s.id::text = g.ai),
           g.occurred_at, g.occurred_at,
           (SELECT s.id FROM public.staff s WHERE s.id::text = g.ai),
           h.occurred_at,
           (SELECT s.id FROM public.staff s WHERE s.id::text = h.ai),
           h.ly_do
      FROM ghi g
      LEFT JOIN huy h ON h.cid = g.cid
     WHERE EXISTS (SELECT 1 FROM public.visit v
                    WHERE v.visit_id = g.vid AND v.clinic_id = g.clinic_id)
       AND NOT EXISTS (SELECT 1 FROM public.payment_cycle c
                        WHERE c.payment_cycle_id = g.cid)
     ORDER BY g.occurred_at
    -- Hai lần thu cũ cùng "đang sống" cho một (lượt, loại) là mâu thuẫn trong sổ
    -- — không chọn hộ, bỏ qua và đếm.
    ON CONFLICT (clinic_id, visit_id, kind)
        WHERE status IN ('PENDING_VERIFICATION', 'PAID') DO NOTHING;
    GET DIAGNOSTICS b = ROW_COUNT;

    RETURN QUERY
    SELECT a, b,
           (SELECT count(DISTINCT e.payload ->> 'payment_cycle_id')::integer
              FROM public.event_log e
             WHERE e.event_type = 'payment.recorded'
               AND NOT EXISTS (
                   SELECT 1 FROM public.payment_cycle c
                    WHERE c.payment_cycle_id::text = e.payload ->> 'payment_cycle_id'));
END
$fn$;

DO $backfill_legacy$
DECLARE
    kq record;
BEGIN
    SELECT * INTO kq FROM public.payment_cycle_backfill_legacy();
    RAISE NOTICE 'payment_cycle legacy: % từ payment, % từ sự kiện, % sự kiện bỏ qua',
        kq.tu_payment, kq.tu_su_kien, kq.su_kien_bo_qua;
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
