-- LÙI việc "đưa lô mẫu DEMO1709-* về 0": cộng lại đúng số đã bớt (cũng bằng ADJUST).
--
--   thử khô:  ... psql -v ON_ERROR_STOP=1 -v ket_thuc=ROLLBACK -U postgres -d postgres < scripts/kho-hoan-tac-lo-mau-ve-0.sql
--   chạy thật: ... psql -v ON_ERROR_STOP=1 -v ket_thuc=COMMIT   -U postgres -d postgres < scripts/kho-hoan-tac-lo-mau-ve-0.sql
--
-- Chỉ động vào các dòng sổ do scripts/kho-dua-lo-mau-ve-0.sql ghi (đúng lý do + đúng
-- kiểu điều chỉnh tay). Mỗi dòng chỉ hoàn tác MỘT lần: chạy lại không cộng thêm.
-- Dòng sổ gốc GIỮ NGUYÊN — sổ chỉ thêm, không sửa, không xoá.
BEGIN;

DO $$
BEGIN
    PERFORM 1 FROM public.drug_batch
     WHERE batch_code LIKE 'DEMO1709-%'
     ORDER BY id FOR UPDATE;
END $$;

CREATE TEMP TABLE _bot ON COMMIT DROP AS
SELECT t.id, t.clinic_id, t.drug_batch_id, -t.quantity AS tra_lai,
       t.performed_by_staff_id
  FROM public.inventory_txn t
 WHERE t.txn_type = 'ADJUST' AND t.ref_type = 'manual'
   AND t.reason = 'Đưa lô mẫu DEMO1709 về 0 để nạp tồn thật (27/10/2026)'
   AND NOT EXISTS (
       SELECT 1 FROM public.inventory_txn r
        WHERE r.txn_type = 'ADJUST' AND r.ref_type = 'manual'
          AND r.reason = 'Hoàn tác điều chỉnh lô mẫu ' || t.id::text);

INSERT INTO public.inventory_txn
    (clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type, ref_id,
     performed_by_staff_id, performed_at)
SELECT b.clinic_id, b.drug_batch_id, 'ADJUST', b.tra_lai,
       'Hoàn tác điều chỉnh lô mẫu ' || b.id::text,
       'manual', NULL, b.performed_by_staff_id, now()
  FROM _bot b;

SELECT count(*) AS so_dong_da_hoan_tac, coalesce(sum(tra_lai), 0) AS tong_da_cong_lai
  FROM _bot;

:ket_thuc;
