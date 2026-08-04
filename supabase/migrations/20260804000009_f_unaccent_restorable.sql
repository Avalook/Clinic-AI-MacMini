-- BẢN SAO LƯU KHÔI PHỤC ĐƯỢC — sửa hàm chặn đường khôi phục.
--
-- PHÁT HIỆN NGÀY 04/08/2026, bằng cách thử khôi phục thật bản lưu 02:00 vào một
-- Postgres trắng. Backup vẫn chạy hằng đêm và dữ liệu bên trong ĐÚNG (đếm khớp
-- từng bảng), nhưng nạp lại thì hỏng ngay ở bảng `patient`:
--
--     ERROR: function unaccent(unknown, text) does not exist
--     CONTEXT: SQL function "f_unaccent" during inlining
--     → rồi 55 lỗi "relation public.patient does not exist" nối theo
--
-- VÌ SAO CHẠY BÌNH THƯỜNG MÀ KHÔI PHỤC LẠI HỎNG.
--
-- `patient.full_name_unaccent` là cột sinh (generated), biểu thức của nó gọi
-- `f_unaccent`. Lúc chạy bình thường, session có search_path = public nên
-- `unaccent('unaccent', $1)` tìm thấy cả hàm lẫn từ điển. Nhưng pg_dump mở đầu
-- bản lưu bằng:
--
--     SELECT pg_catalog.set_config('search_path', '', false);
--
-- search_path RỖNG là cố ý và đúng (chống chiếm quyền qua schema giả). Hệ quả:
-- mọi thứ không ghi rõ schema đều không tìm thấy — kể cả hàm của chính mình.
--
-- Nên một hàm không ghi rõ schema thì CHẠY ĐƯỢC nhưng KHÔNG KHÔI PHỤC ĐƯỢC, và
-- không có gì báo cho ta biết cho tới đúng ngày cần khôi phục. Các hàm khác
-- trong repo này đã ghim search_path từ trước (ultrasound_signed_block_update,
-- work_item_room_matches_clinic…); f_unaccent bị bỏ sót.
--
-- Sửa hai chỗ, cả hai đều cần:
--   1. Ghim search_path cho hàm — nó không còn phụ thuộc session gọi nó.
--   2. Ghi rõ public.unaccent và ép kiểu regdictionary — để cả khi ai đó gọi
--      với search_path rỗng thì vẫn giải được tên.

CREATE OR REPLACE FUNCTION public.f_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
STRICT
SET search_path TO 'public', 'pg_catalog'
AS $function$
  SELECT public.unaccent('public.unaccent'::regdictionary, $1)
$function$;

COMMENT ON FUNCTION public.f_unaccent(text) IS
    'Bỏ dấu tiếng Việt. search_path ĐƯỢC GHIM và tên ghi rõ schema: cột sinh '
    'patient.full_name_unaccent gọi hàm này, mà pg_dump khôi phục với '
    'search_path rỗng — không ghim thì bản sao lưu không nạp lại được.';

-- Kiểm ngay tại đây, đúng điều kiện của lúc khôi phục.
DO $verify$
DECLARE
    got text;
BEGIN
    PERFORM set_config('search_path', '', false);
    SELECT public.f_unaccent('Nguyễn Thị Hoà') INTO got;
    IF got IS DISTINCT FROM 'Nguyen Thi Hoa' THEN
        RAISE EXCEPTION 'f_unaccent trả về % — sai', got;
    END IF;
    PERFORM set_config('search_path', 'public', false);
    RAISE NOTICE 'f_unaccent chạy được với search_path rỗng: %', got;
END
$verify$;
