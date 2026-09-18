-- SỨC CHỨA = SỐ KHÁCH ONLINE + SỐ KHÁCH TRỰC TIẾP, QUẢN LÝ ĐẶT (15/09/2026).
--
-- LUẬT (Tuyền chốt 15/09 tối): "2+1" chỉ là yêu cầu cũ của một phòng khám. Sản
-- phẩm để quản lý đặt, cho từng bác sĩ × khoảng giờ, hai con số:
--   · số khách ONLINE  = `regular_cap` (CSKH/online đặt trước),
--   · số khách TRỰC TIẾP = `walkin_cap` (lễ tân đặt tại quầy, check-in luôn).
-- Ba tầng cấu hình (mặc định phòng khám / luật cố định theo bác sĩ-giờ / ngoại
-- lệ tạm) đã có từ 20260803000011 — không đổi. Sức chứa để mọi người thấy lượng
-- khách và không dồn một bác sĩ vô tội vạ; KHÁM vẫn theo thứ tự check-in thật.
--
-- Hai thay đổi:
--
-- 1. BỎ "khách có hẹn đến muộn chiếm một ghế trực tiếp" (20260807000001 →
--    20260821000002, ghế VANG_LAI_TRE). Luật ấy đếm một khách hai lần (ghế hẹn
--    ở khung đặt + ghế trực tiếp ở khung tới nơi) và làm lễ tân không đặt được
--    khách trực tiếp chỉ vì có người đến trễ — trong khi thứ tự khám đã theo
--    giờ check-in, không cần ghế nào để "xếp" người trễ nữa.
--
-- 2. LỊCH VƯỢT TRẦN SAU KHI CÔNG BỐ → VIỆC CSKH TỪNG LỊCH. Trước khi có lịch trực,
--    CSKH đặt không giới hạn (20260915000001). Công bố xong, khung nào có nhiều
--    lịch online hơn trần thì những lịch ĐẶT SAU CÙNG (theo created_at) thành
--    việc `VUOT_SUC_CHUA` ở màn CSKH — ví dụ trần 10 mà có 12 lịch thì 2 lịch
--    đặt muộn nhất. Trước bản này chỉ Trưởng ca nhận MỘT thông báo liệt kê khung,
--    không nói lịch nào, và CSKH — người gọi khách — không được báo.

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
ROWS 64
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
    SELECT CASE WHEN upper(coalesce(a.booking_channel, '')) = 'WALK_IN'
                THEN 'VANG_LAI' ELSE 'DAT_HEN' END,
           a.slot_start,
           a.slot_start
      FROM public.appointment a
     WHERE a.clinic_id = p_clinic_id
       AND a.id IS DISTINCT FROM p_exclude_appointment
       AND a.location_id IS NOT DISTINCT FROM
           coalesce(p_location_id, a.location_id)
       AND coalesce(a.doctor_id::text, '~none~')
           = coalesce(p_doctor_id::text, '~none~')
       AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
       AND a.slot_start >= p_from
       AND a.slot_start <  p_to
$function$;

COMMENT ON FUNCTION public.slot_seats_ban(
    uuid, uuid, timestamptz, timestamptz, uuid, uuid) IS
  'Ghế của một khoảng giờ: DAT_HEN (online) và VANG_LAI (trực tiếp) theo giờ '
  'hẹn. Không còn ghế VANG_LAI_TRE — khách đến muộn không chiếm ghế trực tiếp '
  '(20260915000014).';

