-- One unresolved lab result must have at most one open doctor-review task.
--
-- The graph can be retried by HTTP clients, workers, or after a timeout where
-- the caller never saw the first successful response. Application-side
-- "check then insert" cannot close that race; the partial unique index is the
-- database arbiter. Historical duplicates are retained for audit and marked
-- CANCELLED rather than deleted.

WITH ranked_open_reviews AS (
    SELECT task_id,
           row_number() OVER (
               PARTITION BY clinic_id, source_id
               ORDER BY created_at, task_id
           ) AS duplicate_number
      FROM public.staff_task
     WHERE task_type = 'LAB_REVIEW'
       AND source_type = 'LAB_RESULT'
       AND source_id IS NOT NULL
       AND status IN ('PENDING', 'IN_PROGRESS')
)
UPDATE public.staff_task AS task
   SET status = 'CANCELLED',
       completed_at = COALESCE(task.completed_at, now()),
       updated_at = now(),
       description = concat_ws(
           E'\n',
           NULLIF(task.description, ''),
           '[migration 20260730000018] duplicate open LAB_REVIEW cancelled'
       )
  FROM ranked_open_reviews AS ranked
 WHERE task.task_id = ranked.task_id
   AND ranked.duplicate_number > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_task_open_lab_review
    ON public.staff_task (clinic_id, source_id)
    WHERE task_type = 'LAB_REVIEW'
      AND source_type = 'LAB_RESULT'
      AND source_id IS NOT NULL
      AND status IN ('PENDING', 'IN_PROGRESS');

COMMENT ON INDEX public.uq_staff_task_open_lab_review IS
    'Race-safe idempotency: one PENDING/IN_PROGRESS LAB_REVIEW per lab result and clinic.';

