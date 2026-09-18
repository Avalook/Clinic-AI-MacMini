-- Slice 1 (18/09/2026): việc CSKH về KẾT QUẢ đọc rail mới.
--
-- `v_viec_cskh` có ba nhánh đọc `lab_result` (CHO_BAC_SI, KQ_CHUA_GUI,
-- CHO_KQ_XN). Luồng khám mới ghi chỉ định vào `service_order` và kết quả vào
-- `service_order.ket_qua_luc` / `tep_ket_qua` — không ghi `lab_result` — nên
-- một xét nghiệm gửi đối tác mà kết quả về muộn KHÔNG sinh việc "kết quả muộn"
-- nào cho CSKH (đo bằng đọc định nghĩa view, 18/09).
--
-- Thay ba nhánh ấy bằng hai nhánh trên `service_order`:
--   * CHO_KQ_XN: chỉ định cho-kết-quả-sau đã làm, chưa có kết quả; hạn lấy từ
--     follow_up_case bác sĩ đặt nếu có;
--   * CHO_BAC_SI: có kết quả (không phải tệp) mà bác sĩ chưa duyệt.
-- KQ_CHUA_GUI và CHO_BAC_SI dạng tệp vẫn do hai nhánh `tep_ket_qua` sẵn có.
-- Mọi nhánh khác giữ nguyên từng chữ (chép từ 20260915000014).

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
         -- RAIL MỚI (Slice 1, 20260918000002). Ba nhánh `lab_result` cũ nằm ở
         -- đây đã được thay: luồng khám mới không ghi `lab_result`, nên kết quả
         -- xét nghiệm của nó không bao giờ sinh việc CSKH nào.
         --
         -- CHO_BAC_SI: chỉ định cho-kết-quả-sau (làm bên ngoài / nhóm kết quả)
         -- đã có kết quả nhưng bác sĩ chưa duyệt, và kết quả KHÔNG ở dạng tệp
         -- (tệp đã có nhánh `tep_ket_qua` riêng bên dưới — không đếm hai lần).
         SELECT o.clinic_id,
            vi.clinic_patient_id,
            'CHO_BAC_SI'::text AS loai,
            1 AS uu_tien,
            (o.ket_qua_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay AS han,
            vi.appointment_id
           FROM service_order o
             JOIN visit vi ON vi.visit_id = o.visit_id AND vi.clinic_id = o.clinic_id
             JOIN node_definition nd ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
             JOIN luat_cskh l_1 ON l_1.clinic_id = o.clinic_id AND l_1.loai_viec = 'CHO_BAC_SI'::text AND l_1.bat
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text)
            AND o.exec_status <> ALL (ARRAY['draft'::text, 'cancelled'::text])
            AND o.ket_qua_luc IS NOT NULL AND o.duyet_luc IS NULL
            AND NOT (EXISTS ( SELECT 1
                   FROM tep_ket_qua k
                  WHERE k.clinic_id = o.clinic_id AND k.service_order_id = o.id))
        UNION ALL
         -- CHO_KQ_XN (KẾT QUẢ MUỘN): đã lấy mẫu / đã làm mà kết quả chưa về.
         -- Hạn = hạn của việc theo dõi bác sĩ đặt (follow_up_case) nếu có, không
         -- thì ngày làm + so_ngay của luật. Tự hết khi kết quả gắn vào chỉ định.
         SELECT o.clinic_id,
            vi.clinic_patient_id,
            'CHO_KQ_XN'::text AS text,
            3,
            COALESCE((f.due_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date,
                     (COALESCE(o.finished_at, o.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay),
            vi.appointment_id
           FROM service_order o
             JOIN visit vi ON vi.visit_id = o.visit_id AND vi.clinic_id = o.clinic_id
             JOIN node_definition nd ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
             JOIN luat_cskh l_1 ON l_1.clinic_id = o.clinic_id AND l_1.loai_viec = 'CHO_KQ_XN'::text AND l_1.bat
             LEFT JOIN follow_up_case f ON f.clinic_id = o.clinic_id AND f.service_order_id = o.id AND f.status = 'OPEN'::text
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text)
            AND o.exec_status = 'performed'::text
            AND o.ket_qua_luc IS NULL
            AND o.created_at > (now() - '60 days'::interval)
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
