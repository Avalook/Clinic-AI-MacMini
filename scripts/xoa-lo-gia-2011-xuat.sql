-- Bản KHÔI PHỤC cho scripts/xoa-lo-gia-2011.sql — chạy TRƯỚC, chỉ đọc. Mỗi dòng
-- một JSON {"bang": …, "dong": {…}} — đủ để INSERT lại đúng như cũ nếu cần.
--   psql -X -At -v ON_ERROR_STOP=1 -f scripts/xoa-lo-gia-2011-xuat.sql > xoa-lo-gia-2011.jsonl
WITH lo_gia AS (
  SELECT id FROM public.drug_batch
   WHERE batch_code LIKE 'DEMO1709-%' OR batch_code = '[đua]39ac97'
)
SELECT json_build_object('bang', 'drug_batch', 'dong', row_to_json(b))
  FROM public.drug_batch b WHERE b.id IN (SELECT id FROM lo_gia)
UNION ALL
SELECT json_build_object('bang', 'inventory_txn', 'dong', row_to_json(t))
  FROM public.inventory_txn t WHERE t.drug_batch_id IN (SELECT id FROM lo_gia)
UNION ALL
SELECT json_build_object('bang', 'phieu_kho_dong', 'dong', row_to_json(d))
  FROM public.phieu_kho_dong d
 WHERE d.drug_batch_id IN (SELECT id FROM lo_gia)
    OR d.drug_batch_nguon_id IN (SELECT id FROM lo_gia)
UNION ALL
SELECT json_build_object('bang', 'pharmacy_inventory_request', 'dong', row_to_json(q))
  FROM app_private.pharmacy_inventory_request q WHERE q.drug_batch_id IN (SELECT id FROM lo_gia)
UNION ALL
SELECT json_build_object('bang', 'prescription_truoc_khi_go', 'dong', row_to_json(r))
  FROM public.prescription r
 WHERE r.id IN (SELECT t.ref_id FROM public.inventory_txn t
                 WHERE t.drug_batch_id IN (SELECT id FROM lo_gia)
                   AND t.ref_type = 'prescription');
