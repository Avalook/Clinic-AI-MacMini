-- Trạng thái phải nói về LƯỢT đang xem, không phải về cả khách.
--
-- QUANG 10/08/2026, ca của Cường: *"Cường đang ở lượt khám tái khám mà vào đã
-- check in luôn rồi, nên từ chờ xác nhận lịch trước 7 ngày chứ nhỉ"*.
--
-- Đúng, và đây là chỗ hỏng. `v_trang_thai_cskh` là `DISTINCT ON (clinic_id,
-- clinic_patient_id)` — MỘT dòng cho MỘT KHÁCH. Cường có ba lịch:
--
--     4d76c247  10/08 18:30  (lúc ấy CHECKED_IN)   ← việc thắng: DA_CHECKIN, ưu tiên 0
--     c8cafced  11/08 17:15  CONFIRMED, tái khám   ← lượt đang mở trên màn
--     c18e58bd  10/09 18:30  CONFIRMED
--
-- Màn hình mở lượt tái khám `c8cafced`, còn cột trạng thái nhận `DA_CHECKIN`
-- của lượt `4d76c247`. Nên node "Đã check-in" sáng chữ "đang ở đây" trên một
-- lượt khách CHƯA từng đến, và khối bên phải đổi tiêu đề thành "ĐÃ CHECK-IN —
-- XEM VIỆC TIẾP THEO" kèm nút "Check-in cho khách". Cả hai đều nói về lượt hôm
-- qua trong khi người trực đang chuẩn bị cho lượt ngày mai.
--
-- VIEW ĐÃ BIẾT ĐIỀU NÀY TỪ ĐẦU và vẫn trả cột `appointment_id` nói rõ việc ấy
-- thuộc lịch nào. Chỉ là không ai đọc: một dòng gộp cho cả khách thì cột ấy chỉ
-- kể được về đúng việc thắng, còn mọi việc của những lượt khác bị `DISTINCT ON`
-- ném đi trước khi tới được màn hình.
--
-- CÁCH CHỮA: bóc tầng `viec` ra thành một VIEW THẬT.
--
--     v_viec_cskh        MỌI việc đang mở, mỗi việc một dòng, có `appointment_id`
--     v_trang_thai_cskh  vẫn là "việc gấp nhất của mỗi khách", nay dựng TRÊN nó
--
-- Không viết lại luật ưu tiên bằng TypeScript. Luật ấy gồm mười nhánh, mỗi
-- nhánh một câu hỏi nghiệp vụ, và số ngày lấy từ `luat_cskh` — thứ phòng khám
-- sửa được không cần deploy. Chép sang trình duyệt là dựng bản thứ hai của một
-- thứ đã có, và bản thứ hai luôn là bản trôi đi.
--
-- Cùng lý do, `so_viec_mo` / `co_viec_qua_han` cũng đọc `v_viec_cskh`: trước
-- đây chúng được đếm trong cùng một câu bằng một CTE riêng, tức hai phép tính
-- song song cho một sự thật. Nay chỉ còn một chỗ đếm.
--
-- KHÔNG ĐỔI ĐẦU RA CỦA `v_trang_thai_cskh` — cùng cột, cùng thứ tự, cùng kiểu.
-- Đây là bản dựng lại bên trong, không phải hợp đồng mới.

