-- Quyền khởi động: người nào vào hệ thống cũng có quyền theo vai, và phòng khám
-- không bao giờ mất người cấp quyền (CORE-B, 23/09/2026).
--
-- VÌ SAO. Audit 23/09 gọi `can()` thật trên stack local: cả 12 tài khoản thử có
-- 0 quyền — bác sĩ không đặt được chỉ định, và quản lý KHÔNG có
-- `permission.manage`, tức là không ai cấp quyền được cho ai. Nguyên nhân: chỉ
-- đường "thêm nhân sự trên màn" mới cấp preset; fixture và ba script tạo tài
-- khoản chèn thẳng `clinic_membership` mà không cấp gì.
--
-- 1. `cap_quyen_theo_preset()` — MỘT chỗ cấp preset, cho Python, fixture và
--    script. Bỏ qua mọi quyền người đó TỪNG có (kể cả đã bị thu): chạy lại
--    không được lẳng lặng bật lại thứ quản lý đã chủ ý tắt. (Khoá duy nhất của
--    `capability_grant` chỉ canh dòng CÒN SỐNG, nên ON CONFLICT không đủ.)
--
-- 2. `cap_quyen_cho_moi_thanh_vien()` — chạy hàm trên cho mọi thành viên đang
--    làm. Gọi ở cuối migration này và ở cuối các fixture tạo nhân sự.
--
-- 3. BẤT BIẾN: mỗi phòng khám luôn còn ít nhất một người ĐANG LÀM giữ
--    `permission.manage` (phạm vi toàn phòng khám, không hết hạn). Ép ở
--    Postgres — hai người thu quyền của hai quản lý khác nhau cùng lúc là kẽ
--    tranh chấp, kiểm ở Python sẽ lọt. Trigger chạy lúc COMMIT và khoá dòng
--    phòng khám trước khi đếm, nên giao dịch thứ hai chờ và đếm lại.

CREATE OR REPLACE FUNCTION public.cap_quyen_theo_preset(
    p_clinic uuid,
    p_staff uuid,
    p_vai text,
    p_du_phong text[] DEFAULT '{}',
    p_ly_do text DEFAULT 'Cấp theo preset của vai'
) RETURNS SETOF text
LANGUAGE sql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
    INSERT INTO public.capability_grant
        (clinic_id, staff_id, capability, tu_khoi, tu_preset, ly_do)
    SELECT p_clinic, p_staff, c.ma, c.work_pack, p_vai, p_ly_do
      FROM public.capability c
     WHERE c.work_pack = ANY(
               coalesce((SELECT p.khoi FROM public.quyen_preset p
                          WHERE p.clinic_id = p_clinic AND p.ma = p_vai
                            AND p.active),
                        p_du_phong))
       AND NOT EXISTS (
               SELECT 1 FROM public.capability_grant g
                WHERE g.clinic_id = p_clinic AND g.staff_id = p_staff
                  AND g.capability = c.ma)
    ON CONFLICT DO NOTHING
    RETURNING capability;
$fn$;

COMMENT ON FUNCTION public.cap_quyen_theo_preset(uuid, uuid, text, text[], text) IS
    'Cấp preset của vai. Bỏ qua quyền người đó từng có (kể cả đã thu) — chạy lại không bật lại thứ đã tắt.';

CREATE OR REPLACE FUNCTION public.cap_quyen_cho_moi_thanh_vien()
RETURNS integer
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
    n integer := 0;
    m record;
BEGIN
    FOR m IN
        SELECT cm.clinic_id, cm.staff_id, cm.role
          FROM public.clinic_membership cm
          JOIN public.staff s ON s.id = cm.staff_id AND s.is_active
         WHERE cm.is_active
    LOOP
        n := n + (SELECT count(*) FROM public.cap_quyen_theo_preset(
                      m.clinic_id, m.staff_id, m.role));
    END LOOP;
    RETURN n;
END
$fn$;

-- ── Bất biến: luôn còn người cấp quyền ─────────────────────────────────────

CREATE OR REPLACE FUNCTION public.con_nguoi_cap_quyen(p_clinic uuid)
RETURNS boolean
LANGUAGE sql STABLE
SET search_path TO 'pg_catalog', 'public'
AS $fn$
    SELECT EXISTS (
        SELECT 1
          FROM public.capability_grant g
          JOIN public.staff s ON s.id = g.staff_id AND s.is_active
          JOIN public.clinic_membership m
            ON m.staff_id = g.staff_id AND m.clinic_id = g.clinic_id
           AND m.is_active
         WHERE g.clinic_id = p_clinic
           AND g.capability = 'permission.manage'
           AND g.scope_type = 'CLINIC'
           AND g.revoked_at IS NULL
           AND (g.valid_from IS NULL OR g.valid_from <= now()));
$fn$;

CREATE OR REPLACE FUNCTION public.giu_nguoi_cap_quyen()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
    v_ds uuid[];
    v_clinic uuid;
