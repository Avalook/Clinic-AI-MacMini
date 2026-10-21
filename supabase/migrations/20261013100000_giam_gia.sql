-- Giảm giá tại quầy thu (13/10/2026).
--
-- Giảm bằng số tiền HOẶC %, kèm lý do bắt buộc, người thực hiện.
-- 0đ sau giảm vẫn thanh toán, in phiếu, giao thuốc.
-- Phiếu cũ đọc như không giảm giá (discount_amount = 0, original_amount = NULL).
--
-- ── 1. Gỡ CHECK amount > 0 trên payment_cycle ──────────────────────────────
-- Tên CHECK tự sinh khi viết inline: payment_cycle_amount_check.
-- Tìm constraint thật bằng tên cột + loại, gỡ cả hai tên có thể.
DO $$
BEGIN
    -- Inline CHECK sinh ra có thể mang tên bảng_cột_check hoặc payment_cycle_check*
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE table_schema = 'public' AND table_name = 'payment_cycle'
           AND constraint_name = 'payment_cycle_amount_check'
    ) THEN
        ALTER TABLE public.payment_cycle DROP CONSTRAINT payment_cycle_amount_check;
    END IF;

    -- Nếu Postgres đặt tên theo convention khác
    IF EXISTS (
        SELECT 1 FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
         WHERE n.nspname = 'public' AND t.relname = 'payment_cycle'
           AND c.contype = 'c'
           AND pg_get_constraintdef(c.oid) LIKE '%amount > 0%'
    ) THEN
        EXECUTE (
            SELECT format('ALTER TABLE public.payment_cycle DROP CONSTRAINT %I',
                          c.conname)
              FROM pg_constraint c
              JOIN pg_class t ON t.oid = c.conrelid
              JOIN pg_namespace n ON n.oid = t.relnamespace
             WHERE n.nspname = 'public' AND t.relname = 'payment_cycle'
               AND c.contype = 'c'
               AND pg_get_constraintdef(c.oid) LIKE '%amount > 0%'
             LIMIT 1
        );
    END IF;
END $$;

ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_amount_gte0 CHECK (amount >= 0);

-- ── 2. Gỡ CHECK amount > 0 trên payment (hình chiếu) ───────────────────────
ALTER TABLE public.payment
    DROP CONSTRAINT IF EXISTS payment_positive_amount_check;
ALTER TABLE public.payment
    ADD CONSTRAINT payment_positive_amount_check
    CHECK (
        status = 'VOIDED'
        OR (amount IS NOT NULL AND amount >= 0)
    ) NOT VALID;

-- ── 3. Thêm cột giảm giá vào payment_cycle ─────────────────────────────────
ALTER TABLE public.payment_cycle
    ADD COLUMN IF NOT EXISTS discount_type    text,
    ADD COLUMN IF NOT EXISTS discount_value   numeric(14, 2),
    ADD COLUMN IF NOT EXISTS discount_amount  integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS discount_reason  text,
    ADD COLUMN IF NOT EXISTS discount_by      uuid REFERENCES public.staff(id)
                                              ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS original_amount  integer;

-- Ràng buộc: loại + giá trị đi đôi
ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_discount_pair CHECK (
        (discount_type IS NULL AND discount_value IS NULL)
        OR (discount_type IN ('AMOUNT', 'PERCENT')
            AND discount_value IS NOT NULL
            AND discount_value >= 0));

-- % trong 0–100
ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_discount_pct CHECK (
        discount_type IS DISTINCT FROM 'PERCENT'
        OR (discount_value >= 0 AND discount_value <= 100));

-- Tiền giảm không vượt tổng gốc, không âm
ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_discount_bound CHECK (
        discount_amount >= 0
        AND (original_amount IS NULL
             OR discount_amount <= original_amount));

-- Có giảm phải có lý do (5–500 ký tự) và người áp dụng
ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_discount_reason CHECK (
        discount_amount = 0
        OR (char_length(btrim(coalesce(discount_reason, ''))) BETWEEN 5 AND 500
            AND discount_by IS NOT NULL));

-- amount = original_amount - discount_amount (khi có original_amount)
ALTER TABLE public.payment_cycle
    ADD CONSTRAINT payment_cycle_discount_math CHECK (
        original_amount IS NULL
        OR amount = original_amount - discount_amount);

COMMENT ON COLUMN public.payment_cycle.discount_type IS
    'AMOUNT = giảm bằng số tiền, PERCENT = giảm bằng %';
COMMENT ON COLUMN public.payment_cycle.discount_value IS
    'Giá trị giảm: số tiền (VND) hoặc % (0–100)';
COMMENT ON COLUMN public.payment_cycle.discount_amount IS
    'Tiền giảm thực tế (VND), máy chủ tính. 0 = không giảm.';
