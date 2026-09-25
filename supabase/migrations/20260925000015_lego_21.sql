-- Phân quyền = 21 LEGO theo node thanh bên (Tuyền 25/09/2026).
--
-- Quyền đi theo TÀI KHOẢN, không theo vai: có lego nào làm được việc lego ấy;
-- vai chỉ là gói mẫu. Mười ba khối mới cho những màn trước đây còn gác theo VAI
-- (nhân sự, tài khoản, cài đặt, báo cáo, vận hành, CSKH, danh sách bệnh nhân,
-- thêm bệnh nhân, lịch làm việc, bảng giá, việc cần xử lý, điều phối ca, đối tác)
-- — khớp `permissions/catalogue.py` (test_danh_muc_quyen_db so hai bên).
--
-- KHÔNG AI MẤT VIỆC: mỗi khối mới vào nhóm mẫu của ĐÚNG những vai hôm nay đang
-- vào được màn ấy (NAV_ROLES + cửa backend, bản đồ 25/09), rồi
-- `cap_quyen_cho_moi_thanh_vien()` cấp cho người đang làm. Ai quản lý đã từng
-- thu quyền thì hàm ấy giữ nguyên (không cấp lại thứ đã tắt).
--
-- Chạy lại được.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('viec_can_xu_ly', 'Việc cần xử lý', 'worklist',
     'Xem và xử lý việc được giao'),
    ('truong_ca', 'Điều phối ca', 'dispatch',
     'Điều phối ca, chuyển khách, đổi bác sĩ, ngưỡng cảnh báo — xếp phòng cao nhất'),
    ('them_benh_nhan', 'Thêm bệnh nhân', 'patient',
     'Thêm hồ sơ bệnh nhân mới, không cần đặt lịch'),
    ('cham_soc_khach', 'Chăm sóc khách hàng', 'crm',
     'Quản lý khách hàng, nhắc tái khám'),
    ('ds_benh_nhan', 'Danh sách bệnh nhân', 'patient',
     'Xem danh sách bệnh nhân'),
    ('lich_lam_viec', 'Lịch làm việc', 'roster',
     'Xem lịch làm việc, ca trực'),
    ('bang_gia', 'Bảng giá dịch vụ', 'catalogue',
     'Sửa giá dịch vụ'),
    ('bao_cao', 'Báo cáo', 'report',
     'Báo cáo, lịch đổ về'),
    ('cai_dat', 'Cài đặt phòng khám', 'config',
     'Luật đặt lịch, cấu trúc phòng khám, xếp lịch trực'),
    ('nhan_su', 'Nhân sự & tài khoản', 'staff',
     'Thêm nhân sự, tạo tài khoản đăng nhập, đặt lại mật khẩu'),
    ('van_hanh', 'Vận hành hệ thống', 'ops',
     'Theo dõi tình trạng hệ thống'),
    ('lich_su_thao_tac', 'Lịch sử thao tác', 'ops',
     'Xem nhật ký thao tác'),
    ('doi_tac', 'Đối tác', 'partner',
     'Khách được phân cho mình, điền thông tin, gửi tài liệu')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('worklist.handle', 'Xem và xử lý việc cần xử lý',
     'viec_can_xu_ly', 'worklist', 'operational', false),
    ('dispatch.manage', 'Điều phối ca — chuyển khách, đổi bác sĩ, xếp phòng cao nhất',
     'truong_ca', 'dispatch', 'operational', false),
    ('patient.create', 'Thêm bệnh nhân mới',
     'them_benh_nhan', 'patient', 'operational', false),
    ('crm.manage', 'Quản lý khách hàng và nhắc tái khám',
     'cham_soc_khach', 'crm', 'operational', false),
    ('patient.list.view', 'Xem danh sách bệnh nhân',
     'ds_benh_nhan', 'patient', 'operational', false),
    ('roster.view', 'Xem lịch làm việc',
     'lich_lam_viec', 'roster', 'operational', false),
    ('price.service.manage', 'Sửa bảng giá dịch vụ',
     'bang_gia', 'catalogue', 'financial', false),
    ('report.view', 'Xem báo cáo',
     'bao_cao', 'report', 'admin', false),
    ('config.clinic.manage', 'Cài đặt phòng khám (luật đặt lịch, cấu trúc, lịch trực)',
     'cai_dat', 'config', 'admin', false),
    ('staff.manage', 'Thêm / sửa / nghỉ việc nhân sự',
     'nhan_su', 'staff', 'admin', false),
    ('account.manage', 'Tạo tài khoản đăng nhập, đặt lại mật khẩu',
     'nhan_su', 'staff', 'admin', false),
    ('ops.view', 'Xem vận hành hệ thống',
     'van_hanh', 'ops', 'admin', false),
    ('audit.view', 'Xem lịch sử thao tác',
     'lich_su_thao_tac', 'ops', 'admin', false),
    ('partner.work', 'Làm việc đối tác (khách được phân, gửi tài liệu)',
     'doi_tac', 'partner', 'operational', false)
