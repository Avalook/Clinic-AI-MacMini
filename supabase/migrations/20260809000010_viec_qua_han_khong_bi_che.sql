-- Việc QUÁ HẠN không được nấp sau một việc mới hơn.
--
-- CÁCH PHÁT HIỆN. Ô "Quá SLA" hiện 0. Không tin con số ấy — dựng một việc quá
-- hạn thật (hẹn gọi lại từ ba ngày trước) rồi xem ô có nhúc nhích không. Nó
-- không. Việc ấy biến mất hẳn khỏi màn.
--
-- VÌ SAO. View trả MỘT dòng cho mỗi khách (bảng là một dòng một khách), chọn
-- bằng `DISTINCT ON … ORDER BY uu_tien, han`. Chị Lan có hai việc đang mở:
--
--     HOI_LY_DO_HUY   ưu tiên 5, hạn hôm nay        ← thắng
--     HEN_GOI_LAI     ưu tiên 6, hạn 3 ngày trước   ← bị che
--
-- Ưu tiên thắng, nên việc trễ ba ngày nằm im cho tới khi việc kia được làm
-- xong. Mà "làm xong" ở đây là một cuộc gọi có thể không bao giờ diễn ra.
--
-- ĐÂY LÀ HAI HỎNG, KHÔNG PHẢI MỘT:
--   1. CSKH mất việc — thứ tính năng này sinh ra để chống.
--   2. Ô "Quá SLA" đếm hụt, và một ô số sai theo hướng thấp hơn sự thật là ô
--      số không ai đi kiểm.
--
-- SỬA: quá hạn xếp TRƯỚC. Thứ tự mới là (quá hạn, rồi ưu tiên, rồi hạn) — một
-- việc đã trễ luôn nổi lên trên một việc chưa tới hạn, dù việc kia gấp hơn về
-- bản chất. Kèm `so_viec_mo` để màn nói được "còn N việc khác", thay vì im lặng
-- giấu chúng.

-- DROP rồi tạo lại, không CREATE OR REPLACE: view thêm hai cột ở GIỮA, và
-- `CREATE OR REPLACE VIEW` chỉ nối thêm cột ở CUỐI — nó từ chối với
-- "cannot change name of view column". Không gì phụ thuộc view này (dashboard
-- đọc qua PostgREST), nên drop an toàn; GRANT cấp lại ở cuối file.
DROP VIEW IF EXISTS public.v_trang_thai_cskh;

