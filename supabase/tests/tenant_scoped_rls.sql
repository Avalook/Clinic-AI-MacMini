-- Regression assertions for 20260730000004_tenant_scoped_rls.sql (W3).
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/tenant_scoped_rls.sql
--
-- The property under test: reading a row requires active membership of the
-- clinic that owns it. Everything else — the shared clinic-gate account, a
-- stolen anon key, a JWT from another tenant — reads nothing.

BEGIN;

DO $patient_summary_is_private_and_invoker_scoped$
DECLARE
    options text[];
BEGIN
    SELECT c.reloptions
      INTO options
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relname = 'patient_summary'
       AND c.relkind = 'v';

    IF options IS NULL
       OR NOT ('security_invoker=true' = ANY (options)) THEN
        RAISE EXCEPTION
            'patient_summary must use security_invoker so its base-table RLS applies';
    END IF;

    IF has_table_privilege('authenticated', 'public.patient_summary', 'SELECT') THEN
        RAISE EXCEPTION
            'authenticated must not read patient_summary directly';
    END IF;

    IF has_table_privilege('anon', 'public.patient_summary', 'SELECT') THEN
        RAISE EXCEPTION
            'anon must not read patient_summary directly';
    END IF;

    IF NOT has_table_privilege('service_role', 'public.patient_summary', 'SELECT') THEN
        RAISE EXCEPTION
            'service_role must retain patient_summary access for the backend';
    END IF;
END
$patient_summary_is_private_and_invoker_scoped$;

DO $no_blanket_reads$
DECLARE
    offenders text;
BEGIN
    -- province and ward are the national administrative lists: no patient data,
    -- identical for every tenant.
    --
    -- work_pack và capability (23/09/2026) là DANH MỤC CỦA PHẦN MỀM: tên các
    -- khối công việc và các quyền mà mã nguồn biết cách kiểm. Chúng giống nhau
    -- ở mọi phòng khám và không chứa dữ liệu của ai — đó cũng là lý do chúng
    -- không có `clinic_id` và không nằm trong phép đếm bảng tenant.
    --
    -- Cho mỗi phòng khám một bản riêng là mời họ định nghĩa lại "quyền
    -- clinical.order.place nghĩa là gì", trong khi câu trả lời nằm trong code.
    -- Thứ THEO PHÒNG KHÁM là ai được cấp quyền gì — `capability_grant` và
    -- `quyen_preset` — và cả hai đều có clinic_id, đều lọc theo phòng khám.
    --
    -- Everything else must be scoped.
    SELECT string_agg(tablename || '.' || policyname, ', ')
      INTO offenders
      FROM pg_policies
     WHERE schemaname = 'public'
       AND coalesce(qual, '') IN ('true', '(true)')
       AND tablename NOT IN ('province', 'ward', 'work_pack', 'capability');

    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'blanket USING(true) read policies still present: %', offenders;
    END IF;
END
$no_blanket_reads$;

DO $every_tenant_table_is_scoped$
DECLARE
    unscoped text;
    scoped_count integer;
