-- Hồ sơ nhân sự: tám cột mà màn Quản lý nhân sự đã VẼ RA nhưng chưa lưu được.
--
-- ------------------------------------------------------------------------------
-- BỐI CẢNH
--
-- Màn `Quản lý nhân sự` có một khối ghi thẳng: *"Chưa lưu được — bảng nhân sự
-- chưa có những cột này"*, liệt kê ngày sinh, giới tính, CCCD, điện thoại,
-- email, CCHN + ngày cấp, phạm vi hoạt động chuyên môn.
--
-- Khối đó là cách trung thực nhất để nói "chưa làm" — nó tồn tại đúng vì người
-- viết màn hình từ chối vẽ những ô nhập rồi để dữ liệu rơi vào hư không. Nay
-- các cột có thật, nên khối ấy không còn lý do tồn tại.
--
-- ------------------------------------------------------------------------------
-- CCCD — QUYẾT ĐỊNH VỀ QUYỀN ĐỌC
--
-- Chính màn hình đặt câu hỏi này: *"định danh công dân — cần quyết định về
-- quyền đọc"*. Quyết định: LƯU, nhưng chỉ Quản lý và Trưởng ca đọc được.
--
-- Chốt nằm ở tầng ứng dụng, tại `_STAFF_MANAGEMENT_GUARD` — đường DUY NHẤT đọc
-- và ghi bảng này đã giới hạn ở hai vai đó từ trước. Không thêm cột này vào bất
-- kỳ endpoint nào khác.
--
-- Vì sao vẫn lưu: CCHN và phạm vi hoạt động chuyên môn là hồ sơ pháp lý bắt
-- buộc của một cơ sở khám chữa bệnh, và CCCD là thứ gắn chúng với đúng một
-- con người. Bỏ trống thì phòng khám vẫn phải giữ giấy tờ ấy ở đâu đó — thường
-- là một tệp Excel không ai kiểm soát được.
--
-- ------------------------------------------------------------------------------
-- KHÔNG CÓ CỘT CHO "TÀI LIỆU ĐÍNH KÈM"
--
-- Ô đó cần một CHỖ LƯU TỆP, không phải một cột. Hệ chưa có kho đối tượng nào
-- được cấu hình, nên thêm một cột `text` để chứa đường dẫn là tạo ra một lời
-- hứa không có gì đứng sau. Ô ấy ở lại trong danh sách "chưa làm được", và nói
-- đúng lý do.

ALTER TABLE public.staff
    ADD COLUMN IF NOT EXISTS date_of_birth      date,
    ADD COLUMN IF NOT EXISTS gender             text,
    ADD COLUMN IF NOT EXISTS national_id_number text,
    ADD COLUMN IF NOT EXISTS phone              text,
    ADD COLUMN IF NOT EXISTS email              text,
    -- Chứng chỉ hành nghề: SỐ và NGÀY CẤP là hai dữ kiện, không phải một chuỗi.
    -- Gộp làm một ô văn bản thì không lọc được "ai sắp hết hạn".
    ADD COLUMN IF NOT EXISTS license_number     text,
    ADD COLUMN IF NOT EXISTS license_issued_on  date,
    ADD COLUMN IF NOT EXISTS practice_scope     text;

COMMENT ON COLUMN public.staff.national_id_number IS
    'Số CCCD của nhân sự. CHỈ Quản lý và Trưởng ca đọc được — chốt ở '
    '_STAFF_MANAGEMENT_GUARD, đường duy nhất chạm bảng này. Không đưa cột này '
    'vào bất kỳ endpoint nào khác.';

COMMENT ON COLUMN public.staff.license_number IS
    'Số chứng chỉ hành nghề (CCHN). Cùng license_issued_on tạo thành hồ sơ pháp '
    'lý bắt buộc của cơ sở khám chữa bệnh.';

COMMENT ON COLUMN public.staff.practice_scope IS
    'Phạm vi hoạt động chuyên môn ghi trên CCHN — thứ giới hạn người này được '
    'làm gì, không phải mô tả công việc nội bộ.';

-- CCCD 12 chữ số, để trống được (nhiều nhân sự chưa nộp).
--
-- Kiểm ở database chứ không chỉ ở biểu mẫu: cùng một bảng còn được sửa bằng
-- script khi nhập liệu hàng loạt, và một số CCCD sai định dạng thì không đối
-- chiếu được với giấy tờ thật.
ALTER TABLE public.staff
    DROP CONSTRAINT IF EXISTS staff_cccd_12_so;

ALTER TABLE public.staff
    ADD CONSTRAINT staff_cccd_12_so CHECK (
        national_id_number IS NULL
        OR national_id_number ~ '^[0-9]{12}$'
    );

ALTER TABLE public.staff
    DROP CONSTRAINT IF EXISTS staff_gender_hop_le;

ALTER TABLE public.staff
    ADD CONSTRAINT staff_gender_hop_le CHECK (
        gender IS NULL OR gender = ANY (ARRAY['Nam', 'Nữ', 'Khác'])
    );

-- Một số CCCD chỉ thuộc về một người. Bán phần vì phần lớn dòng còn để trống.
CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_cccd
    ON public.staff (national_id_number)
 WHERE national_id_number IS NOT NULL;
