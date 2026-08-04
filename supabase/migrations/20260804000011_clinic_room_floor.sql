-- TẦNG — thứ Trưởng ca đang phải tự nhớ 40–60 lần mỗi buổi.
--
-- Báo cáo onsite 23/04/2026 (cơ sở Kim Ngưu):
--     Tầng 1: Tiếp đón, Lấy mẫu xét nghiệm, Chỉ định, Khám, Thuốc
--     Tầng 2: Siêu âm
--     Tầng 4: Siêu âm
--
-- Siêu âm nằm ở HAI tầng khác nhau, mọi thứ còn lại ở tầng 1. Nên "cho bệnh
-- nhân lên tầng mấy" là một quyết định thật, lặp lại theo từng lượt khám — mà
-- hệ thống không hề biết có tầng, nên câu chuyển phòng chỉ nói được "sang SA2"
-- chứ không nói được "lên tầng 4, phòng SA2".
--
-- VÌ SAO LÀ `text` CHỨ KHÔNG PHẢI `int`.
--
-- Ở đây tầng là 1, 2, 4 (không có tầng 3). Nơi khác sẽ là "Trệt", "Lửng",
-- "B1", "Tòa A – T5". Ghim kiểu số là ghim sản phẩm vào cách đánh số của đúng
-- một toà nhà — trái với nguyên tắc: danh mục là của tenant, không phải hằng số
-- sản phẩm (xem docs/kien-truc-nhieu-phong-kham.md).
--
-- VÌ SAO KHÔNG THÊM CỘT `floor_sort`.
--
-- Thứ tự phòng đã do `sort` quyết định. Thứ tự TẦNG suy ra được từ `min(sort)`
-- của các phòng trên tầng đó — một nguồn sự thật, không có gì để lệch. Thêm một
-- cột thứ tự thứ hai là thêm một chỗ để hai con số nói hai điều khác nhau.
--
-- NULL CÓ NGHĨA, VÀ KHÁC RỖNG. NULL = "chưa khai tầng", và giao diện phải NÓI
-- RA điều đó thay vì đoán. Phòng khám một tầng cứ để NULL hết là đúng.

ALTER TABLE public.clinic_room
    ADD COLUMN IF NOT EXISTS floor text;

COMMENT ON COLUMN public.clinic_room.floor IS
    'Nhãn tầng do phòng khám tự khai ("1", "2", "Trệt", "B1"…). NULL = chưa '
    'khai. Thứ tự tầng suy từ min(sort) của các phòng trên tầng, không có cột '
    'thứ tự riêng.';

-- Nhãn trắng và nhãn rỗng là cùng một chuyện: chưa khai. Đừng để tồn tại hai
-- cách viết cho cùng một trạng thái — lọc "chưa khai tầng" sẽ sót một nửa.
ALTER TABLE public.clinic_room
    DROP CONSTRAINT IF EXISTS clinic_room_floor_not_blank;
ALTER TABLE public.clinic_room
    ADD CONSTRAINT clinic_room_floor_not_blank
    CHECK (floor IS NULL OR btrim(floor) <> '');

CREATE INDEX IF NOT EXISTS idx_clinic_room_floor
    ON public.clinic_room (clinic_id, location_id, floor);

-- ---------------------------------------------------------------------------
-- Khai tầng cho Kim Ngưu — CHỈ những phòng báo cáo nói CHẮC CHẮN
-- ---------------------------------------------------------------------------
-- Báo cáo ghi "Tầng 1: Tiếp đón, Lấy mẫu xét nghiệm, Chỉ định, Khám, Thuốc".
-- Mười phòng dưới đây nằm gọn trong câu đó.
--
-- BA PHÒNG SIÊU ÂM ĐỂ NGUYÊN NULL. Báo cáo nói siêu âm ở tầng 2 VÀ tầng 4,
-- nhưng không nói phòng nào ở tầng nào — mà hệ thống có SA1, SA2, SA3. Đoán
-- một cái thì hai phần ba khả năng là sai, và cái sai đó sẽ được đọc lên thành
-- một câu chỉ đường cho bệnh nhân. Để trống, hiện "chưa khai tầng", rồi người
-- biết sẽ khai.

UPDATE public.clinic_room r
   SET floor = '1'
  FROM public.clinic_location l
 WHERE l.id = r.location_id
   AND l.name = 'Kim Ngưu'
   AND r.floor IS NULL
   AND r.code IN ('TIEPNHAN', 'SINHHIEU', 'KB01', 'KB02', 'KB03', 'KB04',
                  'XETNGHIEM', 'NHATHUOC', 'THUNGAN');

DO $verify$
DECLARE
    da_khai int;
    chua_khai text;
BEGIN
    SELECT count(*) FILTER (WHERE floor IS NOT NULL),
           string_agg(code, ', ') FILTER (WHERE floor IS NULL)
      INTO da_khai, chua_khai
      FROM public.clinic_room WHERE is_active;
    RAISE NOTICE 'tầng: % phòng đã khai; chưa khai: %',
                 da_khai, coalesce(chua_khai, '(không còn)');
END
$verify$;
