-- C.5 — Track patient's physical location during a visit.
--
-- The workflow kernel (W4) assigns work items to nodes, but the PATIENT is not
-- the work item. A patient can have three pending work items at three different
-- nodes while physically standing at only one.
--
-- This migration adds three columns to visit:
--   current_node_code  — which node the patient is currently at
--   current_node_since — when they arrived there
--   previous_node_code — where they came from (debug/audit)
--
-- A trigger on work_item keeps these columns in sync: when a work_item moves
-- to IN_PROGRESS, the visit's current_node_code becomes that item's node_code.
-- When all items are terminal, current_node_code is NULLed (patient left).

-- ---------------------------------------------------------------------------
-- 1. Columns
-- ---------------------------------------------------------------------------

ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS current_node_code text,
    ADD COLUMN IF NOT EXISTS current_node_since timestamptz,
    ADD COLUMN IF NOT EXISTS previous_node_code text;

COMMENT ON COLUMN public.visit.current_node_code IS
  'C.5: Node where the patient is physically present right now. '
  'Updated by trigger on work_item status changes. NULL = patient left.';

-- Index for the dispatch board: "which patients are at node X right now?"
CREATE INDEX IF NOT EXISTS idx_visit_current_node
    ON public.visit (clinic_id, current_node_code)
    WHERE current_node_code IS NOT NULL
      AND status IN ('OPEN', 'IN_PROGRESS');

-- ---------------------------------------------------------------------------
-- 2. Trigger function
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.update_visit_current_node()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_visit_id     uuid;
    v_clinic_id    uuid;
    v_active_node  text;
BEGIN
    -- Only care about status changes on items that belong to a visit.
    v_visit_id  := coalesce(NEW.visit_id, OLD.visit_id);
    v_clinic_id := coalesce(NEW.clinic_id, OLD.clinic_id);

    IF v_visit_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Find the most recently started IN_PROGRESS work item for this visit.
    -- That is where the patient is right now.
    SELECT w.node_code
      INTO v_active_node
      FROM public.work_item w
     WHERE w.visit_id = v_visit_id
       AND w.clinic_id = v_clinic_id
       AND w.status = 'IN_PROGRESS'
     ORDER BY w.started_at DESC NULLS LAST
     LIMIT 1;

    -- Update visit — only if the node actually changed (avoid noisy updates).
    UPDATE public.visit
       SET previous_node_code = current_node_code,
           current_node_code  = v_active_node,
           current_node_since = CASE
               WHEN v_active_node IS DISTINCT FROM current_node_code
               THEN now()
               ELSE current_node_since
           END,
           updated_at = now()
     WHERE visit_id = v_visit_id
       AND clinic_id = v_clinic_id
       AND current_node_code IS DISTINCT FROM v_active_node;

    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.update_visit_current_node() IS
  'C.5: Keeps visit.current_node_code in sync with the most recently '
  'started IN_PROGRESS work item. Fires on work_item INSERT/UPDATE.';

-- ---------------------------------------------------------------------------
-- 3. Trigger
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_work_item_update_visit_node ON public.work_item;

CREATE TRIGGER trg_work_item_update_visit_node
    AFTER INSERT OR UPDATE OF status ON public.work_item
    FOR EACH ROW
    EXECUTE FUNCTION public.update_visit_current_node();

-- ---------------------------------------------------------------------------
-- 4. Backfill existing visits (if any have IN_PROGRESS work items)
-- ---------------------------------------------------------------------------

UPDATE public.visit v
   SET current_node_code = sub.node_code,
       current_node_since = sub.started_at
  FROM (
      SELECT DISTINCT ON (w.visit_id)
             w.visit_id, w.clinic_id, w.node_code, w.started_at
        FROM public.work_item w
       WHERE w.status = 'IN_PROGRESS'
         AND w.visit_id IS NOT NULL
       ORDER BY w.visit_id, w.started_at DESC NULLS LAST
  ) sub
 WHERE v.visit_id = sub.visit_id
   AND v.clinic_id = sub.clinic_id
   AND v.current_node_code IS NULL;

-- ---------------------------------------------------------------------------
-- 5. Realtime publication for work_item tables
-- ---------------------------------------------------------------------------
-- The RealtimeRefresher in the dashboard subscribes to postgres_changes on
-- these tables. Without publication membership, no events fire.

-- `ALTER PUBLICATION ... ADD TABLE` KHÔNG có dạng IF NOT EXISTS: chạy lần hai
-- là lỗi "already member of publication". CI cố ý áp lại mọi migration từ
-- 30/07 (vì `db push` có retry, và diễn tập khôi phục phát lại cả chuỗi), nên
-- hai dòng trần ở đây làm cả bước đó đứt.
DO $realtime$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['work_item', 'work_item_event'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
             WHERE pubname = 'supabase_realtime'
               AND schemaname = 'public' AND tablename = t
        ) THEN
            EXECUTE format(
                'ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', t);
        END IF;
    END LOOP;
END
$realtime$;
