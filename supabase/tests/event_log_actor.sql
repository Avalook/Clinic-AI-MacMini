-- Assertions for 20260802000003_event_log_actor.sql.
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/event_log_actor.sql

BEGIN;

DO $shape$
DECLARE
    is_nullable boolean;
    has_default boolean;
    delete_action "char";
    index_count integer;
    orphan_count integer;
BEGIN
    SELECT NOT a.attnotnull, a.atthasdef
      INTO is_nullable, has_default
      FROM pg_attribute a
     WHERE a.attrelid = 'public.event_log'::regclass
       AND a.attname = 'actor_staff_id'
       AND NOT a.attisdropped;

    IF is_nullable IS NULL THEN
        RAISE EXCEPTION 'event_log.actor_staff_id is missing';
    END IF;

    -- Deliberately nullable. Relay, worker and outside channels (Zalo, walk-in)
    -- produce events with nobody behind them; NOT NULL would force those rows to
    -- point at an invented staff member, i.e. lie in the audit table itself.
    IF NOT is_nullable THEN
        RAISE EXCEPTION 'actor_staff_id must stay nullable — NULL means system';
    END IF;

    IF has_default THEN
        RAISE EXCEPTION 'actor_staff_id must not have a default';
    END IF;

    SELECT c.confdeltype
      INTO delete_action
      FROM pg_constraint c
     WHERE c.conrelid = 'public.event_log'::regclass
       AND c.contype = 'f'
       AND c.confrelid = 'public.staff'::regclass
       AND c.conkey = ARRAY[
           (SELECT attnum FROM pg_attribute
             WHERE attrelid = 'public.event_log'::regclass
               AND attname = 'actor_staff_id')
       ]::smallint[];

    IF delete_action IS NULL THEN
        RAISE EXCEPTION 'actor_staff_id has no foreign key to staff';
    END IF;

    -- 'r' = RESTRICT. SET NULL would let a hard delete quietly erase who acted.
    IF delete_action <> 'r' THEN
        RAISE EXCEPTION 'actor_staff_id FK must be ON DELETE RESTRICT, found %',
            delete_action;
    END IF;

    -- "What did this person do here, most recent first" — and clinic_id leads,
    -- so the index also satisfies the tenant invariant on index shape.
    SELECT count(*)
      INTO index_count
      FROM pg_index i
      JOIN pg_attribute lead
        ON lead.attrelid = i.indrelid AND lead.attnum = i.indkey[0]
      JOIN pg_attribute second
        ON second.attrelid = i.indrelid AND second.attnum = i.indkey[1]
     WHERE i.indrelid = 'public.event_log'::regclass
       AND lead.attname = 'clinic_id'
       AND second.attname = 'actor_staff_id';

    IF index_count = 0 THEN
        RAISE EXCEPTION 'no index on (clinic_id, actor_staff_id, ...)';
    END IF;

    -- End state of the backfill, stated as a property instead of a row count so
    -- it means something on a fresh database and on production alike: no event
    -- may name a real staff member in metadata while the column stays empty.
    SELECT count(*)
      INTO orphan_count
      FROM public.event_log e
      JOIN public.staff s
        ON s.id::text = e.metadata ->> 'clinic_staff_id'
     WHERE e.actor_staff_id IS NULL;

    IF orphan_count <> 0 THEN
        RAISE EXCEPTION '% events kept the actor in metadata only', orphan_count;
    END IF;
END
$shape$;

-- Behaviour: the FK is real, not decorative. Fixtures roll back with the txn.
INSERT INTO auth.users (id) VALUES ('10000000-0000-0000-0000-0000000000a1');

INSERT INTO public.staff (id, full_name, primary_department, auth_user_id)
VALUES (
    '20000000-0000-0000-0000-0000000000a1',
    'Actor test doctor',
    'DOCTOR',
    '10000000-0000-0000-0000-0000000000a1'
);

INSERT INTO public.event_log (
    event_id, clinic_id, event_type, aggregate_type, aggregate_id,
    payload, source, actor_staff_id
)
VALUES (
    '30000000-0000-0000-0000-0000000000a1',
    'a0000000-0000-4000-8000-000000000001',
    'patient.viewed',
    'patient',
    '40000000-0000-0000-0000-0000000000a1',
    '{"status":"test"}',
    'actor-test',
    '20000000-0000-0000-0000-0000000000a1'
);

DO $unknown_actor_rejected$
BEGIN
    BEGIN
        INSERT INTO public.event_log (
            event_id, clinic_id, event_type, aggregate_type, aggregate_id,
            payload, source, actor_staff_id
        )
        VALUES (
            '30000000-0000-0000-0000-0000000000a2',
            'a0000000-0000-4000-8000-000000000001',
            'patient.viewed',
            'patient',
            '40000000-0000-0000-0000-0000000000a2',
            '{"status":"test"}',
            'actor-test',
            '20000000-0000-0000-0000-00000000ffff'
        );
        RAISE EXCEPTION 'event_log accepted an actor who is not staff';
    EXCEPTION
        WHEN foreign_key_violation THEN NULL;
    END;
END
$unknown_actor_rejected$;

DO $system_actor_allowed$
BEGIN
    INSERT INTO public.event_log (
        event_id, clinic_id, event_type, aggregate_type, aggregate_id,
        payload, source, actor_staff_id
    )
    VALUES (
        '30000000-0000-0000-0000-0000000000a3',
        'a0000000-0000-4000-8000-000000000001',
        'zalo.message',
        'patient',
        '40000000-0000-0000-0000-0000000000a3',
        '{"status":"test"}',
        'relay:zalo',
        NULL
    );
END
$system_actor_allowed$;

DO $delete_blocked_by_history$
DECLARE
    blocking_constraint text;
BEGIN
    BEGIN
        DELETE FROM public.staff
         WHERE id = '20000000-0000-0000-0000-0000000000a1';
        RAISE EXCEPTION 'deleting staff erased their audit trail';
    EXCEPTION
        WHEN foreign_key_violation THEN
            GET STACKED DIAGNOSTICS blocking_constraint = CONSTRAINT_NAME;
    END;

    -- Naming the constraint matters: staff is referenced from many tables, and a
    -- RESTRICT somewhere else would make this test pass while the audit trail
    -- stayed deletable.
    IF blocking_constraint <> 'event_log_actor_staff_id_fkey' THEN
        RAISE EXCEPTION 'delete was blocked by %, not by the audit trail',
            blocking_constraint;
    END IF;
END
$delete_blocked_by_history$;

ROLLBACK;
