-- Quyền XEM bảng giá dịch vụ & phòng (Tuyền 11/11/2026).
--
-- Trước: muốn mở màn `/cashier/dich-vu` chỉ có lego Bảng giá = quyền SỬA giá
-- (`price.service.manage`). Kế toán cần xem giá mà không được sửa.
-- Khối `xem_bang_gia` vào nhóm mẫu Quản lý (có mọi khối) và hai nhóm mẫu Kế toán
-- (`KE_TOAN`, vai `ACCOUNTANT`). KHÔNG cấp cho tài khoản nào — quản lý bật trên
-- màn Phân quyền cho đúng người.
--
-- Chạy lại được (ON CONFLICT / điều kiện NOT @>), không BEGIN/COMMIT.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('xem_bang_gia', 'Xem bảng giá', 'catalogue',
     'Xem bảng giá dịch vụ & phòng, không sửa được — vd kế toán')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('price.service.view', 'Xem bảng giá dịch vụ', 'xem_bang_gia', 'catalogue',
     'operational', false)
ON CONFLICT (ma) DO NOTHING;

UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['xem_bang_gia']) AS k)
 WHERE p.he_thong
   AND p.ma IN ('MANAGEMENT', 'KE_TOAN', 'ACCOUNTANT')
   AND NOT (p.khoi @> ARRAY['xem_bang_gia']);
