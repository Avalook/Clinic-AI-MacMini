-- Trần sức chứa chỉ CHẶN khi tuần lịch trực ĐÃ CÔNG BỐ.
--
-- LUẬT (CONTEXT v1.0, Tuyền chốt 12/09/2026):
--   · Đặt lịch TRƯỚC khi công bố lịch trực: nhận, không chặn bằng sức chứa.
--   · Lúc công bố: đối soát — giữ hết lịch, khung vượt trần thành xung đột có
--     người xử lý (config_service.apply_week).
--   · SAU khi công bố: khung đầy thì chặn, kiểm ở server khi đồng thời.
--
-- VÌ SAO. Trước bản này trigger kiểm trần cho MỌI lịch đã chọn bác sĩ, bất kể
-- tuần đó phòng khám đã chốt ai trực chưa. Trần "2 chỗ mỗi khung" là câu trả
-- lời cho "bác sĩ này khám được mấy người lúc 18:00" — một câu chỉ có nghĩa
-- khi đã biết bác sĩ ấy đi làm. CSKH nhận đặt trước cả tháng theo nguyện vọng
-- của khách; từ chối khách thứ ba vì một con số áp lên một lịch trực chưa tồn
-- tại là để hệ thống quyết thay phòng khám.
--
-- "ĐÃ CÔNG BỐ" = có dòng trong `roster_week` (20260808000001) cho tuần chứa
-- giờ hẹn — cùng một sự thật mà booking_service._roster_warning và
-- capacity_service.quote đã dùng. Không suy ra từ work_roster.status.
--
-- KHÁCH VÃNG LAI KHÔNG ĐỔI: họ đang đứng ở quầy trong ngày, `walkin_cap` vẫn
-- là con số giữ cho phòng chờ không vỡ (xem 20260808000002).

CREATE OR REPLACE FUNCTION public.tuan_lich_truc_da_cong_bo(
    p_clinic_id uuid,
    p_ts        timestamptz
) RETURNS boolean
LANGUAGE sql
STABLE
AS $function$
    SELECT EXISTS (
        SELECT 1
          FROM public.roster_week rw
         WHERE rw.clinic_id = p_clinic_id
           AND rw.week_start = date_trunc(
                   'week', (p_ts AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               )::date
    );
$function$;

COMMENT ON FUNCTION public.tuan_lich_truc_da_cong_bo(uuid, timestamptz) IS
  'Tuần (thứ Hai giờ VN) chứa mốc p_ts đã được quản lý bấm Áp dụng lịch trực '
  'chưa. Nguồn cho luật "trần chỉ chặn sau công bố" (20260915000001).';

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

    v_walkin := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';

    -- LỊCH HẸN chưa phân bác sĩ → chưa chiếm ghế của ai → không kiểm.
    -- KHÁCH VÃNG LAI thì vẫn kiểm (20260808000002).
    IF NEW.doctor_id IS NULL AND NOT v_walkin THEN
        RETURN NEW;
    END IF;

    -- LỊCH HẸN vào tuần CHƯA CÔNG BỐ lịch trực → nhận, đối soát lúc công bố.
    IF NOT v_walkin
       AND NOT public.tuan_lich_truc_da_cong_bo(NEW.clinic_id, NEW.slot_start)
    THEN
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
  'Trần số chỗ mỗi khung mỗi bác sĩ. LỊCH HẸN chưa phân bác sĩ, hoặc rơi vào '
  'tuần CHƯA công bố lịch trực, được miễn — đối soát lúc công bố '
  '(20260915000001). Khách VÃNG LAI luôn bị trần walkin_cap (20260808000002).';

-- ĐỐI SOÁT LÚC CÔNG BỐ. Những khung (bác sĩ × khung giờ) của một tuần mà số
-- lịch hẹn còn sống, chưa tới giờ, VƯỢT trần. Không huỷ, không đổi gì — chỉ
-- liệt kê để config_service.apply_week giao cho người xử lý (Trưởng ca).
-- Đếm bằng CHÍNH slot_seats_used mà trigger dùng, để "vượt trần" ở đây và
-- "đầy" ở trigger là cùng một con số.
CREATE OR REPLACE FUNCTION public.khung_vuot_tran_trong_tuan(
    p_clinic_id  uuid,
    p_week_start date
) RETURNS TABLE (
    doctor_id    uuid,
    bat_dau      timestamptz,
    so_phut      integer,
    tran         integer,
    da_dung      integer
)
LANGUAGE sql
STABLE
AS $function$
    WITH lich AS (
        SELECT a.doctor_id, a.slot_start, p.slot_minutes, p.regular_cap
          FROM public.appointment a
          CROSS JOIN LATERAL public.resolve_effective_cap(
                  a.clinic_id, a.doctor_id, a.slot_start) AS p
         WHERE a.clinic_id = p_clinic_id
           AND a.doctor_id IS NOT NULL
           AND upper(coalesce(a.booking_channel, '')) <> 'WALK_IN'
           AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
           AND a.slot_start > now()
           AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               BETWEEN p_week_start AND p_week_start + 6
    ),
    khung AS (
        SELECT DISTINCT
               l.doctor_id,
               to_timestamp(floor(extract(epoch FROM l.slot_start)
                                  / (l.slot_minutes * 60))
                            * (l.slot_minutes * 60)) AS bat_dau,
               l.slot_minutes,
               l.regular_cap
          FROM lich l
    ),
    dem AS (
        SELECT k.*,
               public.slot_seats_used(
                   p_clinic_id, k.doctor_id, k.bat_dau,
                   k.bat_dau + make_interval(mins => k.slot_minutes),
                   FALSE, NULL) AS da_dung
          FROM khung k
    )
    SELECT d.doctor_id, d.bat_dau, d.slot_minutes, d.regular_cap, d.da_dung
      FROM dem d
     WHERE d.da_dung > d.regular_cap
     ORDER BY d.bat_dau, d.doctor_id;
$function$;

COMMENT ON FUNCTION public.khung_vuot_tran_trong_tuan(uuid, date) IS
  'Khung vượt trần của một tuần — đối soát lúc công bố lịch trực. Chỉ đọc; '
  'không huỷ lịch nào (CONTEXT v1.0, 20260915000001).';