BEGIN
    -- A tenant table with clinic_id but no policy mentioning current_clinic_ids
    -- is either unreachable or unguarded; both are bugs worth failing on.
    SELECT string_agg(c.table_name, ', ')
      INTO unscoped
      FROM information_schema.columns c
     WHERE c.table_schema = 'public'
       AND c.column_name = 'clinic_id'
       AND c.table_name NOT IN ('clinic_membership')
       AND EXISTS (
           SELECT 1 FROM pg_policies p
            WHERE p.schemaname = 'public' AND p.tablename = c.table_name
       )
       AND NOT EXISTS (
           SELECT 1 FROM pg_policies p
            WHERE p.schemaname = 'public'
              AND p.tablename = c.table_name
              -- current_clinical_clinic_ids() is current_clinic_ids() narrowed
              -- to the clinical roles (ROLE-02, 20260730000013): still scoped by
              -- tenant, and additionally by role. Matching on the name alone
              -- would have read that tightening as a tenant leak.
              AND (coalesce(p.qual, '') LIKE '%current_clinic_ids%'
                OR coalesce(p.qual, '') LIKE '%current_clinical_clinic_ids%')
       );

    IF unscoped IS NOT NULL THEN
        RAISE EXCEPTION 'tables with a policy that ignores the tenant: %', unscoped;
    END IF;

    SELECT count(*) INTO scoped_count
      FROM pg_policies
     WHERE schemaname = 'public'
       AND policyname LIKE '%_select_own_clinic';

    -- 23 tenant tables + staff + 7 workflow-kernel tables (W4)
    -- + block_budget, which became client-readable in W5. clinical_record and
    -- clinical_form_response keep this name but a narrower rule (ROLE-02).
    -- 32 → 34 on 02/08/2026: drug_batch + inventory_txn (migration
    -- 20260802000001, kho thuốc theo lô).
    -- 34 → 35 ngày 07/08/2026: nhac_tai_kham — việc gọi nhắc tái khám hai lượt
    -- (migration 20260807000005). Đọc theo phòng khám, ghi qua FastAPI.
    -- 35 → 36 ngày 07/08/2026: thong_bao (migration 20260807000006).
    -- 36 → 37 ngày 08/08/2026: roster_week — tuần lịch trực đã áp dụng
    -- (migration 20260808000001). CHỈ ĐỌC cho client, cùng lý do với mọi bảng
    -- luật khác: client tự ghi được nghĩa là client tự chốt được lịch trực.
    -- 37 → 38 ngày 08/08/2026: luat_bac_si_bat_buoc (20260808000003).
    -- 38 → 39 ngày 08/08/2026: vai_duoc_vao_tram (20260809000002). CHỈ ĐỌC:
    -- sửa được ma trận này là quyết được ai đứng ở bàn khám.
    -- 39 → 40 ngày 08/08/2026: tuong_tac_cskh (20260809000003). CHỈ ĐỌC: client
    -- tự ghi được nghĩa là tự khai được "đã gọi rồi" cho cuộc gọi chưa xảy ra.
    -- 40 → 42 ngày 08/08/2026: luat_cskh + hen_goi_lai (20260809000005).
    -- 42 → 43 ngày 08/08/2026: phan_hoi_khach (20260809000007).
    -- 43 → 44 ngày 08/08/2026: tep_ket_qua (20260809000008). CHỈ ĐỌC: khoá tệp
    -- do hệ thống sinh, và client tự ghi được nghĩa là tự khai được một khoá.
    -- 44 → 45 ngày 15/08/2026: patient_sdt_them (20260815000002) — số điện
    -- thoại gắn thêm cho hồ sơ có sẵn, đọc theo đúng luật phòng-khám-của-mình.
    -- 45 → 53 ngày 11/09/2026: tám bảng luồng khám lát 1 (20260911000001). Bảng
    -- thứ chín, command_receipt, có policy riêng `_select_own`: biên nhận chỉ
    -- người gửi đọc được, nên không mang hậu tố `_select_own_clinic`.
    -- Bảng service_order_draft (20260915000008) có policy riêng theo vai bác
    -- sĩ/thư ký nên không làm đổi con số này.
    -- 53 → 54 ngày 15/09/2026: thu_ky_bac_si (20260915000020).
    -- 54 → 55 (16/09/2026, cập nhật bài kiểm 18/09): vi_tri_dong_ca_select_own_clinic
    -- (20260916000011) — qual `clinic_id IN (current_clinic_ids())`, đúng khuôn.
    -- 55 → 56 (19/09/2026): payment_bill_line_select_own_clinic
    -- (20260919000001) — qual `clinic_id IN (current_clinic_ids())`, chỉ SELECT.
    -- 56 → 57 (19/09/2026): payment_cycle_select_own_clinic (20260919000002).
    -- 57 → 58 (19/09/2026): prescription_allocation_select_own_clinic
    -- (20260919000003, contract tiền–thuốc CP3).
    -- 58 → 61 (19/09/2026): payment_refund / payment_refund_line / drug_return
    -- _select_own_clinic (20260919000004, contract tiền–thuốc CP5).
    -- 61 → 62 (20/09/2026): prescription_correction_select_own_clinic
    -- (20260920000002, contract tiền–thuốc CP6 bước 4a).
    -- 62 → 64 (22/09/2026): service_selection_state / service_execution_attempt
    -- _select_own_clinic (20260922000001, Service Lifecycle v1 Slice 1). CHỈ
    -- ĐỌC: ghi qua command FastAPI.
    -- 64 → 74 (23/09/2026): MƯỜI policy đọc mới, tất cả cùng khuôn
    -- `clinic_id IN (SELECT current_clinic_ids())`, tất cả CHỈ SELECT — ghi đi
    -- qua lệnh FastAPI, không qua PostgREST:
    --   domain_event · event_delivery        (…0001, sổ sự kiện)
    --   luot_dong_thoi_gian                  (…0002, projection hành trình)
    --   capability_grant                     (…0003, quyền đã cấp cho từng người)
    --   ket_qua_mau · dich_vu_mau_ket_qua    (…0004, danh mục mẫu kết quả)
    --   form_definition · form_instance      (…0005, Form Template Engine)
    --   hen_gio                              (…0008, hẹn kiểm lại)
    --   quyen_preset                         (…0011, nhóm quyền mẫu)
    -- 74 → 76 (23/09/2026): result_correction · form_result_release
    -- (20260923000014). Cùng khuôn `current_clinic_ids()`, CHỈ SELECT — ghi đi
    -- qua lệnh FastAPI, và cả hai bảng có trigger chặn UPDATE/DELETE.
    -- 76 → 78 (24/09/2026, nhóm 3): day_nhan_thong_bao · appointment_doi_lich
    -- (20260924000004), cùng khuôn `clinic_id IN (current_clinic_ids())`.
    -- 78 → 80 (24/09/2026, nhóm 5): day_nghiep_vu · nhac_viec_ca_nhan.
    -- 80 → 81 (23/09/2026 tối): phieu_kham_luot (20260924000008).
    -- 81 → 82 (24/09/2026 chiều): doi_tac_nhan_viec (20260925000009, đối tác
    -- nhận việc qua sự kiện).
    -- 82 → 83 (25/09/2026): phieu_kham_lich_su (20260925000018, lịch sử sửa
    -- phiếu khám — P4A).
    -- 83 → 84 (27/09/2026): ghi_chu_khach (20260927000003, ghi chú về khách).
    -- 84 → 85 (27/09/2026 đợt 3): doi_tac_thanh_toan (20260928000091, đối tác
    -- ghi nhận đã thu tiền khách).
    -- 85 → 87 (28/09/2026): ky_nang + nhan_su_ky_nang (phân quyền theo kỹ năng).
    -- 87 → 88 (28/09/2026): thuoc_giao_chua_gan_lo (giao thuốc không cần lô).
    -- 88 → 90 (28/09/2026): phu_thu_mau + luot_phu_thu.
    -- 90 → 92 (28/09/2026): loai_kham_phi + luot_phi_kham (phí khám KiotViet).
    -- 92 → 93 (29/09/2026): work_roster_thay_nguoi (vết đổi người trong ca).
    -- 93 → 95 (29/09/2026): phieu_kho + phieu_kho_dong (20260929960000).
    -- 95 → 96 (30/09/2026): payment_cycle_doi_hinh_thuc (20260930500000).
    -- 96 → 97 (01/10/2026): cong_no (20261002500000).
    -- 97 → 99 (01/10/2026): payment_cycle_phan + anh_chuyen_khoan (20261002300000).
    -- 99 → 100 (02/10/2026): ngoai_le_ca_truc_select_own_clinic (20261002600000).
    -- 100 → 102 (01/10/2026, C13): luot_vat_tu + vat_tu_goi_y (20261003000000).
    -- 102 → 103 (07/10/2026): form_instance_lich_su (20261007630000, lịch sử sửa
    -- mọi phiếu kết quả — chỉ thêm, trigger ghi).
    -- 103 → 104 (07/10/2026): luot_ghi_chu (20261007640000, ô chữ tự do lượt
    -- "Khác" — chỉ thêm phiên bản).
    IF scoped_count <> 104 THEN
        RAISE EXCEPTION 'expected 104 tenant-scoped read policies, found %', scoped_count;
    END IF;
