-- Take away the database's licence to guess which clinic a row belongs to.
--
-- W2 gave every tenant table `clinic_id uuid DEFAULT public.default_clinic_id()
-- NOT NULL`. That default was scaffolding, and it was honest scaffolding: it
-- resolves while exactly one clinic exists and returns NULL the moment there
-- are two, so it could never file a row under the wrong clinic — an INSERT that
-- forgot the tenant would fail on NOT NULL instead.
--
-- Honest, but still a way to write a row without saying where it belongs. The
-- application no longer needs it: StaffIdentity.clinic_id is a required `str`,
-- every service and background tool takes the tenant as a required argument,
-- and the 45 `COALESCE(..., default_clinic_id())` fallbacks in the query layer
-- are gone. mypy now proves what the default used to paper over.
--
-- With the default dropped, "forgot the tenant" fails immediately and in the
-- same way whether there is one clinic or fifty. That is the whole point: the
-- single-clinic case stops being a special case that hides mistakes until the
-- day a second clinic makes them expensive.
--
-- The FUNCTION stays. staff_ensure_default_membership still calls it to give a
-- new hire a membership while the deployment is single-tenant, and it already
-- returns NULL — no membership, insert it yourself — once that is ambiguous.
-- Removing the function would mean rewriting that trigger, which is a separate
-- decision about onboarding, not about this.

DO $drop_defaults$
DECLARE
    col record;
    dropped integer := 0;
BEGIN
    FOR col IN
        SELECT c.table_name
          FROM information_schema.columns c
         WHERE c.table_schema = 'public'
           AND c.column_name = 'clinic_id'
           AND c.column_default LIKE '%default_clinic_id%'
         ORDER BY c.table_name
    LOOP
        EXECUTE format(
            'ALTER TABLE public.%I ALTER COLUMN clinic_id DROP DEFAULT',
            col.table_name
        );
        dropped := dropped + 1;
    END LOOP;

    RAISE NOTICE 'dropped clinic_id DEFAULT on % tables', dropped;
END
$drop_defaults$;

-- Every tenant column must still be NOT NULL. Dropping a default from a
-- nullable column would replace "guessed clinic" with "no clinic", which is
-- worse: the row lands where no policy can see it and no report counts it.
DO $still_not_null$
DECLARE
    nullable text;
BEGIN
    SELECT string_agg(c.table_name, ', ' ORDER BY c.table_name)
      INTO nullable
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema
       AND t.table_name = c.table_name
       AND t.table_type = 'BASE TABLE'
     WHERE c.table_schema = 'public'
       AND c.column_name = 'clinic_id'
       AND c.is_nullable = 'YES';

    IF nullable IS NOT NULL THEN
        RAISE EXCEPTION
            'clinic_id is nullable on: % — a tenant column with no default '
            'must still be NOT NULL', nullable;
    END IF;
END
$still_not_null$;

-- And none may quietly come back.
DO $no_defaults_left$
DECLARE
    remaining text;
BEGIN
    SELECT string_agg(c.table_name, ', ' ORDER BY c.table_name)
      INTO remaining
      FROM information_schema.columns c
     WHERE c.table_schema = 'public'
       AND c.column_name = 'clinic_id'
       AND c.column_default IS NOT NULL;

    IF remaining IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_id still has a DEFAULT on: %', remaining;
    END IF;
END
$no_defaults_left$;

-- ---------------------------------------------------------------------------
-- Child rows inherit the tenant from their parent
-- ---------------------------------------------------------------------------
-- work_item_dependency and work_item_event have no tenant of their own: an edge
-- belongs to whichever clinic owns the items it joins, and an event belongs to
-- the item it happened to. Until now they got it from the column DEFAULT, which
-- is why workflow_kernel.sql could assert "events must inherit the tenant" and
-- pass — it was really asserting the default resolved.
--
-- Deriving it from the parent is not a guess, it is a lookup, so it stays.
-- Rejecting a mismatch is the part that is new: an edge between two clinics'
-- work items was previously accepted and silently labelled with the default.

CREATE OR REPLACE FUNCTION public.work_item_dependency_inherit_clinic()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public', 'pg_temp'
AS $$
DECLARE
    pred_clinic uuid;
    succ_clinic uuid;
BEGIN
    SELECT clinic_id INTO pred_clinic
      FROM public.work_item WHERE id = NEW.predecessor_work_item_id;
    SELECT clinic_id INTO succ_clinic
      FROM public.work_item WHERE id = NEW.successor_work_item_id;

    IF pred_clinic IS NULL OR succ_clinic IS NULL THEN
        RAISE EXCEPTION 'work_item_dependency references a work_item that does not exist';
    END IF;
    IF pred_clinic <> succ_clinic THEN
        RAISE EXCEPTION
            'a dependency cannot cross clinics (% -> %)', pred_clinic, succ_clinic;
    END IF;

    IF NEW.clinic_id IS NULL THEN
        NEW.clinic_id := pred_clinic;
    ELSIF NEW.clinic_id <> pred_clinic THEN
        RAISE EXCEPTION
            'dependency clinic_id % does not match its work items (%)',
            NEW.clinic_id, pred_clinic;
    END IF;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS work_item_dependency_inherit_clinic
    ON public.work_item_dependency;
CREATE TRIGGER work_item_dependency_inherit_clinic
    BEFORE INSERT OR UPDATE ON public.work_item_dependency
    FOR EACH ROW EXECUTE FUNCTION public.work_item_dependency_inherit_clinic();

CREATE OR REPLACE FUNCTION public.work_item_event_inherit_clinic()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public', 'pg_temp'
AS $$
DECLARE
    item_clinic uuid;
BEGIN
    SELECT clinic_id INTO item_clinic
      FROM public.work_item WHERE id = NEW.work_item_id;

    IF item_clinic IS NULL THEN
        RAISE EXCEPTION 'work_item_event references a work_item that does not exist';
    END IF;

    IF NEW.clinic_id IS NULL THEN
        NEW.clinic_id := item_clinic;
    ELSIF NEW.clinic_id <> item_clinic THEN
        RAISE EXCEPTION
            'event clinic_id % does not match its work item (%)',
            NEW.clinic_id, item_clinic;
    END IF;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS work_item_event_inherit_clinic ON public.work_item_event;
CREATE TRIGGER work_item_event_inherit_clinic
    BEFORE INSERT OR UPDATE ON public.work_item_event
    FOR EACH ROW EXECUTE FUNCTION public.work_item_event_inherit_clinic();
