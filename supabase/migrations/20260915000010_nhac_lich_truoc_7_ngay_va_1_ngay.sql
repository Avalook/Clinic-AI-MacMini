-- NHẮC LỊCH TRƯỚC 7 NGÀY VÀ TRƯỚC 1 NGÀY — đúng mốc Tuyền mô tả (15/09/2026).
--
-- LUẬT (nguyên văn ý Tuyền): khách gọi/Zalo ngày 2/9 đặt lịch khám 15/9 thì
-- trước 15/9 bảy ngày (8/9) CSKH phải liên hệ nhắc, và trước một ngày (14/9)
-- nhắc lại — để khách có đổi hay huỷ lịch thì còn xử lý được.
--
-- HAI CHỖ BẢN CŨ (20260812000001) LỆCH:
--   · CHO_XAC_NHAN hiện cho mọi lịch trong 7 ngày tới và HẠN = NGÀY KHÁM, nên
--     trước ngày khám việc không bao giờ đỏ — người trực không biết mình đã trễ
--     mốc 7 ngày.
--   · NHAC_HEN_MAI chỉ tồn tại ĐÚNG ngày hôm trước (slot = hôm nay + 1). Bỏ lỡ
--     hôm đó thì sang ngày khám việc biến mất, không ai biết đã không nhắc.
--
-- NAY:
--   · CHO_XAC_NHAN (so_ngay = 7): hạn = ngày khám − 7. Chỉ sinh cho lịch được
--     ĐẶT TRƯỚC mốc ấy — lịch đặt trong vòng 7 ngày thì cuộc gọi đặt lịch vừa
--     xảy ra đã là lần liên hệ, không bịa thêm một việc đã quá hạn từ lúc sinh.
--   · NHAC_HEN_MAI (so_ngay = 1): hạn = ngày khám − 1, còn mở tới khi khách đến.
--   · Đóng việc như cũ: có lần chạm cùng loại chưa hoàn tác. Gọi không nghe máy/
--     hẹn gọi lại thì nhánh GOI_LAI tiếp tục có hạn — "không nghe vẫn có
--     người/hạn tiếp tục" (CONTEXT v1.0).
--   · Số ngày vẫn lấy từ `luat_cskh` — phòng khám sửa được không cần deploy.
--
-- VÀ HAI NHÁNH KẾT QUẢ XÉT NGHIỆM (phát hiện khi chạy thật 15/09/2026):
--   · CHO_BAC_SI trước đây chỉ khi `requires_doctor_review` — cờ do AI bật.
--   · KQ_CHUA_GUI trước đây sinh khi `NOT requires_doctor_review` — nên KHÔNG
--     có AI thì CSKH bị giục gửi khách một kết quả bác sĩ CHƯA xem.
--   Nay theo quyết định "bác sĩ đánh giá/cho phép gửi" (CONTEXT v1.0): có kết
--   quả mà chưa chốt → CHO_BAC_SI; bác sĩ đã chốt (`is_finalized`, DB bắt buộc
--   có người duyệt) → KQ_CHUA_GUI. Nhóm AI không còn quyết việc của CSKH.
--
-- NGOÀI BỐN NHÁNH TRÊN KHÔNG ĐỔI GÌ. Mọi nhánh khác chép nguyên văn bản 20260812000001; đầu ra
-- (cột, thứ tự, kiểu) giữ nguyên nên `v_trang_thai_cskh` dựng trên nó không đổi.

BEGIN;

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
          WHERE k.gui_luc IS NULL
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

COMMIT;
