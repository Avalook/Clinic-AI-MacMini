-- Khoá /rest/v1: PostgREST chỉ còn trả `staff` + `clinic_membership` của CHÍNH
-- người đang đăng nhập. Kế hoạch: docs/ke-hoach/khoa-rest-v1-2210.md (Tuyền duyệt
-- "khoá hẳn" 22/10/2026).
--
-- Vì sao: chính sách đọc cũ chỉ hỏi "có thuộc phòng khám không", không hỏi vai.
-- Đo 22/10 trên DB local: tài khoản ĐỐI TÁC đọc được 70 khách, 51 lịch hẹn qua
-- /rest/v1; `authenticated` có SELECT trên 117 bảng/view (kể cả view
-- security-definer — RLS không chặn được view).
--
-- Giao diện chỉ cần đúng hai chỗ (đăng nhập + proxy.ts):
--   staff              id, auth_user_id, is_active, primary_department
--   clinic_membership  clinic_id, staff_id, role, is_active
-- Mọi thứ khác đi qua FastAPI, nối bằng chủ database (BYPASS RLS) — không đổi.
--
-- Chỉ đổi QUYỀN + CHÍNH SÁCH. Không sửa/xoá dòng dữ liệu nào. Chạy lại lần hai
-- không lỗi (CI máy áp lại cả chuỗi từ 20260730 — chuỗi đó có 20260730000008
-- cấp lại SELECT theo policy, nên tệp này phải đứng SAU nó và áp lại được).
-- Hoàn tác: scripts/chup-acl-rest.sh sinh rollback.sql từ ACL chụp ngay trước khi áp.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Thu hết quyền bảng / view / sequence / hàm của anon, authenticated
-- ---------------------------------------------------------------------------
-- "ALL TABLES" gồm cả view, view vật thể, bảng phân vùng. REVOKE mức bảng cũng
-- thu luôn quyền theo cột (vd. clinical_record cấp theo cột ở 20260915000007).
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL ROUTINES  IN SCHEMA public FROM PUBLIC, anon, authenticated;

-- Bảng/hàm sinh SAU này không được tự mở. Bảng do `postgres` tạo (chạy migration
-- bằng nó — apply-pending-migrations.sh, ci-may.sh, test-nhanh.sh). Thời
-- Supabase cloud còn `supabase_admin` cấp mặc định ALL cho anon/authenticated;
-- nên quét MỌI vai đang có dòng trong pg_default_acl, cộng `postgres`.
-- Không thu được (thiếu quyền trên vai đó) mà dòng ấy còn mở cho anon/
-- authenticated → dừng hẳn, đừng để khoá nửa vời.
DO $mac_dinh$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT DISTINCT ro.rolname
          FROM pg_roles ro
         WHERE ro.rolname = 'postgres'
            OR ro.oid IN (SELECT defaclrole FROM pg_default_acl)
    LOOP
        IF pg_has_role(current_user, r.rolname, 'USAGE') THEN
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
                'REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated', r.rolname);
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
                'REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated', r.rolname);
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
                'REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated', r.rolname);
            -- Mặc định toàn cục của Postgres: EXECUTE cho PUBLIC trên hàm mới.
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I '
                'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC', r.rolname);
        ELSIF EXISTS (
            SELECT 1
              FROM pg_default_acl d
              CROSS JOIN LATERAL aclexplode(d.defaclacl) a
             WHERE d.defaclrole = (SELECT oid FROM pg_roles WHERE rolname = r.rolname)
               AND a.grantee IN (0,
                   (SELECT oid FROM pg_roles WHERE rolname = 'anon'),
                   (SELECT oid FROM pg_roles WHERE rolname = 'authenticated'))
        ) THEN
            RAISE EXCEPTION
                'khoa_rest_v1: % không thu được quyền mặc định của vai % (còn mở cho anon/authenticated) — áp bằng vai đủ quyền',
                current_user, r.rolname;
        END IF;
    END LOOP;
END
$mac_dinh$;

-- ---------------------------------------------------------------------------
-- 2. Chỉ cấp lại đúng các cột giao diện đọc
-- ---------------------------------------------------------------------------
-- Không CCCD, SĐT, ngày sinh, số CCHN, tên. Thêm cột ở đây = mở thêm ra Internet;
-- bài canh src/tests/services/test_khoa_rest_v1_db.py giữ danh sách cố định.
GRANT SELECT (id, auth_user_id, is_active, primary_department)
    ON public.staff TO authenticated;
