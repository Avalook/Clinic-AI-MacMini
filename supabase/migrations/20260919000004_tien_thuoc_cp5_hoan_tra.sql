-- Contract tiền–thuốc, CP5 (19/09/2026): HUỶ PHIẾU ≠ HOÀN TIỀN ≠ KHÁCH TRẢ THUỐC.
--
-- Thiết kế đã chốt với reviewer:
--   * Hoàn tiền (`payment_refund` + `payment_refund_line`) là tiền thật trả lại
--     khách, tham chiếu ĐÚNG dòng ảnh chụp hoá đơn đã thu (`payment_bill_line`).
--     Số tiền do DB tính = số lượng × đơn giá ảnh chụp; trình duyệt không quyết.
--     Hoàn được lần thu ĐÃ TỪNG thu (paid_at), kể cả lần thu sau đó bị huỷ
--     phiếu. Hoàn tiền KHÔNG đụng kho.
--   * Khách trả thuốc (`drug_return`) ghi nhận thuốc THẬT quay lại quầy, tham
--     chiếu DISPENSE gốc + lô gốc. Sổ kho ghi `RETURN_RECEIVED` (+ vật lý), nhưng
--     phần trả CHƯA có quyết định xử lý bị trừ khỏi `drug_batch_kha_dung()` —
--     không tự đem bán lại. Quyết định xử lý (bán lại / huỷ / cách ly) là HOLD
--     J1/J2: CP5 KHÔNG có lệnh ấy. Khách trả thuốc KHÔNG tự hoàn tiền.
--   * "Huỷ bán phần chưa giao" = `SALE_REVERSAL` đúng bằng `bán − đã xuất` của
--     phân lô, CHỈ khi có căn cứ tài chính: lần thu đã huỷ phiếu, hoặc đã hoàn
--     tiền (COMPLETED) đủ cho phần đó. Sau đó phân lô không xuất thêm được.
--
-- Chỉ THÊM. Chạy lại nhiều lần được.

-- ── Neo khoá ngoại ghép ──────────────────────────────────────────────────
DO $cp5_neo$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.payment_bill_line'::regclass
                      AND conname = 'uq_payment_bill_line_id_clinic_cycle') THEN
        ALTER TABLE public.payment_bill_line
            ADD CONSTRAINT uq_payment_bill_line_id_clinic_cycle
            UNIQUE (id, clinic_id, payment_cycle_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.inventory_txn'::regclass
                      AND conname = 'uq_inventory_txn_id_clinic_batch') THEN
        ALTER TABLE public.inventory_txn
            ADD CONSTRAINT uq_inventory_txn_id_clinic_batch
            UNIQUE (id, clinic_id, drug_batch_id);
    END IF;
END
$cp5_neo$;

-- ══ HOÀN TIỀN ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.payment_refund (
    refund_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('thuoc', 'dich_vu')),
    payment_cycle_id uuid NOT NULL,
    amount           numeric(14, 0) NOT NULL CHECK (amount > 0),
    status           text NOT NULL
        CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    method           text NOT NULL CHECK (method IN ('CASH', 'TRANSFER', 'QR')),
    reason           text NOT NULL CHECK (length(btrim(reason)) >= 5),
    reference        text,
    created_by       uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    created_at       timestamptz NOT NULL DEFAULT now(),
    completed_by     uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    completed_at     timestamptz,
    closed_by        uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    closed_at        timestamptz,
    closed_reason    text,
    CONSTRAINT payment_refund_cycle_fkey
        FOREIGN KEY (payment_cycle_id, clinic_id, visit_id)
        REFERENCES public.payment_cycle (payment_cycle_id, clinic_id, visit_id)
        ON DELETE RESTRICT,
    CONSTRAINT payment_refund_hoan_co_nguoi CHECK (
        (status = 'COMPLETED') = (completed_at IS NOT NULL AND completed_by IS NOT NULL)),
    -- Chuyển khoản / QR: hoàn xong phải có mã giao dịch (giống lúc thu).
    CONSTRAINT payment_refund_dien_tu_co_ma CHECK (
        status <> 'COMPLETED' OR method = 'CASH' OR reference IS NOT NULL),
    CONSTRAINT payment_refund_dong_co_ly_do CHECK (
        (status IN ('FAILED', 'CANCELLED'))
        = (closed_at IS NOT NULL AND closed_by IS NOT NULL AND closed_reason IS NOT NULL)),
    CONSTRAINT uq_payment_refund_id_clinic UNIQUE (refund_id, clinic_id)
);
CREATE INDEX IF NOT EXISTS idx_payment_refund_cycle
    ON public.payment_refund (clinic_id, payment_cycle_id);
