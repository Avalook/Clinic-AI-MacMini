-- Contract tiền–thuốc, CP6 bước 2 (20/09/2026): migration nền.
--
-- 1. Khoá ngoại GHÉP cùng phòng khám cho hai quan hệ tài chính còn nối bằng
--    UUID đơn (nợ từ review CP2):
--      payment_cycle(payment_id, clinic_id)           → payment(id, clinic_id)
--      payment_bill_line(payment_cycle_id, clinic_id) → payment_cycle(payment_cycle_id, clinic_id)
--    Backend chạy service_role (bỏ qua RLS) nên ràng buộc phải nằm ở DB. Thêm
--    NOT VALID rồi VALIDATE: dữ liệu lệch phòng khám thì migration DỪNG, không
--    sửa hộ.
-- 2. `payment_cycle.doi_soat_ly_do` — mã NGUYÊN NHÂN cần đối soát, là lịch sử:
--      HOA_DON_DOI   hoá đơn lúc xác minh khác ảnh chụp của lần thu
--      CHUA_GHI_BAN  đã nhận tiền nhưng không ghi bán được thuốc
--    Bất biến: can_doi_soat = (có ít nhất một mã). Chỉ hình thành cùng lúc
--    PENDING_VERIFICATION → PAID, sau đó không đổi. KHÔNG có "đã đối soát xong"
--    ở đây: lần thu đã từng cần đối soát là sự thật lịch sử.
--
-- Dữ liệu đã chạy CP2–CP5: dựng lại mã từ sự kiện; còn dòng cần đối soát mà
-- không dựng được thì migration DỪNG và báo số lượng — không gán mã đoán.
-- Chạy lại nhiều lần được.

-- ── 1. Khoá ngoại ghép ────────────────────────────────────────────────────
DO $cp6_neo$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.payment'::regclass
                      AND conname = 'uq_payment_id_clinic') THEN
        ALTER TABLE public.payment
            ADD CONSTRAINT uq_payment_id_clinic UNIQUE (id, clinic_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.payment_cycle'::regclass
                      AND conname = 'uq_payment_cycle_id_clinic') THEN
        ALTER TABLE public.payment_cycle
            ADD CONSTRAINT uq_payment_cycle_id_clinic UNIQUE (payment_cycle_id, clinic_id);
    END IF;
END
$cp6_neo$;

-- payment_id rỗng (lần thu đang chờ, chưa có dòng payment) → khoá ghép chưa ép
-- (MATCH SIMPLE) cho tới khi có payment_id; lúc ấy phải cùng phòng khám.
ALTER TABLE public.payment_cycle DROP CONSTRAINT IF EXISTS payment_cycle_payment_id_fkey;
ALTER TABLE public.payment_cycle DROP CONSTRAINT IF EXISTS payment_cycle_payment_same_clinic_fkey;
ALTER TABLE public.payment_cycle ADD CONSTRAINT payment_cycle_payment_same_clinic_fkey
    FOREIGN KEY (payment_id, clinic_id) REFERENCES public.payment (id, clinic_id)
    ON DELETE RESTRICT NOT VALID;
ALTER TABLE public.payment_cycle VALIDATE CONSTRAINT payment_cycle_payment_same_clinic_fkey;

ALTER TABLE public.payment_bill_line DROP CONSTRAINT IF EXISTS payment_bill_line_cycle_fkey;
ALTER TABLE public.payment_bill_line DROP CONSTRAINT IF EXISTS payment_bill_line_cycle_same_clinic_fkey;
ALTER TABLE public.payment_bill_line ADD CONSTRAINT payment_bill_line_cycle_same_clinic_fkey
    FOREIGN KEY (payment_cycle_id, clinic_id)
    REFERENCES public.payment_cycle (payment_cycle_id, clinic_id)
    ON DELETE RESTRICT NOT VALID;
ALTER TABLE public.payment_bill_line VALIDATE CONSTRAINT payment_bill_line_cycle_same_clinic_fkey;

-- ── 2. Mã nguyên nhân cần đối soát ───────────────────────────────────────
ALTER TABLE public.payment_cycle
    ADD COLUMN IF NOT EXISTS doi_soat_ly_do text[] NOT NULL DEFAULT '{}';
