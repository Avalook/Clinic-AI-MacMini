-- TRƯỞNG CA XẾP LỊCH LÀM VIỆC (Tuyền 01/10/2026: "chuyển khả năng đặt lịch làm
-- việc của quản lý hệ thống sang cho trưởng ca").
--
-- Trước migration này: xếp ca, áp dụng tuần, duyệt/xoá ca đều đòi
-- `config.clinic.manage` (lego "Cài đặt phòng khám") — quá rộng để cấp cho
-- trưởng ca (kèm luật đặt lịch, cấu trúc phòng, dây nối...). Trưởng ca chỉ đổi
-- được người trong ca (`roster.shift.swap`, 29/09).
--
-- 1. Quyền `roster.manage` trong khối `truong_ca` (lego Điều phối khách) — lego
--    thật: quản lý bật/tắt từng tài khoản ở /phan-quyen. Người đứng vị trí
--    trưởng ca (`DIEU_PHOI`) hôm nay cũng có qua `v_quyen_thuc_te` (khối
--    `truong_ca` theo lịch) — không phải sửa view.
-- 2. Cấp bù cho ai đang giữ khối ấy + mọi tài khoản vai Trưởng ca (grant lưu
--    theo từng quyền, không theo khối) — y hệt cách cấp `roster.shift.swap`.
-- Người có lego Cài đặt phòng khám VẪN xếp được (máy chủ hỏi một trong hai);
-- phạm vi vị trí (vai nào đứng trạm nào) vẫn chỉ ở lego Cài đặt.

INSERT INTO capability (ma, ten, work_pack, module, rui_ro)
VALUES ('roster.manage',
        'Xếp lịch làm việc (xếp ca, áp dụng tuần)',
        'truong_ca', 'roster', 'operational')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, tu_preset,
     ly_do)
SELECT DISTINCT a.clinic_id, a.staff_id, 'roster.manage', 'CLINIC',
       NULL::uuid, 'truong_ca', NULL::text,
       'Quyền mới của khối Điều phối ca (01/10/2026) — trưởng ca xếp lịch làm việc'
  FROM (
        SELECT g.clinic_id, g.staff_id
          FROM public.capability_grant g
         WHERE g.capability = 'dispatch.manage'
           AND g.scope_type = 'CLINIC'
           AND g.revoked_at IS NULL
           AND (g.valid_until IS NULL OR g.valid_until > now())
        UNION
        SELECT m.clinic_id, m.staff_id
          FROM public.clinic_membership m
          JOIN public.staff s ON s.id = m.staff_id AND s.is_active
         WHERE m.role = 'TRUONG_CA' AND m.is_active
       ) a
ON CONFLICT DO NOTHING;

-- Xếp lịch phải NHÌN được lịch: cấp kèm khối Lịch làm việc cho ai thiếu.
INSERT INTO capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, ly_do)
SELECT DISTINCT g.clinic_id, g.staff_id, c.ma, 'CLINIC', NULL::uuid,
       'lich_lam_viec',
       'Kèm quyền Xếp lịch làm việc (01/10/2026) — phải xem được lịch mới xếp được'
  FROM public.capability_grant g
  JOIN public.capability c ON c.work_pack = 'lich_lam_viec'
 WHERE g.capability = 'roster.manage'
   AND g.revoked_at IS NULL
ON CONFLICT DO NOTHING;
