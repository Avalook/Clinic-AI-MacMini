-- KHÁCH CÒN NỢ — danh sách truy thu (Tuyền 01/10/2026). CHỈ ĐỌC.
--
-- Sự cố 30/09: nhân sự không có ca mở phiên khám, chỉ định, kê đơn; lễ tân
-- check-out khi còn vướng → khách về, phòng khám thu 0đ. Câu này liệt kê mọi
-- lượt ĐÃ CHECK-OUT (closed_at) từ mốc `tu_ngay` còn khoản chưa thu.
--
-- Chạy trên prod (chỉ SELECT):
--   ssh clinic-vps-moi "docker exec -i clinicai_db psql -U postgres -P pager=off" \
--     < scripts/bao-cao/khach-con-no.sql
--
-- Cùng luật hoá đơn máy chủ (`bill_service.hoa_don_con_no`) nhưng viết thuần SQL:
--   PHÍ KHÁM   : dịch vụ khám đã tick (luot_phi_kham còn hiệu lực) theo giá
--                bảng giá; chưa tick → giá mặc định của loại khám. Lịch "đi
--                thẳng phòng" mà khách đi thẳng phòng thật → không có phí khám.
--   DỊCH VỤ    : chỉ định khách ĐÃ CHỌN (SELECTED) còn tính tiền được, CỘNG chỉ
--                định ĐÃ LÀM / ĐANG LÀM dù quầy chưa chốt (làm rồi là phải thu).
--                Đối tác tự thu (EXTERNAL_PARTNER) không tính.
--   PHỤ THU    : luot_phu_thu đang tick của chỉ định còn tính.
--   ĐÃ PHỦ     : nguồn đã nằm trong lần thu PAID / PENDING_VERIFICATION
--                (payment_bill_line) thì không còn nợ.
-- Cột CẦN XÁC MINH (không cộng vào nợ chắc chắn):
--   * chỉ định bác sĩ đã ra mà khách CHƯA QUYẾT (selection PENDING) và máy
--     chưa ghi là đã làm — có thể làm ngoài máy (vd siêu âm ghi thẳng vào
--     phiếu khám), phải hỏi phòng;
--   * thuốc đã kê chưa thu — prod chưa ghi "đã giao" (dispense_status luôn
--     CHUA_CAP), nên phải hỏi quầy thuốc khách đã lấy chưa.
WITH tham_so AS (
    SELECT timestamptz '2026-09-29 00:00+07' AS tu_ngay
),
luot AS (
    SELECT v.*
      FROM public.visit v, tham_so t
     WHERE v.closed_at >= t.tu_ngay
),
-- ── Phí khám ────────────────────────────────────────────────────────────────
kham_goc AS (
    SELECT l.visit_id, l.clinic_id, st.name AS loai_kham,
           coalesce(st.gia_mac_dinh, 0) AS gia_mac_dinh,
           (coalesce(st.di_thang_phong, false)
            AND coalesce(ef.route_decision, 'SERVICES') = 'SERVICES') AS khong_kham
      FROM luot l
      LEFT JOIN public.appointment a
        ON a.id = l.appointment_id AND a.clinic_id = l.clinic_id
      LEFT JOIN public.service_type st
        ON st.id = coalesce(l.service_type_id, a.service_type_id)
      LEFT JOIN public.encounter_flow ef
        ON ef.clinic_id = l.clinic_id AND ef.visit_id = l.visit_id
),
dong_kham AS (
    -- Đã tick dịch vụ khám con.
    SELECT k.visit_id, k.clinic_id, 'Phí khám: ' || sp.name AS ten,
           coalesce(sp.unit_price, 0) AS tien,
           'exam-' || k.visit_id || '-selected-' || sp.id AS nguon
      FROM kham_goc k
      JOIN public.luot_phi_kham lp
        ON lp.clinic_id = k.clinic_id AND lp.visit_id = k.visit_id
       AND lp.bo_luc IS NULL
      JOIN public.service_price sp
        ON sp.id = lp.service_price_id AND sp.clinic_id = lp.clinic_id
     WHERE NOT k.khong_kham
       AND coalesce(sp.billing_owner, 'CLINIC') = 'CLINIC'
    UNION ALL
    -- Chưa tick → giá mặc định của loại khám.
    SELECT k.visit_id, k.clinic_id, 'Phí khám ' || k.loai_kham || ' (mặc định)',
           k.gia_mac_dinh, 'exam-' || k.visit_id
      FROM kham_goc k
     WHERE NOT k.khong_kham AND k.loai_kham IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM public.luot_phi_kham lp
                        WHERE lp.clinic_id = k.clinic_id
                          AND lp.visit_id = k.visit_id AND lp.bo_luc IS NULL)
),
-- ── Dịch vụ (chỉ định) ─────────────────────────────────────────────────────
gia_dv AS (
    -- Ưu tiên giá đang dùng nhóm dịch vụ; không có thì lấy giá bất kỳ của mã
    -- (hoá đơn máy chủ sẽ báo "chưa có giá" — nhưng khách vẫn nợ số này).
    SELECT clinic_id, service_code,
           coalesce(max(unit_price) FILTER (WHERE active AND "group" = 'dich_vu'),
                    max(unit_price) FILTER (WHERE active),
                    max(unit_price)) AS gia,
           coalesce(bool_or(billing_owner = 'EXTERNAL_PARTNER')
                      FILTER (WHERE active AND "group" = 'dich_vu'), false)
               AS doi_tac_thu
      FROM public.service_price
     GROUP BY clinic_id, service_code
),
chi_dinh AS (
    SELECT o.visit_id, o.clinic_id, o.id, o.service_name,
           coalesce(g.gia, 0) AS tien,
           coalesce(g.doi_tac_thu, false) AS doi_tac_thu,
           o.selection_status,
           (o.exec_status IN ('in_progress', 'performed')
            OR o.execution_status IN ('IN_PROGRESS', 'COMPLETED')) AS da_lam,
           (o.exec_status IN ('authorized', 'assigned', 'in_progress', 'performed')
            AND coalesce(o.execution_status, 'PENDING')
                IN ('PENDING', 'IN_PROGRESS', 'COMPLETED')) AS con_tinh,
           EXISTS (SELECT 1 FROM public.payment_bill_line bl
                     JOIN public.payment_cycle c
                       ON c.clinic_id = bl.clinic_id
                      AND c.payment_cycle_id = bl.payment_cycle_id
                    WHERE bl.clinic_id = o.clinic_id
                      AND bl.source_type = 'service_order'
                      AND bl.source_id = o.id::text
                      AND c.status IN ('PENDING_VERIFICATION', 'PAID')) AS da_phu
      FROM public.service_order o
      JOIN luot l ON l.visit_id = o.visit_id AND l.clinic_id = o.clinic_id
      LEFT JOIN gia_dv g
        ON g.clinic_id = o.clinic_id AND g.service_code = o.service_code
),
-- ── Thuốc đã kê ────────────────────────────────────────────────────────────
thuoc AS (
    SELECT r.visit_id, r.clinic_id, r.id, r.drug_name_raw,
           -- dispensed_qty = 0 nghĩa là "chưa cấp" (mặc định), không phải 0 viên.
           coalesce(nullif(r.dispensed_qty, 0), r.purchased_qty, r.quantity_num, 0)
             * coalesce(dc.unit_price, 0) AS tien,
           (coalesce(nullif(r.dispensed_qty, 0), r.purchased_qty, r.quantity_num)
              IS NULL) AS thieu_so_luong,
           EXISTS (SELECT 1 FROM public.payment_bill_line bl
                     JOIN public.payment_cycle c
                       ON c.clinic_id = bl.clinic_id
                      AND c.payment_cycle_id = bl.payment_cycle_id
                    WHERE bl.clinic_id = r.clinic_id
                      AND bl.source_type = 'prescription'
                      AND bl.source_id = r.id::text
                      AND c.status IN ('PENDING_VERIFICATION', 'PAID')) AS da_phu
      FROM public.prescription r
      JOIN luot l ON l.visit_id = r.visit_id AND l.clinic_id = r.clinic_id
      LEFT JOIN public.drug_catalog dc
        ON dc.id = r.drug_catalog_id AND dc.clinic_id = r.clinic_id
     WHERE r.removed_at IS NULL AND r.refusal_reason IS NULL
       AND coalesce(r.purchased_qty, 1) <> 0
),
-- ── Gom từng dòng còn nợ ───────────────────────────────────────────────────
dong_no AS (
    SELECT k.visit_id, 'CHAC' AS loai, k.ten, k.tien
      FROM dong_kham k
     WHERE NOT EXISTS (
         SELECT 1 FROM public.payment_bill_line bl
           JOIN public.payment_cycle c
             ON c.clinic_id = bl.clinic_id
            AND c.payment_cycle_id = bl.payment_cycle_id
          WHERE bl.clinic_id = k.clinic_id AND bl.source_type = 'exam'
            AND bl.billing_owner = 'CLINIC'
            AND c.status IN ('PENDING_VERIFICATION', 'PAID')
            -- nguồn đúng dòng, hoặc dòng khám gộp đời trước V2 (coi như phủ).
            AND bl.source_id IN (k.nguon, 'exam-' || k.visit_id))
    UNION ALL
    SELECT o.visit_id,
           CASE WHEN o.selection_status = 'SELECTED' OR o.da_lam THEN 'CHAC'
                ELSE 'XAC_MINH' END,
           o.service_name
             || CASE WHEN o.da_lam THEN ' (đã làm)'
                     WHEN o.selection_status = 'SELECTED' THEN ' (đã chốt)'
                     ELSE ' (chỉ định, khách chưa chốt)' END,
           o.tien
      FROM chi_dinh o
     WHERE o.con_tinh AND NOT o.da_phu AND NOT o.doi_tac_thu
       AND coalesce(o.selection_status, 'PENDING') <> 'NOT_SELECTED'
    UNION ALL
    SELECT p.visit_id, 'CHAC', 'Phụ thu: ' || p.ten, p.don_gia
      FROM public.luot_phu_thu p
      JOIN chi_dinh o ON o.id = p.service_order_id
     WHERE p.bo_luc IS NULL AND o.con_tinh
       AND (o.selection_status = 'SELECTED' OR o.da_lam)
       AND NOT EXISTS (
           SELECT 1 FROM public.payment_bill_line bl
             JOIN public.payment_cycle c
               ON c.clinic_id = bl.clinic_id
              AND c.payment_cycle_id = bl.payment_cycle_id
            WHERE bl.clinic_id = p.clinic_id AND bl.source_type = 'phu_thu'
              AND bl.source_id = p.id::text
              AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
    UNION ALL
    SELECT t.visit_id, 'THUOC',
           'Thuốc: ' || t.drug_name_raw
             || CASE WHEN t.thieu_so_luong THEN ' (đơn không ghi số lượng)' ELSE '' END,
           t.tien
      FROM thuoc t
     WHERE NOT t.da_phu
),
tong AS (
    SELECT visit_id,
           sum(tien) FILTER (WHERE loai = 'CHAC')     AS no_chac,
           sum(tien) FILTER (WHERE loai = 'XAC_MINH') AS chi_dinh_chua_chot,
           sum(tien) FILTER (WHERE loai = 'THUOC')    AS thuoc_chua_thu,
           -- Dòng 0đ vẫn liệt kê: "phí khám mặc định 0đ" nghĩa là chưa ai chọn
           -- dịch vụ khám — phí khám THẬT chưa được tính.
           string_agg(ten || ' ' || to_char(tien, 'FM999G999G999') || 'đ', '; '
                      ORDER BY loai, ten) AS cac_dong,
           bool_or(tien = 0 AND ten LIKE 'Phí khám %(mặc định)') AS phi_kham_0d
      FROM dong_no
     GROUP BY visit_id
),
da_thu AS (
    SELECT visit_id, sum(amount) AS da_thu
      FROM public.payment
     WHERE status = 'PAID' AND voided_at IS NULL
     GROUP BY visit_id
)
SELECT to_char(l.closed_at AT TIME ZONE 'Asia/Ho_Chi_Minh', 'DD/MM HH24:MI') AS checkout_luc,
       p.full_name                                    AS khach,
       p.patient_code                                 AS ma_kh,
       CASE WHEN length(p.phone_primary) >= 7
            THEN left(p.phone_primary, length(p.phone_primary) - 6) || '***'
                 || right(p.phone_primary, 3)
            ELSE p.phone_primary END                  AS sdt,
       coalesce(bs.full_name, '(không ghi BS)')      AS bac_si,
       nk.ai_kham                                     AS ai_kham_thuc_te,
       co.full_name                                   AS ai_checkout,
       CASE WHEN l.status = 'INCOMPLETE' THEN 'về giữa chừng' ELSE 'đã về' END AS kieu,
       coalesce(dt.da_thu, 0)                          AS da_thu,
       coalesce(t.no_chac, 0)                          AS con_no,
       coalesce(t.chi_dinh_chua_chot, 0)               AS can_xac_minh_chi_dinh,
       coalesce(t.thuoc_chua_thu, 0)                   AS can_xac_minh_thuoc,
       CASE WHEN t.phi_kham_0d THEN 'chưa chọn dịch vụ khám — phí khám 0đ'
            END                                       AS ghi_chu,
       t.cac_dong
  FROM luot l
  JOIN tong t ON t.visit_id = l.visit_id
  LEFT JOIN da_thu dt ON dt.visit_id = l.visit_id
  LEFT JOIN public.patient p
    ON p.clinic_patient_id = l.clinic_patient_id AND p.clinic_id = l.clinic_id
  LEFT JOIN public.appointment a
    ON a.id = l.appointment_id AND a.clinic_id = l.clinic_id
  LEFT JOIN LATERAL (
      SELECT c.doctor_staff_id, c.started_by
        FROM public.consultation c
       WHERE c.visit_id = l.visit_id AND c.clinic_id = l.clinic_id
         AND c.status <> 'cancelled'
       ORDER BY c.round_no LIMIT 1
  ) c1 ON true
  LEFT JOIN public.staff bs
    ON bs.id = coalesce(c1.doctor_staff_id, l.attending_doctor_id, a.doctor_id)
  LEFT JOIN LATERAL (
      SELECT string_agg(DISTINCT s.full_name, ', ') AS ai_kham
        FROM public.consultation c
        JOIN public.staff s ON s.id IN (c.started_by, c.completed_by)
       WHERE c.visit_id = l.visit_id AND c.clinic_id = l.clinic_id
         AND c.status <> 'cancelled'
  ) nk ON true
  LEFT JOIN public.staff co ON co.id = l.closed_by_staff_id
 WHERE coalesce(t.no_chac, 0) + coalesce(t.chi_dinh_chua_chot, 0)
       + coalesce(t.thuoc_chua_thu, 0) > 0
    OR t.phi_kham_0d
 ORDER BY l.closed_at;