GRANT SELECT (clinic_id, staff_id, role, is_active)
    ON public.clinic_membership TO authenticated;

-- ---------------------------------------------------------------------------
-- 3. Chính sách đọc: chỉ hàng của chính mình
-- ---------------------------------------------------------------------------
-- Bỏ MỌI policy cho phép (permissive) trên hai bảng — cũ là
-- staff_select_own_clinic (cả phòng khám) và clinic_membership_select_own (cả
-- phòng khám). Policy hạn chế (restrictive) chỉ hẹp thêm, giữ nguyên.
DO $bo_policy$
DECLARE
    p record;
BEGIN
    FOR p IN
        SELECT pol.polname, c.relname
          FROM pg_policy pol
          JOIN pg_class c ON c.oid = pol.polrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN ('staff', 'clinic_membership')
           AND pol.polpermissive
    LOOP
        EXECUTE format('DROP POLICY %I ON public.%I', p.polname, p.relname);
    END LOOP;
END
$bo_policy$;

ALTER TABLE public.staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_membership ENABLE ROW LEVEL SECURITY;

-- Không lọc is_active: màn đăng nhập phải thấy hàng của mình kể cả khi đã nghỉ
-- để báo đúng câu (resolveLinkedStaffAuthority). Không gọi hàm public nào —
-- chỉ auth.uid() (schema auth, không bị thu ở trên).
CREATE POLICY staff_select_chinh_minh ON public.staff
    FOR SELECT TO authenticated
    USING (auth_user_id = auth.uid());

-- Truy vấn con chạy dưới quyền người gọi → đi qua policy staff ở trên, và chỉ
-- cần SELECT(id, auth_user_id) vừa cấp.
CREATE POLICY clinic_membership_select_chinh_minh ON public.clinic_membership
    FOR SELECT TO authenticated
    USING (staff_id IN (
        SELECT s.id FROM public.staff s WHERE s.auth_user_id = auth.uid()
    ));

-- ---------------------------------------------------------------------------
-- 4. EXECUTE hàm: chỉ giữ hàm mà policy RLS còn gọi
-- ---------------------------------------------------------------------------
-- Policy của ~130 bảng khác VẪN GIỮ làm lớp thứ hai: lỡ sau này ai GRANT lại một
-- bảng thì policy vẫn lọc theo phòng khám/vai, thay vì đổ lỗi hoặc mở toang. Muốn
-- vậy `authenticated` phải gọi được đúng các hàm chúng dùng (đếm trong
-- pg_policies 22/10). Cả năm hàm chỉ trả thông tin VỀ CHÍNH NGƯỜI GỌI:
--   current_staff_id()                    id nhân viên của mình       (2 policy)
--   current_clinic_ids()                  phòng khám của mình         (133 policy)
--   current_clinic_ids_for_roles(text[])  phòng khám của mình theo vai (3 policy;
--                                         + current_clinical_clinic_ids gọi nó,
--                                         hàm đó là SECURITY INVOKER)
--   current_clinical_clinic_ids()         phòng khám mình có vai lâm sàng (9 policy)
--   thu_ky_duoc_xem_khach(uuid, uuid)     mình (thư ký) có được xem khách này
--                                         không — true/false            (11 policy)
-- Thu (trước đây authenticated gọi được qua /rpc): clinic_hours_for_date,
-- resolve_effective_cap(s), la_ca_kham_bac_si, current_clinic_roles,
-- read_prescription_draft — không policy nào gọi, giao diện không .rpc() nào;
-- FastAPI gọi chúng bằng chủ database nên không ảnh hưởng.
GRANT EXECUTE ON FUNCTION
    public.current_staff_id(),
    public.current_clinic_ids(),
    public.current_clinic_ids_for_roles(text[]),
    public.current_clinical_clinic_ids(),
    public.thu_ky_duoc_xem_khach(uuid, uuid)
TO authenticated;

-- service_role (backend tin cậy) giữ nguyên mọi quyền — câu trên không đụng nó.

NOTIFY pgrst, 'reload schema';
COMMIT;
