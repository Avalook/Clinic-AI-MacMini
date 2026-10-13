-- Giảm giá tại quầy thu — theo TỔNG hoá đơn (Tuyền chốt 09/10 + 13/10/2026).
--
-- Giảm bằng số tiền HOẶC %, người thu tiền bấm, lý do chữ tự do bắt buộc, ghi ai.
-- Giảm gắn thẳng vào LẦN THU (không có bảng giảm giá riêng): "hoàn tác" chính là
-- "Hoàn tác lần thu" có sẵn → giảm lại → thu lại. Phiếu cũ đọc như không giảm
-- (discount_amount = 0, các cột giảm còn lại NULL).
--
-- Hai điều cố ý:
--   * `payment_bill_line.line_total` là số SAU giảm. Mọi chỗ đang cộng line_total
--     làm "số đã thu" (sổ sửa chỉ định, tiền thừa, hoàn tác dịch vụ…) tự đúng,
--     không phải sửa từng nơi. Phần giảm của dòng nằm ở `discount_allocated`.
--   * Lần thu 0đ CHỈ tồn tại khi có giảm giá (kèm lý do + người giảm). Mọi lần
--     thu 0đ khác vẫn bị DB chặn như trước. Dòng/dịch vụ/thuốc giá 0đ trong hệ
--     thống không đổi: tổng hoá đơn 0đ không giảm vẫn đi đường cũ (chốt 0đ).

