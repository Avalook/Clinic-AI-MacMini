-- "Đã check-in" phải là một trạng thái, không chỉ là một dòng sổ.
--
-- QUANG 09/08/2026: *"rõ ràng đã checkin rồi mà trạng thái chưa được đồng bộ…
-- ngay khi ấn vào đã checkin là mặc định chuyển trạng thái người này thành đã
-- checkin, chứ không phải là nhắc khám"*.
--
-- HAI VIỆC TÁCH RỜI, VÀ CHÍNH CHỖ TÁCH ẤY LÀ LỖI.
--
--   `appointment.status = 'CHECKED_IN'`  — máy trạng thái BIẾT khách đã đến.
--   `v_trang_thai_cskh`                  — KHÔNG có khái niệm ấy.
--
-- `luat_cskh` có 11 loại việc và không loại nào là "đã check-in". Nên khách
-- đang đứng ở phòng khám vẫn bị view xếp vào việc gấp nhất CÒN LẠI — thường là
-- "Chờ xác nhận lịch" của một lịch khác trong tương lai. Cột giữa nói khách đã
-- tới, chip bên trái nói cần gọi xác nhận: hai câu về cùng một người.
--
-- Thêm DA_CHECKIN với ƯU TIÊN 0 — cao hơn mọi việc khác. Khách có mặt tại chỗ
-- là sự thật gấp nhất về người đó; mọi cuộc gọi đều đợi được, còn người đang
-- đứng đấy thì không.
--
-- VÀ LOẠI CHECKED_IN RA KHỎI BA NHÁNH GỌI ĐIỆN. Cùng một lỗi như
-- 20260810000003 đã sửa cho NHAC_DI_KHAM, chỉ khác chỗ: CHO_XAC_NHAN,
-- NHAC_HEN_MAI, GOI_LAI đều đã lọc CANCELLED/NO_SHOW/DOCTOR_DECLINED/COMPLETED
-- nhưng bỏ sót CHECKED_IN — nên chúng vẫn giục gọi một người vừa bước vào cửa.
--
-- Không đụng HOI_LY_DO_HUY: nhánh ấy chỉ nhận status = 'CANCELLED'.

INSERT INTO public.luat_cskh (clinic_id, loai_viec, nhan, so_ngay, bat)
SELECT c.id, 'DA_CHECKIN', 'Đã check-in', 0, true
  FROM public.clinic c
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Dựng lại view: thêm nhánh DA_CHECKIN, và loại CHECKED_IN khỏi ba nhánh gọi
-- ---------------------------------------------------------------------------
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
    -- KHÁCH ĐANG ĐỨNG Ở PHÒNG KHÁM — ưu tiên 0, trên mọi việc khác.
    --
    -- Đây là nhánh DUY NHẤT không phải "việc CSKH phải làm" mà là "khách đang ở
    -- đâu". Cố ý: cột trạng thái là thứ người trực đọc để biết chuyện gì đang
    -- xảy ra với người này, và không có gì đang xảy ra rõ hơn việc họ có mặt.
    --
    -- `han = h.d` (hôm nay) nên nó không bao giờ quá hạn — người đã tới rồi thì
    -- không có gì để trễ. Đứng trước nhờ uu_tien, không nhờ cờ quá hạn.
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
     -- CHECKED_IN vào danh sách: ba nhánh này đều là GỌI ĐIỆN, và gọi cho một
     -- người vừa bước vào cửa thì vô nghĩa. Xem ghi chú đầu file.
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
     -- CHECKED_IN vào danh sách: ba nhánh này đều là GỌI ĐIỆN, và gọi cho một
     -- người vừa bước vào cửa thì vô nghĩa. Xem ghi chú đầu file.
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
     -- CHECKED_IN vào danh sách: ba nhánh này đều là GỌI ĐIỆN, và gọi cho một
     -- người vừa bước vào cửa thì vô nghĩa. Xem ghi chú đầu file.
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                            'COMPLETED', 'CHECKED_IN')
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
