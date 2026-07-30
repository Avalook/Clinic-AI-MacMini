-- Regression assertions for 20260730000016_payment_audit.sql.

BEGIN;

DO $structure$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'payment'
           AND column_name = 'voided_at'
    ) OR NOT EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'payment'
           AND column_name = 'voided_by_staff_id'
    ) OR NOT EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'payment'
           AND column_name = 'void_reason'
    ) OR NOT EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'payment'
           AND column_name = 'payment_cycle_id'
    ) THEN
        RAISE EXCEPTION 'payment soft-void audit columns are missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_trigger
         WHERE tgrelid = 'public.payment'::regclass
           AND tgname = 'trg_payment_no_delete'
           AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'payment hard-delete guard is missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'payment'
           AND policyname = 'payment_select_own_clinic'
           AND qual LIKE '%status%PAID%'
    ) THEN
        RAISE EXCEPTION 'authenticated reads do not hide VOIDED payments';
    END IF;
END
$structure$;

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES (
    'd6000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'PAY-AUDIT',
    'Cơ sở payment audit'
);

INSERT INTO public.service_type (id, clinic_id, code, name)
VALUES (
    'd7000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'PAY-AUDIT',
    'Dịch vụ payment audit'
);

INSERT INTO public.staff (id, full_name, primary_department)
VALUES (
    'd5000000-0000-4000-8000-000000000001',
    'Thu ngân audit',
    'CASHIER'
);

INSERT INTO public.patient (
    clinic_patient_id, clinic_id, patient_code, full_name, location_id
)
VALUES (
    'd2000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'BN-PAY-AUDIT',
    'Bệnh nhân payment audit',
    'd6000000-0000-4000-8000-000000000001'
);

INSERT INTO public.appointment (
    id, clinic_id, clinic_patient_id, location_id, service_type_id,
    slot_start, slot_end, status
)
VALUES (
    'd3000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'd2000000-0000-4000-8000-000000000001',
    'd6000000-0000-4000-8000-000000000001',
    'd7000000-0000-4000-8000-000000000001',
    '2026-07-30 08:00:00+07',
    '2026-07-30 08:30:00+07',
    'COMPLETED'
);

INSERT INTO public.visit (
    visit_id, clinic_id, clinic_patient_id, appointment_id, status
)
VALUES (
    'd4000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'd2000000-0000-4000-8000-000000000001',
    'd3000000-0000-4000-8000-000000000001',
    'IN_PROGRESS'
);

INSERT INTO public.payment (
    id, clinic_id, visit_id, clinic_patient_id, kind, status, amount,
    paid_by_staff_id
)
VALUES (
    'd9000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'd4000000-0000-4000-8000-000000000001',
    'd2000000-0000-4000-8000-000000000001',
    'dich_vu',
    'PAID',
    150000,
    'd5000000-0000-4000-8000-000000000001'
);

UPDATE public.payment
   SET status = 'VOIDED',
       voided_at = now(),
       voided_by_staff_id = 'd5000000-0000-4000-8000-000000000001',
       void_reason = 'Khách đổi phương thức thanh toán'
 WHERE id = 'd9000000-0000-4000-8000-000000000001';

DO $soft_void$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM public.payment
         WHERE id = 'd9000000-0000-4000-8000-000000000001'
           AND status = 'VOIDED'
           AND voided_at IS NOT NULL
           AND voided_by_staff_id =
               'd5000000-0000-4000-8000-000000000001'
           AND void_reason = 'Khách đổi phương thức thanh toán'
    ) THEN
        RAISE EXCEPTION 'payment reversal did not retain its audit fields';
    END IF;
END
$soft_void$;

DO $new_cycle_after_repayment$
DECLARE
    old_cycle uuid;
    new_cycle uuid;
