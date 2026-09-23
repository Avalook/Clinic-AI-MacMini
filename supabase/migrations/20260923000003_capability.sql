-- Quyền theo capability — tài khoản là người, vai chỉ là preset (23/09/2026).
--
-- VÌ SAO. Hôm nay quyền nằm ở VAI: khoảng 50 tập vai chép tay trong service và
-- router, cộng một bản sao nữa trong `roles.ts` phía trình duyệt. Hệ quả đã thấy:
-- muốn cho điều dưỡng điều phối khách thì phải nhớ sửa năm cửa, và quản lý không
-- tự đổi được gì nếu không có người sửa code.
--
-- Mô hình chốt trong chat (#124, #132, #133, #134):
--   TÀI KHOẢN → THUỘC PHÒNG KHÁM → PRESET (chỉ là gói mẫu) → CA/VỊ TRÍ
--   → CAPABILITY + PHẠM VI → lệnh hỏi `can(...)`.
--
-- Hai điều quan trọng nhất, ghi ở đây để sau không phải tra lại chat:
--   1. `default_presets` là GỢI Ý, không phải trần. Quản lý (`permission.manage`)
--      cấp được bất kỳ khối nào cho bất kỳ ai trong phòng khám.
--   2. Preset KHÔNG phải thừa kế sống: bấm "thêm preset Điều dưỡng" là CHÉP một
--      loạt dòng cấp quyền. Sau đó sửa preset không đụng tới người đã cấp.
--
-- Chạy lại được: IF NOT EXISTS / ON CONFLICT DO NOTHING.

-- ── Danh mục khối công việc ────────────────────────────────────────────────
-- Quản lý bật/tắt theo KHỐI (Tuyền #133: "phải nằm trong 1 khối để kích hoạt cả
-- khối"). Quyền con vẫn tồn tại bên dưới để chỗ nào cần chặt thì chặt được.
CREATE TABLE IF NOT EXISTS public.work_pack (
    ma      text PRIMARY KEY,
    ten     text NOT NULL,
    module  text NOT NULL,
    mo_ta   text NOT NULL DEFAULT ''
);

-- ── Danh mục quyền ─────────────────────────────────────────────────────────
-- Bảng này là bản sao trong database của `permissions/catalogue.py`; một test CI
-- so hai bên, lệch là đỏ. Có bảng thì dòng cấp quyền mới khoá ngoại được — cấp
-- một quyền không tồn tại phải hỏng ngay lúc ghi, không phải lúc đọc.
CREATE TABLE IF NOT EXISTS public.capability (
    ma                  text PRIMARY KEY,
    ten                 text NOT NULL,
    work_pack           text NOT NULL REFERENCES public.work_pack(ma),
    module              text NOT NULL,
    rui_ro              text NOT NULL,
    chung_chi_lam_sang  boolean NOT NULL DEFAULT false,
    CONSTRAINT capability_rui_ro
        CHECK (rui_ro IN ('operational', 'financial', 'clinical', 'admin'))
);

-- ── Cấp quyền cho một người ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.capability_grant (
    grant_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    uuid NOT NULL,
    staff_id     uuid NOT NULL REFERENCES public.staff(id) ON DELETE CASCADE,
    capability   text NOT NULL REFERENCES public.capability(ma),

    -- Phạm vi: trống = toàn phòng khám; PHONG = chỉ phòng ấy; CA = chỉ ca ấy.
    scope_type   text NOT NULL DEFAULT 'CLINIC',
    scope_id     uuid,
    valid_from   timestamptz,
    valid_until  timestamptz,

    -- Khối nào sinh ra dòng này (quản lý bật cả khối), để thu hồi cũng theo khối.
    tu_khoi      text REFERENCES public.work_pack(ma),
    -- Preset nào đã chép ra dòng này — chỉ để kể lại, không phải liên kết sống.
    tu_preset    text,

    granted_by   uuid REFERENCES public.staff(id),
    granted_at   timestamptz NOT NULL DEFAULT now(),
    revoked_by   uuid REFERENCES public.staff(id),
    revoked_at   timestamptz,
    ly_do        text,

    CONSTRAINT capability_grant_scope_type
        CHECK (scope_type IN ('CLINIC', 'ROOM', 'SHIFT')),
    -- Phạm vi hẹp thì phải nói rõ hẹp ở đâu.
    CONSTRAINT capability_grant_scope_id
        CHECK ((scope_type = 'CLINIC') = (scope_id IS NULL)),
    CONSTRAINT capability_grant_hieu_luc
        CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from),
    CONSTRAINT capability_grant_thu_hoi
        CHECK ((revoked_at IS NULL) = (revoked_by IS NULL))
);

-- Một người + một quyền + một phạm vi: chỉ một dòng còn sống. Cấp hai lần không
-- tạo hai dòng — ép ở Postgres, không bằng "nhớ kiểm tra trước khi ghi".
CREATE UNIQUE INDEX IF NOT EXISTS uq_capability_grant_song
    ON public.capability_grant (clinic_id, staff_id, capability, scope_type,
                                COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_capability_grant_nguoi
    ON public.capability_grant (clinic_id, staff_id)
    WHERE revoked_at IS NULL;

ALTER TABLE public.work_pack ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.capability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.capability_grant ENABLE ROW LEVEL SECURITY;

-- Danh mục đọc được cho mọi người đã đăng nhập: màn quản lý cần vẽ khối và
-- quyền con. Nó chỉ là tên gọi, không phải dữ liệu bệnh nhân.
DROP POLICY IF EXISTS work_pack_select ON public.work_pack;
CREATE POLICY work_pack_select ON public.work_pack
    FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS capability_select ON public.capability;
CREATE POLICY capability_select ON public.capability
    FOR SELECT TO authenticated USING (true);
-- Ai được cấp gì thì chỉ đọc trong phòng khám của mình.
DROP POLICY IF EXISTS capability_grant_select_own_clinic ON public.capability_grant;
CREATE POLICY capability_grant_select_own_clinic ON public.capability_grant
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));

