-- Tài khoản THỬ đang nằm lẫn trong danh sách 44 nhân sự thật, mang tên viết tắt
-- và không dấu. Viết đủ chữ, và nói rõ nó là tài khoản thử — người thứ hai mở
-- danh sách này ra phải phân biệt được ngay đâu là người, đâu là chỗ để đăng nhập.
BEGIN;
UPDATE public.staff SET full_name = v.ten, short_name = v.ngan
  FROM (VALUES
    ('BS SA local',   'Bác sĩ siêu âm (tài khoản thử)',        'BS siêu âm'),
    ('DD SA local',   'Điều dưỡng siêu âm (tài khoản thử)',    'ĐD siêu âm'),
    ('BS A local',    'Bác sĩ khám (tài khoản thử)',           'BS khám'),
    ('Le tan local',  'Lễ tân (tài khoản thử)',                'Lễ tân'),
    ('Thu ngan local','Thu ngân (tài khoản thử)',              'Thu ngân'),
    ('Quan ly local', 'Quản lý (tài khoản thử)',               'Quản lý'),
    ('Duoc si local', 'Dược sĩ (tài khoản thử)',               'Dược sĩ'),
    ('CSKH local',    'CSKH (tài khoản thử)',                  'CSKH')
  ) AS v(cu, ten, ngan)
 WHERE public.staff.full_name = v.cu;
COMMIT;
SELECT full_name, short_name, primary_department FROM public.staff
 WHERE full_name LIKE '%tài khoản thử%' ORDER BY primary_department;