END
$every_tenant_table_is_scoped$;

DO $reads_only$
DECLARE
    writable text;
BEGIN
    -- ADR-0012: the backend owns every write, so no client-facing write policy
    -- may exist. A single INSERT policy would undo that guarantee silently.
    SELECT string_agg(tablename || '.' || policyname || ' (' || cmd || ')', ', ')
      INTO writable
      FROM pg_policies
     WHERE schemaname = 'public'
       AND cmd <> 'SELECT';

    IF writable IS NOT NULL THEN
        RAISE EXCEPTION 'client-facing write policies must not exist: %', writable;
    END IF;
END
$reads_only$;

DO $backend_only_tables$
DECLARE
    exposed text;
    backend_only text[] := ARRAY[
        'idempotency_key',  -- stores replayed request/response bodies
        'clinic_secret',    -- POS/Zalo credentials: RLS on, zero policies
        'mpi_merge_queue',  -- patient identifiers pending a merge decision
        'staff_capability', -- staffing config
        'pos_outbox'        -- pending pushes to an external till
        -- ultrasound_record was here while app/api/ultrasound read it with the
        -- service-role key. It now reads with the caller's own session, so the
        -- table has a tenant-scoped SELECT policy (20260730000012) and being
        -- policy-free would mean the page reads nothing.
    ];
