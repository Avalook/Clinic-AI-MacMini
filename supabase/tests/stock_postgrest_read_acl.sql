-- Kho thuốc/vật tư được đọc qua FastAPI, không cấp SELECT trực tiếp cho JWT
-- `authenticated`. Test cả quyền và policy để tránh lộ lại sau khi có GRANT.
BEGIN;

DO $acl$
DECLARE
    ten text;
    bang text[] := ARRAY[
        'drug_batch',
        'inventory_txn',
        'drug_return',
        'phieu_kho',
        'phieu_kho_dong',
        'kiem_ke_ca',
        'kiem_ke_ca_dong',
        'vat_tu_phieu',
        'vat_tu_ton',
        'vat_tu_txn',
        'vat_tu_nhap_cho_duyet'
    ];
BEGIN
    FOREACH ten IN ARRAY bang LOOP
        IF has_table_privilege('authenticated', format('public.%I', ten), 'SELECT') THEN
            RAISE EXCEPTION 'authenticated vẫn có SELECT trên public.%', ten;
        END IF;
        IF has_table_privilege('authenticated', format('public.%I', ten), 'INSERT')
           OR has_table_privilege('authenticated', format('public.%I', ten), 'UPDATE')
           OR has_table_privilege('authenticated', format('public.%I', ten), 'DELETE') THEN
            RAISE EXCEPTION 'authenticated vẫn có quyền ghi trên public.%', ten;
        END IF;
        IF has_table_privilege('anon', format('public.%I', ten), 'SELECT') THEN
            RAISE EXCEPTION 'anon vẫn có SELECT trên public.%', ten;
        END IF;
        IF NOT has_table_privilege('service_role', format('public.%I', ten), 'SELECT') THEN
            RAISE EXCEPTION 'service_role mất SELECT trên public.%', ten;
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_policies p
             WHERE p.schemaname = 'public'
               AND p.tablename = ten
               AND p.cmd IN ('SELECT', 'ALL')
               AND (
                   'authenticated' = ANY (p.roles::text[])
                   OR 'public' = ANY (p.roles::text[])
               )
        ) THEN
            RAISE EXCEPTION 'public.% còn policy đọc cho authenticated/public', ten;
        END IF;
    END LOOP;
END
$acl$;

ROLLBACK;
