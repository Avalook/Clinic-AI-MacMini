-- Payments are financial records: voiding reverses them, it never erases them.
--
-- The backend previously used DELETE for "undo payment". That destroyed who
-- collected what and made a POS reversal impossible to reconcile after the
-- fact. Keep the original row, mark the reversal, and make hard deletion fail
-- with the same guard already used for visits and clinical records.

ALTER TABLE public.payment
    ADD COLUMN IF NOT EXISTS voided_at timestamptz,
    ADD COLUMN IF NOT EXISTS voided_by_staff_id uuid,
    ADD COLUMN IF NOT EXISTS void_reason text,
    ADD COLUMN IF NOT EXISTS payment_cycle_id uuid;

-- One payment row may be paid -> voided -> paid again. Each paid cycle needs a
-- different external reference so the POS receives a new invoice after the
-- preceding one was voided, while the stable payment id remains the ledger id.
UPDATE public.payment
   SET payment_cycle_id = gen_random_uuid()
 WHERE payment_cycle_id IS NULL;
ALTER TABLE public.payment
    ALTER COLUMN payment_cycle_id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN payment_cycle_id SET NOT NULL;
ALTER TABLE public.payment
    DROP CONSTRAINT IF EXISTS uq_payment_clinic_cycle;
ALTER TABLE public.payment
    ADD CONSTRAINT uq_payment_clinic_cycle
    UNIQUE (clinic_id, payment_cycle_id);

ALTER TABLE public.payment
    DROP CONSTRAINT IF EXISTS payment_status_check;
ALTER TABLE public.payment
    ADD CONSTRAINT payment_status_check
    CHECK (status = ANY (ARRAY['PAID'::text, 'VOIDED'::text]));

ALTER TABLE public.payment
    DROP CONSTRAINT IF EXISTS payment_positive_amount_check;
-- NOT VALID lets the migration land even if a historical deployment already
-- contains a NULL/zero payment. PostgreSQL still enforces it for every new or
-- updated row; legacy cleanup can be reviewed separately without inventing a
-- financial amount during deployment.
ALTER TABLE public.payment
    ADD CONSTRAINT payment_positive_amount_check
    CHECK (
        status = 'VOIDED'
        OR (amount IS NOT NULL AND amount > 0)
    ) NOT VALID;

ALTER TABLE public.payment
    DROP CONSTRAINT IF EXISTS payment_void_metadata_check;
ALTER TABLE public.payment
    ADD CONSTRAINT payment_void_metadata_check
    CHECK (
        (status = 'PAID'
            AND voided_at IS NULL
            AND voided_by_staff_id IS NULL
            AND void_reason IS NULL)
        OR
        (status = 'VOIDED'
            AND voided_at IS NOT NULL
            AND voided_by_staff_id IS NOT NULL
            AND void_reason IS NOT NULL
            AND char_length(btrim(void_reason)) BETWEEN 5 AND 500)
    ) NOT VALID;

ALTER TABLE public.payment
    DROP CONSTRAINT IF EXISTS payment_voided_by_staff_id_fkey;
ALTER TABLE public.payment
    ADD CONSTRAINT payment_voided_by_staff_id_fkey
    FOREIGN KEY (voided_by_staff_id) REFERENCES public.staff(id)
    ON DELETE RESTRICT NOT VALID;

DROP TRIGGER IF EXISTS trg_payment_no_delete ON public.payment;
CREATE TRIGGER trg_payment_no_delete
    BEFORE DELETE ON public.payment
    FOR EACH ROW EXECUTE FUNCTION public.prevent_hard_delete();

DROP TRIGGER IF EXISTS trg_payment_no_truncate ON public.payment;
CREATE TRIGGER trg_payment_no_truncate
    BEFORE TRUNCATE ON public.payment
    FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_hard_delete();

-- Existing dashboard reads infer "paid" from the presence of a row and do not
-- request status. Hide reversals from authenticated/PostgREST reads while the
-- owner/service-role backend retains the full ledger.
DROP POLICY IF EXISTS payment_select_own_clinic ON public.payment;
CREATE POLICY payment_select_own_clinic
    ON public.payment
    FOR SELECT
    TO authenticated
    USING (
        status = 'PAID'
        AND clinic_id IN (SELECT public.current_clinic_ids())
    );

COMMENT ON COLUMN public.payment.voided_at IS
    'When this payment was reversed. The payment row is retained for audit.';
COMMENT ON COLUMN public.payment.voided_by_staff_id IS
    'Verified staff identity that reversed this payment.';
COMMENT ON COLUMN public.payment.void_reason IS
    'Required human-entered reason for reversing this payment (5-500 chars).';
COMMENT ON COLUMN public.payment.payment_cycle_id IS
    'External invoice id for the current paid/void cycle; rotated on re-payment.';
