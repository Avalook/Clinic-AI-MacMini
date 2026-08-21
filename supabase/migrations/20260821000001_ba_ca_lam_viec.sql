-- Ba ca làm việc thay vì hai, và giờ ca thành CẤU HÌNH của phòng khám.
--
-- Tuyền chốt 21/08/2026: *"chia thành 3 ca thay vì 2 như trước"*, kèm giờ cụ
-- thể cho Dr4Women, và *"tính năng này là chung cho mọi phòng khám sau này vì
-- có phòng người ta mở từ 8h sáng, phòng từ 9h"*.
--
-- VÌ SAO KHÔNG CHỈ THÊM MỘT MỐC CHIA. Bản cũ suy ca từ MỘT mốc viết cứng lúc
-- 12:00 (`core/shifts.py`): sáng = mở cửa → 12:00, chiều = 12:00 → đóng cửa.
-- Ba ca mới KHÔNG chia được như vậy vì giữa sáng và chiều có khoảng trống:
--
--     sáng  08:00 ─ 13:00
--                   ╳  nghỉ trưa 13:00–14:00
--     chiều 14:00 ─ 17:30
--     tối   17:30 ─ 21:30
--
-- Một mốc chia không tạo ra được khoảng trống. Nên giờ ca được KHAI TƯỜNG MINH
-- trong `clinic.settings->'ca_lam_viec'`, và mỗi phòng khám tự đổi được.
--
-- Hệ quả đáng ghi: ca CẢ NGÀY (FULL) nay là HAI khoảng rời nhau, không còn là
-- một. Đó là lý do `shift_window()` đổi thành `shift_windows()` trả về danh
-- sách — sáu nơi gọi đã sửa theo.
--
-- GIỜ LÀM VIỆC ≠ GIỜ MỞ CỬA. `settings->'hours'` nói cửa mở lúc nào; hợp ba ca
-- nói lúc nào CÓ NGƯỜI KHÁM. Tuyền chốt: ngoài ba ca thì không đặt lịch được,
-- nên lưới đặt lịch đọc hợp-ba-ca chứ không đọc giờ mở cửa.
--
-- ĐÃ ĐO TRƯỚC KHI ĐỔI (21/08/2026): prod có ĐÚNG 1 lịch hẹn còn sống và nó nằm
-- trong khung mới; staging có 2 lịch ngoài khung nhưng cả hai đã qua. Không ai
-- mất lịch vì thay đổi này.

BEGIN;

-- ① Nới ràng buộc để nhận ca TỐI ------------------------------------------
ALTER TABLE public.work_roster
    DROP CONSTRAINT IF EXISTS work_roster_shift_check;

ALTER TABLE public.work_roster
    ADD CONSTRAINT work_roster_shift_check
    CHECK (shift = ANY (ARRAY['FULL'::text, 'SANG'::text, 'CHIEU'::text,
                              'TOI'::text]));

COMMENT ON COLUMN public.work_roster.shift IS
    'FULL | SANG | CHIEU | TOI. Giờ của từng ca do phòng khám khai trong '
    'clinic.settings->''ca_lam_viec''; FULL = hợp cả ba ca.';

-- ② Giờ ca của Dr4Women ----------------------------------------------------
-- Ghi cho MỌI phòng khám đang có mà chưa khai, không riêng Dr4Women: một phòng
-- khám không có cấu hình sẽ lùi về mặc định trong code — giống hệt giá trị này
-- — nên ghi ra đây chỉ để quản lý MỞ RA SỬA ĐƯỢC, không đổi hành vi.
UPDATE public.clinic
   SET settings = coalesce(settings, '{}'::jsonb)
                || jsonb_build_object('ca_lam_viec', jsonb_build_object(
                       'SANG',  jsonb_build_object('bat_dau', '08:00',
                                                   'ket_thuc', '13:00'),
                       'CHIEU', jsonb_build_object('bat_dau', '14:00',
                                                   'ket_thuc', '17:30'),
                       'TOI',   jsonb_build_object('bat_dau', '17:30',
                                                   'ket_thuc', '21:30')
                   )),
       updated_at = now()
 WHERE settings -> 'ca_lam_viec' IS NULL;

-- ③ Giờ mở cửa bao trọn ba ca ---------------------------------------------
-- Giờ mở cửa là chốt NGOÀI CÙNG: `shift_windows` kẹp mọi ca vào trong nó, nên
-- một phòng khám khai ca tối tới 21:30 mà cửa đóng lúc 20:00 sẽ mất một tiếng
-- rưỡi cuối mà không ai báo. Nới đủ rộng để ba ca sống trọn vẹn; hẹp lại là
-- việc của Quản lý, có màn riêng.
UPDATE public.clinic
   SET settings = jsonb_set(
           settings, ARRAY['hours'],
           (SELECT jsonb_object_agg(
                       k,
                       jsonb_build_object('open', '07:00', 'close', '22:00'))
              FROM jsonb_object_keys(settings -> 'hours') AS k)),
       updated_at = now()
 WHERE settings -> 'hours' IS NOT NULL;

COMMIT;
