-- ĐIỀU DƯỠNG + THƯ KÝ Y KHOA TRỌN QUYỀN Ở MỌI PHÒNG (Tuyền 29/09/2026).
--
-- Lỗi thật trên prod: ĐD/TKYK không điền được ở phòng Lấy mẫu, Thủ thuật, Đo
-- sinh hiệu, Đối tác… — phải mượn tài khoản Quản lý. Nguyên nhân: quyền làm dịch
-- vụ của họ chỉ đến từ kỹ năng (theo TỪNG phòng) hoặc từ lịch hôm nay (đúng phòng
-- được xếp); gói mẫu TKYK thiếu Đo sinh hiệu / Đối tác / Hoàn tất khám / Duyệt
-- kết quả. Tuyền: "mở full quyền cho họ".
--
-- Cấp (phạm vi TOÀN PHÒNG KHÁM) cho mọi tài khoản đang hoạt động vai
-- NURSE_ULTRASOUND hoặc TKYK các khối: sinh_hieu, chi_dinh, dieu_phoi, kham,
-- ghi_benh_an, hoan_tat_kham, thuc_hien, ket_qua, duyet_ket_qua, doi_tac.
-- Gói mẫu trong DB (`quyen_preset`) thêm cùng các khối để tài khoản tạo sau cũng
-- có. Chỉ THÊM, không thu gì; chạy lại được.

INSERT INTO capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, tu_preset,
     ly_do)
SELECT DISTINCT m.clinic_id, m.staff_id, c.ma, 'CLINIC', NULL::uuid,
       c.work_pack, m.role,
       'ĐD/TKYK trọn quyền ở mọi phòng (Tuyền 29/09/2026)'
  FROM public.clinic_membership m
  JOIN public.staff s ON s.id = m.staff_id AND s.is_active
  JOIN public.capability c
    ON c.work_pack = ANY (ARRAY['sinh_hieu', 'chi_dinh', 'dieu_phoi', 'kham',
                                'ghi_benh_an', 'hoan_tat_kham', 'thuc_hien',
                                'ket_qua', 'duyet_ket_qua', 'doi_tac'])
 WHERE m.is_active
   AND m.role IN ('NURSE_ULTRASOUND', 'TKYK')
ON CONFLICT DO NOTHING;

UPDATE quyen_preset p
   SET khoi = (
       SELECT array_agg(DISTINCT k ORDER BY k)
         FROM unnest(p.khoi || ARRAY['sinh_hieu', 'chi_dinh', 'dieu_phoi',
                                     'kham', 'ghi_benh_an', 'hoan_tat_kham',
                                     'thuc_hien', 'ket_qua', 'duyet_ket_qua',
                                     'doi_tac']) AS k)
 WHERE p.ma IN ('NURSE_ULTRASOUND', 'TKYK');
