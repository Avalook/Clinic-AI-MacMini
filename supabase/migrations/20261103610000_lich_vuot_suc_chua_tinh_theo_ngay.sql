-- lich_vuot_suc_chua(): tra sức chứa MỘT LẦN cho mỗi (bác sĩ, ngày), không phải
-- mỗi lịch một lần.
--
-- Bản 20260915000014 gọi `resolve_effective_cap` cho TỪNG lịch tương lai, và mỗi
-- lần gọi lại đọc chính sách phòng khám + hai bảng ngoại lệ (~0,75 ms). Prod
-- 03/11: 163 lịch → 116 ms, cho kết quả 0 dòng. View `v_viec_cskh` chạy hàm này
-- nên nó nằm trong lịch tuần trang chủ (284 ms tb, 52k lượt) và các câu đếm của
-- khung CSKH (176 ms tb, 31k lượt).
--
-- `resolve_effective_caps` (bản mảng, cùng luật — `resolve_effective_cap` chỉ là
-- vỏ gọi nó với mảng một phần tử) nhận cả danh sách phút trong ngày, nên gom theo
-- (phòng khám, bác sĩ, ngày) là đủ. Phút trong ngày tính đúng biểu thức của
-- `resolve_effective_cap`. Không có chính sách thì cả hai bản đều bỏ dòng (CROSS
-- JOIN LATERAL ↔ JOIN). Đối chiếu trên prod (READ ONLY): 163/163 dòng xếp hạng
-- trùng khít cả `thu_tu`, `tran`; 116 ms → 9,8 ms.
--
-- Giữ nguyên chữ ký, STABLE, search_path → quyền và view không đổi.

CREATE OR REPLACE FUNCTION public.lich_vuot_suc_chua()
 RETURNS TABLE(clinic_id uuid, appointment_id uuid, clinic_patient_id uuid,
               doctor_id uuid, slot_start timestamp with time zone, tran integer,
               thu_tu integer, cong_bo_luc timestamp with time zone)
 LANGUAGE sql
 STABLE
 SET search_path TO 'pg_catalog', 'public'
AS $function$
    WITH lich AS (
        SELECT a.clinic_id, a.id, a.clinic_patient_id, a.doctor_id, a.slot_start,
               a.created_at, a.location_id, rw.applied_at,
               (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay,
               EXTRACT(HOUR FROM a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::int * 60
             + EXTRACT(MINUTE FROM a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::int
                   AS phut
          FROM public.appointment a
          JOIN public.roster_week rw
            ON rw.clinic_id = a.clinic_id
           AND rw.week_start = date_trunc(
                   'week', (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date
         WHERE a.doctor_id IS NOT NULL
           AND upper(coalesce(a.booking_channel, '')) <> 'WALK_IN'
           AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                                'CHECKED_IN', 'COMPLETED')
           AND a.slot_start > now()
    ),
    caps AS MATERIALIZED (
        SELECT k.clinic_id, k.doctor_id, k.ngay, c.minute_of_day,
               c.slot_minutes, c.regular_cap
          FROM (SELECT l.clinic_id, l.doctor_id, l.ngay,
                       array_agg(DISTINCT l.phut) AS ds
                  FROM lich l
                 GROUP BY l.clinic_id, l.doctor_id, l.ngay) k
          CROSS JOIN LATERAL public.resolve_effective_caps(
                  k.clinic_id, k.doctor_id, k.ngay, k.ds) AS c
    ),
    xep AS (
        SELECT l.*, p.slot_minutes, p.regular_cap,
               row_number() OVER (
                   PARTITION BY l.clinic_id, l.location_id, l.doctor_id,
                       floor(extract(epoch FROM l.slot_start) / (p.slot_minutes * 60))
                   ORDER BY l.created_at, l.id
               )::integer AS thu_tu
          FROM lich l
          JOIN caps p
            ON p.clinic_id = l.clinic_id AND p.doctor_id = l.doctor_id
           AND p.ngay = l.ngay AND p.minute_of_day = l.phut
    )
    SELECT x.clinic_id, x.id, x.clinic_patient_id, x.doctor_id, x.slot_start,
           x.regular_cap, x.thu_tu, x.applied_at
      FROM xep x
     WHERE x.thu_tu > x.regular_cap;
$function$;
