-- Đếm ghế CẢ NGÀY một lần, thay vì 120 lần cho một lượt vẽ lưới.
--
-- ĐO TRƯỚC KHI SỬA (staging, 21/08/2026): một lượt `/appointments/quote` mất
-- 283ms, trong đó ~250ms là 2×60 lần gọi `slot_seats_used` — hàm SECURITY
-- DEFINER nên Postgres KHÔNG inline được, mỗi lần gọi là một lượt quét riêng.
-- Ép 25 người xem lưới cùng lúc: database ăn 349% CPU (3,5/4 nhân) trong khi
-- api chỉ 13% — trần ~20 lượt/giây nằm ở ĐÂY, không nằm ở số tiến trình api.
--
-- CÁCH SỬA MÀ KHÔNG NHÂN ĐÔI LUẬT. Luật đếm ghế là thứ trigger sức chứa dựa
-- vào để nhận/từ chối lịch — hai bản chép của nó thì bản nào cũng sẽ lỡ mất
-- lần sửa sau (chính chỗ này đã dọn một lần ở 20260807000001). Nên tách:
--
--   slot_seats_ban(khoảng thời gian)  ← LUẬT, một nguồn duy nhất:
--       mỗi ghế một dòng, kèm mốc thời gian ĐẶT nó vào khung
--   slot_seats_used(một khung)        ← vỏ mỏng đếm trên slot_seats_ban,
--       CHỮ KÝ VÀ HÀNH VI GIỮ NGUYÊN — trigger không biết gì đã đổi
--   lưới đặt lịch                     ← gọi slot_seats_ban MỘT lần cho cả
--       ngày rồi chia khung bằng số học (capacity_service)
--
-- Vì sao dòng ghế mang CẢ ts lẫn ts_goc: ghế "vãng lai trễ" (khách có hẹn
-- đến muộn) chỉ chiếm khung check-in khi khung ấy nằm SAU giờ hẹn
-- (`slot_start < bucket_start`). Phép so ấy cần cả hai mốc, và nó là phép so
-- của NGƯỜI ĐẾM THEO KHUNG chứ không phải của luật chọn ghế — nên nằm ở vỏ.

BEGIN;

