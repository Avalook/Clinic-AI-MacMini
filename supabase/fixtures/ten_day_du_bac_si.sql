-- Tên đầy đủ kèm học hàm cho bác sĩ.
--
-- NGUỒN: bảng do phòng khám cung cấp, đã dùng ở dự án trước
-- (Clinic-AI-Dr4Women, seed/053_doctor_full_names.sql). Chép nguyên, không tự
-- chế thêm tên nào.
--
-- KHỚP THEO short_name, KHÔNG theo full_name. Bản gốc khớp theo full_name cũ
-- ("BS Thành"), nên chạy lần hai là không khớp gì — vô hại nhưng cũng không
-- kiểm lại được. short_name là khoá ổn định: nó không đổi khi full_name đổi,
-- nên file này chạy lại bao nhiêu lần cũng cho ra đúng một kết quả.
--
-- KHÔNG đụng short_name. Bảng lịch làm việc và các fixture khác tra theo nó.

BEGIN;

UPDATE public.staff AS s
   SET full_name = m.ten_day_du, updated_at = now()
  FROM (VALUES
    ('Linh NK',    'BSNT. Nguyễn Khánh Linh'),
    ('Thành',      'TS.BS. Phan Chí Thành'),
    ('Hằng',       'Ths.BS. Phan Thu Hằng'),
    ('SA Bá Linh', 'Ths. Đào Bá Linh'),
    ('SA Đạt',     'BS. Nguyễn Thành Đạt'),
    ('SA Minh',    'BS. Phạm Ngọc Minh'),
    ('SA Hoàng',   'Ths. Nguyễn Mạnh Minh Hoàng'),
    ('SA Tiến',    'BS. Nguyễn Trung Tiến'),
    ('Nam',        'BSNT. Nguyễn Phương Nam'),
    ('Hùng',       'BSNT. Vũ Trọng Hùng'),
    ('SA Giáp',    'BSNT. Nguyễn Hữu Giáp'),
    ('Thiệp',      'BSNT. Hoàng Đình Thiệp'),
    ('Quyết',      'BSNT. Lê Thiệu Quyết'),
    ('Nghị',       'BS. Phạm Văn Nghị')
  ) AS m(ngan, ten_day_du)
 WHERE s.short_name = m.ngan
   AND s.primary_department IN ('DOCTOR', 'ULTRASOUND_DOCTOR');

COMMIT;

-- Bác sĩ nào chưa có tên đầy đủ thì nói ra, đừng để lặng lẽ.
DO $$
DECLARE con text;
BEGIN
    SELECT string_agg(full_name, ', ' ORDER BY full_name) INTO con
      FROM public.staff
     WHERE primary_department IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
       AND is_active
       AND full_name NOT LIKE '%.%'
       AND full_name NOT LIKE '%(tài khoản thử)';
    IF con IS NOT NULL THEN
        RAISE NOTICE 'Bác sĩ chưa có tên đầy đủ: %', con;
    END IF;
END $$;
