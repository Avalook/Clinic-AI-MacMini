-- Restored dumps use pg_dump --no-acl, so the migration ledger may say old
-- grants were applied even though they were not restored. PostgreSQL grants
-- EXECUTE to PUBLIC by default; remove that default exposure for every public
-- function, then reapply the intentional role grants from earlier migrations.
-- FastAPI connects as the database owner. PostgREST clients need only the
-- explicitly listed helpers below.
BEGIN;

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- RLS and authenticated PostgREST helpers.
GRANT EXECUTE ON FUNCTION public.current_staff_id(),
    public.current_clinic_ids(),
    public.current_clinic_roles(uuid),
    public.current_clinic_ids_for_roles(text[]),
    public.current_clinical_clinic_ids(),
    public.clinic_hours_for_date(uuid, date),
    public.resolve_effective_cap(uuid, uuid, timestamp with time zone),
    public.resolve_effective_caps(uuid, uuid, date, integer[]),
    public.la_ca_kham_bac_si(uuid, text),
    public.thu_ky_duoc_xem_khach(uuid, uuid)
TO authenticated, service_role;

-- These SECURITY DEFINER functions trust actor/clinic arguments and are only
-- called through the backend. Do not expose them as authenticated RPCs.
REVOKE EXECUTE ON FUNCTION
    public.move_visit_to_station(uuid, uuid, text, uuid, uuid, text, text),
    public.place_visit_at_first_station(uuid, uuid, uuid)
FROM authenticated;
GRANT EXECUTE ON FUNCTION
    public.move_visit_to_station(uuid, uuid, text, uuid, uuid, text, text),
    public.place_visit_at_first_station(uuid, uuid, uuid)
TO service_role;

-- Prescription draft reads are intentionally authenticated-only.
GRANT EXECUTE ON FUNCTION public.read_prescription_draft(uuid)
TO authenticated;

-- Internal functions called by backend/worker jobs using the trusted role.
GRANT EXECUTE ON FUNCTION
    public.sinh_viec_nhac_tai_kham(uuid, date),
    public.instantiate_visit_workflow(uuid, uuid, uuid, text, text),
    public.cancel_visit_workflow(uuid, uuid, uuid, text, text),
    public.order_services(uuid, uuid, text[], uuid, text),
    public.recent_duplicate_services(uuid, uuid, text[], integer),
    public.order_services_lock_visit(uuid),
    public.check_in_appointment(uuid, text[]),
    public.lieu_trinh_phu_lai(uuid, uuid),
    public.lieu_trinh_tinh_lai(uuid, uuid),
    public.lieu_trinh_gan_buoi(uuid, uuid, uuid, text, uuid),
    public.lieu_trinh_go_buoi(uuid, uuid, text, uuid),
    public.lieu_trinh_tinh_lai_theo_lan_thu(uuid, uuid)
TO service_role;

-- Deprecated helper: an earlier migration granted it to authenticated before
-- it was explicitly retired. Keep that revocation effective after ACL restore.
REVOKE EXECUTE ON FUNCTION public.current_staff_department()
    FROM PUBLIC, anon, authenticated;

-- These functions are deliberately inaccessible to every PostgREST role.
-- Restore with --no-acl reapplies the service_role defaults from init SQL,
-- so restore their explicit deny-list here as well.
REVOKE EXECUTE ON FUNCTION
    public.don_khach_thu(uuid, uuid[], boolean, timestamp with time zone, uuid, text, text),
    public._don_thu_khoa(regclass, text),
    public._don_thu_lap(text, text),
    public._don_thu_lan(text[]),
    public._don_thu_lap_so(timestamp with time zone),
    public.lan_don_du_lieu_thu_chi_them(),
    public.du_lieu_da_xoa_khong_sua()
FROM PUBLIC, anon, authenticated, service_role;

COMMIT;
