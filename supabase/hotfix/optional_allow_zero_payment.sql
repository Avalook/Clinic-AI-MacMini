-- OPTIONAL, NOT APPLIED. Only run this if the clinic says a zero-amount payment
-- is legitimate — a free visit, or one fully covered by insurance.
--
-- Production holds five payments with amount = 0 that the target schema's
-- payment_positive_amount CHECK rejects, blocking the data migration. There are
-- two honest answers and this is one of them; the other is to treat those rows
-- as test data and drop them explicitly (PAYMENT_POLICY=drop in
-- scripts/rehearse-data-migration.sh, which prints every row it omits).
--
-- Against this option: all five rows have paid_by_staff_id AND paid_by_text
-- NULL, so nobody is recorded as having taken the money, and production has no
-- prices at all. A real zero-amount payment still has a cashier.
--
-- For it: if the clinic genuinely records free visits as PAID/0, then the CHECK
-- is simply wrong and would keep rejecting them after cutover too.

ALTER TABLE public.payment DROP CONSTRAINT IF EXISTS payment_positive_amount_chk;
ALTER TABLE public.payment ADD CONSTRAINT payment_positive_amount_chk
    CHECK (amount >= 0);

COMMENT ON CONSTRAINT payment_positive_amount_chk ON public.payment IS
  'Relaxed from > 0 to >= 0: the clinic records fully-covered visits as a '
  'zero-amount payment.';
