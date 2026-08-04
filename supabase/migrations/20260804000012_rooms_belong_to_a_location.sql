-- PHÒNG PHẢI THUỘC MỘT CƠ SỞ — nếu không thì "tầng" không có nghĩa.
--
-- Phát hiện khi khai tầng: `clinic_room.location_id` NULL trên CẢ 12 phòng.
-- Migration trước cố khai tầng qua join với `clinic_location` nên không cập
-- nhật được dòng nào — và đó là điều may, vì nó lộ ra cái lỗ thật.
--
-- VÌ SAO ĐÂY LÀ LỖ THẬT, KHÔNG PHẢI CHUYỆN NHỎ.
--
-- Hệ thống có HAI cơ sở: Kim Ngưu và Hào Nam. "Tầng 2" ở Kim Ngưu và "tầng 2"
-- ở Hào Nam là hai chỗ khác nhau trong hai toà nhà khác nhau. Một cái nhãn tầng
-- gắn vào một phòng không thuộc cơ sở nào thì không chỉ đường cho ai được.
--
-- Rộng hơn: phòng không thuộc cơ sở nghĩa là khi Hào Nam mở, nhân sự ở đó sẽ
-- thấy nguyên danh sách phòng của Kim Ngưu trên bảng điều phối, và có thể bấm
-- chuyển bệnh nhân sang một phòng cách đó vài cây số.
--
-- HÔM NAY CHƯA AI ĐAU vì Hào Nam có 0 nhân sự (57/57 đều ở Kim Ngưu) — đúng
-- kiểu lỗi chỉ hiện hình vào ngày mở cơ sở thứ hai, tức là đúng ngày bận nhất.

UPDATE public.clinic_room r
   SET location_id = (SELECT id FROM public.clinic_location
                       WHERE name = 'Kim Ngưu' LIMIT 1)
 WHERE r.location_id IS NULL;

-- Từ nay không tạo được phòng lơ lửng nữa. Đặt NOT NULL sau khi đã vá dữ liệu:
-- ràng buộc là để chặn cái SAU, còn cái trước phải sửa bằng tay và có chủ ý.
ALTER TABLE public.clinic_room
    ALTER COLUMN location_id SET NOT NULL;

-- ---------------------------------------------------------------------------
-- Khai tầng cho Kim Ngưu
-- ---------------------------------------------------------------------------
-- Báo cáo onsite 23/04/2026: "Tầng 1: Tiếp đón, Lấy mẫu xét nghiệm, Chỉ định,
-- Khám, Thuốc / Tầng 2: Siêu âm / Tầng 4: Siêu âm".
--
-- Chín phòng dưới đây nằm gọn trong câu tầng 1.

UPDATE public.clinic_room r
   SET floor = '1'
  FROM public.clinic_location l
 WHERE l.id = r.location_id
   AND l.name = 'Kim Ngưu'
   AND r.floor IS NULL
   AND r.code IN ('TIEPNHAN', 'SINHHIEU', 'KB01', 'KB02', 'KB03', 'KB04',
                  'XETNGHIEM', 'NHATHUOC', 'THUNGAN');

-- SA1 / SA2 / SA3 ĐỂ NGUYÊN NULL, CÓ CHỦ Ý.
--
-- Báo cáo nói siêu âm ở tầng 2 VÀ tầng 4, nhưng không nói phòng nào ở tầng nào
-- — mà hệ thống có ba phòng siêu âm. Đoán một cái thì phần lớn khả năng là sai,
-- và cái sai đó sẽ được đọc lên thành câu chỉ đường cho bệnh nhân đang đứng ở
-- sảnh. Màn cấu hình phòng sẽ hiện "chưa khai tầng" để người biết vào khai.
--
-- Khai bằng tay khi đã hỏi được, ví dụ:
--     UPDATE clinic_room SET floor='2' WHERE code IN ('SA1','SA2');
--     UPDATE clinic_room SET floor='4' WHERE code = 'SA3';

DO $verify$
DECLARE
    lo_lung int;
    chua_tang text;
BEGIN
    SELECT count(*) INTO lo_lung
      FROM public.clinic_room WHERE location_id IS NULL;
    IF lo_lung > 0 THEN
        RAISE EXCEPTION 'còn % phòng không thuộc cơ sở nào', lo_lung;
    END IF;

    SELECT string_agg(code, ', ' ORDER BY sort) INTO chua_tang
      FROM public.clinic_room WHERE is_active AND floor IS NULL;
    RAISE NOTICE 'phòng đã thuộc cơ sở. Chưa khai tầng: %',
                 coalesce(chua_tang, '(không còn)');
END
$verify$;
