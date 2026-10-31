-- Tách quyền sửa giá thuốc khỏi quyền giao thuốc (Tuyền 31/10/2026).
--
-- Trước: ai có `pharmacy.dispense` (67/69 tài khoản) đều đổi được giá bán thuốc.
-- Nay giá đi theo khối `gia_thuoc`, mặc định chỉ Quản lý, cấp thêm ở màn Phân quyền.
-- Người đang có quyền Duyệt vật tư được cấp sẵn để không ai đang dùng bị chặn.
--
-- Chạy lại được (ON CONFLICT), không BEGIN/COMMIT.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('gia_thuoc', 'Sửa giá thuốc', 'catalogue',
     'Đổi giá bán thuốc và giá theo từng đơn vị bán — mặc định Quản lý')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('price.medicine.manage', 'Sửa giá bán thuốc', 'gia_thuoc', 'catalogue', 'financial', false)
ON CONFLICT (ma) DO NOTHING;

UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['gia_thuoc']) AS k)
 WHERE p.he_thong
   AND p.ma = 'MANAGEMENT'
   AND NOT (p.khoi @> ARRAY['gia_thuoc']);

INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, tu_preset, ly_do)
SELECT DISTINCT g.clinic_id, g.staff_id, 'price.medicine.manage', 'CLINIC', NULL::uuid,
       'gia_thuoc', g.tu_preset, 'Tách quyền sửa giá thuốc (Tuyền 31/10/2026)'
  FROM public.capability_grant g
  JOIN public.staff s ON s.id = g.staff_id AND s.is_active
 WHERE g.capability = 'vat_tu.approve'
   AND g.revoked_at IS NULL
   AND (g.valid_until IS NULL OR g.valid_until > now())
ON CONFLICT DO NOTHING;
