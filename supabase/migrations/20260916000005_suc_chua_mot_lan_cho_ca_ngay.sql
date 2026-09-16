-- Sức chứa: hỏi MỘT lần cho cả ngày thay vì một lần cho mỗi khung giờ.
--
-- ĐO TRƯỚC KHI SỬA (máy chủ thật, 16/09/2026). Màn Đặt lịch mất 762ms. Không có
-- truy vấn nào chậm; có một HÀM bị gọi quá nhiều lần. `EXPLAIN ANALYZE` một ô
-- của lưới:
--
--     clinic_hours_for_date                    1,94ms  (1 lần)
--     resolve_effective_cap (lấy bước khung)   4,87ms  (1 lần)
--     resolve_effective_cap × 60 khung        15,4ms   ← 68% của cả truy vấn
--     ────────────────────────────────────────────────
--     Execution Time                          22,5ms
--
-- Và 0,256ms mỗi lần gọi ấy KHÔNG phải tiền tra bảng: hai bảng ngoại lệ đang
-- RỖNG (0 dòng) và index vẫn được dùng. Đó là tiền gọi hàm `SECURITY DEFINER`
-- có `SET search_path` — Postgres phải lưu rồi khôi phục GUC ở mỗi lần gọi, và
-- hàm SECURITY DEFINER thì không bao giờ được inline. Lưới tuần gọi nó
-- 18 hàng × 7 ngày × 60 khung = **7.560 lần** cho một lần mở màn.
--
-- CÁCH SỬA: đưa vòng lặp VÀO TRONG hàm. `resolve_effective_caps` nhận một mảng
-- phút và trả một dòng cho mỗi phút — cùng ba tầng luật, cùng thứ tự ưu tiên,
-- viết theo lối tập hợp. Một lời gọi cho cả ngày.
--
-- MỘT NGUỒN LUẬT, KHÔNG PHẢI HAI. `resolve_effective_cap` (một mốc) được viết
-- lại thành vỏ mỏng gọi chính hàm mới. Giữ nguyên chữ ký và kiểu trả về nên
-- trigger sức chứa, `slot_seats_ban` và mọi chỗ khác không phải đổi một dòng —
-- và quan trọng hơn: luật không bao giờ có hai bản để lệch nhau.
--
-- LUẬT KHÔNG ĐỔI. Ba tầng giữ nguyên thứ tự: ngoại lệ tạm thời (tầng 3) đè luật
-- thường trực (tầng 2) đè mặc định phòng khám (tầng 1); trong tầng 2 vẫn là
-- bác-sĩ-và-thứ > bác sĩ > thứ > mọi lúc, khoảng phút NULL nghĩa là cả ngày.
-- Các `ORDER BY ... LIMIT 1` được chép NGUYÊN VĂN sang dạng LATERAL.

BEGIN;

CREATE OR REPLACE FUNCTION public.resolve_effective_caps(
    p_clinic_id uuid,
    p_doctor_id uuid,
    p_date      date,
    p_minutes   integer[]
)
RETURNS TABLE(minute_of_day integer, slot_minutes integer,
              regular_cap integer, walkin_cap integer)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $$
    WITH phut AS (
        SELECT DISTINCT m AS v_minute FROM unnest(p_minutes) AS m
    ),
    -- Tầng 1 — mặc định phòng khám. Một lần cho cả ngày.
    cl AS (
        SELECT p.slot_minutes, p.regular_cap, p.walkin_cap
          FROM public.clinic_booking_policy(p_clinic_id) p
    )
    SELECT ph.v_minute,
           coalesce(d.slot_minutes, cl.slot_minutes),
           coalesce(s.regular_cap, d.regular_cap, cl.regular_cap),
           coalesce(s.walkin_cap,  d.walkin_cap,  cl.walkin_cap)
      FROM phut ph
      CROSS JOIN cl
      -- Tầng 3 — ngoại lệ TẠM THỜI (có khoảng ngày, có lý do bắt buộc).
      LEFT JOIN LATERAL (
          SELECT s2.regular_cap, s2.walkin_cap
            FROM public.slot_booking_override s2
           WHERE s2.clinic_id = p_clinic_id
             AND (s2.doctor_id = p_doctor_id OR s2.doctor_id IS NULL)
             AND p_date BETWEEN s2.date_start AND s2.date_end
             AND ph.v_minute >= s2.minute_start
             AND ph.v_minute <  s2.minute_end
           ORDER BY s2.doctor_id IS NULL
           LIMIT 1
      ) s ON TRUE
      -- Tầng 2 — luật THƯỜNG TRỰC, bốn mức cụ-thể-dần.
      LEFT JOIN LATERAL (
          SELECT d2.slot_minutes, d2.regular_cap, d2.walkin_cap
            FROM public.doctor_booking_override d2
           WHERE d2.clinic_id = p_clinic_id
             AND (d2.doctor_id = p_doctor_id OR d2.doctor_id IS NULL)
             AND d2.effective_from <= p_date
             AND (d2.effective_to IS NULL OR d2.effective_to >= p_date)
             AND (d2.weekday IS NULL
                  OR d2.weekday = EXTRACT(DOW FROM p_date)::smallint)
             AND (d2.minute_start IS NULL
                  OR (ph.v_minute >= d2.minute_start
                      AND ph.v_minute <  d2.minute_end))
           ORDER BY d2.doctor_id IS NULL,
                    d2.weekday IS NULL,
                    d2.minute_start IS NULL,
                    d2.effective_from DESC
           LIMIT 1
      ) d ON TRUE
$$;

COMMENT ON FUNCTION public.resolve_effective_caps(uuid, uuid, date, integer[]) IS
'Sức chứa hiệu lực cho NHIỀU mốc phút trong một ngày, một lời gọi. Ba tầng luật '
'giống hệt resolve_effective_cap — hàm kia nay là vỏ mỏng gọi hàm này.';

-- Vỏ mỏng: giữ nguyên chữ ký cũ cho trigger và mọi nơi đang gọi.
CREATE OR REPLACE FUNCTION public.resolve_effective_cap(
    p_clinic_id   uuid,
    p_doctor_id   uuid,
    p_slot_start  timestamp with time zone
)
RETURNS TABLE(slot_minutes integer, regular_cap integer, walkin_cap integer)
LANGUAGE sql
STABLE SECURITY DEFINER ROWS 1
SET search_path TO 'pg_catalog', 'public'
AS $$
    SELECT c.slot_minutes, c.regular_cap, c.walkin_cap
      FROM public.resolve_effective_caps(
               p_clinic_id,
               p_doctor_id,
               (p_slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,
               ARRAY[
                   EXTRACT(HOUR FROM p_slot_start
                           AT TIME ZONE 'Asia/Ho_Chi_Minh')::int * 60
                 + EXTRACT(MINUTE FROM p_slot_start
                           AT TIME ZONE 'Asia/Ho_Chi_Minh')::int
               ]
           ) c
$$;

GRANT EXECUTE ON FUNCTION
    public.resolve_effective_caps(uuid, uuid, date, integer[]) TO PUBLIC;

COMMIT;
