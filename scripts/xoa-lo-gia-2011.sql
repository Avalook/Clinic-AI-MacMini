-- XOÁ LÔ GIẢ KHỎI KHO THUỐC — Tuyền duyệt 20/11/2026.
--
-- Lô giả = không do người dùng nhập:
--   * DEMO1709-*   : lô mẫu nạp 17/09 (Kim Ngưu), nhân sang Hào Nam 08/10, dời vào
--                    KHO 16/11 (CK-HN-0001), huỷ về 0 sáng 20/11.
--   * [đua]39ac97  : lô thử của tài khoản "Duoc si local" 16/09 + bản nhân 08/10.
-- GIỮ NGUYÊN mọi đơn thuốc, hoá đơn, lần thu (kể cả trước khi có kho thật) — chỉ
-- xoá lô giả và sổ kho / dòng phiếu / khoá gửi trùng của CHÍNH các lô đó.
-- Đơn THẬT lỡ giao vào lô giả (Femoston 15/11): gỡ phần "đã giao" như hoàn tác giao
-- (cùng câu với hoan_tac_giao_service.giam_da_giao) + ghi event_log → dòng ấy về
-- "đã thu, chưa giao" và bù trừ (scripts/bu-tru-kho-thu-chieu.py) trừ vào lô thật.
--
-- MỘT giao dịch. Mọi kiểm tra sai → RAISE → không ghi gì. Chạy bằng postgres:
--   xuất bản khôi phục:  scripts/xoa-lo-gia-2011-xuat.sql  (chạy TRƯỚC)
--   thử khô:  psql -v that=0 -f scripts/xoa-lo-gia-2011.sql   → ROLLBACK
--   làm thật: psql -v that=1 -f scripts/xoa-lo-gia-2011.sql   → COMMIT
-- `inventory_txn`, `phieu_kho_dong`, `pharmacy_inventory_request` có trigger cấm xoá (sổ chỉ ghi
-- thêm). Tắt TRONG giao dịch này, bật lại trước khi kết thúc; ROLLBACK cũng trả
-- trigger về như cũ (DDL trong Postgres nằm trong giao dịch). ALTER TABLE khoá
-- bảng vài giây → chạy ngoài giờ khám.

\set ON_ERROR_STOP on
\if :{?that}
\else
  \echo 'Thiếu -v that=0 (thử khô) hoặc -v that=1 (làm thật)'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE lo_gia ON COMMIT DROP AS
SELECT id FROM public.drug_batch
 WHERE batch_code LIKE 'DEMO1709-%' OR batch_code = '[đua]39ac97';

CREATE TEMP TABLE truoc ON COMMIT DROP AS
SELECT (SELECT coalesce(sum(quantity_on_hand), 0) FROM public.drug_batch
         WHERE id NOT IN (SELECT id FROM lo_gia)) AS ton_that,
       (SELECT count(*) FROM public.drug_batch
         WHERE id NOT IN (SELECT id FROM lo_gia)) AS lo_that,
       (SELECT count(*) FROM public.prescription) AS don,
       (SELECT count(*) FROM public.payment_bill_line) AS dong_hoa_don,
       (SELECT count(*) FROM public.payment_cycle) AS lan_thu;

-- Không có lô giả nào gắn phân lô / chờ gán / khách trả (soát 20/11 = 0). Có là dừng:
-- những dòng ấy là dữ liệu bán của khách, phải xử lý tay, không xoá theo.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.prescription_allocation WHERE drug_batch_id IN (SELECT id FROM lo_gia))
     OR EXISTS (SELECT 1 FROM public.thuoc_giao_chua_gan_lo WHERE drug_batch_id IN (SELECT id FROM lo_gia))
     OR EXISTS (SELECT 1 FROM public.drug_return WHERE drug_batch_id IN (SELECT id FROM lo_gia)) THEN
    RAISE EXCEPTION 'Lô giả đang gắn phân lô / chờ gán / khách trả — dừng, xử lý tay';
  END IF;
END $$;

