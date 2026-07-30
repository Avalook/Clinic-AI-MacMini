-- Regression assertions for 20260730000018_lab_review_idempotency.sql.

BEGIN;

DO $index_exists$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_index i
          JOIN pg_class c ON c.oid = i.indexrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname = 'uq_staff_task_open_lab_review'
           AND i.indisunique
           AND i.indpred IS NOT NULL
    ) THEN
        RAISE EXCEPTION
            'open LAB_REVIEW partial unique index is missing';
    END IF;
END
$index_exists$;

DO $retry_converges$
DECLARE
    first_task uuid;
    retried_task uuid;
    open_count integer;
BEGIN
    INSERT INTO public.staff_task (
        clinic_id, task_type, priority, source_type, source_id, title
    )
    VALUES (
        'a0000000-0000-4000-8000-000000000001',
        'LAB_REVIEW',
        'URGENT',
        'LAB_RESULT',
        'e8100000-0000-4000-8000-000000000001',
        'Review result'
    )
    ON CONFLICT (clinic_id, source_id)
        WHERE task_type = 'LAB_REVIEW'
          AND source_type = 'LAB_RESULT'
          AND source_id IS NOT NULL
          AND status IN ('PENDING', 'IN_PROGRESS')
    DO UPDATE SET updated_at = staff_task.updated_at
    RETURNING task_id INTO first_task;

    INSERT INTO public.staff_task (
        clinic_id, task_type, priority, source_type, source_id, title
    )
    VALUES (
        'a0000000-0000-4000-8000-000000000001',
        'LAB_REVIEW',
        'URGENT',
        'LAB_RESULT',
        'e8100000-0000-4000-8000-000000000001',
        'Review result retry'
    )
    ON CONFLICT (clinic_id, source_id)
        WHERE task_type = 'LAB_REVIEW'
          AND source_type = 'LAB_RESULT'
          AND source_id IS NOT NULL
          AND status IN ('PENDING', 'IN_PROGRESS')
    DO UPDATE SET updated_at = staff_task.updated_at
    RETURNING task_id INTO retried_task;

    SELECT count(*)
      INTO open_count
      FROM public.staff_task
     WHERE clinic_id = 'a0000000-0000-4000-8000-000000000001'
       AND source_id = 'e8100000-0000-4000-8000-000000000001'
       AND task_type = 'LAB_REVIEW'
       AND source_type = 'LAB_RESULT'
       AND status IN ('PENDING', 'IN_PROGRESS');

    IF first_task <> retried_task OR open_count <> 1 THEN
        RAISE EXCEPTION
            'LAB_REVIEW retry did not converge (first %, retry %, count %)',
            first_task, retried_task, open_count;
    END IF;
END
$retry_converges$;

DO $raw_race_loser_is_rejected$
BEGIN
    BEGIN
        INSERT INTO public.staff_task (
            clinic_id, task_type, priority, source_type, source_id, title
        )
        VALUES (
            'a0000000-0000-4000-8000-000000000001',
            'LAB_REVIEW',
            'URGENT',
            'LAB_RESULT',
            'e8100000-0000-4000-8000-000000000001',
            'Unprotected concurrent insert'
        );
        RAISE EXCEPTION 'duplicate open LAB_REVIEW was accepted';
    EXCEPTION
        WHEN unique_violation THEN NULL;
    END;
END
$raw_race_loser_is_rejected$;

ROLLBACK;

