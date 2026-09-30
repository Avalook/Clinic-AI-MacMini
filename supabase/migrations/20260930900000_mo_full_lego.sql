-- MỞ FULL LEGO CHO MỌI NHÂN SỰ NỘI BỘ + TẮT QUYỀN THEO LỊCH (Tuyền 30/09/2026).
--
-- Tuyền: "ai ở chỗ nào cũng thanh toán được, không có trong lịch cũng thao tác
-- được, vì chờ trưởng ca đổi lịch không kịp" — và chiều 30/09: "phòng khám chả
-- có quy trình nào, lúc nào, ai thu cũng được… open hết ra, nhân sự có các node
-- gần full để thao tác cho lẹ".
--
-- 1. Cấp (phạm vi TOÀN PHÒNG KHÁM) MỌI capability của MỌI khối cho mọi tài khoản
--    nội bộ đang hoạt động (vai khác PARTNER / DISPLAY), TRỪ bốn khối chỉ Quản lý
--    giữ để khỏi loạn — đúng hai lego "Cài đặt phòng khám" và "Nhân sự & phân
--    quyền":
--      quan_tri_quyen · nhan_su · cai_dat · danh_muc (mẫu kết quả, dây nối —
--      nằm trong lego Cài đặt).
-- 2. Gói mẫu (`quyen_preset`, nhóm dựng sẵn) của mọi vai thêm cùng các khối để
--    tài khoản tạo sau cũng có. Khớp `PRESET` ở `permissions/catalogue.py`
--    (`test_permission_db` so hai bên).
-- 3. Dây nối `quyen_theo_lich` về TẮT: không còn chặn "chưa được xếp lịch ở
--    phòng này".
--
-- Chỉ THÊM, không thu gì; chạy lại được. THU LẠI sau này: mọi dòng cấp ở đây có
-- ly_do 'Mở full lego (Tuyền 30/09/2026)'.

INSERT INTO capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, tu_preset,
     ly_do)
SELECT DISTINCT m.clinic_id, m.staff_id, c.ma, 'CLINIC', NULL::uuid,
       c.work_pack, m.role,
       'Mở full lego (Tuyền 30/09/2026)'
  FROM public.clinic_membership m
  JOIN public.staff s ON s.id = m.staff_id AND s.is_active
  JOIN public.capability c
    ON c.work_pack <> ALL (ARRAY['quan_tri_quyen', 'nhan_su', 'cai_dat',
                                 'danh_muc'])
 WHERE m.is_active
   AND m.role NOT IN ('PARTNER', 'DISPLAY')
ON CONFLICT DO NOTHING;

UPDATE quyen_preset p
   SET khoi = (
       SELECT array_agg(DISTINCT k ORDER BY k)
         FROM unnest(p.khoi || ARRAY(
                  SELECT w.ma FROM public.work_pack w
                   WHERE w.ma <> ALL (ARRAY['quan_tri_quyen', 'nhan_su',
                                            'cai_dat', 'danh_muc'])
              )) AS k)
 WHERE p.he_thong
   AND p.ma NOT IN ('PARTNER', 'DISPLAY');

UPDATE day_nghiep_vu
   SET gia_tri = 'false'::jsonb, sua_luc = now()
 WHERE ma = 'quyen_theo_lich'
   AND gia_tri IS DISTINCT FROM 'false'::jsonb;
