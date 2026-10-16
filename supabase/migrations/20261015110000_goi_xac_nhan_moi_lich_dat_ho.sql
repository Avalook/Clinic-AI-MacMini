-- GỌI XÁC NHẬN MỌI LỊCH DO NHÂN VIÊN ĐẶT HỘ (Tuyền chốt 15/10/2026).
--
-- TRƯỚC: `CHO_XAC_NHAN` chỉ sinh cho lịch đặt TRƯỚC mốc (ngày khám − 7). Lịch đặt
-- trong vòng 7 ngày cố ý không sinh việc (20260915000010: cuộc gọi đặt lịch coi là
-- lần liên hệ). Tuyền đổi luật: đặt hộ nào CSKH cũng gọi xác nhận lại.
--
-- NAY, nhánh CHO_XAC_NHAN của `v_viec_cskh`:
--   1. Bỏ điều kiện `created_at < slot − so_ngay`.
--   2. Loại lịch kênh WALK_IN (khách trực tiếp, check-in tại quầy). Đây là PHÂN
--      BIỆT DUY NHẤT hiện có: bảng `appointment` không có cột người đặt, và mọi
--      đường ghi lịch (booking_service, scheduling_service, nhập Notion) đều là
--      nhân viên đăng nhập — chưa có cổng khách tự đặt. Khi có cổng đó phải thêm
--      cột nguồn đặt (người đặt/ nguồn) và lọc theo cột ấy; test canh
--      `test_goi_xac_nhan_lich_dat_ho_db.py` đỏ nếu thêm đường ghi lịch mới.
--   3. HẠN = GREATEST(ngày khám − so_ngay, ngày đặt): lịch đặt sát ngày đến hạn
--      đúng hôm đặt, không bị "Quá hạn" ngay khi sinh. Lịch đặt xa giữ nguyên hạn cũ.
--   Cửa sổ hiện việc không đổi: từ hôm nay đến ngày khám ≤ hôm nay + so_ngay.
--   Đóng việc không đổi: có lần chạm XAC_NHAN_LICH chưa hoàn tác (mọi kết quả);
--   không nghe máy / hẹn gọi lại thì nhánh GOI_LAI đón; lịch huỷ/check-in/xong/
--   đã qua thì tự hết; rút lần chạm (huy_luc) thì việc quay lại.
--
-- CHỈ ĐỔI VIEW, KHÔNG BACKFILL: chép NGUYÊN bản 20260930700000, khác đúng nhánh
-- trên. Đầu ra (cột, thứ tự, kiểu) giữ nguyên nên `v_trang_thai_cskh` không đổi.
-- Nếu một nhánh đợt có bản `v_viec_cskh` MỚI HƠN 20260930700000 thì phải dựng lại
-- migration này trên bản đó (đã kiểm 15/10: main, gop-staging-1410m, #475 đều
-- dừng ở 20260930700000).
--
-- NHÃN: "Chờ xác nhận lịch" → "Gọi xác nhận lịch" cho khớp chip/bộ nút.

CREATE OR REPLACE VIEW public.v_viec_cskh
    WITH (security_invoker = true) AS
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
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text) AND (o.exec_status <> ALL (ARRAY['draft'::text, 'cancelled'::text])) AND o.ket_qua_luc IS NOT NULL AND o.duyet_luc IS NULL AND NOT (EXISTS ( SELECT 1
                   FROM tep_ket_qua k
                  WHERE k.clinic_id = o.clinic_id AND k.service_order_id = o.id AND k.da_xoa_luc IS NULL))
        UNION ALL
         SELECT o.clinic_id,
            vi.clinic_patient_id,
            'CHO_KQ_XN'::text AS text,
            3,
            COALESCE((f.due_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date, (COALESCE(o.finished_at, o.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay) AS "coalesce",
            vi.appointment_id
           FROM service_order o
             JOIN visit vi ON vi.visit_id = o.visit_id AND vi.clinic_id = o.clinic_id
             JOIN node_definition nd ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
             JOIN luat_cskh l_1 ON l_1.clinic_id = o.clinic_id AND l_1.loai_viec = 'CHO_KQ_XN'::text AND l_1.bat
             LEFT JOIN follow_up_case f ON f.clinic_id = o.clinic_id AND f.service_order_id = o.id AND f.status = 'OPEN'::text
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text) AND o.exec_status = 'performed'::text AND o.ket_qua_luc IS NULL AND o.created_at > (now() - '60 days'::interval)
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
          WHERE n.trang_thai = 'CHO_GOI'::text
            -- 29/09/2026: việc từ phiếu khám chỉ hiện TỪ hạn gọi (T−7).
            AND (n.nguon <> 'PHIEU_KHAM'::text
                 OR n.han_goi <= (now() AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date)
            AND (n.appointment_id IS NULL OR (EXISTS ( SELECT 1
                   FROM appointment a
                  WHERE a.id = n.appointment_id AND (a.status <> ALL (ARRAY['CHECKED_IN'::text, 'COMPLETED'::text, 'NO_SHOW'::text, 'CANCELLED'::text, 'DOCTOR_DECLINED'::text])))))
        UNION ALL
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
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'CHO_XAC_NHAN'::text AS text,
            10,
            -- Hạn = ngày khám − so_ngay, nhưng không sớm hơn NGÀY ĐẶT: lịch đặt sát ngày
            -- đến hạn đúng hôm đặt (quá hạn từ hôm sau), không sinh ra đã đỏ.
            GREATEST((a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date - l_1.so_ngay,
                     (a.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date),
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'CHO_XAC_NHAN'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= h_1.d AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d + l_1.so_ngay)
            -- 15/10/2026: mọi lịch do nhân viên đặt hộ đều cần gọi xác nhận, kể cả đặt
            -- sát ngày (trước đây bỏ lịch đặt trong vòng so_ngay ngày). Không có cột
            -- "ai đặt": mọi đường ghi lịch đều là nhân viên đăng nhập, chỉ trừ
            -- khách trực tiếp (kênh WALK_IN, tới quầy là check-in luôn).
            AND upper(coalesce(a.booking_channel, '')) <> 'WALK_IN' AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH'::text AND t.huy_luc IS NULL))
        UNION ALL
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.xac_nhan_trang_thai = 'HOP_LE'::text AND k.gui_luc IS NULL AND k.da_xoa_luc IS NULL
        UNION ALL
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.xac_nhan_trang_thai IS NULL AND k.gui_luc IS NULL AND k.da_xoa_luc IS NULL
        UNION ALL
         SELECT o.clinic_id,
            o.clinic_patient_id,
            'VUOT_SUC_CHUA'::text AS text,
            0,
            h_1.d,
            o.appointment_id
           FROM lich_vuot_suc_chua() o(clinic_id, appointment_id, clinic_patient_id, doctor_id, slot_start, tran, thu_tu, cong_bo_luc)
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

UPDATE public.luat_cskh
   SET nhan = 'Gọi xác nhận lịch'
 WHERE loai_viec = 'CHO_XAC_NHAN' AND nhan = 'Chờ xác nhận lịch';