ON CONFLICT (ma) DO NOTHING;

-- Nhóm mẫu HỆ THỐNG: thêm khối (chỉ thêm, không ghi đè; chạy lại không nhân đôi).
UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || v.them) AS k)
  FROM (VALUES
          ('DOCTOR', ARRAY['viec_can_xu_ly', 'ds_benh_nhan', 'lich_lam_viec']),
          ('TKYK', ARRAY['viec_can_xu_ly', 'ds_benh_nhan', 'lich_lam_viec']),
          ('RECEPTION', ARRAY['viec_can_xu_ly', 'them_benh_nhan', 'cham_soc_khach', 'ds_benh_nhan', 'lich_lam_viec', 'bang_gia']),
          ('NURSE_ULTRASOUND', ARRAY['viec_can_xu_ly', 'ds_benh_nhan', 'lich_lam_viec']),
          ('CASHIER', ARRAY['viec_can_xu_ly', 'cham_soc_khach', 'ds_benh_nhan', 'lich_lam_viec', 'bang_gia']),
          ('CASHIER_DV', ARRAY['viec_can_xu_ly', 'cham_soc_khach', 'ds_benh_nhan', 'lich_lam_viec', 'bang_gia']),
          ('CASHIER_THUOC', ARRAY['cham_soc_khach', 'ds_benh_nhan', 'lich_lam_viec', 'bang_gia']),
          ('TRUONG_CA', ARRAY['viec_can_xu_ly', 'truong_ca', 'them_benh_nhan', 'cham_soc_khach', 'ds_benh_nhan', 'lich_lam_viec', 'bang_gia', 'bao_cao', 'lich_su_thao_tac']),
          ('PHARMACIST', ARRAY['lich_lam_viec']),
          ('CSKH', ARRAY['them_benh_nhan', 'cham_soc_khach', 'ds_benh_nhan', 'lich_lam_viec', 'lich_su_thao_tac']),
          ('ULTRASOUND_DOCTOR', ARRAY['viec_can_xu_ly', 'ds_benh_nhan', 'lich_lam_viec']),
          ('MANAGEMENT', ARRAY['viec_can_xu_ly', 'truong_ca', 'them_benh_nhan', 'cham_soc_khach', 'ds_benh_nhan', 'lich_lam_viec', 'bang_gia', 'bao_cao', 'cai_dat', 'nhan_su', 'van_hanh', 'lich_su_thao_tac', 'doi_tac'])
       ) AS v(ma, them)
 WHERE p.ma = v.ma AND p.he_thong
   AND NOT (p.khoi @> v.them);

-- Tài khoản đối tác: CHỈ lego Đối tác (backend vẫn chặn PARTNER ở mọi cửa khác).
INSERT INTO public.quyen_preset (clinic_id, ma, ten, khoi, he_thong, mo_ta)
SELECT c.id, 'PARTNER', 'Đối tác', ARRAY['doi_tac'], true, 'Nhóm dựng sẵn theo vai'
  FROM public.clinic c
ON CONFLICT DO NOTHING;

-- Người đang làm nhận các khối mới theo vai.
SELECT public.cap_quyen_cho_moi_thanh_vien();
