-- Nhóm quyền mẫu do QUẢN LÝ tự đặt (23/09/2026).
--
-- Trước migration này, "preset của vai" là một hằng số trong Python: muốn phòng
-- khám có thêm một nhóm ("Điều dưỡng ca tối", "Lễ tân kiêm thu ngân") thì phải
-- sửa mã, chờ deploy. Tuyền 23/09: *"quản lý quyền cao nhất, thay đổi các nút
-- và vai trò, mặc định các nút ở đó có thể thêm sửa xoá được"*.
--
-- Nên preset chuyển thành DỮ LIỆU. Quản lý thêm nhóm mới, đổi khối trong nhóm,
-- xoá nhóm mình đặt — không ai phải mở trình soạn thảo.
--
-- HAI THỨ KHÔNG ĐỔI, và đây là chỗ dễ hiểu nhầm nhất:
--
-- 1. **Nhóm mẫu KHÔNG phải quyền.** Quyền thật vẫn nằm ở từng dòng
--    `capability_grant` của từng người. Nhóm mẫu chỉ là "bấm một cái cấp cả
--    loạt". Sửa nhóm mẫu KHÔNG đổi quyền của ai đã được cấp — vì nếu nó đổi
--    được, thì một lần sửa nhóm là một lần âm thầm đổi quyền của mười người.
--
-- 2. **Nhóm hệ thống xoá được nhưng không mất.** `he_thong = true` là mấy nhóm
--    dựng sẵn theo vai; quản lý tắt (`active = false`) chứ không xoá cứng, để
--    người cũ còn tra được "hồi ấy cấp theo nhóm nào".

CREATE TABLE IF NOT EXISTS public.quyen_preset (
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    ma         text NOT NULL,
    ten        text NOT NULL,
    -- Các khối công việc trong nhóm. Khối không có thật thì lệnh cấp từ chối —
    -- kiểm ở lệnh chứ không ở đây, vì danh mục khối nằm trong mã.
    khoi       text[] NOT NULL DEFAULT '{}',
    mo_ta      text,
    -- Nhóm dựng sẵn theo vai. Quản lý sửa được khối bên trong, nhưng không xoá
    -- cứng: `cap_preset_mac_dinh` lúc thêm nhân sự vẫn tra theo mã vai.
    he_thong   boolean NOT NULL DEFAULT false,
    active     boolean NOT NULL DEFAULT true,
    tao_boi    uuid REFERENCES public.staff(id),
    tao_luc    timestamptz NOT NULL DEFAULT now(),
    sua_boi    uuid REFERENCES public.staff(id),
    sua_luc    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, ma),
    CONSTRAINT quyen_preset_ma_hoa
        CHECK (ma = upper(ma) AND ma ~ '^[A-Z0-9_]{2,32}$'),
    CONSTRAINT quyen_preset_ten_khong_rong
        CHECK (length(btrim(ten)) > 0)
);

ALTER TABLE public.quyen_preset ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quyen_preset_select_own_clinic ON public.quyen_preset;
CREATE POLICY quyen_preset_select_own_clinic ON public.quyen_preset
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));

GRANT SELECT ON public.quyen_preset TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.quyen_preset TO service_role;

-- ── Chép 11 nhóm dựng sẵn từ hằng số Python sang dữ liệu ──────────────────
-- Danh sách này phải khớp `clinicai/permissions/catalogue.py::PRESET`. Có một
-- bài kiểm giữ cho hai bên không lệch — lệch nghĩa là người mới vào làm được
-- cấp một bộ quyền khác với bộ quản lý nhìn thấy trên màn.
INSERT INTO public.quyen_preset (clinic_id, ma, ten, khoi, he_thong, mo_ta)
SELECT c.id, v.ma, v.ten, v.khoi, true, 'Nhóm dựng sẵn theo vai'
  FROM public.clinic c
 CROSS JOIN (VALUES
    ('DOCTOR', 'Bác sĩ',
     ARRAY['chi_dinh','dieu_phoi','ket_qua','thuc_hien']),
    ('TKYK', 'Thư ký y khoa',
     ARRAY['chi_dinh','dieu_phoi','ket_qua','thuc_hien']),
    ('RECEPTION', 'Lễ tân',
     ARRAY['tiep_don','chon_dich_vu','thu_tien_dv','dieu_phoi']),
    ('NURSE_ULTRASOUND', 'Điều dưỡng siêu âm',
     ARRAY['sinh_hieu','dieu_phoi','ket_qua','thuc_hien']),
    ('CASHIER', 'Thu ngân',
     ARRAY['thu_tien_dv','chon_dich_vu']),
    ('CASHIER_DV', 'Thu ngân dịch vụ',
     ARRAY['thu_tien_dv','chon_dich_vu']),
    ('CASHIER_THUOC', 'Thu ngân nhà thuốc',
     ARRAY['thu_tien_dv']),
    ('TRUONG_CA', 'Trưởng ca',
     ARRAY['dieu_phoi','tiep_don','chon_dich_vu','thuc_hien']),
    ('ULTRASOUND_DOCTOR', 'Bác sĩ siêu âm',
     ARRAY['dieu_phoi','ket_qua','thuc_hien']),
    ('MANAGEMENT', 'Quản lý',
     ARRAY['tiep_don','sinh_hieu','chi_dinh','chon_dich_vu','thu_tien_dv',
           'dieu_phoi','ket_qua','thuc_hien','danh_muc','quan_tri_quyen'])
 ) AS v(ma, ten, khoi)
ON CONFLICT (clinic_id, ma) DO NOTHING;

COMMENT ON TABLE public.quyen_preset IS
    'Nhóm quyền mẫu: bấm một cái cấp cả loạt khối. KHÔNG phải quyền — quyền thật ở capability_grant.';
