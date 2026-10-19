-- Assert that restored or freshly migrated public functions do not inherit
-- PostgreSQL's default PUBLIC execute privilege. Run after migrations:
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f supabase/tests/public_function_acl.sql

DO $assertions$
DECLARE
    exposed_function text;
    function_signature text;
    function_signatures text[] := ARRAY[
        'public.move_visit_to_station(uuid,uuid,text,uuid,uuid,text,text)',
        'public.place_visit_at_first_station(uuid,uuid,uuid)',
        'public.lieu_trinh_phu_lai(uuid,uuid)',
        'public.lieu_trinh_tinh_lai(uuid,uuid)',
        'public.lieu_trinh_gan_buoi(uuid,uuid,uuid,text,uuid)',
        'public.lieu_trinh_go_buoi(uuid,uuid,text,uuid)',
        'public.lieu_trinh_tinh_lai_theo_lan_thu(uuid,uuid)'
    ];
    private_signatures text[] := ARRAY[
        'public.don_khach_thu(uuid,uuid[],boolean,timestamp with time zone,uuid,text,text)',
        'public._don_thu_khoa(regclass,text)',
        'public._don_thu_lap(text,text)',
        'public._don_thu_lan(text[])',
        'public._don_thu_lap_so(timestamp with time zone)',
        'public.lan_don_du_lieu_thu_chi_them()',
        'public.du_lieu_da_xoa_khong_sua()'
    ];
    function_id oid;
BEGIN
    -- No public function should be callable by an anonymous PostgREST role.
    SELECT p.oid::regprocedure::text
      INTO exposed_function
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.prokind = 'f'
       AND has_function_privilege('anon', p.oid, 'EXECUTE')
     LIMIT 1;

    IF exposed_function IS NOT NULL THEN
        RAISE EXCEPTION 'anon can execute public function: %',
            exposed_function;
    END IF;

    FOREACH function_signature IN ARRAY function_signatures LOOP
        function_id := to_regprocedure(function_signature);
        IF function_id IS NULL THEN
            RAISE EXCEPTION 'missing protected function: %',
                function_signature;
        END IF;

        IF has_function_privilege('anon', function_id, 'EXECUTE') THEN
            RAISE EXCEPTION 'anon can execute protected function: %',
                function_signature;
        END IF;
    END LOOP;

    FOREACH function_signature IN ARRAY private_signatures LOOP
        function_id := to_regprocedure(function_signature);
        IF function_id IS NULL THEN
            RAISE EXCEPTION 'missing private function: %',
                function_signature;
        END IF;

        IF has_function_privilege('anon', function_id, 'EXECUTE')
           OR has_function_privilege('authenticated', function_id, 'EXECUTE')
           OR has_function_privilege('service_role', function_id, 'EXECUTE') THEN
            RAISE EXCEPTION 'a PostgREST role can execute private function: %',
                function_signature;
        END IF;
    END LOOP;

    IF has_function_privilege(
        'authenticated',
        'public.move_visit_to_station(uuid,uuid,text,uuid,uuid,text,text)',
        'EXECUTE'
    ) OR has_function_privilege(
        'authenticated',
        'public.place_visit_at_first_station(uuid,uuid,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'authenticated can execute internal visit dispatch helper';
    END IF;

    IF NOT has_function_privilege(
        'service_role',
        'public.move_visit_to_station(uuid,uuid,text,uuid,uuid,text,text)',
        'EXECUTE'
    ) OR NOT has_function_privilege(
        'service_role',
        'public.place_visit_at_first_station(uuid,uuid,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'service_role cannot execute visit dispatch helper';
    END IF;

    IF NOT has_function_privilege(
        'service_role',
        'public.lieu_trinh_phu_lai(uuid,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'service_role cannot execute lifecycle helper';
    END IF;

    IF has_function_privilege(
        'authenticated',
        'public.lieu_trinh_phu_lai(uuid,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'authenticated can execute internal lifecycle helper';
    END IF;

    IF has_function_privilege(
        'authenticated',
        'public.current_staff_department()',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'deprecated current_staff_department is executable';
    END IF;

END
$assertions$;

-- Future functions created by the migration role must not inherit PUBLIC EXECUTE.
CREATE FUNCTION public.test_default_function_acl()
RETURNS integer
LANGUAGE sql
AS $$ SELECT 1 $$;

DO $default_privileges$
BEGIN
    IF has_function_privilege(
        'anon',
        'public.test_default_function_acl()',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'future public function inherited anon EXECUTE';
    END IF;
END
$default_privileges$;

DROP FUNCTION public.test_default_function_acl();
