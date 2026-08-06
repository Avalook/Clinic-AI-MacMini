-- Vai DISPLAY — tài khoản của cái tivi treo ở phòng chờ.
--
-- VÌ SAO CẦN MỘT VAI RIÊNG THAY VÌ DÙNG TÀI KHOẢN NHÂN VIÊN.
--
-- Bảng gọi số phải hiện cho khách xem, nên máy tính chạy nó đăng nhập một lần
-- rồi bỏ đó cả ngày, ở một nơi công cộng, không ai trông. Nếu nó đăng nhập bằng
-- tài khoản Lễ tân thì bất kỳ ai đứng cạnh chỉ cần mở một tab mới là đọc được
-- danh sách bệnh nhân, số điện thoại, chẩn đoán. Cái tivi không cần quyền của
-- một con người, và không nên có.
--
-- Chốt thật nằm ở tầng ứng dụng: `get_current_identity` TỪ CHỐI vai này, nên nó
-- bị chặn ở MỌI endpoint theo mặc định — kể cả 26 endpoint chưa có RoleGuard.
-- Chỉ `get_display_identity` nhận nó, và hôm nay đúng một đường dùng tới:
-- GET /api/v1/display/queue, vốn không trả về một mẩu danh tính nào.
--
-- Migration này chỉ nới ràng buộc để lưu được vai. Chạy hai lần vẫn đúng (CI
-- phát lại toàn bộ chuỗi).

ALTER TABLE public.clinic_membership
    DROP CONSTRAINT IF EXISTS clinic_membership_role_check;

ALTER TABLE public.clinic_membership
    ADD CONSTRAINT clinic_membership_role_check CHECK (
        role = ANY (ARRAY[
            'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION',
            'CSKH', 'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA',
            'CASHIER_THUOC', 'CASHIER_DV', 'PHARMACIST',
            'DISPLAY'
        ])
    );

COMMENT ON CONSTRAINT clinic_membership_role_check ON public.clinic_membership IS
    'Danh sách vai hợp lệ. DISPLAY là tài khoản của màn hình TV phòng chờ, '
    'không phải của một người — nó bị get_current_identity từ chối nên chỉ vào '
    'được đúng bảng gọi số.';

-- ---------------------------------------------------------------------------
-- staff: vai DISPLAY, và một loại hợp đồng cho thứ không phải người
-- ---------------------------------------------------------------------------
-- `primary_department` phải nhận DISPLAY, nếu không thì không tạo nổi dòng nhân
-- sự cho cái tivi.
ALTER TABLE public.staff
    DROP CONSTRAINT IF EXISTS staff_primary_department_check;

ALTER TABLE public.staff
    ADD CONSTRAINT staff_primary_department_check CHECK (
        primary_department = ANY (ARRAY[
            'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION',
            'CSKH', 'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA',
            'CASHIER_THUOC', 'CASHIER_DV', 'PHARMACIST',
            'DISPLAY'
        ])
    );

-- `employment_type` thêm 'SYSTEM'.
--
-- Ba giá trị cũ (FULL_TIME / PART_TIME / CONTRACT) đều mô tả quan hệ lao động
-- với một CON NGƯỜI. Nhét cái tivi vào một trong ba là làm hỏng mọi báo cáo
-- nhân sự đếm đầu người — im lặng, và đúng loại sai lệch không ai đi kiểm.
ALTER TABLE public.staff
    DROP CONSTRAINT IF EXISTS staff_employment_type_check;

ALTER TABLE public.staff
    ADD CONSTRAINT staff_employment_type_check CHECK (
        employment_type = ANY (ARRAY[
            'FULL_TIME', 'PART_TIME', 'CONTRACT',
            'SYSTEM'
        ])
    );

COMMENT ON CONSTRAINT staff_employment_type_check ON public.staff IS
    'SYSTEM = dòng nhân sự của một THIẾT BỊ (màn hình phòng chờ), không phải '
    'của một người. Báo cáo đếm đầu người phải loại nó ra.';