CREATE INDEX IF NOT EXISTS idx_payment_refund_ngay
    ON public.payment_refund (clinic_id, created_at);

CREATE TABLE IF NOT EXISTS public.payment_refund_line (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id            uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    refund_id            uuid NOT NULL,
    payment_cycle_id     uuid NOT NULL,
    payment_bill_line_id uuid NOT NULL,
    quantity             numeric NOT NULL CHECK (quantity > 0),
    amount               numeric(14, 0) NOT NULL CHECK (amount > 0),
    created_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT payment_refund_line_refund_fkey FOREIGN KEY (refund_id, clinic_id)
        REFERENCES public.payment_refund (refund_id, clinic_id) ON DELETE RESTRICT,
    -- Dòng hoá đơn phải thuộc ĐÚNG lần thu của khoản hoàn, cùng phòng khám.
    CONSTRAINT payment_refund_line_bill_fkey
        FOREIGN KEY (payment_bill_line_id, clinic_id, payment_cycle_id)
        REFERENCES public.payment_bill_line (id, clinic_id, payment_cycle_id)
        ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_payment_refund_line_bill
    ON public.payment_refund_line (clinic_id, payment_bill_line_id);
CREATE INDEX IF NOT EXISTS idx_payment_refund_line_refund
    ON public.payment_refund_line (clinic_id, refund_id);

-- Khoản hoàn: chỉ trên lần thu đã từng thu; chỉ chuyển PENDING → một trạng thái
-- đóng; không sửa số tiền / lần thu; không xoá.
CREATE OR REPLACE FUNCTION public.payment_refund_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lan record;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'payment_refund không xoá — huỷ bằng trạng thái'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF TG_OP = 'INSERT' THEN
        SELECT kind, paid_at INTO lan FROM public.payment_cycle
         WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id
         FOR UPDATE;
        IF lan.paid_at IS NULL OR lan.kind IS DISTINCT FROM NEW.kind THEN
            RAISE EXCEPTION 'Hoàn tiền chỉ trên lần thu đã từng thu, đúng loại khoản'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.status NOT IN ('PENDING', 'COMPLETED') THEN
            RAISE EXCEPTION 'Khoản hoàn mới phải PENDING hoặc COMPLETED'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.refund_id <> OLD.refund_id OR NEW.clinic_id <> OLD.clinic_id
       OR NEW.visit_id <> OLD.visit_id OR NEW.kind <> OLD.kind
       OR NEW.payment_cycle_id <> OLD.payment_cycle_id OR NEW.amount <> OLD.amount
       OR NEW.method <> OLD.method OR NEW.reason <> OLD.reason
       OR NEW.created_by <> OLD.created_by OR NEW.created_at <> OLD.created_at
       OR NOT (OLD.status = 'PENDING'
               AND NEW.status IN ('COMPLETED', 'FAILED', 'CANCELLED')) THEN
        RAISE EXCEPTION 'payment_refund: chỉ PENDING → COMPLETED/FAILED/CANCELLED'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_payment_refund_guard ON public.payment_refund;
CREATE TRIGGER trg_payment_refund_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.payment_refund
    FOR EACH ROW EXECUTE FUNCTION public.payment_refund_guard();

-- Dòng hoàn: đúng dòng CLINIC của ảnh chụp, số tiền = số lượng × đơn giá ảnh
-- chụp, và LUỸ KẾ hoàn (khoản chưa FAILED/CANCELLED) trên dòng ấy không vượt
-- số lượng đã thu. Khoá lần thu trước khi cộng — hai khoản hoàn cùng lúc phải
-- xếp hàng, không chỉ nhờ ứng dụng.
CREATE OR REPLACE FUNCTION public.payment_refund_line_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    dong record;
    hoan record;
    da_hoan numeric;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment_refund_line chỉ thêm (%)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Khoá theo ĐÚNG thứ tự của service (review CP5 P1-B): lần thu → khoản
    -- hoàn, RỒI mới đọc trạng thái. Đọc trước khoá sau thì một lệnh ghi thẳng
    -- có thể thấy PENDING trong khi khoản hoàn vừa bị chuyển FAILED/CANCELLED.
    PERFORM 1 FROM public.payment_cycle
      WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id
      FOR UPDATE;
    SELECT payment_cycle_id, status INTO hoan FROM public.payment_refund
     WHERE refund_id = NEW.refund_id AND clinic_id = NEW.clinic_id
     FOR UPDATE;
    IF hoan.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id
       OR hoan.status NOT IN ('PENDING', 'COMPLETED') THEN
        RAISE EXCEPTION 'Dòng hoàn phải thuộc đúng lần thu của khoản hoàn còn mở'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT quantity, unit_price, billing_owner INTO dong
      FROM public.payment_bill_line
     WHERE id = NEW.payment_bill_line_id AND clinic_id = NEW.clinic_id;
    IF dong.billing_owner IS DISTINCT FROM 'CLINIC' OR dong.unit_price IS NULL THEN
        RAISE EXCEPTION 'Chỉ hoàn dòng phòng khám đã thu có giá'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.amount <> round(NEW.quantity * dong.unit_price) THEN
        RAISE EXCEPTION 'Số tiền hoàn phải = số lượng × đơn giá ảnh chụp'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT coalesce(sum(l.quantity), 0) INTO da_hoan
      FROM public.payment_refund_line l
      JOIN public.payment_refund r
        ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
     WHERE l.payment_bill_line_id = NEW.payment_bill_line_id
       AND l.clinic_id = NEW.clinic_id
       AND r.status IN ('PENDING', 'COMPLETED');
    IF da_hoan + NEW.quantity > dong.quantity THEN
        RAISE EXCEPTION 'Hoàn vượt số đã thu của dòng (% + % > %)',
            da_hoan, NEW.quantity, dong.quantity
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_payment_refund_line_guard ON public.payment_refund_line;
CREATE TRIGGER trg_payment_refund_line_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.payment_refund_line
    FOR EACH ROW EXECUTE FUNCTION public.payment_refund_line_guard();

-- Tiền hoàn ở đầu khoản = TỔNG các dòng, kiểm lúc commit (dòng thêm sau đầu).
CREATE OR REPLACE FUNCTION public.payment_refund_tong_khop()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    tong numeric;
BEGIN
    SELECT coalesce(sum(amount), 0) INTO tong FROM public.payment_refund_line
     WHERE refund_id = NEW.refund_id AND clinic_id = NEW.clinic_id;
    IF tong <> NEW.amount THEN
        RAISE EXCEPTION 'Khoản hoàn %: tiền đầu khoản % ≠ tổng dòng %',
            NEW.refund_id, NEW.amount, tong
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS trg_payment_refund_tong_khop ON public.payment_refund;
CREATE CONSTRAINT TRIGGER trg_payment_refund_tong_khop
    AFTER INSERT ON public.payment_refund
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.payment_refund_tong_khop();

-- Review CP5 P1-B: kiểm LẠI khi thêm dòng. Chỉ kiểm lúc chèn đầu khoản thì sau
-- khi khoản hoàn đã commit, một dòng chèn thêm làm tổng dòng ≠ đầu khoản mà
-- không ai chặn — sổ hoàn tiền tự lệch.
CREATE OR REPLACE FUNCTION public.payment_refund_line_tong_khop()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    dau numeric;
    tong numeric;
BEGIN
    SELECT amount INTO dau FROM public.payment_refund
     WHERE refund_id = NEW.refund_id AND clinic_id = NEW.clinic_id;
    SELECT coalesce(sum(amount), 0) INTO tong FROM public.payment_refund_line
     WHERE refund_id = NEW.refund_id AND clinic_id = NEW.clinic_id;
    IF tong IS DISTINCT FROM dau THEN
        RAISE EXCEPTION 'Khoản hoàn %: tiền đầu khoản % ≠ tổng dòng %',
            NEW.refund_id, dau, tong
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS trg_payment_refund_line_tong_khop ON public.payment_refund_line;
CREATE CONSTRAINT TRIGGER trg_payment_refund_line_tong_khop
    AFTER INSERT ON public.payment_refund_line
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.payment_refund_line_tong_khop();

-- ══ KHÁCH TRẢ THUỐC ════════════════════════════════════════════════════
-- Neo cho khoá ngoại ghép của phân lô.
DO $cp5_neo_pl$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription_allocation'::regclass
                      AND conname = 'uq_prescription_allocation_id_clinic') THEN
        ALTER TABLE public.prescription_allocation
            ADD CONSTRAINT uq_prescription_allocation_id_clinic UNIQUE (id, clinic_id);
    END IF;