BEGIN
    SELECT string_agg(c.relname, ', ')
      INTO exposed
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relname = ANY (backend_only)
       AND (
           NOT c.relrowsecurity
           OR EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid)
       );

    IF exposed IS NOT NULL THEN
        RAISE EXCEPTION 'these tables must stay service_role-only (RLS on, no policy): %', exposed;
    END IF;
END
$backend_only_tables$;

-- A new hire must not land in an app where every screen is silently empty, so
-- membership is created by the table itself rather than by whichever code path
-- happened to insert the staff row.
DO $membership_is_automatic$
DECLARE
    new_staff uuid;
BEGIN
    INSERT INTO public.staff (full_name, primary_department)
    VALUES ('Nhân viên mới', 'RECEPTION')
    RETURNING id INTO new_staff;

    IF NOT EXISTS (
        SELECT 1 FROM public.clinic_membership
         WHERE staff_id = new_staff
           AND clinic_id = 'a0000000-0000-4000-8000-000000000001'
           AND role = 'RECEPTION'
    ) THEN
        RAISE EXCEPTION 'inserting a staff row must create its clinic_membership';
    END IF;

    DELETE FROM public.clinic_membership WHERE staff_id = new_staff;
    DELETE FROM public.staff WHERE id = new_staff;
END
$membership_is_automatic$;

DO $policies_need_grants$
DECLARE
    ungranted text;
BEGIN
    -- A read policy only narrows a privilege the role already holds. The frozen
    -- baseline was dumped without ACLs, so on a fresh project every policy
    -- written in W1-W4 was unreachable and the app died on permission denied —
    -- invisible in production, fatal in a new environment. 20260730000008
    -- restores them; this makes sure they stay.
    SELECT string_agg(DISTINCT c.relname, ', ')
      INTO ungranted
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_policy p ON p.polrelid = c.oid
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND p.polcmd IN ('r', '*')
       -- HỎI "ĐỌC ĐƯỢC THỨ GÌ ĐÓ", KHÔNG PHẢI "CẦM SELECT CẢ BẢNG".
       --
       -- 20260805000002 rút SELECT mức bảng khỏi `clinic` rồi cấp lại theo
       -- CỘT, để `clinic.settings` (nơi tài liệu đang dạy đặt credential POS)
       -- không đọc được bằng anon key. Bảng vẫn có policy đọc và ứng dụng vẫn
       -- chạy — nhưng `has_table_privilege(..., 'SELECT')` trả false, nên câu
       -- hỏi cũ báo `clinic` là "có policy mà không đọc nổi", một kết luận sai.
       AND NOT EXISTS (
           SELECT 1 FROM pg_attribute a
            WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
              AND has_column_privilege('authenticated', c.oid, a.attnum, 'SELECT')
       );

    IF ungranted IS NOT NULL THEN
        RAISE EXCEPTION
            'these tables have a read policy but authenticated cannot SELECT them: %',
            ungranted;
    END IF;
END
$policies_need_grants$;

-- --------------------------------------------------------------------------
-- Behaviour. Two clinics, one staff member each, one patient each.
-- --------------------------------------------------------------------------

INSERT INTO auth.users (id)
VALUES
    ('11111111-1111-4111-8111-111111111111'),  -- staff at Dr4Women
    ('22222222-2222-4222-8222-222222222222'),  -- staff at the other clinic
    ('99999999-9999-4999-8999-999999999999');  -- the shared clinic-gate account

INSERT INTO public.clinic (id, code, name)
VALUES ('b0000000-0000-4000-8000-000000000002', 'OTHER', 'Phòng khám khác');

-- Phòng khám trong bài kiểm này có nhiều hơn một cơ sở, nên hệ thống KHÔNG
-- đoán hộ (trigger 20260804000015). Fixture phải chỉ rõ.
INSERT INTO public.staff
    (id, full_name, primary_department, auth_user_id, primary_location_id)
VALUES
    ('c0000000-0000-4000-8000-00000000000a', 'RLS test A', 'DOCTOR',
     '11111111-1111-4111-8111-111111111111',
     (SELECT id FROM public.clinic_location WHERE is_active
      ORDER BY created_at, id LIMIT 1)),
    ('c0000000-0000-4000-8000-00000000000b', 'RLS test B', 'DOCTOR',
     '22222222-2222-4222-8222-222222222222',
     (SELECT id FROM public.clinic_location WHERE is_active
      ORDER BY created_at, id LIMIT 1));

INSERT INTO public.clinic_membership (clinic_id, staff_id, role)
VALUES
    ('a0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-00000000000a', 'DOCTOR'),
    ('b0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-00000000000b', 'DOCTOR');

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES
    ('d0000000-0000-4000-8000-00000000000a', 'a0000000-0000-4000-8000-000000000001', 'CS1', 'Cơ sở A'),
    ('d0000000-0000-4000-8000-00000000000b', 'b0000000-0000-4000-8000-000000000002', 'CS1', 'Cơ sở B');

