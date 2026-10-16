-- Vai KẾ TOÁN (`ACCOUNTANT`) — một cái NHÃN để chọn ở ô Vai khi thêm nhân viên.
--
-- Tuyền 16/10/2026: màn Quản lý nhân sự → Thêm nhân viên chưa có "Kế toán" trong
-- ô Vai (chỉ có 11 vai), nên người làm kế toán phải đăng ký tạm bằng vai khác.
--
-- CHỈ LEGO, KHÔNG VAI (Tuyền 27/09): vai này KHÔNG cấp quyền nào. Quyền thật vẫn
-- là dòng `capability_grant` của khối `ke_toan` (`accounting.finance.full`,
-- `accounting.tax.manage`) — vai chỉ làm một việc: người mới tạo với vai này
-- được CẤP SẴN gói mẫu "Kế toán" (cùng cơ chế mọi vai khác: nhóm mẫu mã = mã vai,
-- `cap_quyen_theo_preset`). Quản lý thu/đổi từng khối trên màn Phân quyền; vai
-- thì KHÔNG nằm trong `KHOI_CHI_QUAN_LY`/mở-full-lego, nên thiếu lego là 403.
--
-- Ba việc, chỉ THÊM (chạy lại được):
--   1. CHECK `clinic_membership_role_check` + `staff_primary_department_check`
--      thêm 'ACCOUNTANT'. Danh sách giữ NGUYÊN 14 vai hiện hành (lấy từ
--      20260916000007_vai_doi_tac.sql — migration mới nhất đụng hai ràng buộc
--      này; kiểm 16/10 không migration nào khác sửa chúng).
--   2. Nhóm mẫu hệ thống 'ACCOUNTANT' = đúng khối của nhóm 'KE_TOAN' hiện có
--      (sao chép theo từng phòng khám; chưa có KE_TOAN thì dùng bộ năm khối
--      mặc định) — khớp `PRESET["ACCOUNTANT"]` trong catalogue.py
--      (`test_nhom_dung_san_khop_voi_hang_so_trong_ma` so hai bên).
--   3. Không đụng RLS: các chính sách tra `clinic_membership` theo vai
--      (MANAGEMENT, TRUONG_CA…) hoặc theo "thành viên phòng khám"; ACCOUNTANT
--      không nằm trong tập vai nào, chỉ có quyền của một thành viên nội bộ thường
--      như CSKH. Khác PARTNER: đây là người TRONG phòng khám.

BEGIN;

ALTER TABLE public.clinic_membership
    DROP CONSTRAINT IF EXISTS clinic_membership_role_check;
ALTER TABLE public.clinic_membership
    ADD CONSTRAINT clinic_membership_role_check CHECK (role = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'CASHIER_THUOC', 'CASHIER_DV', 'TKYK',
        'TRUONG_CA', 'PHARMACIST', 'DISPLAY', 'PARTNER', 'ACCOUNTANT'
    ]));

ALTER TABLE public.staff
    DROP CONSTRAINT IF EXISTS staff_primary_department_check;
ALTER TABLE public.staff
    ADD CONSTRAINT staff_primary_department_check CHECK (primary_department = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'CASHIER_THUOC', 'CASHIER_DV', 'TKYK',
        'TRUONG_CA', 'PHARMACIST', 'DISPLAY', 'PARTNER', 'ACCOUNTANT'
    ]));

-- Nhóm mẫu theo vai: cùng khối với gói "Kế toán" (KE_TOAN) — báo cáo, kế toán,
-- danh sách bệnh nhân, lịch làm việc, kho vật tư. CỐ Ý không có khối thu tiền.
INSERT INTO public.quyen_preset (clinic_id, ma, ten, khoi, he_thong, mo_ta)
SELECT c.id, 'ACCOUNTANT', 'Kế toán',
       COALESCE(k.khoi, ARRAY['bao_cao', 'ds_benh_nhan', 'ke_toan',
                              'kho_vat_tu', 'lich_lam_viec']),
       true, 'Nhóm dựng sẵn theo vai — kế toán không thu tiền'
  FROM public.clinic c
  LEFT JOIN public.quyen_preset k
         ON k.clinic_id = c.id AND k.ma = 'KE_TOAN'
ON CONFLICT DO NOTHING;

COMMIT;
