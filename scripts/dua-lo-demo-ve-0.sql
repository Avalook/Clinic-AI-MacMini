-- Đưa lô mẫu DEMO1709-* về 0 trước khi phòng khám nhập tồn thật (Tuyền 31/10/2026).
--
-- Vì sao: máy tự chọn lô hết hạn sớm nhất. Còn lô mẫu thì giao thật sẽ trừ vào lô mẫu,
-- số trên kệ thật và số trên sổ lệch ngay từ ngày đầu.
--
-- Sổ kho chỉ-thêm: mỗi lô ghi một dòng ADJUST âm, không xoá gì, lịch sử giữ nguyên.
-- Lô đang có khách giữ (đã bán chưa giao, chờ xác minh, thuốc trả chờ kiểm) KHÔNG đụng,
-- in ra để xử lý tay.
--
-- Mặc định XEM TRƯỚC rồi ROLLBACK. Ghi thật phải thêm `-v ap_dung=1`.
-- Chạy trên staging trước, xem số khớp rồi mới chạy prod.

\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE lo_mau ON COMMIT DROP AS
SELECT b.id, b.clinic_id, b.location_id, b.batch_code, b.unit, b.quantity_on_hand AS ton,
       public.drug_batch_kha_dung(b.clinic_id, b.id) AS kha_dung
  FROM public.drug_batch b
 WHERE b.batch_code LIKE 'DEMO1709-%'
   AND b.quantity_on_hand > 0;

\echo '== Lô mẫu còn tồn, theo cơ sở'
SELECT l.name AS co_so, count(*) AS so_lo, sum(m.ton) AS tong_ton
  FROM lo_mau m
  JOIN public.clinic_location l ON l.id = m.location_id
 GROUP BY 1
 ORDER BY 1;

\echo '== Lô đang có khách giữ: KHÔNG đưa về 0, cần xử lý tay'
SELECT l.name AS co_so, m.batch_code, m.unit, m.ton, m.kha_dung
  FROM lo_mau m
  JOIN public.clinic_location l ON l.id = m.location_id
 WHERE m.kha_dung IS DISTINCT FROM m.ton
 ORDER BY 1, 2;

WITH ghi AS (
    INSERT INTO public.inventory_txn
        (clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,
         performed_by_staff_id, performed_at)
    SELECT m.clinic_id, m.id, 'ADJUST', -m.ton,
           'Đưa lô mẫu về 0 trước khi nhập tồn thật', 'manual',
           (SELECT s.id FROM public.staff s
             WHERE s.full_name = 'Quản lý hệ thống' ORDER BY s.created_at LIMIT 1),
           now()
      FROM lo_mau m
     WHERE m.kha_dung IS NOT DISTINCT FROM m.ton
    RETURNING drug_batch_id
)
SELECT count(*) AS so_lo_da_ghi FROM ghi;

\echo '== Sau khi ghi: lô mẫu còn tồn (chỉ còn lô đang có khách giữ)'
SELECT count(*) AS so_lo, coalesce(sum(b.quantity_on_hand), 0) AS tong_ton
  FROM public.drug_batch b
 WHERE b.batch_code LIKE 'DEMO1709-%'
   AND b.quantity_on_hand > 0;

\if :{?ap_dung}
    COMMIT;
    \echo '== ĐÃ GHI.'
\else
    ROLLBACK;
    \echo '== Xem trước, chưa ghi gì. Ghi thật: thêm -v ap_dung=1'
\endif