-- ── 1 · Đơn thật lỡ giao vào lô giả ─────────────────────────────────────────
CREATE TEMP TABLE giao_nham ON COMMIT DROP AS
SELECT r.id AS rx, r.clinic_id, sum(-t.quantity) AS so
  FROM public.inventory_txn t
  JOIN public.drug_batch b ON b.id = t.drug_batch_id
  JOIN public.prescription r ON r.id = t.ref_id AND t.ref_type = 'prescription'
 WHERE t.drug_batch_id IN (SELECT id FROM lo_gia)
   AND t.txn_type IN ('DISPENSE', 'DISPENSE_REVERSAL')
 GROUP BY r.id, r.clinic_id
HAVING sum(-t.quantity) <> 0;

DO $$
BEGIN
  -- Số trên sổ là đơn vị LÔ; dispensed_qty là đơn vị DÒNG ĐƠN — chỉ trừ thẳng khi khớp.
  IF EXISTS (
    SELECT 1 FROM giao_nham g
      JOIN public.prescription r ON r.id = g.rx
      JOIN public.inventory_txn t ON t.ref_id = r.id AND t.ref_type = 'prescription'
      JOIN public.drug_batch b ON b.id = t.drug_batch_id
     WHERE b.id IN (SELECT id FROM lo_gia)
       AND lower(btrim(b.unit)) <> lower(btrim(coalesce(r.unit, b.unit)))) THEN
    RAISE EXCEPTION 'Đơn giao nhầm vào lô giả khác đơn vị lô — dừng, xử lý tay';
  END IF;
END $$;

\echo '== Đơn thật lỡ giao vào lô giả (sẽ về "đã thu, chưa giao"):'
SELECT g.rx, coalesce(r.drug_name_raw, '?') AS thuoc, g.so, r.dispensed_qty AS da_giao_truoc
  FROM giao_nham g JOIN public.prescription r ON r.id = g.rx;

UPDATE public.prescription r
   SET dispensed_qty = greatest(r.dispensed_qty - g.so, 0),
       dispensed_at = CASE WHEN r.dispensed_qty - g.so > 0 THEN r.dispensed_at END,
       dispensed_by_staff_id =
           CASE WHEN r.dispensed_qty - g.so > 0 THEN r.dispensed_by_staff_id END,
       closed_at = CASE WHEN r.removed_at IS NULL AND r.refusal_reason IS NULL
                        THEN NULL ELSE r.closed_at END,
       updated_at = now()
  FROM giao_nham g
 WHERE r.id = g.rx;

INSERT INTO public.event_log
    (clinic_id, event_type, aggregate_type, aggregate_id, payload, metadata, source,
     event_published)
SELECT g.clinic_id, 'pharmacy.dispense_undone', 'prescription', g.rx,
       jsonb_build_object('quantity', g.so::text, 'dot', '[XOA-LO-GIA-2011]',
                          'ly_do', 'Lần giao ghi vào lô mẫu (không có thật) — gỡ để trừ vào lô thật'),
       jsonb_build_object('script', 'scripts/xoa-lo-gia-2011.sql'),
       'script:xoa-lo-gia-2011', FALSE
  FROM giao_nham g;

-- ── 2 · Xoá: dòng phiếu → khoá gửi trùng → sổ kho → lô ──────────────────────
ALTER TABLE public.inventory_txn DISABLE TRIGGER inventory_txn_append_only;
ALTER TABLE public.phieu_kho_dong DISABLE TRIGGER phieu_kho_dong_chi_them;
ALTER TABLE app_private.pharmacy_inventory_request
  DISABLE TRIGGER pharmacy_inventory_request_immutable;

\echo '== Đã xoá:'
WITH x AS (
  DELETE FROM public.phieu_kho_dong
   WHERE drug_batch_id IN (SELECT id FROM lo_gia)
      OR drug_batch_nguon_id IN (SELECT id FROM lo_gia)
  RETURNING 1)
SELECT 'phieu_kho_dong' AS bang, count(*) FROM x;

WITH x AS (
  DELETE FROM app_private.pharmacy_inventory_request
   WHERE drug_batch_id IN (SELECT id FROM lo_gia)
  RETURNING 1)