COMMENT ON COLUMN public.payment_cycle.discount_reason IS
    'Lý do giảm giá / miễn phí (bắt buộc khi discount_amount > 0)';
COMMENT ON COLUMN public.payment_cycle.discount_by IS
    'Nhân viên áp dụng giảm giá (server-verified identity)';
COMMENT ON COLUMN public.payment_cycle.original_amount IS
    'Tổng gốc trước giảm. NULL = phiếu cũ trước tính năng giảm giá.';

-- ── 4. Phân bổ giảm trên payment_bill_line ──────────────────────────────────
ALTER TABLE public.payment_bill_line
    ADD COLUMN IF NOT EXISTS discount_allocated integer NOT NULL DEFAULT 0;

ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_discount_bound CHECK (
        discount_allocated >= 0);

-- Phần giảm không vượt giá dòng
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_discount_le_line CHECK (
        discount_allocated <= coalesce(line_total, 0));

COMMENT ON COLUMN public.payment_bill_line.discount_allocated IS
    'Phần giảm giá phân bổ cho dòng này (VND). Hoàn tiền tính thực thu = line_total - discount_allocated.';

-- ── 5. Cập nhật trigger guard ────────────────────────────────────────────────
-- Thêm cột giảm giá vào danh sách "đã ghi không sửa được".
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
        -- Giảm giá: cột đã ghi lúc INSERT, không sửa được.
       OR NEW.discount_type IS DISTINCT FROM OLD.discount_type
       OR NEW.discount_value IS DISTINCT FROM OLD.discount_value
       OR NEW.discount_amount IS DISTINCT FROM OLD.discount_amount
       OR NEW.discount_reason IS DISTINCT FROM OLD.discount_reason
       OR NEW.discount_by IS DISTINCT FROM OLD.discount_by
       OR NEW.original_amount IS DISTINCT FROM OLD.original_amount
    THEN
        RAISE EXCEPTION 'payment_cycle: cột đã ghi không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- Cập nhật trigger guard payment_refund_line để cho phép hoàn tiền theo thực thu khi có giảm giá.
CREATE OR REPLACE FUNCTION public.payment_refund_line_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    dong record;
    hoan record;
    da_hoan_sl numeric;
    da_hoan_tien bigint;
    thuc_thu bigint;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment_refund_line chỉ thêm (%)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;
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
    SELECT quantity, unit_price, line_total, coalesce(discount_allocated, 0) AS discount_allocated, billing_owner
      INTO dong
      FROM public.payment_bill_line
     WHERE id = NEW.payment_bill_line_id AND clinic_id = NEW.clinic_id;
    IF dong.billing_owner IS DISTINCT FROM 'CLINIC' OR dong.unit_price IS NULL THEN
        RAISE EXCEPTION 'Chỉ hoàn dòng phòng khám đã thu có giá'
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT coalesce(sum(l.quantity), 0), coalesce(sum(l.amount), 0)
      INTO da_hoan_sl, da_hoan_tien
      FROM public.payment_refund_line l
      JOIN public.payment_refund r
        ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
     WHERE l.payment_bill_line_id = NEW.payment_bill_line_id
       AND l.clinic_id = NEW.clinic_id
       AND r.status IN ('PENDING', 'COMPLETED');

    IF da_hoan_sl + NEW.quantity > dong.quantity THEN
        RAISE EXCEPTION 'Hoàn vượt số đã thu của dòng (% + % > %)',
            da_hoan_sl, NEW.quantity, dong.quantity
            USING ERRCODE = 'check_violation';
    END IF;

    thuc_thu := coalesce(dong.line_total, round(dong.quantity * dong.unit_price)) - dong.discount_allocated;
    IF thuc_thu < 0 THEN
        thuc_thu := 0;
    END IF;

    IF dong.discount_allocated = 0 THEN
        IF NEW.amount <> round(NEW.quantity * dong.unit_price) THEN
            RAISE EXCEPTION 'Số tiền hoàn phải = số lượng × đơn giá ảnh chụp'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        -- Dòng có giảm giá: hoàn theo thực thu, luỹ kế tiền không vượt thực thu
        IF da_hoan_tien + NEW.amount > thuc_thu THEN
            RAISE EXCEPTION 'Hoàn vượt số tiền thực thu của dòng (% + % > %)',
                da_hoan_tien, NEW.amount, thuc_thu
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NEW;
END $$;

-- ── 6. Index cho báo cáo giảm giá ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_payment_cycle_giam_gia
    ON public.payment_cycle (clinic_id, created_at DESC)
    WHERE discount_amount > 0;

-- ── 7. Grant service_role ───────────────────────────────────────────────────
-- Cột mới thuộc bảng đã được grant; không cần thêm.
