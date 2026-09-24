-- Thu ngân có khối Điều phối (Tuyền chốt 24/09/2026).
--
-- Trước: lễ tân thu tiền dịch vụ thì khách TỰ được xếp phòng (dây H4 hỏi quyền
-- người thu), còn thu ngân thu thì phải chờ trưởng ca xếp tay — vì nhóm mẫu
-- Thu ngân không có khối `dieu_phoi`. Tuyền: thu ngân là một nút của quầy lễ
-- tân, quyền đi theo khối/module chứ không theo tên vai.
--
-- Chỉ hai nhóm thu TIỀN DỊCH VỤ; thu ngân nhà thuốc không thu dịch vụ nên không
-- cần. Khớp PRESET trong permissions/catalogue.py (test_danh_muc_quyen_db so).
-- Chạy lại được.

UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['dieu_phoi']) AS k)
 WHERE p.ma IN ('CASHIER', 'CASHIER_DV') AND p.he_thong
   AND NOT ('dieu_phoi' = ANY (p.khoi));

-- Người đang làm nhận khối mới theo nhóm (ai đã bị quản lý thu thì giữ nguyên).
SELECT public.cap_quyen_cho_moi_thanh_vien();