GRANT SELECT ON public.work_pack, public.capability TO authenticated;
GRANT SELECT ON public.capability_grant TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.work_pack, public.capability TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.capability_grant TO service_role;

-- ── Seed danh mục (khớp với permissions/catalogue.py — CI so hai bên) ───────
INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('tiep_don',        'Tiếp đón',            'reception',         'Đón khách, check-in, khách vãng lai'),
    ('sinh_hieu',       'Sinh hiệu',           'vitals',            'Đo và ghi sinh hiệu'),
    ('chi_dinh',        'Chỉ định dịch vụ',    'service_order',     'Chốt dịch vụ cho khách làm'),
    ('chon_dich_vu',    'Khách chọn dịch vụ',  'service_selection', 'Xác nhận khách đồng ý làm dịch vụ nào'),
    ('dieu_phoi',       'Điều phối khách',     'service_routing',   'Xem tải phòng, xếp phòng'),
    ('thu_tien_dv',     'Thu tiền dịch vụ',    'payment',           'Thu và huỷ phiếu dịch vụ'),
    ('quan_tri_quyen',  'Phân quyền',          'permission',        'Cấp và thu quyền cho nhân sự')
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, module = EXCLUDED.module, mo_ta = EXCLUDED.mo_ta;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('reception.checkin.perform',  'Check-in khách',                    'tiep_don',       'reception',         'operational', false),
    ('vitals.measure',             'Đo sinh hiệu',                      'sinh_hieu',      'vitals',            'operational', false),
    ('clinical.order.place',       'Chỉ định dịch vụ cho khách',        'chi_dinh',       'service_order',     'clinical',    false),
    ('service_selection.confirm',  'Xác nhận khách chọn dịch vụ',       'chon_dich_vu',   'service_selection', 'operational', false),
    ('service.routing.view',       'Xem phòng phù hợp và tải phòng',    'dieu_phoi',      'service_routing',   'operational', false),
    ('service.routing.assign',     'Xếp phòng cho khách',               'dieu_phoi',      'service_routing',   'operational', false),
    ('service.routing.invalidate', 'Huỷ xếp phòng khi phòng hỏng',      'dieu_phoi',      'service_routing',   'operational', false),
    ('payment.service.collect',    'Thu tiền dịch vụ',                  'thu_tien_dv',    'payment',           'financial',   false),
    ('permission.manage',          'Cấp và thu quyền',                  'quan_tri_quyen', 'permission',        'admin',       false)
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, work_pack = EXCLUDED.work_pack, module = EXCLUDED.module,
        rui_ro = EXCLUDED.rui_ro, chung_chi_lam_sang = EXCLUDED.chung_chi_lam_sang;

