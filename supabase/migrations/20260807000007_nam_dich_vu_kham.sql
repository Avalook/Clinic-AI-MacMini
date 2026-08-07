-- Phòng khám chỉ còn ĐÚNG NĂM dịch vụ khám, trùng khít với năm biểu mẫu.
--
-- Quang chốt 07/08/2026: "5 biểu mẫu khám PK / SK / NT / NK / HMVS — từ giờ nó
-- là 5 dịch vụ khám luôn. Tiền hôn nhân,… tạm thời ẩn đã, ẩn cả trong đặt lịch
-- luôn, coi như mặc định giờ mình mới có 5 loại dịch vụ kia thôi."
--
-- SỐ 1/2/3 LÀ SỐ TẦNG, KHÔNG PHẢI LOẠI KHÁM. "Sản 1 / Sản 2 / Sản 3" là sản
-- khoa ở tầng 1, 2, 3 — vẫn một biểu mẫu Sản khoa duy nhất. Cùng luật với
-- "SA1 / SA2 / SA3" là phòng siêu âm theo tầng. Đây là lần thứ hai điều này
-- phải nói ra, nên ghi thẳng vào đây thay vì để trong đầu ai đó.
--
-- ẨN CHỨ KHÔNG XOÁ. `is_active = FALSE` là đủ: màn đặt lịch đã lọc theo cột
-- này (appointments/page.tsx và booking_service.py cùng lọc `st.is_active`).
-- Xoá cứng sẽ đứt khoá ngoại của 29 lịch hẹn đang trỏ vào `FREE` và mọi lịch
-- lịch sử khác — và những dịch vụ này còn có thể quay lại.
--
-- Ánh xạ `service_type.form_code` ĐÃ CÓ SẴN và đã đúng (Hồ sơ sinh, Khám tiền
-- sản, Sản 1/2/3 đều trỏ SK). Migration này không đụng vào nó — chỉ thu hẹp
-- danh sách đang bật.

-- ---------------------------------------------------------------------------
-- 1. Tắt mọi dịch vụ ngoài năm loại khám
-- ---------------------------------------------------------------------------
UPDATE public.service_type
   SET is_active = FALSE
 WHERE code NOT IN ('PHU_KHOA', 'SAN_1', 'NOI_TIET_TINH_DUC',
                    'NAM_KHOA', 'HIEM_MUON');

-- ---------------------------------------------------------------------------
-- 2. Năm loại còn lại: bật, và đặt tên đúng loại khám
-- ---------------------------------------------------------------------------
-- "Sản 1" đổi thành "Sản khoa": con số là tầng, không thuộc về tên dịch vụ.
-- "Nội tiết - Tình dục" rút gọn còn "Nội tiết" cho khớp tên biểu mẫu.
UPDATE public.service_type SET is_active = TRUE, name = 'Phụ khoa',
       form_code = 'PK'   WHERE code = 'PHU_KHOA';
UPDATE public.service_type SET is_active = TRUE, name = 'Sản khoa',
       form_code = 'SK'   WHERE code = 'SAN_1';
UPDATE public.service_type SET is_active = TRUE, name = 'Nội tiết',
       form_code = 'NT'   WHERE code = 'NOI_TIET_TINH_DUC';
UPDATE public.service_type SET is_active = TRUE, name = 'Nam khoa',
       form_code = 'NK'   WHERE code = 'NAM_KHOA';
UPDATE public.service_type SET is_active = TRUE, name = 'Hiếm muộn / Vô sinh',
       form_code = 'HMVS' WHERE code = 'HIEM_MUON';

-- ---------------------------------------------------------------------------
-- 3. VÌ SAO KHÔNG THÊM RÀNG BUỘC "đang bật thì phải có biểu mẫu"
-- ---------------------------------------------------------------------------
-- Đã viết rồi gỡ ra. Nghe hợp lý — `FREE` bật suốt mà không có biểu mẫu chính
-- là gốc của chuyện "Loại khám: FREE" — nhưng nó sai ở hai chỗ:
--
--   1. Nó chặn cả những thứ không liên quan: fixture đếm số thứ tự lịch hẹn
--      tạo một "Dịch vụ A (test)" và chẳng quan tâm biểu mẫu nào.
--   2. `service_type` không chỉ chứa dịch vụ KHÁM. Ngày phòng khám bật lại
--      "Thủ thuật", ràng buộc này bắt họ bịa ra một biểu mẫu khám cho một thủ
--      thuật — tức là bắt dữ liệu nói dối để qua cửa.
--
-- Thứ thật sự cần: bàn khám phải nói rõ khi dịch vụ chưa có biểu mẫu, thay vì
-- hiện một khoảng trắng. Chỗ đó đã xử lý ở giao diện.

COMMENT ON COLUMN public.service_type.form_code IS
    'Biểu mẫu khám của dịch vụ: PK / SK / NT / NK / HMVS. NULL = dịch vụ không '
    'phải một loại khám (thủ thuật, tư vấn…) — bàn khám nói rõ thay vì để trống.';
