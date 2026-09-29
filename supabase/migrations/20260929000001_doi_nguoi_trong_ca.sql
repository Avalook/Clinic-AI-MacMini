-- ĐỔI NGƯỜI TRONG CA (Tuyền 29/09/2026).
--
-- Kịch bản thật: điều dưỡng Hà đứng Phòng siêu âm 1, giữa ca có việc phải về;
-- trưởng ca xếp B vào thay. Trước migration này:
--   · trưởng ca KHÔNG ghi được lịch — mọi lệnh ghi lịch đòi `config.clinic.manage`
--     (lego "Cài đặt phòng khám", quá rộng để cấp cho trưởng ca);
--   · không có lệnh "thay": xoá Hà rồi thêm B, quên xoá thì Hà giữ trọn quyền
--     phòng cả ngày, và không còn dấu vết Hà đã đứng buổi sáng;
--   · người xếp vào phòng dịch vụ thiếu khối xếp phòng + xem lịch so với người
--     đứng chính (Tuyền: "người khác vào cùng cũng để giúp người đó full tính năng");
--   · tiền tố `DICHVU-` khớp luôn `DICHVU-THUOC` — dược sĩ đứng kho được duyệt
--     kết quả toàn phòng khám;
--   · vị trí trưởng ca (`DIEU_PHOI`) không gắn phòng nên xếp lịch không mở khối
--     Điều phối.
--
-- 1. Quyền `roster.shift.swap` trong khối `truong_ca` (lego Điều phối khách) —
--    lego thật: quản lý bật/tắt cho từng tài khoản ở màn Phân quyền. Cấp bù cho
--    ai đang giữ khối ấy (grant lưu theo từng quyền, không theo khối).
-- 2. Sổ `work_roster_thay_nguoi`: ai thay ai, lúc nào, ai đổi. Dòng lịch giữ
--    nguyên và đổi người (mọi chỗ đọc lịch — quyền, thanh bên, bác sĩ cùng phòng —
--    thấy người mới ngay, không phải sửa từng chỗ đọc); vết người cũ nằm ở sổ này.
-- 3. `v_quyen_thuc_te` viết lại với bảng tra đã sửa.

-- ── 1. Quyền mới ────────────────────────────────────────────────────────────
INSERT INTO capability (ma, ten, work_pack, module, rui_ro)
VALUES ('roster.shift.swap',
        'Đổi người trong ca (hôm nay và các ngày tới)',
        'truong_ca', 'roster', 'operational')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, tu_preset,
     ly_do)
SELECT DISTINCT a.clinic_id, a.staff_id, 'roster.shift.swap', 'CLINIC',
       NULL::uuid, 'truong_ca', NULL::text,
       'Quyền mới của khối Điều phối ca (29/09/2026) — cấp bù cho người đang có khối / vai trưởng ca'
  FROM (
        -- Ai đang giữ khối trưởng ca (lego Điều phối khách).
        SELECT g.clinic_id, g.staff_id
          FROM public.capability_grant g
         WHERE g.capability = 'dispatch.manage'
           AND g.scope_type = 'CLINIC'
           AND g.revoked_at IS NULL
           AND (g.valid_until IS NULL OR g.valid_until > now())
        UNION
        -- Và mọi tài khoản vai Trưởng ca đang hoạt động — trên prod tài khoản
        -- trưởng ca phải đổi được người ngay sau deploy, kể cả khi lego của nó
        -- từng bị chỉnh tay.
        SELECT m.clinic_id, m.staff_id
          FROM public.clinic_membership m
          JOIN public.staff s ON s.id = m.staff_id AND s.is_active
         WHERE m.role = 'TRUONG_CA' AND m.is_active
       ) a
ON CONFLICT DO NOTHING;

-- Đổi người phải NHÌN được lịch: ai vừa có quyền đổi người mà thiếu quyền xem
-- lịch (lego Lịch làm việc — preset trưởng ca vốn có) thì cấp kèm.
INSERT INTO capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, ly_do)
SELECT DISTINCT g.clinic_id, g.staff_id, c.ma, 'CLINIC', NULL::uuid,
       'lich_lam_viec',
       'Kèm quyền Đổi người trong ca (29/09/2026) — phải xem được lịch mới đổi được'
  FROM public.capability_grant g
  JOIN public.capability c ON c.work_pack = 'lich_lam_viec'
 WHERE g.capability = 'roster.shift.swap'
   AND g.revoked_at IS NULL
ON CONFLICT DO NOTHING;