-- ① Luật chọn ghế, phiên bản THEO KHOẢNG ----------------------------------
--
-- Trả về mỗi ghế một dòng:
--   loai   = 'DAT_HEN'     — ghế đặt hẹn, đặt vào khung theo slot_start
--            'VANG_LAI'    — khách vãng lai, đặt vào khung theo slot_start
--            'VANG_LAI_TRE'— khách CÓ HẸN nhưng check-in muộn; đặt vào khung
--                            theo giờ check-in, và CHỈ khi khung ấy sau giờ hẹn
--   ts     = mốc đặt ghế vào khung (slot_start hoặc checked_in_at)
--   ts_goc = slot_start gốc — vỏ đếm dùng cho phép so "khung sau giờ hẹn"
--
-- Điều kiện lọc là NGUYÊN VĂN từ slot_seats_used bản 20260807000001, chỉ đổi
-- "trong một khung" thành "trong một khoảng". Riêng ghế VANG_LAI_TRE lọc theo
-- checked_in_at (không theo slot_start): khách hẹn HÔM QUA mà sáng nay mới
-- tới vẫn phải chiếm ghế vãng lai của hôm nay — bản theo-khung cũ đếm đúng
-- như vậy, bản theo-khoảng không được làm rơi họ.
CREATE OR REPLACE FUNCTION public.slot_seats_ban(
    p_clinic_id            uuid,
    p_doctor_id            uuid,
    p_from                 timestamptz,
    p_to                   timestamptz,
    p_exclude_appointment  uuid DEFAULT NULL,
    p_location_id          uuid DEFAULT NULL
)
RETURNS TABLE (loai text, ts timestamptz, ts_goc timestamptz)
LANGUAGE sql
STABLE
-- Ước lượng CÓ THẬT thay cho mặc định 1000 dòng: một ngày phòng khám có vài
-- chục ghế. Thiếu dòng này, chi phí ước tính của lưới phình tới mức kích JIT
-- — đo 21/08/2026: LLVM biên dịch lại 173ms cho MỖI lần vẽ lưới, và đó mới
-- là thứ đốt 349% CPU database, không phải bản thân phép đếm.
ROWS 64
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
    WITH ghe AS (
        SELECT a.id,
               a.slot_start,
               upper(coalesce(a.booking_channel, '')) = 'WALK_IN' AS la_vang_lai
          FROM public.appointment a
         WHERE a.clinic_id = p_clinic_id
           AND a.id IS DISTINCT FROM p_exclude_appointment
           AND a.location_id IS NOT DISTINCT FROM
               coalesce(p_location_id, a.location_id)
           -- Cùng cách so bác sĩ mà trigger dùng: NULL khớp NULL (hàng "chưa
           -- phân bác sĩ" là một hàng riêng, có sức chứa riêng).
           AND coalesce(a.doctor_id::text, '~none~')
               = coalesce(p_doctor_id::text, '~none~')
           AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
    )
    -- Ghế theo giờ hẹn: đặt hẹn và vãng lai thật.
    SELECT CASE WHEN g.la_vang_lai THEN 'VANG_LAI' ELSE 'DAT_HEN' END,
           g.slot_start,
           g.slot_start
      FROM ghe g
     WHERE g.slot_start >= p_from
       AND g.slot_start <  p_to

    UNION ALL

    -- Ghế vãng lai trễ: khách có hẹn, check-in trong khoảng đang hỏi.
    SELECT 'VANG_LAI_TRE', v.checked_in_at, g.slot_start
      FROM ghe g
      JOIN public.visit v ON v.appointment_id = g.id
     WHERE NOT g.la_vang_lai
       AND v.checked_in_at >= p_from
       AND v.checked_in_at <  p_to
$function$;

COMMENT ON FUNCTION public.slot_seats_ban(
    uuid, uuid, timestamptz, timestamptz, uuid, uuid) IS
  'LUẬT chọn ghế, một nguồn duy nhất (20260821000002). slot_seats_used và '
  'lưới đặt lịch đều đếm trên hàm này. Ghế VANG_LAI_TRE cần vỏ đếm tự áp '
  'phép so ts_goc < đầu-khung.';

-- ② slot_seats_used thành vỏ mỏng — chữ ký, thuộc tính, hành vi GIỮ NGUYÊN --
CREATE OR REPLACE FUNCTION public.slot_seats_used(
    p_clinic_id            uuid,
    p_doctor_id            uuid,
    p_bucket_start         timestamptz,
    p_bucket_end           timestamptz,
    p_walkin               boolean,
    p_exclude_appointment  uuid DEFAULT NULL,
    p_location_id          uuid DEFAULT NULL
)
RETURNS integer
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
    SELECT count(*)::integer
      FROM public.slot_seats_ban(
               p_clinic_id, p_doctor_id, p_bucket_start, p_bucket_end,
               p_exclude_appointment, p_location_id) b
     WHERE CASE WHEN p_walkin THEN
                    b.loai = 'VANG_LAI'
                    -- "Khung sau giờ hẹn": nguyên văn slot_start <
                    -- p_bucket_start của bản cũ. Khách check-in ngay trong
                    -- khung hẹn của mình KHÔNG chiếm thêm ghế vãng lai.
                 OR (b.loai = 'VANG_LAI_TRE' AND b.ts_goc < p_bucket_start)
                ELSE
                    b.loai = 'DAT_HEN'
           END
$function$;

COMMENT ON FUNCTION public.slot_seats_used(
    uuid, uuid, timestamptz, timestamptz, boolean, uuid, uuid) IS
  'Số ghế đã dùng của một khung — vỏ mỏng trên slot_seats_ban từ '
  '20260821000002, hành vi y hệt bản 20260807000001. Vẫn là nguồn duy nhất '
  'cho trigger sức chứa và booking_service.';

-- ③ Khai đúng ước lượng cho hai hàm giàn giáo có sẵn --------------------
--
-- `clinic_hours_for_date` trả đúng MỘT dòng (giờ mở cửa của một ngày);
-- `resolve_effective_cap` trả đúng MỘT dòng luật. Mặc định 1000 dòng của
-- Postgres khiến `generate_series` phía trên bị ước thành cả nghìn tỉ dòng
-- → chi phí ảo vượt ngưỡng JIT → biên dịch lại mỗi lần chạy. Sửa ước lượng
-- là sửa tận gốc: mọi câu dùng hai hàm này (lưới, booking, trigger) cùng
-- hưởng, và không phải tắt JIT toàn cục.
ALTER FUNCTION public.clinic_hours_for_date(uuid, date) ROWS 1;
ALTER FUNCTION public.resolve_effective_cap(uuid, uuid, timestamptz) ROWS 1;

COMMIT;
