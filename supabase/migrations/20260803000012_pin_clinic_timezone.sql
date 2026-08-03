-- Một múi giờ, và cột `clinic.timezone` thôi hứa điều nó không giữ.
--
-- QUYẾT ĐỊNH SẢN PHẨM (Quang, 2026-08-03): ClinicAI phục vụ phòng khám tại Việt
-- Nam, không bán ra nước ngoài. Múi giờ là Asia/Ho_Chi_Minh, cố định.
--
-- VÌ SAO CẦN MỘT MIGRATION CHO MỘT QUYẾT ĐỊNH "KHÔNG LÀM GÌ CẢ".
--
-- Bảng `clinic` có cột `timezone` với mặc định 'Asia/Ho_Chi_Minh'. KHÔNG hàm
-- nào đọc nó: resolve_effective_cap, clinic_hours_for_date, v_consultation_
-- duration và mọi chỗ khác đều viết thẳng chuỗi 'Asia/Ho_Chi_Minh'.
--
-- Một cột cấu hình mà hệ thống bỏ qua tệ hơn một cột không tồn tại. Người vận
-- hành nhìn thấy nó, đổi nó, và KHÔNG CÓ GÌ XẢY RA — không lỗi, không cảnh báo,
-- không thay đổi. Đó chính xác là dạng "hai nguồn, một cái có hiệu lực" mà cả
-- đợt rà soát 2026-08-03 đi tìm: giờ mở cửa ở hai file với hai giá trị, sức
-- chứa ở hai bảng mà chỉ một bảng được thi hành, hàm sức chứa tồn tại mà trigger
-- gọi nó thì không gắn. Cột này là cùng một hình dạng, chỉ chưa cắn ai.
--
-- CHECK biến nó từ một lời hứa suông thành một câu trả lời thật: đổi sẽ bị từ
-- chối, kèm lý do. Không âm thầm nữa.
--
-- NGÀY MUỐN ĐA MÚI GIỜ: gỡ CHECK này, rồi cho các hàm SQL đọc c.timezone thay
-- cho hằng chuỗi. Danh sách đầy đủ ở src/clinicai/core/clock.py — ba chỗ, để
-- việc đó là một thay đổi lập kế hoạch được, không phải một cuộc đi tìm.

ALTER TABLE public.clinic
    ALTER COLUMN timezone SET DEFAULT 'Asia/Ho_Chi_Minh';

UPDATE public.clinic
   SET timezone = 'Asia/Ho_Chi_Minh'
 WHERE timezone IS DISTINCT FROM 'Asia/Ho_Chi_Minh';

ALTER TABLE public.clinic
    DROP CONSTRAINT IF EXISTS clinic_timezone_is_vietnam;
ALTER TABLE public.clinic
    ADD CONSTRAINT clinic_timezone_is_vietnam
    CHECK (timezone = 'Asia/Ho_Chi_Minh');

COMMENT ON CONSTRAINT clinic_timezone_is_vietnam ON public.clinic IS
    'ClinicAI chỉ phục vụ phòng khám Việt Nam (quyết định sản phẩm 2026-08-03). '
    'Mọi hàm giờ giấc viết thẳng Asia/Ho_Chi_Minh, nên một giá trị khác ở cột '
    'này sẽ KHÔNG có tác dụng — ràng buộc này từ chối thay vì để nó im lặng '
    'trôi qua. Muốn đa múi giờ: gỡ CHECK rồi cho các hàm đọc cột này (danh sách '
    'ở src/clinicai/core/clock.py).';

COMMENT ON COLUMN public.clinic.timezone IS
    'Luôn là Asia/Ho_Chi_Minh (xem CHECK clinic_timezone_is_vietnam). Giữ cột '
    'lại vì nó là chỗ đúng để bắt đầu khi cần đa múi giờ, không phải vì nó đang '
    'được dùng.';

DO $verify$
DECLARE v_bad int;
BEGIN
    SELECT count(*) INTO v_bad
      FROM public.clinic WHERE timezone <> 'Asia/Ho_Chi_Minh';
    IF v_bad > 0 THEN
        RAISE EXCEPTION 'Còn % phòng khám khai múi giờ khác', v_bad;
    END IF;
    RAISE NOTICE 'clinic.timezone: đã ghim về Asia/Ho_Chi_Minh';
END
$verify$;