-- ── 2. Sổ thay người ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.work_roster_thay_nguoi (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    -- Dòng lịch bị xoá sau này thì vết vẫn còn (ngày, ca, vị trí chép lại).
    roster_id     uuid REFERENCES public.work_roster (id) ON DELETE SET NULL,
    work_date     date NOT NULL,
    shift         text NOT NULL,
    station       text NOT NULL,
    nguoi_cu_id   uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    nguoi_cu_ten  text NOT NULL,
    nguoi_moi_id  uuid NOT NULL REFERENCES public.staff (id),
    nguoi_moi_ten text NOT NULL,
    luc           timestamptz NOT NULL DEFAULT now(),
    boi_staff_id  uuid NOT NULL REFERENCES public.staff (id),
    ly_do         text CHECK (ly_do IS NULL OR length(ly_do) <= 500),
    CONSTRAINT work_roster_thay_nguoi_khac_nguoi
        CHECK (nguoi_cu_id IS NULL OR nguoi_cu_id <> nguoi_moi_id)
);

CREATE INDEX IF NOT EXISTS ix_work_roster_thay_nguoi_ngay
    ON public.work_roster_thay_nguoi (clinic_id, work_date);
CREATE INDEX IF NOT EXISTS ix_work_roster_thay_nguoi_dong
    ON public.work_roster_thay_nguoi (roster_id) WHERE roster_id IS NOT NULL;

COMMENT ON TABLE public.work_roster_thay_nguoi IS
'Vết đổi người trong ca (29/09/2026): dòng lịch đổi sang người mới, sổ này giữ người cũ đứng tới lúc nào và ai đổi. Chỉ thêm.';

ALTER TABLE public.work_roster_thay_nguoi ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS work_roster_thay_nguoi_select_own_clinic
    ON public.work_roster_thay_nguoi;
CREATE POLICY work_roster_thay_nguoi_select_own_clinic
    ON public.work_roster_thay_nguoi
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.work_roster_thay_nguoi TO service_role;

-- ── 3. Bảng tra lịch → khối, viết lại ───────────────────────────────────────
-- `lego` = lego mà các khối được chép từ đó. `_them` = khối LẺ cộng thêm (không
-- trọn một lego): người xếp vào phòng dịch vụ được xếp phòng (`dieu_phoi`) như
-- người đứng chính, nhưng không được cả lego Điều phối (điều phối ca).
CREATE OR REPLACE FUNCTION public.quyen_theo_lich_bang()
RETURNS TABLE (tien_to text, lego text, work_pack text, theo_phong boolean)
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT * FROM (VALUES
        -- Phòng dịch vụ: khối làm dịch vụ chỉ ở ĐÚNG phòng ấy (như lego 5).
        ('DICHVU-',     'phong',          'thuc_hien',      true),
        ('DICHVU-',     'phong',          'ket_qua',        false),
        ('DICHVU-',     'phong',          'ghi_benh_an',    false),
        ('DICHVU-',     'phong',          'duyet_ket_qua',  false),
        ('DICHVU-',     '_them',          'dieu_phoi',      false),
        -- Phòng bác sĩ chính (Bàn khám).
        ('KHAM-',       'ban_kham',       'kham',           false),
        ('KHAM-',       'ban_kham',       'chi_dinh',       false),
        ('KHAM-',       'ban_kham',       'ghi_benh_an',    false),
        ('KHAM-',       'ban_kham',       'hoan_tat_kham',  false),
        ('KHAM-',       'ban_kham',       'ket_qua',        false),
        ('KHAM-',       'ban_kham',       'duyet_ket_qua',  false),
        -- Bác sĩ tư vấn.
        ('LUOTKHAM-02', 'tu_van',         'tu_van',         false),
        ('LUOTKHAM-02', 'tu_van',         'ghi_benh_an',    false),
        -- Đo sinh hiệu.
        ('LUOTKHAM-03', 'do_sinh_hieu',   'sinh_hieu',      false),
        -- Quầy lễ tân: tiếp đón + thu tiền (dịch vụ, thuốc).
        ('LUOTKHAM-01', 'tiep_don',       'tiep_don',       false),
        ('LUOTKHAM-01', 'thu_tien_dv',    'thu_tien_dv',    false),
        ('LUOTKHAM-01', 'thu_tien_dv',    'chon_dich_vu',   false),
        ('LUOTKHAM-01', 'thu_tien_dv',    'dieu_phoi',      false),
        ('LUOTKHAM-01', 'thu_tien_thuoc', 'thu_tien_thuoc', false),
        ('LUOTKHAM-14', 'tiep_don',       'tiep_don',       false),
        -- Kho thuốc: nhà thuốc + thu tiền thuốc.
        ('THUOC-',      'kho_thuoc',      'nha_thuoc',      false),
        ('THUOC-',      'kho_thuoc',      'xem_nha_thuoc',  false),
        ('THUOC-',      'thu_tien_thuoc', 'thu_tien_thuoc', false),
        ('DICHVU-THUOC', 'kho_thuoc',     'nha_thuoc',      false),
        ('DICHVU-THUOC', 'kho_thuoc',     'xem_nha_thuoc',  false)
    ) AS t(tien_to, lego, work_pack, theo_phong)
$fn$;

