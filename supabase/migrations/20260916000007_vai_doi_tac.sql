-- Vai ĐỐI TÁC — người NGOÀI phòng khám, vào để gửi kết quả họ vừa làm.
--
-- Tuyền yêu cầu 16/09/2026: một tài khoản `doi-tac-pk` cho bên đối tác có chỗ
-- tải tài liệu lên. Tôi đã nêu lo ngại (một mật khẩu thường trực nằm ngoài tầm
-- quản lý của phòng khám) và Tuyền chốt vẫn làm — nên làm cho CHẶT, không làm
-- cho xong.
--
-- BỐN RÀNG BUỘC ĐỊNH NGHĨA VAI NÀY. Chúng nằm ở đây, trong lược đồ, chứ không
-- chỉ trong mã — vì mã đổi dễ hơn lược đồ, và một vai "người ngoài" nới ra vài
-- lần là thành một vai xem được bệnh án:
--
--   1. CHỈ THẤY VIỆC CỦA MÌNH. Đối tác chỉ nhìn được những chỉ định ở bước
--      ĐƯỢC ĐÁNH DẤU là làm bên ngoài, và chỉ những cái CHƯA có kết quả.
--   2. KHÔNG TRA CỨU. Không có đường nào để họ tìm một bệnh nhân bất kỳ.
--   3. KHÔNG ĐỌC BỆNH ÁN. Họ thấy tên + mã bệnh nhân + tên dịch vụ, hết. Đủ để
--      gắn đúng tệp vào đúng người — họ vốn đã gặp bệnh nhân ấy ngoài đời — và
--      không hơn.
--   4. GỬI LÊN, KHÔNG LẤY VỀ. Họ không tải xuống được tệp nào, kể cả tệp chính
--      mình vừa gửi.
--
-- `lam_ben_ngoai` là cái công tắc ở điều 1. Đánh dấu ở BƯỚC (node) chứ không ở
-- từng dịch vụ: một bước đã gửi ra ngoài thì mọi dịch vụ thuộc nó đều thế, và
-- thêm dịch vụ mới sau này không phải nhớ bật cờ lần nữa.

BEGIN;

-- ── 1. Cho phép giá trị vai mới ────────────────────────────────────────────
ALTER TABLE public.clinic_membership
    DROP CONSTRAINT IF EXISTS clinic_membership_role_check;
ALTER TABLE public.clinic_membership
    ADD CONSTRAINT clinic_membership_role_check CHECK (role = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'CASHIER_THUOC', 'CASHIER_DV', 'TKYK',
        'TRUONG_CA', 'PHARMACIST', 'DISPLAY', 'PARTNER'
    ]));

ALTER TABLE public.staff
    DROP CONSTRAINT IF EXISTS staff_primary_department_check;
ALTER TABLE public.staff
    ADD CONSTRAINT staff_primary_department_check CHECK (primary_department = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'CASHIER_THUOC', 'CASHIER_DV', 'TKYK',
        'TRUONG_CA', 'PHARMACIST', 'DISPLAY', 'PARTNER'
    ]));

-- ── 2. Bước nào là "làm bên ngoài" ─────────────────────────────────────────
ALTER TABLE public.node_definition
    ADD COLUMN IF NOT EXISTS lam_ben_ngoai boolean NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN public.node_definition.lam_ben_ngoai IS
'Bước này do bên NGOÀI phòng khám thực hiện — chỉ những bước bật cờ này mới hiện '
'ra cho vai PARTNER. Tắt cờ là đối tác thôi nhìn thấy nó ngay, không cần sửa mã.';

UPDATE public.node_definition
   SET lam_ben_ngoai = TRUE
 WHERE code IN (
     -- Chụp chiếu gửi ra ngoài: MRI vú, chụp tử cung–vòi trứng, chụp vú ép.
     -- `actor_roles` của bước này là {CSKH, TRUONG_CA} — tức người trong phòng
     -- khám chỉ ĐIỀU PHỐI, việc làm ở nơi khác.
     'DICHVU-HINHANH-NGOAI',
     -- Bệnh phẩm lấy tại phòng khám nhưng CHẠY ở lab đối tác; kết quả quay về
     -- dưới dạng tệp.
     'DICHVU-LAYMAU-MAU',
     'DICHVU-LAYMAU-NUOCTIEU',
     'DICHVU-LAYMAU-AMDAO',
     'DICHVU-SANGLOC-COTUCUNG'
 );

-- ── 3. Đối tác KHÔNG đọc được bảng nào qua PostgREST ────────────────────────
--
-- Vai này đăng nhập bằng Supabase như mọi vai khác, nên trình duyệt của họ có
-- một token hợp lệ. Mọi màn của đối tác đi qua FastAPI (có gác vai ở đó), nhưng
-- token ấy về nguyên tắc vẫn gõ thẳng PostgREST được. Chốt chặn nằm ở chính các
-- chính sách RLS: chúng đều tra `clinic_membership` theo vai, và PARTNER không
-- nằm trong tập vai nào. Ghi lại ở đây để lần sau viết chính sách mới thì nhớ:
-- ĐỪNG dùng "mọi thành viên phòng khám" làm điều kiện — PARTNER cũng là thành
-- viên.

DO $$
DECLARE
    so_buoc integer;
BEGIN
    SELECT count(*) INTO so_buoc
      FROM public.node_definition WHERE lam_ben_ngoai;
    RAISE NOTICE 'Có % bước được đánh dấu làm bên ngoài', so_buoc;
END $$;

COMMIT;