-- Lịch online vượt trần ở các tuần ĐÃ công bố, chưa tới giờ. Thứ tự trong khung
-- theo lúc đặt: ai đặt sau cùng là người vượt.
CREATE OR REPLACE FUNCTION public.lich_vuot_suc_chua()
RETURNS TABLE (
    clinic_id         uuid,
    appointment_id    uuid,
    clinic_patient_id uuid,
    doctor_id         uuid,
    slot_start        timestamptz,
    tran              integer,
    thu_tu            integer,
    cong_bo_luc       timestamptz
)
LANGUAGE sql
STABLE
-- SECURITY INVOKER có chủ ý: hàm nằm trong v_viec_cskh, và người đọc view phải
-- có quyền gọi mọi hàm trong đó. Chạy bằng quyền người gọi thì RLS của
-- appointment/roster_week vẫn khoá theo phòng khám nếu ai gọi thẳng qua RPC.
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $function$
    WITH lich AS (
        SELECT a.clinic_id, a.id, a.clinic_patient_id, a.doctor_id, a.slot_start,
               a.created_at, a.location_id, p.slot_minutes, p.regular_cap,
               rw.applied_at
          FROM public.appointment a
          JOIN public.roster_week rw
            ON rw.clinic_id = a.clinic_id
           AND rw.week_start = date_trunc(
                   'week', (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date
          CROSS JOIN LATERAL public.resolve_effective_cap(
                  a.clinic_id, a.doctor_id, a.slot_start) AS p
         WHERE a.doctor_id IS NOT NULL
           AND upper(coalesce(a.booking_channel, '')) <> 'WALK_IN'
           AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                                'CHECKED_IN', 'COMPLETED')
           AND a.slot_start > now()
    ),
    xep AS (
        SELECT l.*,
               row_number() OVER (
                   PARTITION BY l.clinic_id, l.location_id, l.doctor_id,
                       floor(extract(epoch FROM l.slot_start) / (l.slot_minutes * 60))
                   ORDER BY l.created_at, l.id
               )::integer AS thu_tu
          FROM lich l
    )
    SELECT x.clinic_id, x.id, x.clinic_patient_id, x.doctor_id, x.slot_start,
           x.regular_cap, x.thu_tu, x.applied_at
      FROM xep x
     WHERE x.thu_tu > x.regular_cap;
$function$;

COMMENT ON FUNCTION public.lich_vuot_suc_chua() IS
  'Lịch online đặt sau cùng vượt số khách online của khung, ở tuần đã công bố '
  'lịch trực — nguồn việc CSKH VUOT_SUC_CHUA (20260915000014).';


INSERT INTO public.luat_cskh (clinic_id, loai_viec, so_ngay, nhan)
SELECT c.id, 'VUOT_SUC_CHUA', 0, 'Lịch vượt sức chứa — gọi khách chốt hoặc đổi ca'
  FROM public.clinic c
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW public.v_viec_cskh AS
 WITH hom_nay AS (
         SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date AS d
        ), cham_cuoi AS (
         SELECT DISTINCT ON (t.appointment_id) t.appointment_id,
            t.ket_qua,
            t.xay_ra_luc
           FROM tuong_tac_cskh t
          WHERE t.appointment_id IS NOT NULL AND t.huy_luc IS NULL
          ORDER BY t.appointment_id, t.xay_ra_luc DESC
        ), viec AS (
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'DA_CHECKIN'::text AS loai,
            0 AS uu_tien,
            h_1.d AS han,
            a.id AS appointment_id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'DA_CHECKIN'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE a.status = 'CHECKED_IN'::text
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'CHO_BAC_SI'::text AS loai,
            1 AS uu_tien,
            (r.result_received_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay AS han,
            NULL::uuid AS appointment_id
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'CHO_BAC_SI'::text AND l_1.bat
          WHERE r.result_value IS NOT NULL AND NOT r.is_finalized
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (COALESCE(r.reviewed_at, r.result_received_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay,
            NULL::uuid AS uuid
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'KQ_CHUA_GUI'::text AND l_1.bat
          WHERE r.result_value IS NOT NULL AND r.is_finalized AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.clinic_patient_id = r.clinic_patient_id AND t.loai = 'TRA_KQ'::text AND t.xay_ra_luc >= COALESCE(r.reviewed_at, r.result_received_at, r.created_at) AND t.huy_luc IS NULL))
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'CHO_KQ_XN'::text AS text,
            3,
            (COALESCE(r.sample_collected_at, r.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay,
            NULL::uuid AS uuid
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'CHO_KQ_XN'::text AND l_1.bat
          WHERE r.result_value IS NULL
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'GOI_LAI'::text AS text,
            4,
            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date AS timezone,
            a.id
           FROM appointment a
             JOIN cham_cuoi c ON c.appointment_id = a.id
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'GOI_LAI'::text AND l_1.bat
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (c.ket_qua = ANY (ARRAY['CHUA_NGHE_MAY'::text, 'KHONG_LIEN_LAC_DUOC'::text, 'HEN_GOI_LAI'::text]))
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'HOI_LY_DO_HUY'::text AS text,
            5,
            (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'HOI_LY_DO_HUY'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE a.status = 'CANCELLED'::text AND a.cancelled_at IS NOT NULL AND (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= (h_1.d - COALESCE(l_1.cua_so_ngay, 14)) AND (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d - l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'HOI_LY_DO_HUY'::text AND t.huy_luc IS NULL))
        UNION ALL
         SELECT g.clinic_id,
            g.clinic_patient_id,
            'HEN_GOI_LAI'::text AS text,
            6,
            g.ngay_goi,
            NULL::uuid AS uuid
           FROM hen_goi_lai g
             JOIN luat_cskh l_1 ON l_1.clinic_id = g.clinic_id AND l_1.loai_viec = 'HEN_GOI_LAI'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE g.dong_luc IS NULL AND g.ngay_goi <= h_1.d
        UNION ALL
         SELECT n.clinic_id,
            n.clinic_patient_id,
                CASE n.luot_goi
                    WHEN 1 THEN 'MOI_TAI_KHAM'::text
                    ELSE 'NHAC_DI_KHAM'::text
                END AS "case",
                CASE n.luot_goi
                    WHEN 1 THEN 9
                    ELSE 7
                END AS "case",
            n.han_goi,
            n.appointment_id
           FROM nhac_tai_kham n
             JOIN luat_cskh l_1 ON l_1.clinic_id = n.clinic_id AND l_1.bat AND l_1.loai_viec =
                CASE n.luot_goi
                    WHEN 1 THEN 'MOI_TAI_KHAM'::text
                    ELSE 'NHAC_DI_KHAM'::text
                END
          WHERE n.trang_thai = 'CHO_GOI'::text AND (n.appointment_id IS NULL OR (EXISTS ( SELECT 1
                   FROM appointment a
                  WHERE a.id = n.appointment_id AND (a.status <> ALL (ARRAY['CHECKED_IN'::text, 'COMPLETED'::text, 'NO_SHOW'::text, 'CANCELLED'::text, 'DOCTOR_DECLINED'::text])))))
        UNION ALL
         -- NHẮC TRƯỚC 1 NGÀY (15/09): hiện từ mốc (ngày khám − so_ngay), hạn đúng
         -- mốc ấy, còn mở tới khi khách đến — bỏ lỡ ngày hôm trước thì sang ngày
         -- khám việc vẫn còn, đỏ quá hạn, không lặng lẽ biến mất như bản cũ.
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'NHAC_HEN_MAI'::text AS text,
            8,
            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date - l_1.so_ngay,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'NHAC_HEN_MAI'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= h_1.d AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d + l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'NHAC_HEN'::text AND t.huy_luc IS NULL))
        UNION ALL
         -- NHẮC TRƯỚC 7 NGÀY (15/09): chỉ cho lịch ĐẶT XA hơn so_ngay; hiện và
         -- đến hạn đúng ngày (ngày khám − so_ngay), quá mốc chưa gọi là đỏ.
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'CHO_XAC_NHAN'::text AS text,
            10,
            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date - l_1.so_ngay,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'CHO_XAC_NHAN'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= h_1.d AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d + l_1.so_ngay) AND (a.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date < ((a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date - l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH'::text AND t.huy_luc IS NULL))

        UNION ALL

        -- TỆP KẾT QUẢ CSKH TẢI LÊN MÀ CHƯA GỬI KHÁCH.
        --
        -- Nhánh `lab_result` phía trên đã có từ trước và chạy đúng — nhưng nó
        -- đọc BẢNG KHÁC với bảng CSKH thật sự dùng. CSKH tải phiếu kết quả lên
        -- `tep_ket_qua`; `lab_result` là kết quả xét nghiệm có cấu trúc, và các
        -- endpoint ghi vào đó gác cho vai lâm sàng — CSKH không tạo được.
        --
        -- Đo ngày 12/08/2026: tải một tệp lên, chưa gửi, và KHÔNG việc nào sinh
        -- ra. Tệp nằm im với `gui_luc IS NULL`, không gì nhắc ai cả. Nghĩa là
        -- khách có thể không bao giờ nhận được kết quả, và phòng khám không biết.
        --
        -- Điều kiện đóng việc là `gui_luc IS NOT NULL` — CSKH có nút "đã gửi"
        -- riêng cho tệp. KHÔNG dùng thêm `NOT EXISTS (TRA_KQ)` như nhánh
        -- lab_result: tệp có mốc gửi tường minh của chính nó, thêm một đường
        -- đóng thứ hai chỉ làm mờ câu hỏi "tệp này đã gửi chưa".
        SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.gui_luc IS NULL AND k.cho_phep_gui_luc IS NOT NULL
        UNION ALL
        -- TỆP CHƯA ĐƯỢC BÁC SĨ CHO PHÉP GỬI (20260915000011): CSKH thấy đang
        -- chờ bác sĩ, KHÔNG thấy việc "gửi kết quả".
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'CHO_BAC_SI'::text AS text,
            1,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_bs.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_bs ON l_bs.clinic_id = k.clinic_id AND l_bs.loai_viec = 'CHO_BAC_SI'::text AND l_bs.bat
          WHERE k.gui_luc IS NULL AND k.cho_phep_gui_luc IS NULL
        UNION ALL
        -- LỊCH VƯỢT SỨC CHỨA SAU KHI CÔNG BỐ LỊCH TRỰC (20260915000014): những
        -- khách đặt SAU CÙNG vượt số khách online quản lý đặt cho khung. CSKH gọi
        -- khách chốt giữ hay đổi ca. Tự hết khi lịch đổi/huỷ/quản lý nâng trần,
        -- hoặc khi CSKH ghi một lần chạm cho việc này sau lúc công bố.
         SELECT o.clinic_id,
            o.clinic_patient_id,
            'VUOT_SUC_CHUA'::text AS text,
            0,
            h_1.d,
            o.appointment_id
           FROM lich_vuot_suc_chua() o
             JOIN luat_cskh l_vt ON l_vt.clinic_id = o.clinic_id AND l_vt.loai_viec = 'VUOT_SUC_CHUA'::text AND l_vt.bat
             CROSS JOIN hom_nay h_1
          WHERE NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = o.appointment_id AND t.trang_thai_ma = 'VUOT_SUC_CHUA'::text AND t.xay_ra_luc >= o.cong_bo_luc AND t.huy_luc IS NULL))
        )
 SELECT v.clinic_id,
    v.clinic_patient_id,
    v.loai AS trang_thai,
    l.nhan,
    v.uu_tien,
    v.han AS han_xu_ly,
    v.han < h.d AS qua_han,
    v.appointment_id
   FROM viec v
     CROSS JOIN hom_nay h
     JOIN luat_cskh l ON l.clinic_id = v.clinic_id AND l.loai_viec = v.loai;
