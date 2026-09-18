-- Refresh live workflow boards when committed clinical/queue state changes.
-- Existing notify_row_change emits only {t: table, c: clinic_id}; readers then
-- fetch through authenticated, tenant-scoped API routes. No chart text or IDs
-- are sent over the notification channel. All tables below have clinic_id.
DO $workflow_notifications$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'encounter_flow', 'vital_measurement', 'consultation',
        'consultation_note', 'service_order', 'queue_entry',
        'review_round', 'round_requirement'
    ] LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS %I ON public.%I',
            'trg_notify_' || table_name, table_name
        );
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.notify_row_change()',
            'trg_notify_' || table_name, table_name
        );
    END LOOP;
END
$workflow_notifications$;