-- ── Chép preset cho nhân sự đang làm ───────────────────────────────────────
-- Đây là bước chuyển: mọi người đang làm được cấp đúng những quyền mà vai của
-- họ vẫn đang cho phép, nên không ai mất việc giữa ca. Từ giờ trở đi, đổi quyền
-- là việc của quản lý trên màn, không phải của người sửa code.
--
-- `granted_by` để trống = hệ thống chép lúc chuyển, không phải người nào cấp.
INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, tu_khoi, tu_preset, ly_do)
SELECT m.clinic_id, m.staff_id, c.ma, c.work_pack, m.role,
       'Chép từ preset lúc chuyển sang mô hình capability (23/09/2026)'
  FROM public.clinic_membership m
  JOIN LATERAL (
      SELECT unnest(CASE m.role
          WHEN 'DOCTOR'            THEN ARRAY['chi_dinh', 'dieu_phoi']
          WHEN 'TKYK'              THEN ARRAY['chi_dinh', 'dieu_phoi']
          WHEN 'RECEPTION'         THEN ARRAY['tiep_don', 'chon_dich_vu', 'thu_tien_dv', 'dieu_phoi']
          WHEN 'NURSE_ULTRASOUND'  THEN ARRAY['sinh_hieu', 'dieu_phoi']
          WHEN 'CASHIER'           THEN ARRAY['thu_tien_dv', 'chon_dich_vu']
          WHEN 'CASHIER_DV'        THEN ARRAY['thu_tien_dv', 'chon_dich_vu']
          WHEN 'CASHIER_THUOC'     THEN ARRAY['thu_tien_dv']
          WHEN 'TRUONG_CA'         THEN ARRAY['dieu_phoi', 'tiep_don', 'chon_dich_vu']
          WHEN 'ULTRASOUND_DOCTOR' THEN ARRAY['dieu_phoi']
          WHEN 'MANAGEMENT'        THEN ARRAY['tiep_don', 'sinh_hieu', 'chi_dinh',
                                              'chon_dich_vu', 'dieu_phoi',
                                              'thu_tien_dv', 'quan_tri_quyen']
          ELSE ARRAY[]::text[]
      END) AS khoi
  ) AS p ON true
  JOIN public.capability c ON c.work_pack = p.khoi
 WHERE m.is_active
ON CONFLICT DO NOTHING;

-- ── Quyền hiệu lực: một chỗ duy nhất trả lời "người này làm được gì" ───────
-- Màn hình đọc view này để vẽ thanh bên và ẩn nút; backend VẪN kiểm lại ở lệnh.
-- Ẩn nút không phải bảo mật (#132).
CREATE OR REPLACE VIEW public.v_quyen_hieu_luc AS
SELECT g.clinic_id,
       g.staff_id,
       g.capability,
       c.work_pack,
       g.scope_type,
       g.scope_id
  FROM public.capability_grant g
  JOIN public.capability c ON c.ma = g.capability
 WHERE g.revoked_at IS NULL
   AND (g.valid_from IS NULL OR g.valid_from <= now())
   AND (g.valid_until IS NULL OR g.valid_until > now());

GRANT SELECT ON public.v_quyen_hieu_luc TO authenticated, service_role;

COMMENT ON TABLE public.capability_grant IS
    'Quyền THẬT của một người. Vai chỉ là preset để cấp nhanh; quản lý (permission.manage) cấp/thu được mọi khối.';
COMMENT ON VIEW public.v_quyen_hieu_luc IS
    'Quyền còn hiệu lực theo thời gian. UI đọc để vẽ màn; lệnh vẫn phải kiểm lại.';
