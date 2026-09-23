-- Thu tiền thuốc · nhà thuốc · đặt lịch · quản lý lịch hỏi QUYỀN, không hỏi vai
-- (24/09/2026, nợ "~150 chỗ hỏi vai ngoài đường khám chính").
--
-- Năm khối mới, tách theo ĐÚNG tập vai code đang cho phép để không ai được/mất
-- việc khi chuyển:
--
--   thu_tien_thuoc  payment.medicine.collect  CASHIER, CASHIER_THUOC, PHARMACIST,
--                                             RECEPTION, MANAGEMENT (allowed_kinds)
--   nha_thuoc       pharmacy.dispense         RECEPTION, PHARMACIST, MANAGEMENT
--                                             (VAI_GHI_NHA_THUOC)
--   xem_nha_thuoc   pharmacy.view             + CASHIER_THUOC, TRUONG_CA (_DOC)
--   dat_lich        booking.create            CSKH, RECEPTION, MANAGEMENT, TRUONG_CA
--                                             (INTAKE_ROLES)
--   quan_ly_lich    booking.manage            CSKH, MANAGEMENT, TRUONG_CA
--                                             (MANAGE_ROLES: huỷ / dời / gán bác sĩ)
--
-- Hai nhóm mẫu HỆ THỐNG còn thiếu: PHARMACIST (Dược sĩ) và CSKH — trước đây vai
-- này không có dòng `quyen_preset` nên không nhận quyền nào theo preset.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('thu_tien_thuoc', 'Thu tiền thuốc', 'payment', 'Thu và huỷ phiếu tiền thuốc'),
    ('nha_thuoc', 'Nhà thuốc', 'pharmacy',
     'Giao thuốc, từ chối, nhập / điều chỉnh / huỷ lô, khách trả thuốc'),
    ('xem_nha_thuoc', 'Xem nhà thuốc', 'pharmacy',
     'Xem hàng chờ quầy thuốc, đơn bán, tồn kho'),
    ('dat_lich', 'Đặt lịch', 'booking', 'Đặt lịch, giữ chỗ, xác nhận lịch cũ'),
    ('quan_ly_lich', 'Quản lý lịch hẹn', 'booking',
     'Huỷ lịch, dời lịch, gán / đổi bác sĩ cho lịch')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('payment.medicine.collect', 'Thu tiền thuốc',
     'thu_tien_thuoc', 'payment', 'financial', false),
    ('pharmacy.dispense', 'Giao thuốc và quản lý lô thuốc',
     'nha_thuoc', 'pharmacy', 'operational', false),
    ('pharmacy.view', 'Xem quầy thuốc và tồn kho',
     'xem_nha_thuoc', 'pharmacy', 'operational', false),
    ('booking.create', 'Đặt lịch và giữ chỗ',
     'dat_lich', 'booking', 'operational', false),
    ('booking.manage', 'Huỷ / dời lịch, gán bác sĩ cho lịch',
     'quan_ly_lich', 'booking', 'operational', false)
ON CONFLICT (ma) DO NOTHING;

-- Nhóm mẫu mới cho hai vai chưa có.
INSERT INTO public.quyen_preset (clinic_id, ma, ten, khoi, he_thong, mo_ta)
SELECT c.id, v.ma, v.ten, v.khoi, true, 'Nhóm dựng sẵn theo vai'
  FROM public.clinic c
 CROSS JOIN (VALUES
    ('PHARMACIST', 'Dược sĩ', ARRAY['thu_tien_thuoc', 'nha_thuoc', 'xem_nha_thuoc']),
    ('CSKH', 'Chăm sóc khách hàng', ARRAY['dat_lich', 'quan_ly_lich'])
 ) AS v(ma, ten, khoi)
ON CONFLICT DO NOTHING;

-- Thêm khối vào nhóm mẫu HỆ THỐNG đang có (chỉ thêm, không ghi đè; chạy lại
-- không nhân đôi).
UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || v.them) AS k)
  FROM (VALUES
          ('RECEPTION', ARRAY['thu_tien_thuoc', 'nha_thuoc', 'xem_nha_thuoc', 'dat_lich']),
          ('CASHIER', ARRAY['thu_tien_thuoc']),
          ('CASHIER_THUOC', ARRAY['thu_tien_thuoc', 'xem_nha_thuoc']),
          ('TRUONG_CA', ARRAY['xem_nha_thuoc', 'dat_lich', 'quan_ly_lich']),
          ('MANAGEMENT', ARRAY['thu_tien_thuoc', 'nha_thuoc', 'xem_nha_thuoc',
                               'dat_lich', 'quan_ly_lich'])
       ) AS v(ma, them)
 WHERE p.ma = v.ma AND p.he_thong
   AND NOT (p.khoi @> v.them);

-- Người đang làm nhận các khối mới theo vai (ai đã có / đã bị thu thì giữ nguyên).
SELECT public.cap_quyen_cho_moi_thanh_vien();