COMMENT ON FUNCTION public.quyen_theo_lich_bang() IS
'Phòng (theo mã việc của phòng) → khối lego được mở cho người xếp lịch ở phòng ấy hôm nay. Khớp tiền tố DÀI NHẤT (DICHVU-THUOC không ăn khối của DICHVU-). Khối chép từ permissions/catalogue.py.';

-- Vị trí KHÔNG gắn phòng mà vẫn là một việc trọn vẹn: trưởng ca.
CREATE OR REPLACE FUNCTION public.quyen_theo_vi_tri_bang()
RETURNS TABLE (ma_vi_tri text, lego text, work_pack text)
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT * FROM (VALUES
        ('DIEU_PHOI', 'dieu_phoi', 'truong_ca'),
        ('DIEU_PHOI', 'dieu_phoi', 'dieu_phoi')
    ) AS t(ma_vi_tri, lego, work_pack)
$fn$;

COMMENT ON FUNCTION public.quyen_theo_vi_tri_bang() IS
'Vị trí không gắn phòng → khối lego mở cho người xếp lịch ở vị trí ấy hôm nay (29/09/2026).';

CREATE OR REPLACE VIEW public.v_quyen_thuc_te AS
WITH lich_hom_nay AS (
    SELECT w.clinic_id, w.staff_id, w.station
      FROM public.work_roster w
     WHERE w.staff_id IS NOT NULL
       AND w.status <> 'REJECTED'
       AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
), phong_hom_nay AS (
    SELECT DISTINCT l.clinic_id, l.staff_id, r.id AS room_id, r.la_doi_tac
      FROM lich_hom_nay l
      JOIN public.vi_tri_lam_viec v
        ON v.clinic_id = l.clinic_id AND v.code = l.station
       AND v.is_active AND v.room_id IS NOT NULL
      JOIN public.clinic_room r
        ON r.id = v.room_id AND r.clinic_id = v.clinic_id AND r.is_active
), khop AS (
    -- Mỗi node của phòng chỉ khớp tiền tố DÀI NHẤT trong bảng tra.
    SELECT DISTINCT ON (p.clinic_id, p.staff_id, p.room_id, rn.node_code)
           p.clinic_id, p.staff_id, p.room_id, rn.node_code, b.tien_to
      FROM phong_hom_nay p
      JOIN public.clinic_room_node rn
        ON rn.room_id = p.room_id AND rn.clinic_id = p.clinic_id
      JOIN (SELECT DISTINCT tien_to FROM public.quyen_theo_lich_bang()) b
        ON rn.node_code LIKE b.tien_to || '%'
     ORDER BY p.clinic_id, p.staff_id, p.room_id, rn.node_code,
              length(b.tien_to) DESC
)
SELECT q.clinic_id, q.staff_id, q.capability, q.work_pack, q.scope_type, q.scope_id
  FROM public.v_quyen_hieu_luc q
UNION
SELECT l.clinic_id, l.staff_id, c.ma AS capability, c.work_pack,
       CASE WHEN l.theo_phong THEN 'ROOM' ELSE 'CLINIC' END AS scope_type,
       CASE WHEN l.theo_phong THEN l.room_id END AS scope_id
  FROM (
        -- Phòng có việc (theo node của phòng).
        SELECT DISTINCT k.clinic_id, k.staff_id, k.room_id, b.work_pack,
               b.theo_phong
          FROM khop k
          JOIN public.quyen_theo_lich_bang() b ON b.tien_to = k.tien_to
        UNION
        -- Phòng đối tác: người phòng khám đứng đó thao tác hộ đối tác.
        SELECT DISTINCT p.clinic_id, p.staff_id, p.room_id, 'doi_tac', false
          FROM phong_hom_nay p
         WHERE p.la_doi_tac
        UNION
        -- Vị trí không gắn phòng (trưởng ca).
        SELECT DISTINCT l.clinic_id, l.staff_id, NULL::uuid, b.work_pack, false
          FROM lich_hom_nay l
          JOIN public.vi_tri_lam_viec v
            ON v.clinic_id = l.clinic_id AND v.code = l.station AND v.is_active
          JOIN public.quyen_theo_vi_tri_bang() b ON b.ma_vi_tri = l.station
        UNION
        -- Có ca hôm nay thì xem được Lịch làm việc.
        SELECT DISTINCT l.clinic_id, l.staff_id, NULL::uuid, 'lich_lam_viec', false
          FROM lich_hom_nay l
       ) l
  JOIN public.capability c ON c.work_pack = l.work_pack;

COMMENT ON VIEW public.v_quyen_thuc_te IS
'Quyền thực tế = quyền đã cấp ∪ quyền theo lịch hôm nay (xếp vào phòng = toàn quyền phòng ấy + xếp phòng; vị trí trưởng ca = Điều phối; có ca = xem lịch). 29/09/2026. Cửa hỏi quyền đọc view này.';

GRANT SELECT ON public.v_quyen_thuc_te TO authenticated, service_role;