BEGIN
    -- Chỉ xét phòng khám mà thay đổi này thật sự BỚT một người cấp quyền: dòng
    -- quyền vừa bị thu/xoá, hoặc người đang giữ quyền còn sống vừa nghỉ. Tách
    -- nhánh theo bảng: PL/pgSQL đọc mọi `OLD.<cột>` nhắc tới trong câu, kể cả ở
    -- nhánh CASE không chạy, và mỗi bảng có bộ cột khác nhau.
    IF TG_TABLE_NAME = 'capability_grant' THEN
        v_ds := ARRAY[OLD.clinic_id];
    ELSIF TG_TABLE_NAME = 'clinic_membership' THEN
        v_ds := ARRAY(
            SELECT DISTINCT g.clinic_id FROM public.capability_grant g
             WHERE g.capability = 'permission.manage' AND g.revoked_at IS NULL
               AND g.staff_id = OLD.staff_id AND g.clinic_id = OLD.clinic_id);
    ELSE
        v_ds := ARRAY(
            SELECT DISTINCT g.clinic_id FROM public.capability_grant g
             WHERE g.capability = 'permission.manage' AND g.revoked_at IS NULL
               AND g.staff_id = OLD.id);
    END IF;

    FOREACH v_clinic IN ARRAY v_ds LOOP
        -- Khoá phòng khám rồi mới đếm: giao dịch song song thứ hai chờ ở đây và
        -- đếm lại sau khi giao dịch thứ nhất đã commit.
        PERFORM 1 FROM public.clinic WHERE id = v_clinic FOR UPDATE;
        IF NOT public.con_nguoi_cap_quyen(v_clinic) THEN
            RAISE EXCEPTION USING
                ERRCODE = 'check_violation',
                CONSTRAINT = 'phong_kham_con_nguoi_cap_quyen',
                MESSAGE = 'Phòng khám phải còn ít nhất một người đang làm giữ quyền cấp quyền (permission.manage).';
        END IF;
    END LOOP;
    RETURN NULL;
END
$fn$;

DO $$
BEGIN
    -- Quyền cấp quyền không được tự hết hạn và luôn toàn phòng khám: hết hạn
    -- theo đồng hồ thì không có câu lệnh nào để trigger bắt được.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'capability_grant_cap_quyen_ben_vung'
           AND conrelid = 'public.capability_grant'::regclass
    ) THEN
        ALTER TABLE public.capability_grant
            ADD CONSTRAINT capability_grant_cap_quyen_ben_vung
            CHECK (capability <> 'permission.manage'
                   OR (valid_until IS NULL AND scope_type = 'CLINIC'));
    END IF;
END $$;

DROP TRIGGER IF EXISTS giu_nguoi_cap_quyen_grant_thu ON public.capability_grant;
CREATE CONSTRAINT TRIGGER giu_nguoi_cap_quyen_grant_thu
    AFTER UPDATE ON public.capability_grant
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    WHEN (OLD.capability = 'permission.manage' AND OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL)
    EXECUTE FUNCTION public.giu_nguoi_cap_quyen();

DROP TRIGGER IF EXISTS giu_nguoi_cap_quyen_grant_xoa ON public.capability_grant;
CREATE CONSTRAINT TRIGGER giu_nguoi_cap_quyen_grant_xoa
    AFTER DELETE ON public.capability_grant
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    WHEN (OLD.capability = 'permission.manage' AND OLD.revoked_at IS NULL)
    EXECUTE FUNCTION public.giu_nguoi_cap_quyen();

DROP TRIGGER IF EXISTS giu_nguoi_cap_quyen_membership_nghi ON public.clinic_membership;
CREATE CONSTRAINT TRIGGER giu_nguoi_cap_quyen_membership_nghi
    AFTER UPDATE ON public.clinic_membership
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    WHEN (OLD.is_active AND NOT NEW.is_active)
    EXECUTE FUNCTION public.giu_nguoi_cap_quyen();

DROP TRIGGER IF EXISTS giu_nguoi_cap_quyen_membership_xoa ON public.clinic_membership;
CREATE CONSTRAINT TRIGGER giu_nguoi_cap_quyen_membership_xoa
    AFTER DELETE ON public.clinic_membership
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    WHEN (OLD.is_active)
    EXECUTE FUNCTION public.giu_nguoi_cap_quyen();

DROP TRIGGER IF EXISTS giu_nguoi_cap_quyen_staff_nghi ON public.staff;
CREATE CONSTRAINT TRIGGER giu_nguoi_cap_quyen_staff_nghi
    AFTER UPDATE OF is_active ON public.staff
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    WHEN (OLD.is_active AND NOT NEW.is_active)
    EXECUTE FUNCTION public.giu_nguoi_cap_quyen();

-- Người đang làm mà chưa có quyền theo vai: cấp bù. Người đã có (hoặc đã bị
-- thu) quyền nào thì giữ nguyên quyền ấy.
SELECT public.cap_quyen_cho_moi_thanh_vien();
