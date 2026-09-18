-- THƯ KÝ Y KHOA ĐI KÈM TỪNG BÁC SĨ (Tuyền chốt 17/09/2026): mỗi bác sĩ — chính,
-- thủ thuật, siêu âm — có một thư ký riêng gọi khách, check-in/check-out và nhập
-- liệu. Lịch trước chỉ có "Thư ký y khoa" ở phòng Nội tiết; thiếu vị trí ở các
-- phòng khác thì thư ký phải đứng tạm vị trí điều dưỡng và bị lẫn vai.
INSERT INTO
    public.vi_tri_lam_viec (clinic_id, code, ten, tang, phong, nhom_nghe, sort)
SELECT c.id, v.code, v.ten, v.tang, v.phong, 'DIEU_DUONG', v.sort
  FROM public.clinic c
 CROSS JOIN (VALUES
    ('T1_TT_TK',        'Thư ký thủ thuật',            'Tầng 1', 'Phòng thủ thuật',         95),
    ('T1_SA_TK',        'Thư ký siêu âm 1',            'Tầng 1', 'Phòng Siêu âm',          115),
    ('T1_TTNG_TK',      'Thư ký thủ thuật ngoài giờ',  'Tầng 1', 'Thủ thuật ngoài giờ',    145),
    ('T4_SANCHAU_TK',   'Thư ký Sàn chậu',             'Tầng 4', 'Phòng Sàn chậu',         175),
    ('T4_SANCHAU_TKTT', 'Thư ký thủ thuật Sàn chậu',   'Tầng 4', 'Phòng Sàn chậu',         185),
    ('T4_SAN_TK',       'Thư ký Sản',                  'Tầng 4', 'Phòng Sản - Biofeedback', 205),
    ('T4_SA_TK1',       'Thư ký siêu âm 2',            'Tầng 4', 'Phòng siêu âm',          245),
    ('T4_SA_TK2',       'Thư ký siêu âm 3',            'Tầng 4', 'Phòng siêu âm',          265)
 ) AS v(code, ten, tang, phong, sort)
 WHERE EXISTS (SELECT 1 FROM public.vi_tri_lam_viec x WHERE x.clinic_id = c.id)
 ON CONFLICT (clinic_id, code) DO NOTHING;

UPDATE public.vi_tri_lam_viec v
   SET room_id = r.id
  FROM public.clinic_room r
 WHERE r.clinic_id = v.clinic_id
   AND r.code = CASE v.code
        WHEN 'T1_TT_TK' THEN 'KN-THUTHUAT'
        WHEN 'T1_SA_TK' THEN 'KN-SA-T1'
        WHEN 'T1_TTNG_TK' THEN 'KN-TTNG'
        WHEN 'T4_SANCHAU_TK' THEN 'KN-SANCHAU'
        WHEN 'T4_SANCHAU_TKTT' THEN 'KN-SANCHAU'
        WHEN 'T4_SAN_TK' THEN 'KN-SAN-BIO'
        WHEN 'T4_SA_TK1' THEN 'KN-SA1'
        WHEN 'T4_SA_TK2' THEN 'KN-SA2'
       END;
