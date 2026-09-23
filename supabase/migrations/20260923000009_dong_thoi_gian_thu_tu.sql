-- Dòng thời gian cần một mốc xếp thứ tự thật (23/09/2026).
--
-- CHUYỆN ĐÃ XẢY RA. Sáu sự kiện của một lượt khám ghi trong CÙNG một giao dịch
-- có `occurred_at` y hệt nhau — `now()` trong Postgres là giờ bắt đầu giao dịch,
-- không phải giờ của từng câu lệnh. Màn hành trình xếp theo giờ nên rơi vào thế
-- hoà, và thứ tự hiện ra phụ thuộc vào việc bên nhận xử lý cái nào trước: "đã
-- làm xong" có thể đứng trên "bắt đầu làm".
--
-- Ngoài đời sáu chuyện ấy cách nhau hàng phút nên ít khi thấy. Nhưng "ít khi
-- thấy" đúng là loại lỗi tệ nhất: nó chỉ hiện ra khi có người nhìn kỹ một ca
-- bất thường — tức là đúng lúc không được sai.
--
-- `domain_event.seq` là số thứ tự ghi vào sổ, tăng dần theo đúng thứ tự phát.
-- Chép nó sang projection để xếp: trong cùng một giây thì ai vào sổ trước đứng
-- trước.

ALTER TABLE public.luot_dong_thoi_gian
    ADD COLUMN IF NOT EXISTS thu_tu bigint;

-- Dòng cũ: lấy lại từ sổ sự kiện, vì sổ vẫn còn đủ.
UPDATE public.luot_dong_thoi_gian t
   SET thu_tu = e.seq
  FROM public.domain_event e
 WHERE e.event_id = t.event_id AND t.thu_tu IS NULL;

DROP INDEX IF EXISTS ix_luot_dong_thoi_gian_luot;
CREATE INDEX IF NOT EXISTS ix_luot_dong_thoi_gian_luot
    ON public.luot_dong_thoi_gian (clinic_id, visit_id, occurred_at, thu_tu);

COMMENT ON COLUMN public.luot_dong_thoi_gian.thu_tu IS
    'domain_event.seq — mốc xếp thứ tự khi occurred_at bằng nhau (cùng một giao dịch).';