-- ── 1. Cột giảm giá trên sổ các lần thu ───────────────────────────────────
ALTER TABLE public.payment_cycle
    ADD COLUMN IF NOT EXISTS discount_type   text,
    ADD COLUMN IF NOT EXISTS discount_value  numeric(14, 2),
    ADD COLUMN IF NOT EXISTS discount_amount bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS discount_reason text,
    ADD COLUMN IF NOT EXISTS discount_by     uuid
        REFERENCES public.staff (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS original_amount bigint;

COMMENT ON COLUMN public.payment_cycle.discount_type IS
    'AMOUNT = giảm bằng số tiền, PERCENT = giảm bằng %. NULL = không giảm.';
COMMENT ON COLUMN public.payment_cycle.discount_value IS
    'Giá trị người thu nhập: số tiền (đồng) hoặc % (0–100].';
COMMENT ON COLUMN public.payment_cycle.discount_amount IS
    'Tiền giảm thực tế (đồng), máy chủ tính, làm tròn 1đ. 0 = không giảm.';
COMMENT ON COLUMN public.payment_cycle.discount_reason IS
    'Lý do giảm — chữ tự do, bắt buộc khi có giảm. Không ép độ dài ở DB.';
COMMENT ON COLUMN public.payment_cycle.discount_by IS
    'Nhân viên bấm giảm (danh tính máy chủ xác thực).';
COMMENT ON COLUMN public.payment_cycle.original_amount IS
    'Tổng hoá đơn TRƯỚC giảm. NULL = lần thu không giảm (kể cả mọi lần thu cũ).';

-- Một CHECK nói trọn luật: hoặc không giảm gì, hoặc giảm đủ bộ.
ALTER TABLE public.payment_cycle
    DROP CONSTRAINT IF EXISTS payment_cycle_giam_gia_khop;
ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_giam_gia_khop CHECK (
        (discount_amount = 0
            AND discount_type IS NULL AND discount_value IS NULL
            AND discount_reason IS NULL AND discount_by IS NULL
            AND original_amount IS NULL)
        OR
        (discount_amount > 0
            AND discount_type IN ('AMOUNT', 'PERCENT')
            AND discount_value > 0
            AND (discount_type <> 'PERCENT' OR discount_value <= 100)
            AND btrim(coalesce(discount_reason, '')) <> ''
            AND discount_by IS NOT NULL
            AND original_amount IS NOT NULL
            AND discount_amount <= original_amount
            AND amount = original_amount - discount_amount));

-- ── 2. Cho phép lần thu 0đ — chỉ khi có giảm giá ──────────────────────────
-- CHECK `amount > 0` khai inline nên tên do Postgres đặt: tìm theo định nghĩa.
DO $$
DECLARE
    ten text;
BEGIN
    FOR ten IN
        SELECT c.conname
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
         WHERE n.nspname = 'public' AND t.relname = 'payment_cycle'
           AND c.contype = 'c'
           AND regexp_replace(pg_get_constraintdef(c.oid), '[()\s]', '', 'g')
               = 'CHECKamount>0'
    LOOP
        EXECUTE format('ALTER TABLE public.payment_cycle DROP CONSTRAINT %I', ten);
    END LOOP;
END $$;

ALTER TABLE public.payment_cycle
    DROP CONSTRAINT IF EXISTS payment_cycle_amount_duong_hoac_giam_het;
ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_amount_duong_hoac_giam_het CHECK (
        amount > 0 OR (amount = 0 AND discount_amount > 0));

-- Hình chiếu `payment` (một dòng mỗi lần thu): 0đ chỉ ghi cùng một lần thu có
-- giảm — chính lần thu đó bị CHECK ở trên ép. NOT VALID như bản gốc (dòng lịch
-- sử không bị quét lại; mọi dòng mới/sửa vẫn bị kiểm).
ALTER TABLE public.payment
    DROP CONSTRAINT IF EXISTS payment_positive_amount_check;
ALTER TABLE public.payment
    ADD CONSTRAINT payment_positive_amount_check CHECK (
        status = 'VOIDED' OR (amount IS NOT NULL AND amount >= 0)) NOT VALID;

-- ── 3. Ảnh chụp từng dòng: phần giảm đã phân bổ ───────────────────────────
ALTER TABLE public.payment_bill_line
    ADD COLUMN IF NOT EXISTS discount_allocated numeric(14, 0) NOT NULL DEFAULT 0;

-- Dòng có giảm: số SAU giảm + phần giảm = đơn giá × số lượng (ảnh chụp).
ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_giam_khop;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_giam_khop CHECK (
        discount_allocated >= 0
        AND (discount_allocated = 0
             OR (unit_price IS NOT NULL AND line_total IS NOT NULL
                 AND billing_owner = 'CLINIC'
                 AND line_total + discount_allocated
                     = round(quantity * unit_price))));

COMMENT ON COLUMN public.payment_bill_line.discount_allocated IS
    'Phần giảm giá chia cho dòng này (đồng). line_total đã là số SAU giảm.';

-- ── 4. Sổ lần thu: cột giảm giá ghi một lần, không sửa ─────────────────────
-- Nguyên văn bản mới nhất (20260920000001 · CP6) + 6 cột giảm giá.
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

-- ── 5. Hoàn tiền dòng có giảm: tới số đã thu thật, không hơn ───────────────
-- Nguyên văn bản gốc (20260919000004 · CP5); chỉ đổi nhánh kiểm số tiền:
--   * dòng không giảm: như cũ (= số lượng × đơn giá ảnh chụp);
--   * dòng có giảm: luỹ kế tiền hoàn của dòng ≤ line_total (đã sau giảm).
CREATE OR REPLACE FUNCTION public.payment_refund_line_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    dong record;
    hoan record;
    da_hoan numeric;
    da_hoan_tien numeric;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment_refund_line chỉ thêm (%)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Khoá theo ĐÚNG thứ tự của service (review CP5 P1-B): lần thu → khoản
    -- hoàn, RỒI mới đọc trạng thái.
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
    SELECT quantity, unit_price, line_total, discount_allocated, billing_owner
      INTO dong
      FROM public.payment_bill_line
     WHERE id = NEW.payment_bill_line_id AND clinic_id = NEW.clinic_id;
    IF dong.billing_owner IS DISTINCT FROM 'CLINIC' OR dong.unit_price IS NULL THEN
        RAISE EXCEPTION 'Chỉ hoàn dòng phòng khám đã thu có giá'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT coalesce(sum(l.quantity), 0), coalesce(sum(l.amount), 0)
      INTO da_hoan, da_hoan_tien
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
    IF dong.discount_allocated = 0 THEN
        IF NEW.amount <> round(NEW.quantity * dong.unit_price) THEN
            RAISE EXCEPTION 'Số tiền hoàn phải = số lượng × đơn giá ảnh chụp'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF da_hoan_tien + NEW.amount > dong.line_total THEN
        RAISE EXCEPTION 'Hoàn vượt số đã thu của dòng sau giảm giá (% + % > %)',
            da_hoan_tien, NEW.amount, dong.line_total
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- ── 6. Báo cáo giảm giá ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_payment_cycle_giam_gia
    ON public.payment_cycle (clinic_id, created_at DESC)
    WHERE discount_amount > 0;
