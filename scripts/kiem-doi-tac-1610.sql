-- KIỂM TIỀN ĐỐI TÁC (CHỈ ĐỌC — Tuyền 16/10/2026). Chạy trên staging TRƯỚC, rồi prod:
--   ssh clinic-vps-moi 'docker exec -i clinicai_stg_db psql -U postgres -d postgres' < scripts/kiem-doi-tac-1610.sql
-- Trả lời: dịch vụ khách trả đối tác có đang lọt vào tiền phòng khám không?
SET default_transaction_read_only = on;

-- 1) Cờ đối tác hiện tại.
SELECT 'node lam_ben_ngoai=true' AS muc, code, name FROM public.node_definition WHERE lam_ben_ngoai;
SELECT 'dich vu doi_tac_lay_mau=true' AS muc, service_code, name FROM public.service_price WHERE doi_tac_lay_mau;
SELECT 'phong la_doi_tac' AS muc, code, name, is_active FROM public.clinic_room WHERE la_doi_tac;

-- 2) Bên thu từng dịch vụ (group dich_vu): bao nhiêu CLINIC / EXTERNAL_PARTNER.
SELECT billing_owner, billing_owner_chon_tay, count(*) FROM public.service_price
 WHERE "group" = 'dich_vu' GROUP BY 1, 2 ORDER BY 1, 2;

-- 3) LỌT TIỀN: dịch vụ HIỆN là "đối tác thu" nhưng đã vào hoá đơn như tiền phòng khám.
--    (dòng hoá đơn chụp billing_owner lúc thu — dịch vụ đổi sang đối tác SAU đó thì lệch.)
SELECT sp.service_code, sp.name,
       count(*) FILTER (WHERE bl.billing_owner = 'CLINIC')               AS dong_tinh_vao_phong_kham,
       coalesce(sum(bl.line_total) FILTER (WHERE bl.billing_owner = 'CLINIC'), 0) AS tien_phong_kham,
       min(pc.paid_at)::date AS tu_ngay, max(pc.paid_at)::date AS den_ngay
  FROM public.service_price sp
  JOIN public.service_order o  ON o.clinic_id = sp.clinic_id AND o.service_code = sp.service_code
  JOIN public.payment_bill_line bl ON bl.clinic_id = o.clinic_id
       AND bl.source_type = 'service_order' AND bl.source_id = o.id::text
  JOIN public.payment_cycle pc ON pc.payment_cycle_id = bl.payment_cycle_id AND pc.status = 'PAID'
 WHERE sp."group" = 'dich_vu' AND sp.billing_owner = 'EXTERNAL_PARTNER'
 GROUP BY 1, 2
HAVING count(*) FILTER (WHERE bl.billing_owner = 'CLINIC') > 0
 ORDER BY tien_phong_kham DESC;

-- 4) Dịch vụ CHỈ ĐỊNH VÀO PHÒNG ĐỐI TÁC nhưng bên thu vẫn là CLINIC (kẽ hở theo phòng).
SELECT DISTINCT sp.service_code, sp.name, sp.billing_owner
  FROM public.service_order o
  JOIN public.clinic_room r ON r.id = o.room_id AND r.clinic_id = o.clinic_id AND r.la_doi_tac
  JOIN public.service_price sp ON sp.clinic_id = o.clinic_id AND sp."group" = 'dich_vu'
       AND sp.service_code = o.service_code
 WHERE sp.billing_owner <> 'EXTERNAL_PARTNER';