CREATE VIEW public.v_trang_thai_cskh
WITH (security_invoker = true) AS
WITH hom_nay AS (
    SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d
),
cham_cuoi AS (
    SELECT DISTINCT ON (t.appointment_id)
           t.appointment_id, t.ket_qua, t.xay_ra_luc
      FROM public.tuong_tac_cskh t
     WHERE t.appointment_id IS NOT NULL
     ORDER BY t.appointment_id, t.xay_ra_luc DESC
),
viec AS (
    SELECT r.clinic_id, r.clinic_patient_id, 'CHO_BAC_SI' AS loai, 1 AS uu_tien,
           (r.result_received_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               + l.so_ngay AS han, NULL::uuid AS appointment_id
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'CHO_BAC_SI' AND l.bat
     WHERE r.result_value IS NOT NULL
       AND r.requires_doctor_review AND r.reviewed_at IS NULL

    UNION ALL

    SELECT r.clinic_id, r.clinic_patient_id, 'KQ_CHUA_GUI', 2,
           (coalesce(r.reviewed_at, r.result_received_at)
                AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + l.so_ngay, NULL
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'KQ_CHUA_GUI' AND l.bat
     WHERE r.result_value IS NOT NULL
       AND (NOT r.requires_doctor_review OR r.reviewed_at IS NOT NULL)
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.clinic_patient_id = r.clinic_patient_id
                AND t.loai = 'TRA_KQ' AND t.xay_ra_luc >= r.created_at)

    UNION ALL

    SELECT r.clinic_id, r.clinic_patient_id, 'CHO_KQ_XN', 3,
           (coalesce(r.sample_collected_at, r.created_at)
                AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + l.so_ngay, NULL
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'CHO_KQ_XN' AND l.bat
     WHERE r.result_value IS NULL

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'GOI_LAI', 4,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, a.id
      FROM public.appointment a
      JOIN cham_cuoi c ON c.appointment_id = a.id
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'GOI_LAI' AND l.bat
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED', 'COMPLETED')
       AND c.ket_qua IN ('CHUA_NGHE_MAY', 'KHONG_LIEN_LAC_DUOC', 'HEN_GOI_LAI')

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'HOI_LY_DO_HUY', 5,
           (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + l.so_ngay, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'HOI_LY_DO_HUY' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status = 'CANCELLED' AND a.cancelled_at IS NOT NULL
       AND (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             BETWEEN h.d - coalesce(l.cua_so_ngay, 14) AND h.d - l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'HOI_LY_DO_HUY')

    UNION ALL

    SELECT g.clinic_id, g.clinic_patient_id, 'HEN_GOI_LAI', 6, g.ngay_goi, NULL
      FROM public.hen_goi_lai g
      JOIN public.luat_cskh l ON l.clinic_id = g.clinic_id
                             AND l.loai_viec = 'HEN_GOI_LAI' AND l.bat
     CROSS JOIN hom_nay h
     WHERE g.dong_luc IS NULL AND g.ngay_goi <= h.d

    UNION ALL

    SELECT n.clinic_id, n.clinic_patient_id,
           CASE n.luot_goi WHEN 1 THEN 'MOI_TAI_KHAM' ELSE 'NHAC_DI_KHAM' END,
           CASE n.luot_goi WHEN 1 THEN 9 ELSE 7 END,
           n.han_goi, n.appointment_id
      FROM public.nhac_tai_kham n
      JOIN public.luat_cskh l
        ON l.clinic_id = n.clinic_id AND l.bat
       AND l.loai_viec = CASE n.luot_goi WHEN 1 THEN 'MOI_TAI_KHAM'
                                         ELSE 'NHAC_DI_KHAM' END
     WHERE n.trang_thai = 'CHO_GOI'

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'NHAC_HEN_MAI', 8, h.d, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'NHAC_HEN_MAI' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED', 'COMPLETED')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = h.d + l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'NHAC_HEN')

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'CHO_XAC_NHAN', 10,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'CHO_XAC_NHAN' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED', 'COMPLETED')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             BETWEEN h.d AND h.d + l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH')
),
-- Đánh dấu quá hạn NGAY Ở ĐÂY, để nó vào được thứ tự chọn bên dưới.
viec_co_co AS (
    SELECT v.*, (v.han < h.d) AS qua_han FROM viec v CROSS JOIN hom_nay h
),
dem AS (
    SELECT clinic_id, clinic_patient_id,
           count(*) AS so_viec_mo,
           bool_or(qua_han) AS co_viec_qua_han
      FROM viec_co_co GROUP BY 1, 2
),
gap_nhat AS (
    -- QUÁ HẠN TRƯỚC, rồi mới tới ưu tiên. Đảo hai vế này là việc trễ ba ngày
    -- nằm im sau một việc chưa tới hạn — xem chú thích đầu file.
    SELECT DISTINCT ON (clinic_id, clinic_patient_id) *
      FROM viec_co_co
     ORDER BY clinic_id, clinic_patient_id, qua_han DESC, uu_tien, han
)
SELECT v.clinic_id,
       v.clinic_patient_id,
       v.loai            AS trang_thai,
       l.nhan            AS nhan,
       v.han             AS han_xu_ly,
       v.qua_han,
       d.so_viec_mo,
       d.co_viec_qua_han,
       v.appointment_id,
       EXISTS (SELECT 1 FROM public.tuong_tac_cskh t
                WHERE t.appointment_id = v.appointment_id
                  AND t.khach_xac_nhan) AS da_xac_nhan
  FROM gap_nhat v
  JOIN public.luat_cskh l
    ON l.clinic_id = v.clinic_id AND l.loai_viec = v.loai
  JOIN dem d ON d.clinic_id = v.clinic_id
            AND d.clinic_patient_id = v.clinic_patient_id;

COMMENT ON VIEW public.v_trang_thai_cskh IS
    'Việc gấp nhất đang mở của mỗi khách — QUÁ HẠN xếp trước. `so_viec_mo` để '
    'màn nói được còn bao nhiêu việc khác thay vì im lặng giấu chúng.';

GRANT SELECT ON public.v_trang_thai_cskh TO authenticated;
