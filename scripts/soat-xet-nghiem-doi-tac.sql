-- SOÁT XÉT NGHIỆM ĐỐI TÁC — CHỈ ĐỌC (chặng 0, docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md mục 6).
-- Tuyền chạy trên prod, dán kết quả vào PR chặng 1:
--   ssh clinic-vps-moi 'docker exec -i clinicai_db psql -U postgres -d postgres' < scripts/soat-xet-nghiem-doi-tac.sql
-- Chỉ in mã/tên dịch vụ, tên nhân viên và con số — không in tên hay mã khách.
\set ON_ERROR_STOP on
SET default_transaction_read_only = on;
SET statement_timeout = '30s';

-- (a1) Dịch vụ "đối tác thu" (EXTERNAL_PARTNER): mã, tên, giá, bước, ai đặt bên thu.
--      Giá 0/NULL và dịch vụ đã tắt vẫn hiện — đó là thứ cần dọn (kế hoạch câu H).
SELECT '(a1) dich vu doi tac thu' AS muc, c.code AS co_so, sp.service_code, sp.name,
       sp."group", sp.unit_price, sp.node_code, coalesce(n.lam_ben_ngoai, false) AS lam_ben_ngoai,
       sp.doi_tac_lay_mau, sp.billing_owner_chon_tay, sp.active
  FROM public.service_price sp
  JOIN public.clinic c ON c.id = sp.clinic_id
  LEFT JOIN public.node_definition n ON n.clinic_id = sp.clinic_id AND n.code = sp.node_code
 WHERE sp.billing_owner = 'EXTERNAL_PARTNER'
 ORDER BY c.code, sp.active DESC, sp.name;

-- (a2) Cặp tên gần trùng trong dịch vụ đối tác thu còn bật: bỏ dấu cách/ký tự, chữ thường,
--      trùng hẳn hoặc tên này nằm trong tên kia (vd "HPV + ThinPrep" / "ThinPrep").
WITH ds AS (
  SELECT sp.id, sp.clinic_id, sp.service_code, sp.name, sp.unit_price,
         regexp_replace(lower(sp.name), '[^[:alnum:]]+', '', 'g') AS chuan
    FROM public.service_price sp
   WHERE sp.billing_owner = 'EXTERNAL_PARTNER' AND sp.active
)
SELECT '(a2) cap ten gan trung' AS muc, a.service_code AS ma_1, a.name AS ten_1, a.unit_price AS gia_1,
       b.service_code AS ma_2, b.name AS ten_2, b.unit_price AS gia_2
  FROM ds a
  JOIN ds b ON b.clinic_id = a.clinic_id AND a.id < b.id
 WHERE length(a.chuan) >= 3 AND length(b.chuan) >= 3
   AND (a.chuan = b.chuan OR position(a.chuan IN b.chuan) > 0 OR position(b.chuan IN a.chuan) > 0)
 ORDER BY a.name, b.name;

-- (a3) Nghi gắn sai bên thu: dịch vụ còn bật, bước làm bên ngoài hoặc đối tác tự lấy mẫu,
--      nhưng bên thu vẫn là phòng khám.
SELECT '(a3) nghi sai ben thu' AS muc, c.code AS co_so, sp.service_code, sp.name, sp.unit_price,
       sp.node_code, coalesce(n.lam_ben_ngoai, false) AS lam_ben_ngoai, sp.doi_tac_lay_mau,
       sp.billing_owner, sp.billing_owner_chon_tay
  FROM public.service_price sp
  JOIN public.clinic c ON c.id = sp.clinic_id
  LEFT JOIN public.node_definition n ON n.clinic_id = sp.clinic_id AND n.code = sp.node_code
 WHERE sp.active AND sp.billing_owner <> 'EXTERNAL_PARTNER'
   AND (coalesce(n.lam_ben_ngoai, false) OR sp.doi_tac_lay_mau)
 ORDER BY c.code, sp.name;