INSERT INTO public.patient (clinic_patient_id, clinic_id, patient_code, full_name, location_id)
VALUES
    ('e0000000-0000-4000-8000-00000000000a', 'a0000000-0000-4000-8000-000000000001',
     'BN001', 'Bệnh nhân của A', 'd0000000-0000-4000-8000-00000000000a'),
    ('e0000000-0000-4000-8000-00000000000b', 'b0000000-0000-4000-8000-000000000002',
     'BN001', 'Bệnh nhân của B', 'd0000000-0000-4000-8000-00000000000b');

-- The product no longer grants this view to frontend callers.  Grant it only
-- inside the rolled-back test transaction to prove the second line of defence:
-- if somebody accidentally restores the grant later, SECURITY INVOKER still
-- makes the patient table's tenant RLS apply through the view.
GRANT SELECT ON public.patient_summary TO authenticated;

SET LOCAL ROLE authenticated;

SELECT set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', true);

DO $staff_a$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000a'
    ) OR EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION 'staff A must see their own patient and not clinic B''s';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.patient_summary
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000a'
    ) OR EXISTS (
        SELECT 1 FROM public.patient_summary
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION
            'patient_summary must inherit patient RLS and never cross tenants';
    END IF;

    -- Count only what this test inserted: seed.sql loads real clinic_location
    -- rows, so asserting on the whole table passes on an empty database and
    -- fails on a seeded one.
    IF EXISTS (
        SELECT 1 FROM public.clinic_location
         WHERE id = 'd0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION 'staff A must not see another clinic''s locations';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.clinic_location
         WHERE id = 'd0000000-0000-4000-8000-00000000000a'
    ) THEN
        RAISE EXCEPTION 'staff A must see their own clinic''s location';
    END IF;

    -- Self-read must work even before any colleague lookup.
    IF NOT EXISTS (
        SELECT 1 FROM public.staff WHERE id = 'c0000000-0000-4000-8000-00000000000a'
    ) THEN
        RAISE EXCEPTION 'staff must always be able to read their own row';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.staff WHERE id = 'c0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION 'staff A must not read staff of another clinic';
    END IF;
END
$staff_a$;

SELECT set_config('request.jwt.claim.sub', '22222222-2222-4222-8222-222222222222', true);

DO $staff_b$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000b'
    ) OR EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000a'
    ) THEN
        RAISE EXCEPTION 'staff B must see their own patient and not clinic A''s';
    END IF;
END
$staff_b$;

SELECT set_config('request.jwt.claim.sub', '99999999-9999-4999-8999-999999999999', true);

DO $shared_gate_account$
BEGIN
    -- Một tài khoản Supabase hợp lệ nhưng KHÔNG gắn dòng `staff` nào. Trước
    -- đây đó là tài khoản cổng chung của app/(auth)/enter (đã bỏ 05/08/2026);
    -- nay là bất kỳ tài khoản nào chưa được cấp nhân sự. Dưới policy
    -- USING(true) cũ nó đọc được mọi bệnh nhân; giờ phải đọc ra 0 dòng.
    IF EXISTS (SELECT 1 FROM public.patient) THEN
        RAISE EXCEPTION 'an authenticated account with no staff row must read no patients';
    END IF;

    IF EXISTS (SELECT 1 FROM public.patient_summary) THEN
        RAISE EXCEPTION
            'an authenticated account with no staff row must read no patient summaries';
    END IF;

    IF (SELECT count(*) FROM public.staff) <> 0 THEN
        RAISE EXCEPTION 'an authenticated account with no staff row must read no staff';
    END IF;
END
$shared_gate_account$;

RESET ROLE;
SET LOCAL ROLE service_role;

DO $backend_unaffected$
BEGIN
    IF (SELECT count(*) FROM public.patient
         WHERE clinic_patient_id IN (
             'e0000000-0000-4000-8000-00000000000a',
             'e0000000-0000-4000-8000-00000000000b')) <> 2 THEN
        RAISE EXCEPTION 'service_role must still read across tenants for the backend';
    END IF;

    IF (SELECT count(*) FROM public.patient_summary
         WHERE clinic_patient_id IN (
             'e0000000-0000-4000-8000-00000000000a',
             'e0000000-0000-4000-8000-00000000000b')) <> 2 THEN
        RAISE EXCEPTION
            'service_role must retain patient_summary access for the backend';
    END IF;
END
$backend_unaffected$;

RESET ROLE;

ROLLBACK;