END
$cp5_neo_pl$;

CREATE TABLE IF NOT EXISTS public.drug_return (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id                uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id                 uuid NOT NULL,
    prescription_id          uuid NOT NULL,
    original_dispense_txn_id uuid NOT NULL,
    allocation_id            uuid,
    drug_batch_id            uuid NOT NULL,
    returned_qty             numeric(12, 3) NOT NULL CHECK (returned_qty > 0),
    reason                   text NOT NULL CHECK (length(btrim(reason)) >= 3),
    returned_by              uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    returned_at              timestamptz NOT NULL DEFAULT now(),
    -- NULL = RETURN_RECEIVED: đã nhận lại, CHƯA quyết xử lý (HOLD J1/J2).
    disposition              text,
    disposition_by           uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    disposition_at           timestamptz,
    CONSTRAINT drug_return_visit_fkey FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT,
    CONSTRAINT drug_return_rx_fkey FOREIGN KEY (prescription_id, clinic_id)
        REFERENCES public.prescription (id, clinic_id) ON DELETE RESTRICT,
    -- DISPENSE gốc: cùng phòng khám, và lô trả = lô đã xuất.
    CONSTRAINT drug_return_dispense_fkey
        FOREIGN KEY (original_dispense_txn_id, clinic_id, drug_batch_id)
        REFERENCES public.inventory_txn (id, clinic_id, drug_batch_id) ON DELETE RESTRICT,
    CONSTRAINT drug_return_allocation_fkey FOREIGN KEY (allocation_id, clinic_id)
        REFERENCES public.prescription_allocation (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT drug_return_xu_ly_di_cung CHECK (
        (disposition IS NULL) = (disposition_by IS NULL)
        AND (disposition IS NULL) = (disposition_at IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_drug_return_dispense
    ON public.drug_return (clinic_id, original_dispense_txn_id);
CREATE INDEX IF NOT EXISTS idx_drug_return_lo_cho
    ON public.drug_return (clinic_id, drug_batch_id) WHERE disposition IS NULL;


CREATE OR REPLACE FUNCTION public.drug_return_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    xuat record;
    da_tra numeric;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        -- Quyết định xử lý thuốc trả là HOLD J1/J2 — CP5 không có lệnh nào sửa
        -- dòng này. Nới ở migration của quyết định ấy, không ở đây.
        RAISE EXCEPTION 'drug_return: chưa có quyết định xử lý (HOLD J1/J2) — không sửa/xoá (%)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO xuat FROM public.inventory_txn
     WHERE id = NEW.original_dispense_txn_id AND clinic_id = NEW.clinic_id
     FOR UPDATE;
    IF xuat.txn_type IS DISTINCT FROM 'DISPENSE'
       OR xuat.ref_id IS DISTINCT FROM NEW.prescription_id
       OR xuat.allocation_id IS DISTINCT FROM NEW.allocation_id
       OR NEW.disposition IS NOT NULL
       -- Dòng đơn phải thuộc ĐÚNG lượt khai trên lần trả (lineage/audit).
       OR NOT EXISTS (SELECT 1 FROM public.prescription r
                       WHERE r.id = NEW.prescription_id AND r.clinic_id = NEW.clinic_id
                         AND r.visit_id = NEW.visit_id) THEN
        RAISE EXCEPTION 'Khách trả thuốc phải trỏ đúng DISPENSE gốc của dòng đơn'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT coalesce(sum(returned_qty), 0) INTO da_tra FROM public.drug_return
     WHERE original_dispense_txn_id = NEW.original_dispense_txn_id
       AND clinic_id = NEW.clinic_id;
    IF da_tra + NEW.returned_qty > -xuat.quantity THEN
        RAISE EXCEPTION 'Trả vượt số đã xuất (% + % > %)',
            da_tra, NEW.returned_qty, -xuat.quantity
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_drug_return_guard ON public.drug_return;
CREATE TRIGGER trg_drug_return_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.drug_return
    FOR EACH ROW EXECUTE FUNCTION public.drug_return_guard();

-- Mỗi lần trả có ĐÚNG MỘT dòng RETURN_RECEIVED — kiểm lúc commit.
CREATE OR REPLACE FUNCTION public.drug_return_co_dong_kho()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.inventory_txn t
                    WHERE t.txn_type = 'RETURN_RECEIVED' AND t.ref_type = 'drug_return'
                      AND t.ref_id = NEW.id AND t.clinic_id = NEW.clinic_id) THEN
        RAISE EXCEPTION 'drug_return % thiếu dòng RETURN_RECEIVED trong sổ kho', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS trg_drug_return_co_dong_kho ON public.drug_return;
CREATE CONSTRAINT TRIGGER trg_drug_return_co_dong_kho
    AFTER INSERT ON public.drug_return
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.drug_return_co_dong_kho();

-- ══ SỔ KHO ══════════════════════════════════════════════════════════════
ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_type_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_type_check CHECK (
    txn_type IN ('RECEIVE', 'DISPENSE', 'ADJUST', 'DISCARD', 'SALE', 'SALE_REVERSAL',
                 'RETURN_RECEIVED'));

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_qty_sign_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_qty_sign_check CHECK (
    (txn_type IN ('RECEIVE', 'SALE_REVERSAL', 'RETURN_RECEIVED') AND quantity > 0)
    OR (txn_type IN ('DISPENSE', 'DISCARD', 'SALE') AND quantity < 0)
    OR (txn_type = 'ADJUST' AND quantity <> 0));

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_dong_ban_co_nguon;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_dong_ban_co_nguon CHECK (
    CASE
        WHEN txn_type IN ('SALE', 'SALE_REVERSAL') THEN
            payment_cycle_id IS NOT NULL AND allocation_id IS NOT NULL
            AND ref_type = 'payment_cycle' AND ref_id = payment_cycle_id
            AND (reverses_txn_id IS NOT NULL) = (txn_type = 'SALE_REVERSAL')
        WHEN txn_type = 'DISPENSE' THEN
            (payment_cycle_id IS NULL) = (allocation_id IS NULL)
            AND reverses_txn_id IS NULL
        WHEN txn_type = 'RETURN_RECEIVED' THEN
            ref_type = 'drug_return' AND ref_id IS NOT NULL
            AND payment_cycle_id IS NULL AND allocation_id IS NULL
            AND reverses_txn_id IS NULL
        ELSE
            payment_cycle_id IS NULL AND allocation_id IS NULL
            AND reverses_txn_id IS NULL
    END);

CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_txn_tra_mot_dong
    ON public.inventory_txn (ref_id) WHERE txn_type = 'RETURN_RECEIVED';

CREATE OR REPLACE FUNCTION public.inventory_txn_ban_hop_le()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    pl record;
    goc record;
    tra record;
    trang_thai text;
    da_xuat numeric;
    da_hoan numeric;
    da_dao numeric;
BEGIN
    IF NEW.txn_type = 'RETURN_RECEIVED' THEN
        -- Dòng kho của một lần khách trả: đúng lô, đúng số lượng của lần trả.
        SELECT * INTO tra FROM public.drug_return
         WHERE id = NEW.ref_id AND clinic_id = NEW.clinic_id;
        IF tra.drug_batch_id IS DISTINCT FROM NEW.drug_batch_id
           OR tra.returned_qty IS DISTINCT FROM NEW.quantity THEN
            RAISE EXCEPTION 'RETURN_RECEIVED không khớp lần khách trả thuốc'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.txn_type NOT IN ('SALE', 'SALE_REVERSAL')
       AND NOT (NEW.txn_type = 'DISPENSE' AND NEW.allocation_id IS NOT NULL) THEN
        RETURN NEW;
    END IF;
    SELECT * INTO pl FROM public.prescription_allocation
     WHERE id = NEW.allocation_id AND clinic_id = NEW.clinic_id;
    SELECT status INTO trang_thai FROM public.payment_cycle
     WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id;

    IF NEW.txn_type = 'SALE' THEN
        -- Bán TRỌN phân lô, chỉ khi lần thu đã PAID và phân lô còn hiệu lực.
        IF trang_thai IS DISTINCT FROM 'PAID' OR pl.released_at IS NOT NULL
           OR NEW.quantity <> -pl.quantity THEN
            RAISE EXCEPTION 'SALE không khớp phân lô/lần thu đã thu'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.txn_type = 'SALE_REVERSAL' THEN
        -- CP5: đảo ĐÚNG phần chưa giao = bán − đã xuất (tính từ sổ), mỗi SALE
        -- một lần (uq_inventory_txn_dao_mot_lan), và phải có căn cứ tài chính:
        -- lần thu đã huỷ phiếu, HOẶC tổng đã đảo trên dòng đơn ≤ số đã hoàn
        -- xong (COMPLETED) của đúng dòng ảnh chụp hoá đơn ấy.
        PERFORM 1 FROM public.prescription_allocation
          WHERE id = NEW.allocation_id AND clinic_id = NEW.clinic_id FOR UPDATE;
        SELECT * INTO goc FROM public.inventory_txn WHERE id = NEW.reverses_txn_id;
        SELECT coalesce(-sum(d.quantity), 0) INTO da_xuat FROM public.inventory_txn d
         WHERE d.txn_type = 'DISPENSE' AND d.allocation_id = NEW.allocation_id
           AND d.clinic_id = NEW.clinic_id;
        IF goc.txn_type IS DISTINCT FROM 'SALE'
           OR goc.allocation_id IS DISTINCT FROM NEW.allocation_id
           OR goc.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id
           OR goc.drug_batch_id IS DISTINCT FROM NEW.drug_batch_id
           OR goc.clinic_id IS DISTINCT FROM NEW.clinic_id
           OR NEW.quantity <> -goc.quantity - da_xuat THEN
            RAISE EXCEPTION 'SALE_REVERSAL không khớp phần chưa giao của dòng bán gốc'
                USING ERRCODE = 'check_violation';
        END IF;
        IF trang_thai IS DISTINCT FROM 'VOIDED' THEN
            SELECT coalesce(sum(l.quantity), 0) INTO da_hoan
              FROM public.payment_refund_line l
              JOIN public.payment_refund r
                ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
              JOIN public.payment_bill_line b
                ON b.id = l.payment_bill_line_id AND b.clinic_id = l.clinic_id
             WHERE l.clinic_id = NEW.clinic_id
               AND l.payment_cycle_id = NEW.payment_cycle_id
               AND r.status = 'COMPLETED'
               AND b.source_type = 'prescription'
               AND b.source_id = pl.prescription_id::text;
            SELECT coalesce(sum(t.quantity), 0) INTO da_dao
              FROM public.inventory_txn t
              JOIN public.prescription_allocation a
                ON a.id = t.allocation_id AND a.clinic_id = t.clinic_id
             WHERE t.txn_type = 'SALE_REVERSAL' AND t.clinic_id = NEW.clinic_id
               AND t.payment_cycle_id = NEW.payment_cycle_id
               AND a.prescription_id = pl.prescription_id;
            IF da_dao + NEW.quantity > da_hoan THEN
                RAISE EXCEPTION 'Huỷ phần chưa giao cần căn cứ: huỷ phiếu, hoặc đã hoàn tiền đủ (% đã hoàn, cần %)',
                    da_hoan, da_dao + NEW.quantity
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    ELSE
        -- DISPENSE theo phân lô (review CP3 P1-B): lưới cuối ở DB, không chỉ
        -- trong Python — lần thu đang PAID, có SALE chưa đảo, và TỔNG đã xuất
        -- của phân lô (tính từ chính sổ, không từ handed_over_qty) không vượt
        -- số đã phân. Khoá dòng phân lô để hai lệnh ghi thẳng cùng lúc cũng
        -- phải xếp hàng.
        PERFORM 1 FROM public.prescription_allocation
          WHERE id = NEW.allocation_id AND clinic_id = NEW.clinic_id FOR UPDATE;
        IF trang_thai IS DISTINCT FROM 'PAID'
           OR NOT EXISTS (SELECT 1 FROM public.inventory_txn s
                           WHERE s.txn_type = 'SALE'
                             AND s.allocation_id = NEW.allocation_id
                             AND s.payment_cycle_id = NEW.payment_cycle_id
                             AND NOT EXISTS (
                                 SELECT 1 FROM public.inventory_txn r
                                  WHERE r.txn_type = 'SALE_REVERSAL'
                                    AND r.reverses_txn_id = s.id)) THEN
            RAISE EXCEPTION 'DISPENSE theo phân lô: lần thu chưa PAID hoặc chưa bán (đã đảo bán)'
                USING ERRCODE = 'check_violation';
        END IF;
        IF coalesce((SELECT -sum(d.quantity) FROM public.inventory_txn d
                      WHERE d.txn_type = 'DISPENSE'
                        AND d.allocation_id = NEW.allocation_id
                        AND d.clinic_id = NEW.clinic_id), 0)
           - NEW.quantity > pl.quantity THEN
            RAISE EXCEPTION 'DISPENSE theo phân lô: vượt số đã phân (%)', pl.quantity
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Khả dụng kỹ thuật: trừ thêm phần khách trả CHƯA có quyết định xử lý.
CREATE OR REPLACE FUNCTION public.drug_batch_kha_dung(p_clinic uuid, p_batch uuid)
RETURNS numeric LANGUAGE sql STABLE AS $$
    SELECT b.quantity_on_hand
         - coalesce((
               SELECT sum(a.quantity)
                 FROM public.prescription_allocation a
                 JOIN public.payment_cycle c
                   ON c.payment_cycle_id = a.payment_cycle_id
                  AND c.clinic_id = a.clinic_id
                WHERE a.clinic_id = p_clinic AND a.drug_batch_id = p_batch
                  AND a.released_at IS NULL
                  AND (c.status = 'PENDING_VERIFICATION'
                       OR (c.status = 'PAID' AND NOT EXISTS (
                               SELECT 1 FROM public.inventory_txn s
                                WHERE s.txn_type = 'SALE'
                                  AND s.allocation_id = a.id
                                  AND s.payment_cycle_id = a.payment_cycle_id)))), 0)
         - coalesce((
               SELECT sum(greatest(ban.da_ban - a.handed_over_qty, 0))
                 FROM public.prescription_allocation a
                 CROSS JOIN LATERAL (
                     SELECT coalesce(-sum(t.quantity), 0) AS da_ban
                       FROM public.inventory_txn t
                      WHERE t.allocation_id = a.id AND t.clinic_id = a.clinic_id
                        AND t.txn_type IN ('SALE', 'SALE_REVERSAL')) ban
                WHERE a.clinic_id = p_clinic AND a.drug_batch_id = p_batch), 0)
         - coalesce((
               SELECT sum(r.returned_qty) FROM public.drug_return r
                WHERE r.clinic_id = p_clinic AND r.drug_batch_id = p_batch
                  AND r.disposition IS NULL), 0)
      FROM public.drug_batch b
     WHERE b.id = p_batch AND b.clinic_id = p_clinic
$$;

-- ── Quyền ────────────────────────────────────────────────────────────────
ALTER TABLE public.payment_refund ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_refund_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.drug_return ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_refund_select_own_clinic ON public.payment_refund;
CREATE POLICY payment_refund_select_own_clinic ON public.payment_refund
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
DROP POLICY IF EXISTS payment_refund_line_select_own_clinic ON public.payment_refund_line;
CREATE POLICY payment_refund_line_select_own_clinic ON public.payment_refund_line
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
DROP POLICY IF EXISTS drug_return_select_own_clinic ON public.drug_return;
CREATE POLICY drug_return_select_own_clinic ON public.drug_return
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.payment_refund, public.payment_refund_line, public.drug_return
    TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.payment_refund TO service_role;
GRANT SELECT, INSERT ON public.payment_refund_line, public.drug_return TO service_role;
