-- Khách đã đến rồi thì thôi giục gọi nhắc.
--
-- QUANG BẮT ĐƯỢC 09/08/2026: trên cùng một màn, cột giữa tích xanh "Đã
-- check-in" trong khi cột trái vẫn dán nhãn "Nhắc đi khám hôm nay" cho đúng
-- người đó. Ô đếm "Cần xử lý hôm nay" cũng cộng nhầm theo, vì nó đọc chung một
-- nguồn.
--
-- VÌ SAO. Nhánh `MOI_TAI_KHAM` / `NHAC_DI_KHAM` của `v_trang_thai_cskh` đọc
-- hàng đợi `nhac_tai_kham`, và điều kiện DUY NHẤT của nó là
-- `trang_thai = 'CHO_GOI'` — trạng thái của VIỆC GỌI, không phải của lịch hẹn.
-- Việc gọi chỉ đóng khi có người bấm đóng nó. Khách đến, check-in, khám xong,
-- ra về — hàng đợi ấy vẫn mở, vì không ai nói cho nó biết.
--
-- Nhánh này là NGOẠI LỆ DUY NHẤT trong view. Bảy nhánh còn lại có gắn lịch hẹn
-- đều đã lọc `status NOT IN (CANCELLED, NO_SHOW, DOCTOR_DECLINED, COMPLETED)`.
-- Nhánh này bỏ sót, nên nó là nhánh duy nhất nói ngược với phần còn lại.
--
-- SỬA Ở VIEW, KHÔNG SỬA Ở MÀN HÌNH. Sửa tầng hiển thị thì cái nhãn hết sai
-- nhưng con số vẫn sai — ô đếm đọc thẳng view. Bản chất vấn đề nằm ở đây.
--
-- THÊM `CHECKED_IN` VÀO DANH SÁCH, không dùng lại y nguyên bốn trạng thái kia.
-- Với bảy nhánh khác, CHECKED_IN là "đang trong ca khám, vẫn còn việc". Với
-- một lời NHẮC ĐI KHÁM thì nó là dấu chấm hết: người ta đã đi rồi.
--
-- KHÔNG ĐỤNG TỚI VIỆC CHƯA CÓ LỊCH. `appointment_id` là NULL với nguồn
-- CSKH_NHAP (20260810000001) — "khách nói tháng sau quay lại", chưa đặt lịch
-- bao giờ. Đó chính là những người CẦN gọi mời đặt nhất; lọc nhầm chúng đi là
-- đổi một lỗi hiện rõ lấy một lỗi im lặng.
--
-- CREATE OR REPLACE chứ không DROP: cột không đổi, nên giữ được GRANT và view
-- không biến mất một nhịp giữa chừng.

CREATE OR REPLACE VIEW public.v_trang_thai_cskh
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
       -- ĐÂY LÀ TOÀN BỘ THAY ĐỔI CỦA MIGRATION NÀY.
       --
       -- `trang_thai = 'CHO_GOI'` nói việc gọi chưa được đóng; nó KHÔNG nói
       -- khách chưa tới. Hai câu đó khác nhau, và trước đây view chỉ hỏi câu
       -- đầu — nên nhãn "Nhắc đi khám hôm nay" bám dai cả sau khi khách đã
       -- check-in, khám xong, thậm chí đã huỷ.
       --
       -- `IS NULL` phải đứng trước: việc nguồn CSKH_NHAP chưa gắn lịch hẹn nào,
       -- và chúng là những người cần gọi nhất.
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