COMMENT ON COLUMN public.payment_cycle.doi_soat_ly_do IS
    'Mã nguyên nhân cần đối soát (lịch sử, không xoá): HOA_DON_DOI | '
    'CHUA_GHI_BAN. can_doi_soat = có ít nhất một mã. Chỉ hình thành lúc '
    'PENDING_VERIFICATION → PAID.';

-- Dựng lại mã cho dòng đã cần đối soát trước CP6, CHỈ từ sự kiện có thật:
--   payment.reconciliation_needed → HOA_DON_DOI
--   payment.sale_not_applied      → CHUA_GHI_BAN
-- Còn dòng nào không dựng được thì DỪNG kèm số lượng (không gán mã đoán). Gọi
-- khi chốt `payment_cycle_guard` đang tắt — hàm này không tự tắt chốt.
CREATE OR REPLACE FUNCTION public.payment_cycle_dung_lai_ly_do_doi_soat()
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    so_dung integer;
    con_thieu integer;
BEGIN
    UPDATE public.payment_cycle c
       SET doi_soat_ly_do = ARRAY(
               SELECT x.m FROM (VALUES
                   ('HOA_DON_DOI', 'payment.reconciliation_needed'),
                   ('CHUA_GHI_BAN', 'payment.sale_not_applied')) AS x(m, ev)
                WHERE EXISTS (SELECT 1 FROM public.event_log e
                               WHERE e.clinic_id = c.clinic_id
                                 AND e.event_type = x.ev
                                 AND e.payload ->> 'payment_cycle_id'
                                     = c.payment_cycle_id::text)
                ORDER BY x.m)
     WHERE c.can_doi_soat AND cardinality(c.doi_soat_ly_do) = 0;
    GET DIAGNOSTICS so_dung = ROW_COUNT;
    SELECT count(*) INTO con_thieu FROM public.payment_cycle
     WHERE can_doi_soat AND cardinality(doi_soat_ly_do) = 0;
    IF con_thieu > 0 THEN
        RAISE EXCEPTION
            'CP6: % lần thu cần đối soát nhưng không dựng được nguyên nhân từ sự kiện — dừng, không đoán',
            con_thieu
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN so_dung;
END $$;

-- Tắt chốt "cột đã ghi không sửa được" ĐÚNG quanh bước dựng lại (chốt hiện
-- hành từ chối mọi UPDATE giữ nguyên trạng thái), bật lại ngay sau. Hàm dừng
-- thì cả migration dừng, chốt không bị bỏ tắt.
ALTER TABLE public.payment_cycle DISABLE TRIGGER trg_payment_cycle_guard;
DO $cp6_dung_lai$
DECLARE
    so integer;
BEGIN
    so := public.payment_cycle_dung_lai_ly_do_doi_soat();
    RAISE NOTICE 'CP6: dựng lại nguyên nhân đối soát cho % lần thu', so;
END
$cp6_dung_lai$;
ALTER TABLE public.payment_cycle ENABLE TRIGGER trg_payment_cycle_guard;

ALTER TABLE public.payment_cycle DROP CONSTRAINT IF EXISTS payment_cycle_doi_soat_ma_hop_le;
ALTER TABLE public.payment_cycle ADD CONSTRAINT payment_cycle_doi_soat_ma_hop_le CHECK (
    doi_soat_ly_do <@ ARRAY['HOA_DON_DOI', 'CHUA_GHI_BAN']::text[]
    AND array_position(doi_soat_ly_do, NULL) IS NULL);
ALTER TABLE public.payment_cycle DROP CONSTRAINT IF EXISTS payment_cycle_doi_soat_khop_co;
ALTER TABLE public.payment_cycle ADD CONSTRAINT payment_cycle_doi_soat_khop_co CHECK (
    can_doi_soat = (cardinality(doi_soat_ly_do) > 0));

-- ── 3. Chốt lần thu: mã nguyên nhân bất biến ngoài PENDING → PAID ────────
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
       -- Cờ và mã nguyên nhân đối soát chỉ hình thành cùng lúc chờ → đã thu.
       OR ((NEW.can_doi_soat IS DISTINCT FROM OLD.can_doi_soat
            OR NEW.doi_soat_ly_do IS DISTINCT FROM OLD.doi_soat_ly_do)
           AND NOT (OLD.status = 'PENDING_VERIFICATION' AND NEW.status = 'PAID'))
    THEN
        RAISE EXCEPTION 'payment_cycle: cột đã ghi không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
