-- LEGO "KẾ TOÁN" (G5a · Tuyền 14/10/2026).
--
-- Kế toán xem Dòng tiền đầy đủ, hoá đơn, xuất Excel, thống kê theo hàng hoá,
-- không thu tiền. CHỈ LEGO (Tuyền 27/09): không thêm vai, không đụng CHECK vai.
--   · khối `ke_toan` + quyền `accounting.finance.full` (xem tài chính mọi ca /
--     mọi cơ sở, không cần lịch trực — nhánh capability ở report_access_service);
--   · nhóm mẫu hệ thống "KE_TOAN" = báo cáo + kế toán + danh sách bệnh nhân +
--     lịch làm việc — CỐ Ý không có khối thu tiền dịch vụ / thuốc;
--   · Quản lý (nhóm MANAGEMENT) có khối mới như mọi khối; khối KHÔNG vào
--     "mở full lego" (catalogue.KHOI_CHI_QUAN_LY) nên nhân viên khác không tự có.
--
-- Khớp `permissions/catalogue.py` (test_danh_muc_quyen_db so hai bên).
-- Chạy lại được.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('ke_toan', 'Kế toán', 'accounting',
     'Xem tài chính đầy đủ, hoá đơn, xuất Excel, thống kê theo hàng hoá')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability
    (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('accounting.finance.full',
     'Xem tài chính đầy đủ (Dòng tiền, hoá đơn, theo hàng hoá), mọi ca',
     'ke_toan', 'accounting', 'financial', false)
ON CONFLICT (ma) DO NOTHING;

-- Nhóm mẫu "Kế toán" cho mọi phòng khám (có thì giữ nguyên, không ghi đè).
INSERT INTO public.quyen_preset (clinic_id, ma, ten, khoi, he_thong, mo_ta)
SELECT c.id, 'KE_TOAN', 'Kế toán',
       ARRAY['bao_cao', 'ds_benh_nhan', 'ke_toan', 'lich_lam_viec'],
       true, 'Nhóm dựng sẵn — kế toán không thu tiền'
  FROM public.clinic c
ON CONFLICT DO NOTHING;

-- Quản lý có tất cả các khối.
UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['ke_toan']) AS k)
 WHERE p.ma = 'MANAGEMENT' AND p.he_thong
   AND NOT (p.khoi @> ARRAY['ke_toan']);

-- Người quản lý đang làm nhận khối mới (ai từng thu quyền thì giữ nguyên).
SELECT public.cap_quyen_cho_moi_thanh_vien();
