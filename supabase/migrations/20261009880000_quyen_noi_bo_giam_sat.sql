-- QUYỀN NỘI BỘ: TRUNG TÂM GIÁM SÁT AI (09/10/2026).
--
-- Trung tâm giám sát của agent (giamsat.dr4women.io.vn) là việc của ĐỘI VẬN
-- HÀNH ClinicAI, không phải của phòng khám. Tuyền chốt: chỉ đội Avalook xem;
-- đăng nhập bằng tài khoản ClinicAI + một quyền mà quản lý phòng khám — kể cả
-- người có `permission.manage` — KHÔNG tự cấp được.
--
-- Bốn lớp chặn, mỗi lớp đứng được một mình:
--   1. catalogue.py: khối `noi_bo_giam_sat` không thuộc preset nào, không bày
--      trên màn Phân quyền.
--   2. permission_service: cấp / thu / gom vào nhóm đều từ chối khối này.
--   3. trigger dưới đây: Postgres BỎ dòng `capability_grant` của quyền này nếu
--      phiên không bật cờ `clinicai.cap_noi_bo` — đường cấp nào lọt qua code
--      (SQL tay, hàm cũ, preset) cũng đâm vào đây. BỎ DÒNG + cảnh báo, không ném:
--      các lệnh cấp HÀNG LOẠT cũ (vd migration "mở full lego" 30/09 — cấp mọi
--      khối trừ khối quản lý) chạy lại vẫn xong, chỉ không lọt quyền này.
--   4. API /ops/agent* và trang /giam-sat hỏi đúng quyền này.
--
-- CẤP CHO ĐỘI (chạy tay, email KHÔNG nằm trong git):
--   BEGIN;
--   SET LOCAL clinicai.cap_noi_bo = 'on';
--   INSERT INTO capability_grant (clinic_id, staff_id, capability, scope_type,
--                                 tu_khoi, ly_do)
--   SELECT m.clinic_id, s.id, 'giamsat.view', 'CLINIC', 'noi_bo_giam_sat',
--          'Đội vận hành ClinicAI — trung tâm giám sát'
--     FROM staff s JOIN auth.users u ON u.id = s.auth_user_id
--     JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active
--    WHERE lower(u.email) IN ('email1@…', 'email2@…')
--   ON CONFLICT DO NOTHING;
--   COMMIT;
-- Thu lại: UPDATE capability_grant SET revoked_at = now() WHERE capability =
-- 'giamsat.view' AND staff_id = … (không cần cờ — thu bớt quyền luôn được).

INSERT INTO work_pack (ma, ten, module, mo_ta)
VALUES ('noi_bo_giam_sat', 'Giám sát AI (nội bộ)', 'ops',
        'Trung tâm giám sát agent — chỉ đội vận hành ClinicAI')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO capability (ma, ten, work_pack, module, rui_ro)
VALUES ('giamsat.view', 'Xem trung tâm giám sát AI (nội bộ đội vận hành)',
        'noi_bo_giam_sat', 'ops', 'admin')
ON CONFLICT (ma) DO NOTHING;

CREATE OR REPLACE FUNCTION public.chan_cap_quyen_noi_bo()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    IF NEW.capability = 'giamsat.view'
       AND coalesce(current_setting('clinicai.cap_noi_bo', true), '') <> 'on' THEN
        RAISE WARNING
            'Bỏ qua cấp quyền nội bộ giamsat.view cho staff % — chỉ cấp được bằng cờ phiên clinicai.cap_noi_bo',
            NEW.staff_id;
        RETURN NULL;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_chan_cap_quyen_noi_bo ON public.capability_grant;
CREATE TRIGGER trg_chan_cap_quyen_noi_bo
    BEFORE INSERT OR UPDATE OF capability ON public.capability_grant
    FOR EACH ROW EXECUTE FUNCTION public.chan_cap_quyen_noi_bo();