-- (b) Sổ thu hộ doi_tac_thanh_toan theo tháng ghi nhận (giờ Việt Nam) và hình thức:
--     số dòng còn hiệu lực, số dòng đã huỷ, tổng tiền còn hiệu lực.
SELECT '(b) so thu ho theo thang' AS muc, c.code AS co_so,
       to_char(t.ghi_luc AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM') AS thang, t.hinh_thuc,
       count(*) FILTER (WHERE t.huy_luc IS NULL) AS con_hieu_luc,
       count(*) FILTER (WHERE t.huy_luc IS NOT NULL) AS da_huy,
       coalesce(sum(t.so_tien) FILTER (WHERE t.huy_luc IS NULL), 0) AS tong_con_hieu_luc
  FROM public.doi_tac_thanh_toan t
  JOIN public.clinic c ON c.id = t.clinic_id
 GROUP BY 2, 3, 4
 ORDER BY 2, 3, 4;

-- (c) Tài khoản vai PARTNER và lần thao tác gần nhất trong 30 ngày (event_log ghi
--     metadata.clinic_staff_id = staff.id). Không có thao tác nào = cột cuối NULL, 0.
SELECT '(c) tai khoan PARTNER' AS muc, c.code AS co_so, s.full_name, s.is_active AS nv_con_lam,
       m.is_active AS vai_con_bat,
       max(e.occurred_at) AT TIME ZONE 'Asia/Ho_Chi_Minh' AS thao_tac_cuoi_30_ngay,
       count(e.event_id) AS so_thao_tac_30_ngay
  FROM public.clinic_membership m
  JOIN public.clinic c ON c.id = m.clinic_id
  JOIN public.staff s ON s.id = m.staff_id
  LEFT JOIN public.event_log e
    ON e.metadata->>'clinic_staff_id' = s.id::text
   AND e.occurred_at >= now() - interval '30 days'
 WHERE m.role = 'PARTNER'
 GROUP BY 2, 3, 4, 5
 ORDER BY 2, 3;

-- (c2) Sự kiện partner.* 30 ngày theo loại và vai người bấm — bàn cũ còn ai dùng (câu D).
SELECT '(c2) su kien partner 30 ngay' AS muc, e.event_type,
       coalesce(e.metadata->>'vai_tai_khoan', '(he thong)') AS vai, count(*) AS so_lan,
       max(e.occurred_at) AT TIME ZONE 'Asia/Ho_Chi_Minh' AS lan_cuoi
  FROM public.event_log e
 WHERE e.event_type LIKE 'partner.%' AND e.occurred_at >= now() - interval '30 days'
 GROUP BY 2, 3
 ORDER BY 2, 3;

-- (d) Tệp kết quả đang CHO_XAC_NHAN (chưa thu hồi, chưa xoá, còn tệp): bao nhiêu, cũ nhất,
--     bao nhiêu thuộc việc đối tác (có dòng doi_tac_nhan_viec).
SELECT '(d) tep CHO_XAC_NHAN' AS muc, c.code AS co_so, count(*) AS so_tep,
       count(*) FILTER (WHERE nv.service_order_id IS NOT NULL) AS cua_viec_doi_tac,
       count(*) FILTER (WHERE t.gui_luc IS NOT NULL) AS da_gui,
       min(t.tai_len_luc) AT TIME ZONE 'Asia/Ho_Chi_Minh' AS cu_nhat
  FROM public.tep_ket_qua t
  JOIN public.clinic c ON c.id = t.clinic_id
  LEFT JOIN public.doi_tac_nhan_viec nv
    ON nv.clinic_id = t.clinic_id AND nv.service_order_id = t.service_order_id
 WHERE t.xac_nhan_trang_thai = 'CHO_XAC_NHAN'
   AND t.thu_hoi_luc IS NULL AND t.da_xoa_luc IS NULL AND t.da_don_tep_luc IS NULL
 GROUP BY 2
 ORDER BY 2;

-- (e) Việc đối tác đang dở theo trạng thái bàn cũ. CASE dưới đây CHÉP ĐÚNG thứ tự của
--     doi_tac_service.trang_thai_doi_tac() (ket_qua_luc > doi_tac_cho_tai_lieu_luc >
--     exec_status 'performed') — chỉ để đo một lần ở chặng 0; app không đọc tệp này.
--     Lọc như bàn: có dòng nhận việc, chỉ định chưa huỷ/chưa đóng.
SELECT '(e) viec doi tac dang do' AS muc, c.code AS co_so,
       CASE WHEN o.ket_qua_luc IS NOT NULL THEN 'DA_GUI_KET_QUA'
            WHEN o.doi_tac_cho_tai_lieu_luc IS NOT NULL THEN 'DA_NHAN_MAU'
            WHEN o.exec_status = 'performed' THEN 'DA_LAY_MAU'
            ELSE 'CHO_LAY_MAU' END AS trang_thai,
       count(*) AS so_viec,
       count(*) FILTER (WHERE o.created_at < now() - interval '7 days') AS qua_7_ngay,
       count(tt.id) AS co_ghi_nhan_thu,
       min(o.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh' AS chi_dinh_cu_nhat
  FROM public.service_order o
  JOIN public.doi_tac_nhan_viec nv ON nv.clinic_id = o.clinic_id AND nv.service_order_id = o.id
  JOIN public.clinic c ON c.id = o.clinic_id
  LEFT JOIN public.doi_tac_thanh_toan tt
    ON tt.clinic_id = o.clinic_id AND tt.service_order_id = o.id AND tt.huy_luc IS NULL
 WHERE o.exec_status IN ('authorized', 'assigned', 'in_progress', 'performed')
 GROUP BY 2, 3
 ORDER BY 2, 3;