SELECT 'pharmacy_inventory_request' AS bang, count(*) FROM x;

-- Dòng đảo trỏ dòng gốc (reverses_txn_id) — xoá dòng đảo trước.
WITH x AS (
  DELETE FROM public.inventory_txn
   WHERE drug_batch_id IN (SELECT id FROM lo_gia) AND reverses_txn_id IS NOT NULL
  RETURNING 1)
SELECT 'inventory_txn (dòng đảo)' AS bang, count(*) FROM x;

WITH x AS (
  DELETE FROM public.inventory_txn WHERE drug_batch_id IN (SELECT id FROM lo_gia)
  RETURNING 1)
SELECT 'inventory_txn' AS bang, count(*) FROM x;

WITH x AS (
  DELETE FROM public.drug_batch WHERE id IN (SELECT id FROM lo_gia) RETURNING 1)
SELECT 'drug_batch' AS bang, count(*) FROM x;

ALTER TABLE public.inventory_txn ENABLE TRIGGER inventory_txn_append_only;
ALTER TABLE public.phieu_kho_dong ENABLE TRIGGER phieu_kho_dong_chi_them;
ALTER TABLE app_private.pharmacy_inventory_request
  ENABLE TRIGGER pharmacy_inventory_request_immutable;

-- ── 3 · Kiểm — sai một điều là huỷ cả giao dịch ─────────────────────────────
DO $$
DECLARE t record; lech int;
BEGIN
  SELECT * INTO t FROM truoc;
  IF EXISTS (SELECT 1 FROM public.drug_batch
              WHERE batch_code LIKE 'DEMO1709-%' OR batch_code = '[đua]39ac97') THEN
    RAISE EXCEPTION 'Còn lô giả';
  END IF;
  IF (SELECT coalesce(sum(quantity_on_hand), 0) FROM public.drug_batch) <> t.ton_that
     OR (SELECT count(*) FROM public.drug_batch) <> t.lo_that THEN
    RAISE EXCEPTION 'Tồn / số lô THẬT bị đổi';
  END IF;
  IF (SELECT count(*) FROM public.prescription) <> t.don
     OR (SELECT count(*) FROM public.payment_bill_line) <> t.dong_hoa_don
     OR (SELECT count(*) FROM public.payment_cycle) <> t.lan_thu THEN
    RAISE EXCEPTION 'Số đơn / hoá đơn / lần thu bị đổi';
  END IF;
  SELECT count(*) INTO lech FROM (
    SELECT b.id FROM public.drug_batch b
      LEFT JOIN public.inventory_txn x ON x.drug_batch_id = b.id
       AND x.txn_type IN ('RECEIVE','DISPENSE','DISPENSE_REVERSAL','ADJUST','DISCARD',
                          'RETURN_RECEIVED','CHUYEN_RA','CHUYEN_VAO','DISCARD_UNDO')
     GROUP BY b.id, b.quantity_on_hand
    HAVING b.quantity_on_hand <> coalesce(sum(x.quantity), 0)) z;
  IF lech > 0 THEN
    RAISE EXCEPTION '% lô có tồn khác tổng sổ', lech;
  END IF;
  IF (SELECT count(*) FROM pg_trigger
       WHERE tgname IN ('inventory_txn_append_only', 'phieu_kho_dong_chi_them',
                        'pharmacy_inventory_request_immutable')
         AND tgenabled = 'O') <> 3 THEN
    RAISE EXCEPTION 'Trigger chặn xoá chưa bật lại đủ 3';
  END IF;
  RAISE NOTICE 'KIỂM ĐẠT: 0 lô giả · tồn thật % · % lô thật · đơn/hoá đơn/lần thu giữ nguyên · 0 lô lệch sổ',
    t.ton_that, t.lo_that;
END $$;

\if :that
  COMMIT;
  \echo '== ĐÃ GHI (COMMIT).'
\else
  ROLLBACK;
  \echo '== THỬ KHÔ — đã ROLLBACK, không ghi gì. Chạy lại với -v that=1 để làm thật.'
\endif
