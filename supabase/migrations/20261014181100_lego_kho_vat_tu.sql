-- Lego "Kho vật tư" (Tuyền 14/10/2026): màn riêng, KHÔNG suy từ lego Kho thuốc.
-- Quyền đi theo MÀN (một khối, một quyền): xem/lập phiếu/sửa mức tối thiểu/báo cáo.
-- Khớp `permissions/catalogue.py` (test_danh_muc_quyen_db). Chỉ thêm; chạy lại được.
INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('kho_vat_tu', 'Kho vật tư', 'supplies',
     'Phiếu kho, kiểm đếm, mức tối thiểu, báo cáo tiêu hao vật tư')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('vat_tu.manage', 'Kho vật tư: phiếu kho, kiểm đếm, mức tối thiểu, báo cáo tiêu hao',
     'kho_vat_tu', 'supplies', 'operational', false)
ON CONFLICT (ma) DO NOTHING;

-- Nhóm mẫu hệ thống (mọi vai nội bộ đều có khối mở full; đối tác thì không).
UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['kho_vat_tu']) AS k)
 WHERE p.he_thong
   AND p.ma NOT IN ('PARTNER', 'DISPLAY')
   AND NOT (p.khoi @> ARRAY['kho_vat_tu']);

-- Người đang làm (trừ đối tác/màn hình) nhận quyền mới, phạm vi cả phòng khám.
INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, tu_preset, ly_do)
SELECT DISTINCT m.clinic_id, m.staff_id, 'vat_tu.manage', 'CLINIC', NULL::uuid,
       'kho_vat_tu', m.role, 'Lego Kho vật tư (Tuyền 14/10/2026)'
  FROM public.clinic_membership m
  JOIN public.staff s ON s.id = m.staff_id AND s.is_active
 WHERE m.is_active AND m.role NOT IN ('PARTNER', 'DISPLAY')
ON CONFLICT DO NOTHING;