-- ---------------------------------------------------------------------------
-- 1. Tầng việc, phơi ra thành view
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_viec_cskh
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
    -- Chép NGUYÊN VĂN mười nhánh của 20260810000004. Cố ý không sửa một chữ
    -- nào ở đây: migration này chỉ đổi chỗ ĐỨNG của tầng việc, không đổi luật.
    SELECT a.clinic_id, a.clinic_patient_id, 'DA_CHECKIN' AS loai, 0 AS uu_tien,
           h.d AS han, a.id AS appointment_id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'DA_CHECKIN' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status = 'CHECKED_IN'

    UNION ALL

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
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                            'COMPLETED', 'CHECKED_IN')
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
       AND (n.appointment_id IS NULL
            OR EXISTS (SELECT 1
                         FROM public.appointment a
                        WHERE a.id = n.appointment_id
                          AND a.status NOT IN ('CHECKED_IN', 'COMPLETED',
                                               'NO_SHOW', 'CANCELLED',
                                               'DOCTOR_DECLINED')))

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'NHAC_HEN_MAI', 8, h.d, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'NHAC_HEN_MAI' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                            'COMPLETED', 'CHECKED_IN')
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
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                            'COMPLETED', 'CHECKED_IN')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             BETWEEN h.d AND h.d + l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH')
)
SELECT v.clinic_id,
       v.clinic_patient_id,
       v.loai   AS trang_thai,
       l.nhan   AS nhan,
       v.uu_tien,
       v.han    AS han_xu_ly,
       (v.han < h.d) AS qua_han,
       -- NULL = việc KHÔNG thuộc một lượt cụ thể (kết quả xét nghiệm gắn với
       -- `lab_result`, lời hẹn gọi lại gắn với khách). Màn hình phải hiểu NULL
       -- là "đúng với mọi lượt", không phải "không đúng lượt nào".
       v.appointment_id
  FROM viec v
  CROSS JOIN hom_nay h
  JOIN public.luat_cskh l
    ON l.clinic_id = v.clinic_id AND l.loai_viec = v.loai;

COMMENT ON VIEW public.v_viec_cskh IS
    'MỌI việc CSKH đang mở, mỗi việc một dòng. `appointment_id` NULL = việc của '
    'khách chứ không của một lượt cụ thể. `v_trang_thai_cskh` là view này thu '
    'về một dòng mỗi khách.';

GRANT SELECT ON public.v_viec_cskh TO authenticated;

-- ---------------------------------------------------------------------------
-- 2. Việc gấp nhất mỗi khách — nay dựng TRÊN view kia
-- ---------------------------------------------------------------------------
-- Cùng cột, cùng thứ tự, cùng kiểu như 20260810000004, nên `CREATE OR REPLACE`
-- chạy được và không màn nào phải đổi theo.
CREATE OR REPLACE VIEW public.v_trang_thai_cskh
WITH (security_invoker = true) AS
WITH dem AS (
    SELECT clinic_id, clinic_patient_id,
           count(*) AS so_viec_mo,
           bool_or(qua_han) AS co_viec_qua_han
      FROM public.v_viec_cskh GROUP BY 1, 2
),
gap_nhat AS (
    -- QUÁ HẠN TRƯỚC, rồi mới tới ưu tiên. Đảo hai vế này là việc trễ ba ngày
    -- nằm im sau một việc chưa tới hạn (20260809000010).
    SELECT DISTINCT ON (clinic_id, clinic_patient_id) *
      FROM public.v_viec_cskh
     ORDER BY clinic_id, clinic_patient_id, qua_han DESC, uu_tien, han_xu_ly
)
SELECT v.clinic_id,
       v.clinic_patient_id,
       v.trang_thai,
       v.nhan,
       v.han_xu_ly,
       v.qua_han,
       d.so_viec_mo,
       d.co_viec_qua_han,
       v.appointment_id,
       EXISTS (SELECT 1 FROM public.tuong_tac_cskh t
                WHERE t.appointment_id = v.appointment_id
                  AND t.khach_xac_nhan) AS da_xac_nhan
  FROM gap_nhat v
  JOIN dem d ON d.clinic_id = v.clinic_id
            AND d.clinic_patient_id = v.clinic_patient_id;

COMMENT ON VIEW public.v_trang_thai_cskh IS
    'Việc gấp nhất đang mở của mỗi khách — QUÁ HẠN xếp trước. Dựng trên '
    'v_viec_cskh để hai phép tính không thể lệch nhau.';