BEGIN
    SELECT payment_cycle_id INTO old_cycle
      FROM public.payment
     WHERE id = 'd9000000-0000-4000-8000-000000000001';

    INSERT INTO public.payment (
        clinic_id, visit_id, clinic_patient_id, kind, status, amount,
        paid_by_staff_id, paid_at, updated_at
    )
    VALUES (
        'a0000000-0000-4000-8000-000000000001',
        'd4000000-0000-4000-8000-000000000001',
        'd2000000-0000-4000-8000-000000000001',
        'dich_vu', 'PAID', 150000,
        'd5000000-0000-4000-8000-000000000001',
        now(), now()
    )
    ON CONFLICT (visit_id, kind) DO UPDATE SET
        amount = EXCLUDED.amount,
        status = 'PAID',
        paid_by_staff_id = EXCLUDED.paid_by_staff_id,
        paid_at = now(),
        payment_cycle_id = gen_random_uuid(),
        voided_at = NULL,
        voided_by_staff_id = NULL,
        void_reason = NULL,
        updated_at = now()
    WHERE payment.status = 'VOIDED'
    RETURNING payment_cycle_id INTO new_cycle;

    IF new_cycle = old_cycle THEN
        RAISE EXCEPTION 're-payment reused the voided POS invoice cycle';
    END IF;

    UPDATE public.payment
       SET status = 'VOIDED',
           voided_at = now(),
           voided_by_staff_id = 'd5000000-0000-4000-8000-000000000001',
           void_reason = 'Giao dịch kiểm thử bị hoàn tác'
     WHERE id = 'd9000000-0000-4000-8000-000000000001';
END
$new_cycle_after_repayment$;

DO $positive_amount$
BEGIN
    BEGIN
        UPDATE public.payment
           SET status = 'PAID',
               voided_at = NULL,
               voided_by_staff_id = NULL,
               amount = 0
         WHERE id = 'd9000000-0000-4000-8000-000000000001';
        RAISE EXCEPTION 'zero payment amount was accepted';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    BEGIN
        UPDATE public.payment
           SET status = 'PAID',
               voided_at = NULL,
               voided_by_staff_id = NULL,
               amount = NULL
         WHERE id = 'd9000000-0000-4000-8000-000000000001';
        RAISE EXCEPTION 'NULL payment amount was accepted';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;
END
$positive_amount$;

-- Historical deployments may already contain a NULL amount. Such a row must
-- still be reversible; keeping it PAID is forbidden, changing it to VOIDED is
-- the safe cleanup path.
ALTER TABLE public.payment DROP CONSTRAINT payment_positive_amount_check;
UPDATE public.payment
   SET status = 'PAID',
       voided_at = NULL,
       voided_by_staff_id = NULL,
       void_reason = NULL,
       amount = NULL
 WHERE id = 'd9000000-0000-4000-8000-000000000001';
ALTER TABLE public.payment
    ADD CONSTRAINT payment_positive_amount_check
    CHECK (
        status = 'VOIDED'
        OR (amount IS NOT NULL AND amount > 0)
    ) NOT VALID;
UPDATE public.payment
   SET status = 'VOIDED',
       voided_at = now(),
       voided_by_staff_id = 'd5000000-0000-4000-8000-000000000001',
       void_reason = 'Hoàn tác dữ liệu cũ sai số tiền'
 WHERE id = 'd9000000-0000-4000-8000-000000000001';

DO $void_metadata$
BEGIN
    BEGIN
        UPDATE public.payment
           SET voided_at = NULL
         WHERE id = 'd9000000-0000-4000-8000-000000000001';
        RAISE EXCEPTION 'VOIDED payment without void timestamp was accepted';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;
END
$void_metadata$;

DO $void_reason_required$
BEGIN
    BEGIN
        UPDATE public.payment
           SET void_reason = NULL
         WHERE id = 'd9000000-0000-4000-8000-000000000001';
        RAISE EXCEPTION 'VOIDED payment without a reason was accepted';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;
END
$void_reason_required$;

DO $no_delete$
BEGIN
    BEGIN
        DELETE FROM public.payment
         WHERE id = 'd9000000-0000-4000-8000-000000000001';
        RAISE EXCEPTION 'payment hard delete was accepted';
    EXCEPTION
        WHEN insufficient_privilege THEN NULL;
    END;
END
$no_delete$;

ROLLBACK;
