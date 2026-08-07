-- Lịch CHƯA PHÂN BÁC SĨ không chiếm ghế của ai.
--
-- BỐI CẢNH. Khách gọi đặt trước 2–3 tuần hoặc cả tháng — Quang nói đây là việc
-- diễn ra thường xuyên, không phải ca hiếm. Lúc ấy lịch trực chưa công bố, và
-- khách cũng không biết phòng khám có những bác sĩ nào. Nên phải ghi được
-- nguyện vọng khám mà chưa chốt bác sĩ; bác sĩ do quản lý xếp sau.
--
-- Database đã cho phép từ lâu: `appointment.doctor_id` là NULLABLE. Nhưng bộ
-- đếm ghế thì chưa.
--
-- CÁI BẪY. `slot_seats_used` gom bác sĩ bằng `coalesce(doctor_id::text,'~none~')`
-- nên mọi lịch chưa phân bác sĩ rơi vào MỘT làn chung, và trần của làn ấy là
-- `regular_cap` của luật "mọi bác sĩ" — mặc định 2. Khách thứ ba gọi đặt cho
-- một khung giờ tháng sau sẽ nhận "Khung giờ đã đầy" trong khi CẢ BẢY bác sĩ
-- đều trống. Lỗi này chỉ lộ ra khi có tải thật, không lộ lúc thử tay.
--
-- CÁCH SỬA, VÀ VÌ SAO KHÔNG PHẢI LÀ "NÂNG TRẦN".
--
-- Trần số chỗ là trần CỦA MỘT BÁC SĨ trong một khung giờ — nó trả lời "ông này
-- khám được mấy người lúc 18:00". Một lịch chưa có bác sĩ chưa chiếm chỗ của
-- ai cả, nên hỏi câu đó về nó là vô nghĩa. Nâng trần lên một con số to là chọn
-- một con số vô nghĩa khác, và rồi sẽ có ngày ai đó chạm phải nó.
--
-- Nên: MIỄN kiểm cho dòng chưa phân bác sĩ. Ràng buộc không biến mất — nó
-- chuyển sang đúng thời điểm nó có nghĩa. Lúc quản lý gán bác sĩ, `doctor_id`
-- đổi từ NULL sang một người, chốt "đã giữ ghế từ trước" KHÔNG áp dụng (vì
-- `OLD.doctor_id IS NOT DISTINCT FROM NEW.doctor_id` sai), nên trigger chạy đủ
-- và từ chối nếu khung ấy đã đầy. Đó chính là lúc câu hỏi trở thành thật.
--
-- Hệ quả phải nhìn thẳng: hàng chờ không có trần, nên có thể dồn nhiều hơn số
-- ghế thật. Đó là vấn đề XẾP LỊCH của quản lý và phải nhìn thấy được trên màn
-- hàng chờ — không phải lý do để từ chối khách ngay lúc họ gọi điện.

CREATE OR REPLACE FUNCTION public.enforce_slot_capacity()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    dead         text[] := ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'];
    none         text   := '~none~';
    bucket_start timestamptz;
    bucket_end   timestamptz;
    v_walkin     boolean;
    v_minutes    integer;
    v_seconds    integer;
    cap          integer;
    live_count   integer;
    lock_key     bigint;
BEGIN
    IF NEW.status = ANY (dead) THEN
        RETURN NEW;
    END IF;

    -- CHƯA PHÂN BÁC SĨ → chưa chiếm ghế của ai → không kiểm. Xem đầu file.
    IF NEW.doctor_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Đã giữ ghế từ trước → không đòi ghế mới → không kiểm.
    IF TG_OP = 'UPDATE'
       AND NOT (OLD.status = ANY (dead))
       AND OLD.slot_start = NEW.slot_start
       AND OLD.doctor_id IS NOT DISTINCT FROM NEW.doctor_id
       AND upper(coalesce(OLD.booking_channel, ''))
           = upper(coalesce(NEW.booking_channel, ''))
    THEN
        RETURN NEW;
    END IF;

    v_walkin := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';

    SELECT p.slot_minutes,
           CASE WHEN v_walkin THEN p.walkin_cap ELSE p.regular_cap END
      INTO v_minutes, cap
      FROM public.resolve_effective_cap(
               NEW.clinic_id, NEW.doctor_id, NEW.slot_start) AS p;

    v_seconds    := v_minutes * 60;
    bucket_start := to_timestamp(
        floor(extract(epoch FROM NEW.slot_start) / v_seconds) * v_seconds);
    bucket_end   := bucket_start + make_interval(mins => v_minutes);

    lock_key := hashtextextended(
        NEW.clinic_id::text || '|'
        || coalesce(NEW.doctor_id::text, none) || '|'
        || to_char(bucket_start, 'YYYYMMDDHH24MI') || '|'
        || (CASE WHEN v_walkin THEN 'w' ELSE 'r' END),
        0);
    PERFORM pg_advisory_xact_lock(lock_key);

    live_count := public.slot_seats_used(
        NEW.clinic_id, NEW.doctor_id, bucket_start, bucket_end,
        v_walkin, NEW.id);

    IF live_count >= cap THEN
        RAISE EXCEPTION
            'Khung giờ đã đầy: tối đa % chỗ % cho bác sĩ này trong khung % phút.',
            cap,
            CASE WHEN v_walkin THEN 'vãng lai' ELSE 'lịch hẹn' END,
            v_minutes
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.enforce_slot_capacity() IS
  'Trần số chỗ mỗi khung mỗi bác sĩ. Lịch chưa phân bác sĩ được miễn — nó chưa '
  'chiếm ghế của ai; trần áp lúc quản lý gán bác sĩ (20260808000002).';

-- Tra nhanh hàng chờ. Không có index này thì màn "Lịch chờ xếp bác sĩ" quét cả
-- bảng lịch hẹn mỗi lần mở.
CREATE INDEX IF NOT EXISTS idx_appointment_cho_xep_bac_si
    ON public.appointment (clinic_id, slot_start)
 WHERE doctor_id IS NULL
   AND status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED', 'COMPLETED');
